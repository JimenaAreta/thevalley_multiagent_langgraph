"""Local laboratory: uv run --env-file .env streamlit run app.py"""
import json
import os
import uuid

import streamlit as st
from multiagent_store.ui.inspector import render_inspector
from multiagent_store.agents.architectures import ARCHITECTURES, CLASSROOM_ARCHITECTURES, solution_available
from multiagent_store.agents.tools import create_tools
from multiagent_store.execution import execute_turn
from multiagent_store.data.store import DEFAULT_DB_PATH, Store
from multiagent_store.scenarios import SCENARIOS, SCENARIO_LABELS, inspect_selection



def main():
    st.set_page_config(page_title='Laboratorio multiagente', layout='wide')
    st.title('Laboratorio multiagente')
    st.caption('Elige una arquitectura, prueba una consulta y abre cada paso para ver qué información recibe. '
               'Guía de ejercicios: PRACTICA.md.')
    store = Store(os.getenv('TIENDA_DB', str(DEFAULT_DB_PATH)))

    with st.expander('Qué herramientas puede elegir cada agente'):
        groups = create_tools(store)
        all_names = sorted({tool.name for tools in groups.values() for tool in tools})
        rows = [{'Agente': 'single', 'Opciones': len(all_names),
                 'Herramientas disponibles': ', '.join(all_names)},
                {'Agente': 'coordinador', 'Opciones': len(groups),
                 'Herramientas disponibles': ', '.join(f'query_{area}' for area in groups)},
                {'Agente': 'supervisor (LangGraph)', 'Opciones': len(groups) + 1,
                 'Herramientas disponibles': 'Elige el siguiente nodo: ' + ', '.join(groups) + ' o FINISH'}]
        rows += [{'Agente': area, 'Opciones': len(tools),
                  'Herramientas disponibles': ', '.join(tool.name for tool in tools)}
                 for area, tools in groups.items()]
        st.dataframe(rows, hide_index=True)
        st.caption('El coordinador selecciona un área y envía una petición. '
                   'Cada especialista selecciona después una función de negocio. '
                   'Single elige directamente entre todas las funciones. '
                   'En supervisor, los especialistas leen el historial completo y el supervisor solo decide el siguiente nodo.')

    with st.sidebar:
        implementations = ['student', 'solution'] if solution_available() else ['student']
        implementation = st.selectbox('Código que ejecutar', implementations,
            format_func=lambda value: {'solution': 'Solución completa', 'student': 'Ejercicio del alumno'}[value])
        if implementation == 'student':
            st.caption('Completa src/multiagent_store/exercises/student.py. Los TODO pendientes se muestran al ejecutar.')
        architecture = st.selectbox('Arquitectura', ARCHITECTURES)
        st.caption(f"Modelo: {os.getenv('MODEL', 'openai:gpt-5-mini')}")
        st.caption('Las ejecuciones consumen API. La tienda es de demostración; las devoluciones solo se consultan.')

    # valores por defecto simples para la ejecución sin controles de sidebar
    step_limit = 30
    rates = None

    if (st.session_state.get('architecture') != architecture or
            st.session_state.get('implementation') != implementation):
        for key in ('session_id', 'history', 'latest_execution'):
            st.session_state.pop(key, None)
    st.session_state.architecture = architecture
    st.session_state.implementation = implementation
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.history = []


    def render_summary(results):
        st.dataframe([{
            'Arquitectura': r['arquitectura'], 'Repetición': r.get('repeticion', 1),
            'Turno': r.get('turno', 1), 'Llamadas': r['llamadas'],
            'Tokens entrada': r['entrada'], 'Tokens salida': r['salida'],
            'Segundos': r['segundos'], '¿Completa?': r.get('completa', 'pendiente'),
            'Error': r['error'],
            'Objetivo del turno': r.get('tool_selection', {}).get('turn_goal'),
            'Herramienta de referencia': r.get('tool_selection', {}).get('expected_tool'),
            '¿Se consultó?': r.get('tool_selection', {}).get('expected_tool_called'),
        } for r in results], hide_index=True)
        st.caption('La presencia de una herramienta no garantiza que la respuesta sea correcta; '
                   'un seguimiento puede reutilizar datos. Tokens no reportados pueden aparecer como 0.')

    def render_architecture_summary(results):
        rows = []
        for kind in dict.fromkeys(r['arquitectura'] for r in results):
            runs = [r for r in results if r['arquitectura'] == kind]
            selections = [r.get('tool_selection', {}).get('expected_tool_called') for r in runs]
            checked = [s for s in selections if s is not None]
            reviewed = [r['correcta'] for r in runs if r.get('correcta', 'pendiente') != 'pendiente']
            rows.append({
                'Arquitectura': kind, 'Turnos': len(runs),
                'Llamadas': sum(r['llamadas'] for r in runs),
                'Tokens entrada': sum(r['entrada'] for r in runs),
                'Tokens salida': sum(r['salida'] for r in runs),
                'Segundos': round(sum(r['segundos'] for r in runs), 1),
                'Errores': sum(1 for r in runs if r['error']),
                'Herramienta de referencia': f'{sum(checked)}/{len(checked)}' if checked else '—',
                'Correctas (revisadas)': f"{reviewed.count('sí')}/{len(reviewed)}" if reviewed else 'sin revisar',
            })
        st.dataframe(rows, hide_index=True)
        st.caption('Totales de todas las repeticiones. «Herramienta de referencia» cuenta los turnos con una '
                   'herramienta esperada en los que se consultó; «Correctas» solo usa los turnos revisados '
                   'en «Evaluar calidad». Más llamadas no implica peor resultado: compara coste y acierto juntos.')


    try_architecture, compare = st.tabs(['Probar una arquitectura', 'Comparar arquitecturas'])
    with try_architecture:
        example = st.selectbox('Ejemplo', list(SCENARIOS),
                               format_func=SCENARIO_LABELS.get)
        query_index = st.selectbox('Paso del journey', range(len(SCENARIOS[example])),
                                   format_func=lambda i: f'{i+1}. {SCENARIOS[example][i]}')
        st.caption('Ejecuta los pasos en orden, leyendo la respuesta antes de aportar el siguiente dato. '
                   'Al cambiar de variante, pulsa Nueva conversación. La comparación ejecuta el journey completo.')
        query_text = st.text_area('Consulta (puedes editarla)', SCENARIOS[example][query_index], key=f'consulta_{example}_{query_index}')
        if st.button('Nueva conversación'):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.history = []
            st.session_state.pop('latest_execution', None)
        if st.button('Ejecutar consulta') and query_text.strip():
            history = st.session_state.history + [{'role': 'user', 'content': query_text.strip()}]
            with st.spinner('Ejecutando…'):
                response, metrics, events, _ = execute_turn(
                    architecture, history, store, rates, step_limit=step_limit, implementation=implementation)
            if not metrics['error']:
                st.session_state.history = history + [{'role': 'assistant', 'content': response}]
            store.save(st.session_state.session_id, architecture, st.session_state.history, metrics)
            st.session_state.latest_execution = metrics
        for m in st.session_state.history:
            with st.chat_message(m['role']):
                st.write(m['content'])
        if st.session_state.get('latest_execution'):
            latest = st.session_state.latest_execution
            if latest['error']:
                st.error(latest['respuesta'])
            render_summary([latest])
            st.subheader('Qué información se envía en cada paso')
            render_inspector(latest['eventos'])
            st.download_button('Descargar ejecución y mensajes', json.dumps(latest, ensure_ascii=False, indent=2),
                               file_name='ejecucion.json', mime='application/json')

    with compare:
        case = st.selectbox('Escenario', list(SCENARIOS), format_func=SCENARIO_LABELS.get)
        scenario = st.text_area('Mensajes del escenario (uno por línea)',
                                 '\n'.join(SCENARIOS[case]), key=f'escenario_{case}')
        st.caption('Mismo modelo, reglas y herramientas de negocio. Cambia quién selecciona '
                   'las herramientas y qué contexto recibe cada especialista.')
        st.caption('Cada línea es un turno del journey. Revisa si pide los datos que faltan: '
                   'la comparación aporta el siguiente mensaje del guion aunque el agente no lo haya pedido.')
        selected = st.multiselect('Arquitecturas que ejecutar', ARCHITECTURES, default=CLASSROOM_ARCHITECTURES)
        repetitions = st.number_input('Repeticiones por arquitectura', min_value=1, max_value=5, value=1)
        if st.button('Ejecutar comparación (consume API)'):
            messages = [m.strip() for m in scenario.splitlines() if m.strip()]
            results = []
            for attempt in range(repetitions):
                for kind in selected:
                    history = []
                    session_id = f'benchmark-{uuid.uuid4()}'
                    for step, query_text in enumerate(messages, 1):
                        history.append({'role': 'user', 'content': query_text})
                        with st.spinner(f'{kind} · repetición {attempt+1} · turno {step}'):
                            response, metrics, _, _ = execute_turn(
                                kind, history, store, rates, step_limit=step_limit, implementation=implementation)
                        metrics.update({'repeticion': attempt+1, 'turno': step, 'experimento': session_id, 'consulta': query_text,
                                    'caso': case, 'tool_selection': inspect_selection(case, step, metrics['eventos'], query_text)})
                        if not metrics['error']:
                            history.append({'role': 'assistant', 'content': response})
                        store.save(session_id, kind, history, metrics)
                        results.append(metrics)
                        if metrics['error']:
                            break
            st.session_state.pop('revision_calidad', None)
            st.session_state.results = results
        if (st.session_state.get('results') and
                st.session_state.results[0].get('implementation', 'student') == implementation):
            results = st.session_state.results
            st.subheader('Resumen por arquitectura')
            render_architecture_summary(results)
            st.subheader('Detalle por turno')
            render_summary(results)
            index = st.selectbox('Inspeccionar ejecución', range(len(results)),
                                 format_func=lambda i: f"{i+1}. {results[i]['arquitectura']} · "
                                 f"repetición {results[i]['repeticion']} · turno {results[i]['turno']}")
            st.write(results[index]['respuesta'])
            render_inspector(results[index]['eventos'])
            with st.expander('Evaluar calidad y consultar métricas detalladas'):
                st.caption('Revisa las respuestas y los mensajes antes de marcar los criterios.')
                fields = ['ejecucion_id', 'arquitectura', 'repeticion', 'turno',
                          'completa', 'correcta', 'acciones_respaldadas', 'observaciones']
                reviews = st.data_editor(
                    [{k: r[k] for k in fields} for r in results],
                    disabled=['ejecucion_id', 'arquitectura', 'repeticion', 'turno'],
                    column_config={c: st.column_config.SelectboxColumn(
                        options=['pendiente', 'sí', 'no'], required=True)
                        for c in ('completa', 'correcta', 'acciones_respaldadas')},
                    hide_index=True, key='revision_calidad')
                if st.button('Guardar revisión de calidad'):
                    st.session_state.results = [store.save_review(r['ejecucion_id'], r) for r in reviews]
                    st.rerun()
                st.dataframe([{k: v for k, v in r.items() if k != 'eventos'} for r in results], hide_index=True)
            st.download_button('Descargar resultados JSON', json.dumps(results, ensure_ascii=False, indent=2),
                               file_name='comparacion.json', mime='application/json')
