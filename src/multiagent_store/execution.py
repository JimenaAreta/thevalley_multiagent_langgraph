"""Execution, metrics and tracing shared by the web UI and CLI."""
import os
import time
from threading import Lock

from langchain.chat_models import init_chat_model
from langchain_core.callbacks import BaseCallbackHandler

from multiagent_store.agents.architectures import build, SolutionUnavailable
from multiagent_store.agents.messages import message_text

class MetricsCallback(BaseCallbackHandler):
    def __init__(self):
        self.calls = []
        self.events = []
        self.start_times = {}
        self.lock = Lock()

    @staticmethod
    def context(kwargs):
        metadata = kwargs.get('metadata') or {}
        namespace = metadata.get('langgraph_checkpoint_ns', '')
        return {'nodo': metadata.get('langgraph_node'), 'contexto': namespace,
                'etiquetas': kwargs.get('tags', [])}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        with self.lock:
            self.start_times[run_id] = time.perf_counter()
            parameters = kwargs.get('invocation_params') or {}
            self.events.append({
                'tipo': 'modelo', 'run_id': str(run_id),
                'parent_run_id': str(kwargs.get('parent_run_id') or ''),
                **self.context(kwargs),
                'mensajes': [[m.model_dump(mode='json') for m in batch] for batch in messages],
                'configuracion': {k: parameters[k] for k in
                                  ('tools', 'tool_choice', 'response_format') if k in parameters},
            })

    def on_llm_end(self, response, *, run_id, **kwargs):
        usage = {}
        for generation in response.generations:
            for g in generation:
                message = getattr(g, 'message', None)
                if getattr(message, 'usage_metadata', None):
                    usage = message.usage_metadata
                    break
        outputs = []
        for batch in response.generations:
            for generated in batch:
                message = getattr(generated, 'message', None)
                outputs.append(message.model_dump(mode='json') if message is not None
                               else {'content': generated.text})
        with self.lock:
            self.events.append({'tipo': 'respuesta_modelo', 'run_id': str(run_id),
                                 'mensajes': outputs})
            self.calls.append({
                'entrada': usage.get('input_tokens'),
                'salida': usage.get('output_tokens'),
                'cache': usage.get('input_token_details', {}).get('cache_read', 0),
                'segundos': time.perf_counter() - self.start_times.pop(run_id, time.perf_counter()),
            })

    def on_llm_error(self, error, *, run_id, **kwargs):
        with self.lock:
            self.start_times.pop(run_id, None)
            self.calls.append({'entrada': None, 'salida': None, 'cache': 0, 'segundos': None})
            self.events.append({'tipo': 'error_modelo', 'run_id': str(run_id), 'detalle': type(error).__name__})

    def on_tool_start(self, serialized, input_str, **kwargs):
        with self.lock:
            self.events.append({'tipo': 'herramienta', 'nombre': (serialized or {}).get('name'),
                                 'run_id': str(kwargs.get('run_id')),
                                 'parent_run_id': str(kwargs.get('parent_run_id') or ''),
                                 **self.context(kwargs),
                                 'argumentos': kwargs.get('inputs') if kwargs.get('inputs') is not None else input_str})

    def on_tool_end(self, output, **kwargs):
        with self.lock:
            self.events.append({'tipo': 'resultado', 'run_id': str(kwargs.get('run_id')),
                                 'resultado': output.model_dump(mode='json')
                                 if hasattr(output, 'model_dump') else output})

    def on_tool_error(self, error, **kwargs):
        with self.lock:
            self.events.append({'tipo': 'error_herramienta', 'run_id': str(kwargs.get('run_id')),
                                 'detalle': type(error).__name__})


def estimate_cost(calls, rates):
    if rates is None:
        return None
    if any(c['entrada'] is None or c['salida'] is None for c in calls):
        return None
    input_data, cache, output_data = rates
    return sum((max(0, c['entrada'] - c['cache']) * input_data +
                c['cache'] * cache + c['salida'] * output_data) / 1_000_000 for c in calls)


def execute_turn(architecture, history, store, rates, model=None, step_limit=30, implementation='student'):
    model_name = os.getenv('MODEL', 'openai:gpt-5-mini')
    metrics_callback = MetricsCallback()
    start_time = time.perf_counter()
    error = None
    response = ''
    try:
        if model is None:
            model = init_chat_model(model_name, max_retries=0)
        graph = build(architecture, model, store, implementation=implementation)
        result = graph.invoke({'messages': [(m['role'], m['content']) for m in history]}, config={
            'callbacks': [metrics_callback], 'recursion_limit': step_limit,
            'run_name': architecture})
        response = message_text(result['messages'][-1])
        route = result.get('route')
        if route:
            metrics_callback.events.append({
                'tipo': 'routing',
                'run_id': f'routing-{architecture}-{len(metrics_callback.events)}',
                'parent_run_id': '',
                'nodo': 'supervisor',
                'contexto': 'supervisor -> routing',
                'ruta': route,
                'detalle': f'El supervisor eligió {route}',
            })
    except Exception as exc:
        # Do not display HTTP client errors that may contain connection details.
        error = type(exc).__name__
        from multiagent_store.exercises.student import IncompleteExercise
        if isinstance(exc, (IncompleteExercise, SolutionUnavailable)):
            response = str(exc)
        else:
            response = f'La ejecución falló ({error}). Revisa las llamadas registradas en el inspector.'
    metrics = {'implementation': implementation, 'arquitectura': architecture, 'modelo': model_name,
                'llamadas': len(metrics_callback.calls),
                'entrada': sum(c['entrada'] or 0 for c in metrics_callback.calls),
                'cache': sum(c['cache'] for c in metrics_callback.calls),
                'salida': sum(c['salida'] or 0 for c in metrics_callback.calls),
                'coste_usd': estimate_cost(metrics_callback.calls, rates),
                'tarifas_por_millon': list(rates) if rates is not None else None,
                'segundos': round(time.perf_counter()-start_time, 3), 'error': error,
                'respuesta': response, 'calidad': 'pendiente', 'completa': 'pendiente', 'correcta': 'pendiente',
                'acciones_respaldadas': 'pendiente', 'observaciones': '',
                'eventos': metrics_callback.events}
    if not metrics_callback.calls:
        metrics['coste_usd'] = None
    return response, metrics, metrics_callback.events, metrics_callback.calls
