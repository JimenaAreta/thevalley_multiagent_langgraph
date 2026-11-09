import tempfile
import unittest
from pathlib import Path

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from multiagent_store.agents.coordination import CoordinationError, final_response, validate_destination
from multiagent_store.data.store import Store
from multiagent_store.execution import execute_turn


class SupervisorModel(FakeMessagesListChatModel):
    """Scripted model: routes come from with_structured_output, messages from responses."""
    routes: list = []

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(lambda _: schema(next=self.routes.pop(0)))


class CoordinationTests(unittest.TestCase):
    def test_rejects_repeated_or_unknown_destination(self):
        state = {'messages': [HumanMessage('Hola'), AIMessage('Pedido en tránsito', name='orders')]}
        with self.assertRaises(CoordinationError):
            validate_destination('orders', state)
        with self.assertRaises(CoordinationError):
            validate_destination('billing', state, current='billing')
        with self.assertRaises(CoordinationError):
            validate_destination('shipping', state)
        self.assertEqual(validate_destination('returns', state), 'returns')

    def test_final_response_is_named(self):
        original = AIMessage(content='Respuesta')
        self.assertEqual(final_response([original], 'orders').name, 'orders')
        with self.assertRaises(CoordinationError):
            final_response([AIMessage(content='')], 'orders')

    def test_supervisor_shares_history_with_specialist(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'tienda.db')
            model = SupervisorModel(routes=['orders', 'FINISH'], responses=[
                AIMessage(content='', tool_calls=[{'name': 'query_order',
                    'args': {'order_id': '1043'}, 'id': 'pedido'}]),
                AIMessage(content='El pedido 1043 está en tránsito.'),
                AIMessage(content='Tu pedido 1043 sigue en tránsito.'),
            ])
            response, metrics, events, _ = execute_turn('supervisor', [
                {'role': 'user', 'content': 'MARCADOR_HISTORIAL: hola'},
                {'role': 'assistant', 'content': 'Hola, ¿en qué te ayudo?'},
                {'role': 'user', 'content': '¿Cómo está mi pedido 1043?'}], store, None, model=model)
        self.assertIsNone(metrics['error'])
        self.assertEqual(response, 'Tu pedido 1043 sigue en tránsito.')
        self.assertIn('query_order', [e['nombre'] for e in events if e['tipo'] == 'herramienta'])
        inputs = [e for e in events if e['tipo'] == 'modelo']
        # The specialist sees the shared history, unlike the isolated request in subagents.
        self.assertIn('MARCADOR_HISTORIAL', str(inputs[0]['mensajes']))
