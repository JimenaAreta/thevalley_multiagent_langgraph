# Journey de cliente: un agente frente a una solución multiagente con supervisor

**Práctica: Comparamos dos arquitecturas:**

1. **`single`:** un agente con todas las herramientas de negocio.
2. **`supervisor`:** un supervisor con especialistas encargados de áreas concretas.

Los especialistas orders, returns, billing y catalog son áreas dentro de la
arquitectura `supervisor`, no cuatro arquitecturas separadas. Las variantes de
motivo de devolución pertenecen al mismo journey y se prueban con estas dos
versiones.

El ejercicio recorre una conversación completa: seguimiento de un pedido en
camino, devolución de otro recibido, petición de datos que faltan, motivo y
propuesta de reembolso. Después se contrastan pago, reembolso y precio actual.
Comparamos las mismas herramientas, reglas, modelo y mensajes en ambas versiones.

## Plan de práctica

La práctica empieza con la comparación y sigue el flujo de trabajo habitual del ejercicio.

Recorrido obligatorio: **cambio de opinión**, una vez con single y una con
`supervisor`. Se mantienen sus siete turnos. La variante de producto dañado queda
como ampliación o demostración posterior.

Las herramientas, SQLite, las reglas, los prompts base y el inspector se entregan
preparados. El alumno trabaja solo en la creación de single, la creación de
especialistas con su grupo de herramientas y la delegación del supervisor. No
implementa persistencia, interfaz, políticas ni tests durante la práctica.

Para evitar duplicar ejecuciones, usa «Probar una arquitectura» para un primer
turno de comprobación. Después ejecuta el journey completo una sola vez por
arquitectura en comparación; no es necesario repetirlo entero manualmente.

## Preparar y localizar el código

```bash
uv sync
uv run --env-file .env streamlit run app.py
```

Configura `.env` con `OPENAI_API_KEY` y `MODEL`. El inspector local muestra
los mensajes y las herramientas sin servicios de trazas externos. Cada ejecución real consume API.

Código en `src/multiagent_store/`:

- `exercises/student.py`: el código que completa el alumno.
- `agents/tools.py`: funciones de negocio disponibles, agrupadas por área.
- `agents/specialists.py`: áreas, roles y reglas comunes (`AREAS`, `ROLE_DESCRIPTIONS`, `BASE`).
- `agents/architectures.py`: elige entre el código del alumno y la solución local.
- `agents/messages.py`: extrae el texto de un mensaje del modelo.
- `agents/coordination.py`: arquitectura `supervisor` con LangGraph, ya resuelta.
- `scenarios.py`: mensajes del cliente, referencias y objetivos por turno.
- `execution.py`: ejecución y captura de métricas y mensajes.
- `data/store.py`: SQLite, datos y políticas ficticias.
- `ui/`: pantalla e inspector.

El ejercicio se centra en single y `supervisor`. La arquitectura `supervisor` se
entrega resuelta como ampliación: es un `StateGraph` de LangGraph en el que un
supervisor elige el siguiente especialista o FINISH, los especialistas leen el
historial completo y un nodo de síntesis redacta la respuesta. Compárala con
single, donde el agente usa todas las herramientas a la vez. Selecciónala en
«Arquitectura» o en «Arquitecturas que ejecutar»; no se ejecuta por defecto.

## Versión del alumno y solución

La solución local del docente se conserva en
`src/multiagent_store/exercises/student_solution.py`, ignorada por Git.
El archivo para completar está en **`src/multiagent_store/exercises/student.py`**.
No tienes que borrar ni modificar la solución para hacer la práctica.

En Streamlit, selecciona **Código que ejecutar → Ejercicio del alumno**.
Hay tres bloques pendientes:

1. **TODO 1 — `build_single`:** reúne las herramientas de todos los grupos,
   elimina duplicados por nombre y devuelve un agente con BASE.
2. **TODO 2 — `build_specialists`:** devuelve un diccionario de agentes por área,
   cada uno con sus herramientas y sus instrucciones. Usa AREAS y ROLE_DESCRIPTIONS.
3. **TODO 3 — `COORDINATOR_PROMPT` y `build_coordinator`:** redacta cómo delegar el
   contexto y crea el supervisión con las herramientas de especialistas. Debe
   usar BASE y tus instrucciones, sin recibir directamente las herramientas de negocio.

`wrap_specialist` y el punto de entrada `build` ya están preparados. El wrapper
muestra explícitamente que cada especialista solo recibe la petición delegada.
Los TODO lanzan `IncompleteExercise` hasta que sustituyas el `raise` por tu código.
Al ejecutar se muestra cuál falta; un TODO no ejecuta llamadas al modelo.
Necesitas configurar el proveedor igual que para la solución.

Primero completa TODO 1 y prueba single. Después completa TODO 2 y TODO 3 y
prueba la arquitectura `supervisor`. Guarda el archivo antes de volver a ejecutar.
Si Streamlit no recarga el módulo modificado, reinicia la aplicación. Si tienes
el archivo local del docente, usa «Solución completa» para consultar la referencia
y empieza una conversación nueva para comparar. Las métricas y el JSON
identifican si se ejecutó `student` o `solution`.

En terminal:

```bash
uv run --env-file .env multiagent-store single --implementation student --case change_of_mind_journey
uv run --env-file .env multiagent-store --implementation student --case change_of_mind_journey --output student.json
```

El modo alumno es el predeterminado. `--implementation solution` selecciona
la solución del docente solo si existe su archivo local. Sin ese archivo,
Streamlit ofrece únicamente el modo alumno y el repositorio sigue arrancando.
La terminal y la web reutilizan las mismas herramientas y métricas.

## Los dos pedidos del cliente

| Pedido | Situación | Uso |
| --- | --- | --- |
| 1043 | En tránsito | Preguntar por el seguimiento; no darlo por recibido. |
| 2001 | Entregado | Consultar devolución, motivo e importes. |

La fecha de los datos es estática y ficticia. No inventar localización ni una fecha
nueva de entrega. El pedido 2001 corresponde a P1 y a la factura F-2001.

| Concepto del 2001 | Importe inicial |
| --- | --- |
| Precio histórico antes de descuento | 69,90 € |
| Descuento | 10,00 € |
| Producto pagado tras descuento | 59,90 € |
| Envío pagado | 4,90 € |
| Total pagado | **64,80 €** |
| Precio actual de catálogo | **59,90 €** |
| Propuesta por cambio de opinión | **54,90 €** |
| Propuesta por daño | **64,80 €** |

Por cambio de opinión, la política ficticia DEMO-DESIST-1 no reintegra el envío y
resta 5 € de devolución: 59,90 − 5 = 54,90 €. Por daño, DEMO-DANO-1 reintegra el
producto pagado y el envío, sin coste de devolución: 59,90 + 4,90 = 64,80 €.
Son reglas inventadas para el ejercicio, no normativa comercial.

## Journey que debe recorrer el alumno

En «Probar una arquitectura» selecciona el journey y el paso. Ejecuta los pasos
en orden, **leyendo la respuesta antes de aportar el siguiente dato**.
No reinicies la conversación entre turnos. Reiníciala al cambiar de arquitectura
o de variante. El texto se puede editar para responder de forma natural.

| Paso | Mensaje del cliente | Qué esperamos del sistema |
| --- | --- | --- |
| 1 | Hola, ¿cómo está mi pedido 1043? ¿Ya ha llegado? | Consultar 1043 e informar de que está en tránsito. |
| 2 | Gracias. Tengo otro pedido que sí he recibido y quiero devolverlo. | Preguntar qué pedido es. No asumir que sigue siendo 1043. |
| 3 | El pedido que quiero devolver es el 2001. | Conservar 2001 como pedido de devolución y preguntar el motivo. Puede pedirlo junto al número en el turno anterior. |
| 4A | Lo quiero devolver porque ya no lo necesito; he cambiado de opinión. ¿Cuánto me devolveríais? | Consultar elegibilidad y política de cambio de opinión; proponer 54,90 €. |
| 5 | Antes de decidir, ¿cuánto pagué en total por ese pedido, incluidos descuento y envío? | Conservar 2001 y consultar el pago: 64,80 €, no el reembolso. |
| 6 | Explícame por qué la propuesta de reembolso es diferente o igual a lo que pagué. Desglosa los importes. | Explicar diferencia de 9,90 €: envío no reintegrado 4,90 € y coste de devolución 5 €. |
| 7 | ¿Y cuánto cuesta ahora mismo ese producto en el catálogo? | Recuperar el producto del 2001 y consultar precio actual: 59,90 €. |

**Ampliación:** empezar de nuevo el mismo journey y sustituir solo 4A por:

> Lo quiero devolver porque llegó roto. ¿Cuánto me devolveríais?

Ahora la propuesta es 64,80 € y coincide con lo pagado. En el paso 6 debe explicar
que se reintegra envío y no se cobra devolución; no reutilizar la política anterior.

En ambos recorridos se calcula una **propuesta**: no se registra la devolución ni
se ejecuta el reembolso. El sistema no debe afirmar haber realizado esas acciones.

## Construir single

Completa TODO 1 en `exercises/student.py`: reúne las herramientas de los grupos,
elimina duplicados por nombre y crea el agente con el modelo y BASE. La implementación
resuelta está solo en el archivo local del docente.

El mismo modelo interpreta cada turno, selecciona funciones, genera argumentos,
recibe resultados y redacta la respuesta. Tiene todo el historial y todas las
herramientas. Prueba el primer mensaje para comprobar que consulta el pedido;
reserva la ejecución completa para la comparación.

Herramientas próximas que pueden confundirse:

| Función | Significado |
| --- | --- |
| query_order | Estado y entrega de un pedido. |
| query_catalog_price | Precio actual del producto de un pedido. |
| query_order_price | Precio histórico antes de descuento y envío. |
| query_payment | Total efectivamente pagado y desglose. |
| calculate_refund | Propuesta según política y motivo. |

Las descripciones son claras y compartidas entre versiones. No se dificulta el
single con herramientas engañosas ni se ocultan reglas de negocio.

## Construir el supervisor y los especialistas

Completa TODO 2 y TODO 3 en `exercises/student.py`. Reutiliza las mismas funciones y BASE; solo cambia su distribución:

- **orders:** seguimiento.
- **returns:** elegibilidad, políticas, pago y cálculo de propuestas.
- **billing:** importes históricos, pago y factura.
- **catalog:** disponibilidad y precio actual.

`create_tools(store)` ya devuelve las herramientas agrupadas por área. En TODO 2
cada especialista se crea con `create_agent`, solo con las herramientas de su
grupo y con `BASE` más la descripción de su rol. En TODO 3 cada especialista se
envuelve como una herramienta del supervisor con `wrap_specialist`, ya preparado:

```python
def wrap_specialist(name, agent):
    @tool(f'query_{name}', description=ROLE_DESCRIPTIONS[name])
    def delegate(request: str) -> str:
        result = agent.invoke({'messages': [('user', request)]})
        return message_text(result['messages'][-1])
    return delegate
```

El supervisor recibe la conversación y elige a quién delegar. El especialista
recibe **solo la petición redactada por el supervisor**, no el historial completo.
Debe incluir datos ya conocidos: pedido, intención, motivo y antecedentes útiles.
Debe incluir datos ya conocidos: pedido, intención, motivo y antecedentes útiles.
La respuesta del especialista vuelve al supervisor para sintetizarla.

El recorrido esperado de áreas es orders → returns → billing → returns → catalog,
con preguntas aclaratorias cuando faltan datos. No es una ruta fijada en código:
el modelo decide. Para explicar importes, returns también tiene query_payment;
resolver el paso 5 allí puede ser válido. Evaluamos si resuelve bien la petición,
no una secuencia rígida de nombres.

## Qué comprobar en cada turno

1. ¿Mantiene separados 1043 y 2001?
2. ¿Pregunta el número del otro pedido y después el motivo, sin inventarlos?
3. ¿Interpreta respuestas cortas usando el historial?
4. ¿El supervisor envía el pedido 2001 cuando el último mensaje no lo repite?
5. ¿Llega el motivo al especialista y se aplica la política correcta?
6. ¿Distingue pago, precio histórico, precio actual y reembolso?
7. ¿El resumen del especialista conserva el desglose suficiente para el seguimiento?
8. ¿Añade la delegación llamadas, tokens y tiempo? ¿Mejora la selección?

Abre «Qué herramientas puede elegir cada agente» y después las llamadas del
inspector. Localiza argumentos, petición al especialista y respuesta. El inspector
global muestra las consultas interiores, aunque el supervisor solo reciba el resumen.

## Comparación completa

Revisa prioritariamente tres puntos del recorrido:

- **Pasos 2–3:** cambia de pedido y pide número y motivo sin inventarlos.
- **Pasos 4–5:** distingue propuesta de reembolso (54,90 €) de pago (64,80 €).
- **Paso 7:** consulta precio actual (59,90 €) y manda el contexto al área adecuada.

No es necesario abrir todas las llamadas de ambos recorridos. Para esos tres
puntos, localiza herramienta, argumentos y contexto delegado, y registra consumo.

En «Comparar arquitecturas» se ejecutan automáticamente los siete mensajes del
journey con historial independiente para single y supervisor: **14 ejecuciones**
por variante y repetición. Cada línea es un turno, no una conversación separada.

El guion automático envía el siguiente mensaje aunque el agente no haya preguntado
lo que faltaba. Revisa las respuestas de los pasos 2 y 3: que el guion aporte luego
los datos no convierte en correcta una respuesta que los inventó antes. La prueba
manual permite reaccionar al comportamiento del agente.

La tabla incluye objetivos por turno y herramientas de referencia. En los turnos
de aclaración no se exige una llamada. Una herramienta alternativa puede devolver
datos suficientes y un seguimiento puede reutilizar resultados previos. La marca
«¿Se consultó?» **no califica automáticamente la respuesta**. Si editas los mensajes
o añades turnos, se desactivan las referencias de las entradas modificadas.

| Paso | Arquitectura | ¿Pide/usa los datos correctos? | Herramienta y pedido | Motivo y contexto enviados | ¿Respuesta correcta? | Llamadas / tokens / segundos |
| --- | --- | --- | --- | --- | --- | --- |
| 1–7 | single | | | — | | |
| 1–7 | supervisor | | | | | |

Puedes guardar la revisión en «Evaluar calidad y consultar métricas detalladas»
y descargar JSON. Las trazas y los mensajes se guardan en SQLite. No se observa
razonamiento interno: se registran entradas, salidas y llamadas de LangChain.

## Conclusiones

Explica con evidencia dónde hubo confusión: pedido, herramienta, motivo, importe
o contexto. ¿Separar áreas redujo errores? ¿El supervisor introdujo alguno al
delegar o resumir? Si ambos acertaron, ¿compensó el coste adicional?

No hay fallo de single garantizado. Las pruebas con modelos simulados comprueban
la infraestructura, no prueban superioridad de una arquitectura con un modelo real.

## Terminal (alternativa a Streamlit, no tarea adicional)

```bash
uv run --env-file .env multiagent-store --case change_of_mind_journey --output journey1.json
```

Por defecto se ejecutan single y supervisor con conversaciones nuevas por versión
y repetición. No cambies modelo ni reglas entre las dos arquitecturas.
