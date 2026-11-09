"""Streamlit inspector for callback events, messages and tool results."""
import streamlit as st


def messages(data):
    for message in data:
        role = message.get('type', message.get('role', 'mensaje'))
        name = message.get('name')
        st.markdown(f"**{role}{' · ' + name if name else ''}**")
        message_text = message.get('content', '')
        if isinstance(message_text, str):
            st.text(message_text or '(sin texto)')
        else:
            st.json(message_text)
        if message.get('tool_calls'):
            st.write('Llamadas a herramientas solicitadas:')
            st.json(message['tool_calls'])
        with st.expander('Mensaje completo'):
            st.json(message)


def render_inspector(events):
    st.caption('Entradas y salidas registradas en la interfaz de LangChain con el modelo. '
               'Incluye mensajes de sistema, contexto y resultados de herramientas; '
               'no es una captura del cuerpo HTTP del proveedor.')
    steps = [e for e in events if e['tipo'] in ('modelo', 'routing', 'herramienta')]
    if not steps:
        st.info('Esta ejecución no contiene llamadas registradas.')
        return
    for i, event in enumerate(steps, 1):
        is_model = event['tipo'] == 'modelo'
        is_routing = event['tipo'] == 'routing'
        is_tool = event['tipo'] == 'herramienta'
        parts = [p.split(':')[0] for p in event.get('contexto', '').split('|') if p]
        context = ' → '.join(p for p in parts if p not in ('model', 'tools'))
        context = context or event.get('nodo') or 'agente principal'
        if is_model:
            title = 'Llamada al modelo'
        elif is_routing:
            title = f"Ruta del supervisor: {event.get('ruta')}"
        else:
            title = f"Herramienta: {event.get('nombre')}"
        with st.expander(f'{i}. {title} · {context}'):
            st.caption(f"ID de llamada: {event['run_id']} · Padre: {event.get('parent_run_id') or '—'}")
            if is_model:
                st.write('Entrada enviada al modelo, en orden:')
                for batch in event.get('mensajes', []):
                    messages(batch)
                with st.expander('Herramientas y formato de respuesta ofrecidos al modelo'):
                    st.json(event.get('configuracion', {}))
            elif is_routing:
                st.write('Elección del supervisor:')
                st.json({'ruta': event.get('ruta'), 'detalle': event.get('detalle')})
            else:
                st.write('Argumentos enviados:')
                st.json(event.get('argumentos'))
            endings = [e for e in events if e.get('run_id') == event['run_id'] and
                       e['tipo'] in ('respuesta_modelo', 'resultado', 'error_modelo', 'error_herramienta')]
            if is_routing:
                st.write('Salida recibida:')
                st.json({'ruta_seleccionada': event.get('ruta')})
            else:
                st.write('Salida recibida:')
                for end in endings:
                    if end['tipo'] == 'respuesta_modelo':
                        messages(end['mensajes'])
                    elif end['tipo'] == 'resultado':
                        st.json(end['resultado'])
                    else:
                        st.error(end['detalle'])
                if not endings:
                    st.caption('Sin salida registrada.')
    with st.expander('Eventos completos en JSON'):
        st.json(events)
