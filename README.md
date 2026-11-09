# Atención al cliente con LangGraph

Práctica para comparar un único agente con todas las herramientas (`single`) y una solución multiagente con supervisor y especialistas (`supervisor`).

## Ejecutar

Python 3.13 o superior. Configura `.env` a partir de `.env.example`:

```bash
uv sync
uv run --env-file .env streamlit run app.py
uv run --env-file .env main.py --repetitions 3 --output resultados.json
```

`MODEL` selecciona el modelo; configura la clave correspondiente. `TIENDA_DB` selecciona SQLite (por defecto `data/tienda.db`). Sin `--env-file`, las variables se leen del entorno.

La guía paso a paso, los casos y los criterios de evaluación están en [PRACTICA.md](PRACTICA.md).

## Estructura del ejercicio

```text
app.py
main.py
src/multiagent_store/
├── cli.py
├── execution.py
├── scenarios.py
├── agents/
│   ├── architectures.py        # Selección alumno / solución local
│   ├── specialists.py           # Roles e instrucciones proporcionadas
│   ├── tools.py                 # Único archivo de herramientas de la práctica
│   ├── coordination.py          # Arquitectura supervisor con LangGraph (resuelta)
│   └── messages.py              # Utilidades de mensajes
├── exercises/
│   ├── student.py               # Código con TODO: se sube a Git
│   └── student_solution.py      # Resuelto: local, ignorado por Git
├── data/store.py
└── ui/
    ├── application.py
    └── inspector.py
tests/
data/tienda.db
PRACTICA.md
```

El modo predeterminado es `student`. En Streamlit aparece `Solución completa` solo si existe `exercises/student_solution.py`. La terminal permite seleccionarla con `--implementation solution`; sin ese archivo informa de que no está disponible.

`agents/tools.py` es el único archivo de herramientas de negocio: consulta datos y calcula propuestas de reembolso. Las herramientas antiguas se han eliminado.

`uv sync` instala el paquete desde `src/`. La base de datos sigue en `data/tienda.db`; `TIENDA_DB` permite cambiar la ruta.

```bash
uv run --env-file .env multiagent-store --implementation student --case change_of_mind_journey
```

## Verificación

```bash
uv run python -m unittest discover -s tests -v
```

Las pruebas usan modelos simulados y no necesitan claves ni llaman a proveedores.

## Casos de comparación

```bash
uv run --env-file .env multiagent-store --case change_of_mind_journey --output case1.json
uv run --env-file .env multiagent-store --case damaged_journey --output case2.json
```

## Código para completar

Completa los tres TODO de `exercises/student.py`: single, especialistas y coordinador. Los wrappers y las herramientas vienen proporcionados. El archivo `student_solution.py` tiene las mismas funciones ya resueltas y está ignorado por Git. No copies respuestas al archivo del alumno antes de entregar el repositorio.

La guía pública no incluye la solución de esos bloques.
