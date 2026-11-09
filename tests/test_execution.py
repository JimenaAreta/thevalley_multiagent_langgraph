import json
import io
from contextlib import redirect_stdout
import tempfile
import os
from unittest.mock import patch
import unittest
from pathlib import Path

from langchain_core.language_models.fake_chat_models import FakeListChatModel, FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from streamlit.testing.v1 import AppTest

from multiagent_store.agents.architectures import CLASSROOM_ARCHITECTURES, solution_available
if not solution_available():
    raise unittest.SkipTest('Instructor solution is not distributed with the student repository.')
from multiagent_store.agents.tools import create_tools
from multiagent_store.execution import estimate_cost, execute_turn as run_turn
from functools import partial
execute_turn = partial(run_turn, implementation='solution')
from multiagent_store.data.store import Store


def solution_app():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=45)
    next(w for w in app.selectbox if w.label == 'Código que ejecutar').set_value('solution').run()
    return app


class MockModel(FakeListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self



class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/'tienda.db')

    def test_demo_data_and_customer_isolation(self):
        self.assertEqual(len(self.store.products()), 3)
        self.assertEqual(self.store.get_order('1042')['estado'], 'entregado')
        self.assertIn('error', self.store.get_order('1044'))
        self.assertIn('error', self.store.get_order("1042' OR 1=1 --"))

    def test_tools_query_sqlite(self):
        tools = create_tools(self.store)
        self.assertEqual(tools['billing'][0].invoke({'order_id':'1042'})['factura'], 'F-1042')
        result = tools['returns'][0].invoke({'order_id':'1042', 'reason':'roto'})
        self.assertTrue(result['elegible_demo'])
        self.assertFalse(result['registrada'])
        self.assertFalse(tools['returns'][0].invoke({'order_id':'1043', 'reason':'roto'})['elegible_demo'])

    def test_history_and_metrics_persist(self):
        messages = [{'role':'user','content':'Hola'}]
        self.store.save('session_id', 'network', messages, {'coste_usd':0.1})
        other = Store(self.store.path)
        self.assertEqual(json.loads(other.load('session_id')['mensajes']), messages)
        self.assertEqual(other.executions()[0]['coste_usd'], 0.1)

    def test_review_persists_without_changing_measurements(self):
        metrics = {'llamadas': 7, 'error': None}
        self.store.save('session_id', 'network', [], metrics)
        review = dict(completa='sí', correcta='sí', acciones_respaldadas='sí',
                        observaciones='Factura y elegibilidad comprobadas')
        result = self.store.save_review(metrics['ejecucion_id'], review)
        self.assertEqual(result['calidad'], 'apta')
        self.assertEqual(result['llamadas'], 7)
        self.assertEqual(self.store.executions()[0]['observaciones'], review['observaciones'])
        review['correcta'] = 'no'
        self.assertEqual(self.store.save_review(metrics['ejecucion_id'], review)['calidad'], 'no apta')

    def test_cost_separates_cache_and_output(self):
        calls = [{'entrada':1000,'cache':400,'salida':100}]
        self.assertAlmostEqual(estimate_cost(calls, (0.25,0.025,2)), 0.00036)
        self.assertIsNone(estimate_cost([{'entrada':None,'salida':None}], (1,1,1)))

    def test_classroom_architectures_execute_without_api(self):
        for architecture in CLASSROOM_ARCHITECTURES:
            with self.subTest(architecture=architecture):
                output_data, metrics, events, calls = execute_turn(
                    architecture, [{'role':'user','content':'Hola'}], self.store,
                    (0.25,0.025,2), model=MockModel(responses=['Respuesta simulada']))
                self.assertIsNone(metrics['error'])
                self.assertEqual(output_data, 'Respuesta simulada')
                self.assertGreater(metrics['llamadas'], 0)
                self.assertIsNone(metrics['coste_usd'])  # Fake models do not report token usage.

    def test_ui_loads_without_api_calls(self):
        app = solution_app()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs), 2)
        self.assertEqual(len(next(s for s in app.selectbox if s.label == 'Escenario').options), 2)
        self.assertEqual(next(s for s in app.selectbox if s.label == 'Arquitectura').value, 'single')

    def test_web_comparison_and_review_without_api(self):
        model = MockModel(responses=['Respuesta simulada'])
        with patch.dict(os.environ, {'TIENDA_DB': self.store.path}), \
             patch('multiagent_store.execution.init_chat_model', return_value=model):
            app = solution_app()
            next(b for b in app.button if b.label == 'Ejecutar comparación (consume API)').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state.results), 14)
            next(b for b in app.button if b.label == 'Guardar revisión de calidad').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(self.store.executions()), 14)
            self.assertTrue(all(r['calidad'] == 'pendiente' for r in self.store.executions()))

    def test_inspector_captures_model_context_and_tool_results(self):
        class ToolModel(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):
                return self

        model = ToolModel(responses=[
            AIMessage(content='', tool_calls=[{'name': 'query_invoice',
                'args': {'order_id': '1042'}, 'id': 'factura-1'}]),
            AIMessage(content='La factura es F-1042.'),
        ])
        response, metrics, events, _ = execute_turn(
            'single', [{'role': 'user', 'content': 'Factura 1042'}],
            self.store, None, model=model)
        self.assertIsNone(metrics['error'])
        inputs = [e for e in events if e['tipo'] == 'modelo']
        self.assertEqual(len(inputs), 2)
        self.assertEqual(inputs[0]['mensajes'][0][0]['type'], 'system')
        self.assertEqual(inputs[0]['mensajes'][0][-1]['content'], 'Factura 1042')
        self.assertTrue(any(m['type'] == 'tool' and 'F-1042' in str(m['content'])
                            for m in inputs[1]['mensajes'][0]))
        herramienta = next(e for e in events if e['tipo'] == 'herramienta')
        self.assertIn('1042', str(herramienta['argumentos']))
        result = next(e for e in events if e['tipo'] == 'resultado')
        self.assertEqual(herramienta['run_id'], result['run_id'])
        output_data = next(e for e in events if e['tipo'] == 'respuesta_modelo')
        self.assertEqual(inputs[0]['run_id'], output_data['run_id'])
        self.assertEqual(output_data['mensajes'][0]['tool_calls'][0]['args'], {'order_id': '1042'})
        json.dumps(metrics, ensure_ascii=False)  # The trace can be persisted and exported.

    def test_inspector_persists_after_widget_changes(self):
        with patch.dict(os.environ, {'TIENDA_DB': self.store.path}), \
             patch('multiagent_store.execution.init_chat_model', return_value=MockModel(responses=['Respuesta simulada'])):
            app = solution_app()
            next(b for b in app.button if b.label == 'Ejecutar consulta').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state.latest_execution['eventos'])
            self.assertNotIn('Límite de pasos por grafo', [s.label for s in app.slider])
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state.latest_execution['eventos'])

    def test_refund_discounts_shipping_and_isolation(self):
        tools = {t.name: t for group in create_tools(self.store).values() for t in group}
        payment = tools['query_payment'].invoke({'order_id': '1042'})
        self.assertEqual(payment['total_pagado_centimos'], 5480)
        for kind, expected in [('damaged', 5480), ('change_of_mind', 4490)]:
            result = tools['calculate_refund'].invoke({'order_id': '1042', 'kind': kind})
            self.assertEqual(result['importe_reembolso_centimos'], expected)
            self.assertFalse(result['registrada'])
        with self.store.connect() as db:
            db.execute("UPDATE productos SET precio_centimos=99999 WHERE id='P1'")
            self.assertEqual(db.execute('SELECT COUNT(*) FROM devoluciones').fetchone()[0], 0)
        self.assertEqual(self.store.calculate_refund('1042', 'damaged')['importe_reembolso_centimos'], 5480)
        self.assertFalse(self.store.calculate_refund('1043', 'damaged')['elegible_demo'])
        for order_id in ('1044', '9999', "1042' OR 1=1 --"):
            self.assertIn('error', self.store.payment_breakdown(order_id))
            self.assertIn('error', self.store.calculate_refund(order_id, 'damaged'))
        self.assertIn('error', self.store.calculate_refund('1042', 'otro'))
        self.assertEqual(Store(self.store.path).payment_breakdown('1042')['total_pagado_centimos'], 5480)

    def test_subagent_uses_multiple_tools_with_isolated_context(self):
        class ScriptedModel(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):
                return self

        request = 'Calcula el reembolso del 1042 que llegó roto y explica el desglose.'
        operations = [
            ('check_return', {'order_id': '1042', 'reason': 'roto'}),
            ('query_policy', {'kind': 'damaged'}),
            ('query_payment', {'order_id': '1042'}),
            ('calculate_refund', {'order_id': '1042', 'kind': 'damaged'}),
        ]
        queries = AIMessage(content='', tool_calls=[
            {'name': name, 'args': args, 'id': f'paso-{i}'}
            for i, (name, args) in enumerate(operations)])
        explanation = AIMessage(content='DEMO-DANO-1: 59,90 - 10 + 4,90 = 54,80 EUR; no registrado.')
        for architecture in ('single', 'subagents'):
            script = [queries, explanation]
            if architecture == 'subagents':
                script = [AIMessage(content='', tool_calls=[{
                    'name': 'query_returns', 'args': {'request': request}, 'id': 'delegar'}]),
                    *script, explanation]
            model = ScriptedModel(responses=script)
            _, metrics, events, _ = execute_turn(architecture, [
                {'role': 'user', 'content': 'MARCADOR_HISTORIAL: antes consulté catálogo'},
                {'role': 'assistant', 'content': 'Consulta anterior resuelta.'},
                {'role': 'user', 'content': request}], self.store, None, model=model)
            self.assertIsNone(metrics['error'])
            names = [e['nombre'] for e in events if e['tipo'] == 'herramienta']
            self.assertTrue(all(n in names for n, _ in operations))
            inputs = [e for e in events if e['tipo'] == 'modelo']
            if architecture == 'subagents':
                self.assertIn('query_returns', names)
                self.assertNotIn('MARCADOR_HISTORIAL', str(inputs[1]['mensajes']))
                self.assertIn(request, str(inputs[1]['mensajes']))
                self.assertEqual(len(inputs), 4)
            else:
                self.assertNotIn('query_returns', names)
                self.assertEqual(len(inputs), 2)

    def test_cli_journey_preserves_history_and_exports(self):
        import multiagent_store.cli as customer_service
        inputs = []

        def execute(version, history, store, rates, **kwargs):
            kwargs['implementation'] = 'solution'
            inputs.append([dict(m) for m in history])
            return execute_turn(version, history, store, rates,
                model=MockModel(responses=['Respuesta simulada']), **kwargs)

        destination = Path(self.tmp.name) / 'incidencia.json'
        with patch.dict(os.environ, {'TIENDA_DB': self.store.path}), \
             patch('sys.argv', ['main.py', 'single', '--case', 'change_of_mind_journey', '--salida', str(destination)]), \
             patch.object(customer_service, 'execute_turn', side_effect=execute), \
             redirect_stdout(io.StringIO()):
            customer_service.main()
        self.assertEqual(len(inputs), 7)
        self.assertEqual([m['role'] for m in inputs[1]], ['user', 'assistant', 'user'])
        self.assertIn('catálogo', inputs[-1][-1]['content'])
        data = json.loads(destination.read_text())
        self.assertEqual([r['turno'] for r in data], list(range(1, 8)))
        self.assertTrue(all(r['caso'] == 'change_of_mind_journey' for r in data))

    def test_classroom_amounts_are_distinct_and_tools_are_partitioned(self):
        tools = create_tools(self.store)
        all_tools = {t.name: t for group in tools.values() for t in group}
        catalog = all_tools['query_catalog_price'].invoke({'order_id': '2001'})
        original = all_tools['query_order_price'].invoke({'order_id': '2001'})
        paid = all_tools['query_payment'].invoke({'order_id': '2001'})
        refund = all_tools['calculate_refund'].invoke({'order_id': '2001', 'kind': 'change_of_mind'})
        amounts = [catalog['amount_centimos'], original['amount_centimos'],
                   paid['total_pagado_centimos'], refund['importe_reembolso_centimos']]
        self.assertEqual(amounts, [5990, 6990, 6480, 5490])
        self.assertEqual(len(set(amounts)), 4)
        self.assertNotIn('query_catalog_price', [t.name for t in tools['billing']])
        self.assertNotIn('calculate_refund', [t.name for t in tools['billing']])
        for order_id in ('1044', '9999'):
            self.assertIn('error', all_tools['query_catalog_price'].invoke({'order_id': order_id}))
            self.assertIn('error', all_tools['query_order_price'].invoke({'order_id': order_id}))

    def test_tool_selection_report_does_not_grade_answer_correctness(self):
        from multiagent_store.scenarios import inspect_selection, SCENARIOS
        wrong = [{'tipo': 'herramienta', 'nombre': 'query_order_price'}]
        report = inspect_selection('change_of_mind_journey', 5, wrong)
        self.assertFalse(report['expected_tool_called'])
        self.assertEqual(report['expected_amount_centimos'], 6480)
        right = [{'tipo': 'herramienta', 'nombre': 'query_payment'}]
        self.assertTrue(inspect_selection('change_of_mind_journey', 5, right)['expected_tool_called'])
        self.assertIsNone(inspect_selection('change_of_mind_journey', 8, right)['expected_tool_called'])
        self.assertIsNone(inspect_selection('change_of_mind_journey', 5, right, 'Otra pregunta')['expected_tool_called'])
        self.assertEqual(set(SCENARIOS), {'change_of_mind_journey', 'damaged_journey'})

    def test_journey_keeps_orders_and_missing_details_separate(self):
        from multiagent_store.scenarios import SCENARIOS, inspect_selection
        self.assertEqual(self.store.get_order('1043')['estado'], 'en tránsito')
        self.assertEqual(self.store.get_order('2001')['estado'], 'entregado')
        for case, messages in SCENARIOS.items():
            self.assertEqual(len(messages), 7)
            self.assertIn('1043', messages[0])
            self.assertNotIn('2001', messages[1])
            self.assertIn('2001', messages[2])
            self.assertIsNone(inspect_selection(case, 2, [])['expected_tool'])
            self.assertIsNone(inspect_selection(case, 3, [])['expected_tool'])
        tools = {t.name: t for group in create_tools(self.store).values() for t in group}
        self.assertIn('error', tools['check_return'].invoke({'order_id': '2001', 'reason': ' '}))
        self.assertEqual(self.store.calculate_refund('2001', 'damaged')['importe_reembolso_centimos'], 6480)
        self.assertEqual(self.store.calculate_refund('2001', 'change_of_mind')['importe_reembolso_centimos'], 5490)

    def test_student_builder_can_run_with_the_same_execution_and_metrics(self):
        from multiagent_store.agents.architectures import build
        model = MockModel(responses=['Student response'])
        graph = build('single', model, self.store, implementation='solution')
        with patch('multiagent_store.exercises.student.build', return_value=graph) as builder:
            response, metrics, _, _ = execute_turn(
                'single', [{'role': 'user', 'content': 'Hola'}], self.store, None,
                model=model, implementation='student')
        builder.assert_called_once_with('single', model, self.store)
        self.assertEqual(response, 'Student response')
        self.assertIsNone(metrics['error'])
        self.assertEqual(metrics['implementation'], 'student')

    def test_incomplete_student_block_shows_todo_without_model_calls(self):
        from multiagent_store.exercises.student import IncompleteExercise
        with patch('multiagent_store.exercises.student.build',
                   side_effect=IncompleteExercise('TODO 1: completa build_single')):
            response, metrics, _, _ = execute_turn(
                'single', [{'role': 'user', 'content': 'Hola'}], self.store, None,
                model=MockModel(responses=['Unused']), implementation='student')
        self.assertEqual(metrics['error'], 'IncompleteExercise')
        self.assertIn('TODO 1', response)
        self.assertEqual(metrics['llamadas'], 0)
