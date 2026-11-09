"""Checks that do not require the optional instructor solution."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class StudentDistributionTests(unittest.TestCase):
    def test_repository_starts_without_instructor_files(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            shutil.copytree(root / 'src' / 'multiagent_store', destination / 'src' / 'multiagent_store',
                            ignore=shutil.ignore_patterns('student_solution.py', '__pycache__'))
            shutil.copy2(root / 'app.py', destination / 'app.py')
            code = '''
from pathlib import Path
from multiagent_store.agents.architectures import solution_available, build, SolutionUnavailable
from multiagent_store.exercises.student import IncompleteExercise
from multiagent_store.data.store import Store
from multiagent_store.execution import execute_turn
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from streamlit.testing.v1 import AppTest
assert not solution_available()
store = Store('demo.db')
try:
    build('single', None, store)
except IncompleteExercise:
    pass
else:
    raise AssertionError('The exercise must remain incomplete in the student distribution')
try:
    build('single', None, store, implementation='solution')
except SolutionUnavailable:
    pass
else:
    raise AssertionError('The instructor solution must not be importable')
response, metrics, _, _ = execute_turn('single', [{'role': 'user', 'content': 'Hola'}], store, None,
    model=FakeListChatModel(responses=['unused']))
assert metrics['implementation'] == 'student'
assert metrics['error'] == 'IncompleteExercise'
assert metrics['llamadas'] == 0
app = AppTest.from_file(str(Path('app.py').resolve())).run()
assert not app.exception
mode = next(w for w in app.selectbox if w.label == 'Código que ejecutar')
assert mode.options == ['Ejercicio del alumno'], mode.options
'''
            environment = dict(os.environ, PYTHONPATH=str(destination / 'src'),
                               TIENDA_DB=str(destination / 'demo.db'))
            result = subprocess.run([sys.executable, '-c', code], cwd=destination, env=environment,
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_instructor_paths_are_ignored_by_git(self):
        root = Path(__file__).resolve().parents[1]
        paths = ['src/multiagent_store/exercises/student_solution.py']
        result = subprocess.run(['git', 'check-ignore', *paths], cwd=root,
                                capture_output=True, text=True, check=True)
        self.assertEqual(set(result.stdout.splitlines()), set(paths))
        tracked = subprocess.run(['git', 'ls-files', '--', *paths], cwd=root,
                                 capture_output=True, text=True, check=True)
        self.assertEqual(tracked.stdout, '')
