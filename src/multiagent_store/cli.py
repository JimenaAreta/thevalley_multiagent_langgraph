"""Customer-service exercise using the same architectures as the web UI.

uv run --env-file .env main.py
uv run --env-file .env main.py single subagents --case change_of_mind_journey
Returns only calculate proposals; no refund is registered or paid."""
import os
import argparse
import json
from pathlib import Path

from multiagent_store.agents.architectures import ARCHITECTURES, CLASSROOM_ARCHITECTURES
from multiagent_store.execution import execute_turn
from multiagent_store.data.store import DEFAULT_DB_PATH, Store
from multiagent_store.scenarios import SCENARIOS, inspect_selection


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("El valor debe ser mayor que cero")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("versions", nargs="*", metavar="VERSION")
    parser.add_argument('--step-limit', '--limite-pasos', dest='step_limit', type=positive_integer,
                        default=os.getenv("LIMITE_PASOS", "15"))
    parser.add_argument('--repetitions', '--repeticiones', dest='repetitions', type=positive_integer,
                        default=os.getenv("REPETICIONES", "1"))
    parser.add_argument('--output', '--salida', dest='output_data', help='Archivo JSON con resultados y eventos')
    parser.add_argument('--rates', '--tarifas', dest='rates', type=float, nargs=3,
                        metavar=('ENTRADA', 'CACHE', 'SALIDA'),
                        help='USD por millón de tokens; sin tarifas el coste es desconocido')
    parser.add_argument('--case', '--caso', dest='case', choices=list(SCENARIOS), default='change_of_mind_journey',
                        help='Journey completo: seguimiento y devolución por cambio de opinión o daño')
    parser.add_argument('--implementation', choices=['solution', 'student'], default='student',
                        help='Ejecutar la solución o el código del alumno')
    args = parser.parse_args()
    if args.rates and any(t < 0 for t in args.rates):
        parser.error('Las tarifas no pueden ser negativas')
    if any(v not in ARCHITECTURES for v in args.versions):
        parser.error("Versiones válidas: " + ", ".join(ARCHITECTURES))
    selected = args.versions or CLASSROOM_ARCHITECTURES
    store = Store(os.getenv('TIENDA_DB', str(DEFAULT_DB_PATH)))
    results = []
    for version in selected:
        print(f"\n=== {version} ===")
        queries = SCENARIOS[args.case]
        for attempt in range(1, args.repetitions + 1):
            history = []
            for n, query_text in enumerate(queries, 1):
                history.append({'role': 'user', 'content': query_text})
                response, metrics, _, _ = execute_turn(
                    version, history, store, args.rates, step_limit=args.step_limit, implementation=args.implementation)
                metrics.update({'consulta': query_text, 'caso': args.case, 'consulta_numero': n,
                                'repeticion': attempt, 'turno': n,
                                'tool_selection': inspect_selection(args.case, n, metrics['eventos'])})
                results.append(metrics)
                print(f"\n[{n}.{attempt}] {query_text}\n  -> {response}")
                if metrics['error']:
                    break
                else:
                    history.append({'role': 'assistant', 'content': response})
    print("\n=== COMPARACIÓN ===")
    print(f"{'versión':<14}{'caso':<7}{'intento':<9}{'llamadas':<10}{'tokens':<10}{'segundos':<10}error")
    for r in results:
        tokens = r['entrada'] + r['salida']
        print(f"{r['arquitectura']:<14}{r['consulta_numero']:<7}{r['repeticion']:<9}"
              f"{r['llamadas']:<10}{tokens:<10}{r['segundos']:<10}{r['error'] or ''}")
    if args.output_data:
        Path(args.output_data).write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"Resultados y eventos guardados en {args.output_data}")
    print("Revisa completa, correcta y acciones_respaldadas con PRACTICA.md. "
          "Los tokens no reportados no equivalen a consumo cero.")


if __name__ == "__main__":
    main()
