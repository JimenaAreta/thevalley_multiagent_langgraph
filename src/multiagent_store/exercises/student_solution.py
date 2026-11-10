"""Local instructor solution. Ignored by Git; do not distribute to students.

Use the same tools, model and BASE instructions in both architectures.
Select the student implementation in Streamlit or pass --implementation student.
"""


from langchain.agents import create_agent
from langchain_core.tools import tool
from multiagent_store.agents.messages import message_text
from multiagent_store.agents.specialists import AREAS, BASE, ROLE_DESCRIPTIONS
from multiagent_store.agents.tools import create_tools


COORDINATOR_PROMPT = (
    ' Decide qué área necesita la pregunta actual y delega mediante sus herramientas. '
    'Cada especialista solo recibe la petición que redactes: incluye número de pedido, '
    'intención actual, motivo si existe y antecedentes necesarios. '
    'Si el cliente cambia de pedido o de tema, elige de nuevo el área y el contexto. '
    'Pregunta los datos que falten. Sintetiza los resultados sin confundir precio, pago y reembolso.'
)


def build_single(model, groups):
    """Return one agent with all unique business tools."""
    tools = list({tool.name: tool for group in groups.values() for tool in group}.values())
    return create_agent(model, tools=tools, system_prompt=BASE, name='single')


def build_specialists(model, groups):
    """Return one agent per area, with only its own tools."""
    return {
        name: create_agent(model, tools=groups[name],
            system_prompt=BASE + f' Tu área es {name}: {ROLE_DESCRIPTIONS[name]}', name=name)
        for name in AREAS
    }


def wrap_specialist(name, agent):
    """Provided: expose a specialist as a tool receiving an isolated request."""
    @tool(f'query_{name}', description=ROLE_DESCRIPTIONS[name])
    def delegate(request: str) -> str:
        result = agent.invoke({'messages': [('user', request)]})
        return message_text(result['messages'][-1])
    return delegate


def build_coordinator(model, specialists):
    """Return the coordinator with specialist wrappers instead of raw tools."""
    return create_agent(model,
        tools=[wrap_specialist(name, agent) for name, agent in specialists.items()],
        system_prompt=BASE + COORDINATOR_PROMPT, name='coordinator')


def build(architecture, model, store):
    """Provided: same entry signature as the completed implementation."""
    groups = create_tools(store)
    if architecture == 'single':
        return build_single(model, groups)
    if architecture in ('subagents', 'supervisor'):
        specialists = build_specialists(model, groups)
        return build_coordinator(model, specialists)
    raise ValueError('La versión de alumno solo incluye single y supervisor.')
