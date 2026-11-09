# Atención al cliente con LangGraph

Práctica para comparar un único agente con todas las herramientas (`single`) y
una solución multiagente con supervisor y especialistas (`supervisor`). La web y
la terminal usan `multiagent_store.agents.architectures.build`: mismo modelo,
Herramientas SQLite y reglas. La práctica consulta elegibilidad y calcula
propuestas de devolución; no registra devoluciones ni reembolsos.

## Clase de 150 minutos: 60 de teoría y 90 de práctica

Construimos single y una arquitectura multiagente con supervisor y especialistas.
La práctica sigue un journey de siete turnos: pedido 1043 en tránsito,
devolución del pedido recibido 2001, pregunta del número y motivo, propuesta,
pago, explicación y precio actual. La variante de producto roto queda como
ampliación. El inspector permite localizar confusiones entre pedidos,
herramientas, motivos e importes. El plan y el guion están en [PRACTICA.md](PRACTICA.md).

## Ejecutar

Python 3.13 o superior. Configura `.env` a partir de `.env.example`:

```bash
uv sync
uv run --env-file .env streamlit run app.py
uv run --env-file .env main.py --repetitions 3 --output resultados.json
```

`MODEL` selecciona el modelo; configura la clave correspondiente. `TIENDA_DB`
selecciona SQLite (por defecto `data/tienda.db`). Sin `--env-file`, las variables
se leen del entorno. El inspector local muestra mensajes y herramientas sin
configurar servicios de trazas. La aplicación permite comparar conversaciones,
inspeccionar mensajes completos, revisar calidad, guardar revisiones y exportar
JSON. Cada ejecución real consume API.

La guía paso a paso, los casos y los criterios de evaluación están en
[PRACTICA.md](PRACTICA.md).

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
│   ├── specialists.py         # Roles e instrucciones proporcionadas
│   ├── tools.py               # Único archivo de herramientas de la práctica
│   ├── coordination.py        # Arquitectura supervisor con LangGraph (resuelta)
│   └── messages.py            # Utilidades de mensajes
├── exercises/
│   ├── student.py             # Código con TODO: se sube a Git
│   └── student_solution.py    # Resuelto: local, ignorado por Git
├── data/store.py
└── ui/
    ├── application.py
    └── inspector.py
tests/
data/tienda.db
PRACTICA.md
```

El modo predeterminado es **student**. En Streamlit aparece «Solución completa»
solo si existe `exercises/student_solution.py`. La terminal permite seleccionarla
con `--implementation solution`; sin ese archivo informa de que no está
disponible. El repositorio del alumno arranca sin los archivos locales del docente.

`agents/tools.py` es el único archivo de herramientas de negocio: consulta datos
y calcula propuestas de reembolso. Las herramientas antiguas se han eliminado.

`uv sync` instala el paquete desde `src/`. La base de datos sigue en
`data/tienda.db`; `TIENDA_DB` permite cambiar la ruta. Se conservan los datos
previos.

```bash
uv run --env-file .env multiagent-store --implementation student --case change_of_mind_journey
```

## Decisiones y límites

El alumno crea single y una solución multiagente con supervisor y especialistas
usando las mismas herramientas y reglas. El supervisor decide el siguiente
especialista y los especialistas resuelven su área con el contexto relevante.
Las propuestas no registran devoluciones ni ejecutan reembolsos. SQLite conserva
conversaciones y métricas. El cliente es fijo y los datos son ficticios. El
límite de pasos no es un límite de gasto global. Tokens no reportados no
equivalen a consumo cero; revisa la calidad junto con el coste y el tiempo.

## Verificación

```bash
uv run python -m unittest discover -s tests -v
```

Las pruebas usan modelos simulados y no necesitan claves ni llaman a proveedores.
Las comparaciones reales se ejecutan por separado siguiendo PRACTICA.md.

## Ver qué información se manda

Ejecuta una consulta en «Probar una arquitectura» y abre los pasos bajo «Qué
información se envía en cada paso». Cada llamada al modelo muestra los mensajes
en orden y su salida; cada herramienta muestra sus argumentos y resultado.
Los ID relacionan las entradas con sus salidas y con la ejecución padre. Los
esquemas de herramientas se muestran cuando la integración los reporta.
Es una captura de la interfaz LangChain, no de la petición HTTP del proveedor.
El inspector permanece disponible al cambiar controles; el JSON descargable y
SQLite guardan los mensajes. Los registros anteriores al cambio no incluyen
estos detalles.

## Casos de comparación

```bash
uv run --env-file .env multiagent-store --case change_of_mind_journey --output case1.json
uv run --env-file .env multiagent-store --case damaged_journey --output case2.json
```

La tabla de resultados muestra una herramienta de referencia y las consultas
observadas, sin calificar automáticamente la respuesta. Las dos versiones tienen
las mismas reglas y funciones de negocio; los especialistas solo ven el contexto
relevante para su área. Se comparan single y la solución multiagente con
supervisor y especialistas.

## English code identifiers

Los módulos, clases, funciones y variables usan nombres en inglés. La interfaz,
los mensajes de atención al cliente y esta guía siguen en español. La práctica
y la interfaz comparan `single` y `supervisor`; los otros patrones conservados en
el código quedan fuera de la sesión. El esquema SQLite y las claves de métricas
persistidas conservan sus nombres anteriores para poder leer los datos existentes.
Las conversaciones anteriores siguen disponibles desde la arquitectura
equivalente.

```bash
uv run --env-file .env main.py single supervisor --case change_of_mind_journey --output incident.json
```

## Código para completar

Completa los tres TODO de `exercises/student.py`: single, especialistas y
coordinador. Los wrappers y las herramientas vienen proporcionados. El archivo
`student_solution.py` tiene las mismas funciones ya resueltas y está ignorado por
Git. No copies respuestas al archivo del alumno antes de entregar el repositorio.
La guía pública no incluye la solución de esos bloques.

Las pruebas de integración del docente usan la solución local y se omiten si no
está disponible. `test_student_distribution.py` comprueba que la distribución sin
respuestas arranca, ofrece modo alumno y mantiene los archivos resueltos fuera
de Git.
