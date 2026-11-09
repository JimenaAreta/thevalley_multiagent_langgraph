"""Provided LangGraph coordinator: a supervisor routes the shared history between specialists.

Unlike subagents, specialists see the whole conversation and their answers are
added to the shared state. The supervisor only chooses the next area or FINISH.
"""
from typing import Literal

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from multiagent_store.agents.messages import message_text
from multiagent_store.agents.specialists import AREAS, BASE, ROLE_DESCRIPTIONS
from multiagent_store.agents.tools import create_tools

FINISH = 'FINISH'
SUPERVISOR_PROMPT = (
    ' Eres el supervisor. No respondes al cliente ni usas herramientas de negocio: '
    'decides qué especialista debe actuar ahora sobre el último mensaje del cliente. '
    'Los especialistas leen toda la conversación y sus respuestas se añaden a ella. '
    'Elige FINISH cuando las respuestas de este turno bastan o cuando faltan datos '
    'que solo puede aportar el cliente.\nÁreas:\n'
    + '\n'.join(f'- {area}: {description}' for area, description in ROLE_DESCRIPTIONS.items())
)
SYNTHESIS_PROMPT = (
    ' Redacta la respuesta final al cliente con las respuestas de los especialistas '
    'de este turno, sin añadir importes ni datos que no aparezcan en ellas. '
    'Si ningún especialista actuó, pide al cliente los datos que faltan.'
)


class CoordinationError(ValueError):
    """The model proposed an invalid or repeated destination."""


def handled_areas(state):
    """Specialists that already answered in this turn; earlier turns are plain assistant messages."""
    return [m.name for m in state['messages'] if isinstance(m, AIMessage) and m.name in AREAS]


def validate_destination(destination, state, current=None):
    if destination == END:
        return destination
    if destination not in AREAS or destination == current or destination in handled_areas(state):
        raise CoordinationError(f"Destino inválido o repetido: {destination}")
    return destination


def final_response(messages, name):
    if not messages or not isinstance(messages[-1], AIMessage):
        raise CoordinationError(f"{name} no devolvió una respuesta final")
    response = messages[-1]
    if response.tool_calls or not message_text(response).strip():
        raise CoordinationError(f"{name} terminó sin una respuesta de texto")
    return response.model_copy(update={"name": name})


def turn(state: MessagesState, name: str):
    """Append a temporary user instruction to the conversation.

Some models require the final input message to be from the user.
The instruction is not persisted in the shared state."""
    return state["messages"] + [
        HumanMessage(f"Ahora te toca a ti, agente de {name}: atiende solo lo de tu área.")
    ]


def route_schema(available):
    """Offer the supervisor only the areas that have not answered yet in this turn."""
    class Route(BaseModel):
        next: Literal[*available, FINISH] = Field(description='Siguiente área o FINISH')
    return Route


def route_from_text(text, available):
    """Fallback when the model does not support structured output."""
    normalized = (text or '').strip().lower()
    if not normalized:
        return FINISH
    for choice in (*available, FINISH):
        if choice.lower() in normalized:
            return choice
    return FINISH


def build_supervisor(model, store):
    groups = create_tools(store)

    def supervisor(state: MessagesState):
        handled = handled_areas(state)
        available = [area for area in AREAS if area not in handled]
        if not available:
            return Command(goto='synthesis', update={'route': 'synthesis'})
        note = f" Ya han respondido en este turno: {', '.join(handled)}." if handled else ''
        prompt = [SystemMessage(BASE + SUPERVISOR_PROMPT + note), *turn(state, 'supervisión')]
        if hasattr(model, 'with_structured_output'):
            try:
                router = model.with_structured_output(route_schema(available))
                route = router.invoke(prompt)
                next_area = getattr(route, 'next', None)
            except Exception:
                next_area = None
            if next_area is None:
                response = model.invoke(prompt)
                next_area = route_from_text(message_text(response), available)
        else:
            response = model.invoke(prompt)
            next_area = route_from_text(message_text(response), available)
        if next_area == FINISH or next_area is None:
            route_decision = 'synthesis'
        else:
            route_decision = validate_destination(next_area, state)
        return Command(goto=route_decision, update={'route': route_decision})

    def specialist_node(area):
        agent = create_agent(model, tools=groups[area], name=area,
                             system_prompt=BASE + f' Tu área es {area}: {ROLE_DESCRIPTIONS[area]}')

        def run(state: MessagesState):
            result = agent.invoke({'messages': turn(state, area)})
            return {'messages': [final_response(result['messages'], area)]}
        return run

    def synthesis(state: MessagesState):
        response = model.invoke([SystemMessage(BASE + SYNTHESIS_PROMPT), *turn(state, 'síntesis')])
        return {'messages': [final_response([response], 'supervisor')]}

    graph = StateGraph(MessagesState)
    graph.add_node('supervisor', supervisor, destinations=(*AREAS, 'synthesis'))
    for area in AREAS:
        graph.add_node(area, specialist_node(area))
        graph.add_edge(area, 'supervisor')
    graph.add_node('synthesis', synthesis)
    graph.add_edge(START, 'supervisor')
    graph.add_edge('synthesis', END)
    return graph.compile(name='supervisor')
