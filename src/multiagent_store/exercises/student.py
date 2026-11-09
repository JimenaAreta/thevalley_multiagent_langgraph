"""Complete the TODOs without changing agents/architectures.py.

Use the same tools, model and BASE instructions in both architectures.
Select the student implementation in Streamlit or pass --implementation student.
"""


from langchain.agents import create_agent
from langchain_core.tools import tool
from multiagent_store.agents.messages import message_text
from multiagent_store.agents.specialists import AREAS, BASE, ROLE_DESCRIPTIONS
from multiagent_store.agents.tools import create_tools


class IncompleteExercise(NotImplementedError):
    """A student TODO has not been completed yet."""


# TODO 3: write the coordinator instructions in Spanish.
# Explain how to choose an area and pass order ID, intent, reason and context.
# Specialists do not receive the conversation automatically.
COORDINATOR_PROMPT = ''


def build_single(model, groups):
    """TODO 1: return one create_agent with BASE and all unique business tools."""
    # groups is {area: [tools]}. Deduplicate tools by name: query_payment is shared.
    # Do not call the model directly or choose a tool with an if statement.
    raise IncompleteExercise('TODO 1: completa build_single en exercises/student.py.')


def build_specialists(model, groups):
    """TODO 2: return {area: agent}, with only that area's tools per agent."""
    # Use AREAS, BASE and ROLE_DESCRIPTIONS. Give each agent a name.
    # Keep the same business rules as single; do not add tools from other areas.
    raise IncompleteExercise('TODO 2: completa build_specialists en exercises/student.py.')


def wrap_specialist(name, agent):
    """Provided: expose a specialist as a tool receiving an isolated request."""
    @tool(f'query_{name}', description=ROLE_DESCRIPTIONS[name])
    def delegate(request: str) -> str:
        result = agent.invoke({'messages': [('user', request)]})
        return message_text(result['messages'][-1])
    return delegate


def build_coordinator(model, specialists):
    """TODO 3: return an agent with specialist wrappers and a routing prompt."""
    # Call wrap_specialist for each specialist. Offer these wrappers to create_agent.
    # The coordinator must not get the raw business tools.
    # Use BASE plus COORDINATOR_PROMPT so the shared business rules stay the same.
    raise IncompleteExercise('TODO 3: completa COORDINATOR_PROMPT y build_coordinator en exercises/student.py.')


def build(architecture, model, store):
    """Provided: same entry signature as the completed implementation."""
    groups = create_tools(store)
    if architecture == 'single':
        return build_single(model, groups)
    if architecture in ('subagents', 'supervisor'):
        specialists = build_specialists(model, groups)
        return build_coordinator(model, specialists)
    raise ValueError('La versión de alumno solo incluye single y supervisor.')
