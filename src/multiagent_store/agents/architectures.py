"""Select the student implementation or an optional local instructor solution."""
from importlib import import_module
from importlib.util import find_spec

from multiagent_store.agents.coordination import build_supervisor

# The classroom compares single vs a multi-agent supervisor with specialists.
# Keep `subagents` as a compatibility alias for older saved sessions and legacy calls.
ARCHITECTURES = ['single', 'supervisor', 'subagents']
CLASSROOM_ARCHITECTURES = ['single', 'supervisor']
SOLUTION_MODULE = 'multiagent_store.exercises.student_solution'


class SolutionUnavailable(RuntimeError):
    """The local instructor solution is not part of the student repository."""


def solution_available():
    return find_spec(SOLUTION_MODULE) is not None


def build(architecture, model, store, implementation='student'):
    if architecture not in ARCHITECTURES:
        raise ValueError('Arquitectura desconocida')
    if architecture == 'supervisor':
        return build_supervisor(model, store)
    if implementation == 'student':
        module = import_module('multiagent_store.exercises.student')
    elif implementation == 'solution':
        if not solution_available():
            raise SolutionUnavailable('La solución es un archivo local del docente y no está disponible.')
        module = import_module(SOLUTION_MODULE)
    else:
        raise ValueError('Unknown implementation')
    return module.build(architecture, model, store)
