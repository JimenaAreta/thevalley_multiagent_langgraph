"""Complete customer journeys with two return-reason variants."""

def customer_journey(reason):
    return [
        'Hola, ¿cómo está mi pedido 1043? ¿Ya ha llegado?',
        'Gracias. Tengo otro pedido que sí he recibido y quiero devolverlo.',
        'El pedido que quiero devolver es el 2001.',
        reason,
        'Antes de decidir, ¿cuánto pagué en total por ese pedido, incluidos descuento y envío?',
        'Explícame por qué la propuesta de reembolso es diferente o igual a lo que pagué. Desglosa los importes.',
        '¿Y cuánto cuesta ahora mismo ese producto en el catálogo?',
    ]


SCENARIOS = {
    'change_of_mind_journey': customer_journey('Lo quiero devolver porque ya no lo necesito; he cambiado de opinión. ¿Cuánto me devolveríais?'),
    'damaged_journey': customer_journey('Lo quiero devolver porque llegó roto. ¿Cuánto me devolveríais?'),
}
SCENARIO_LABELS = {
    'change_of_mind_journey': 'Journey · Seguimiento → devolución por cambio de opinión',
    'damaged_journey': 'Journey · Seguimiento → devolución por producto dañado',
}
EXPECTED_TOOLS = {
    case: ['query_order', None, None, 'calculate_refund', 'query_payment', 'calculate_refund', 'query_catalog_price']
    for case in SCENARIOS
}
EXPECTED_AMOUNTS = {
    'change_of_mind_journey': [None, None, None, 5490, 6480, 5490, 5990],
    'damaged_journey': [None, None, None, 6480, 6480, 6480, 5990],
}
TURN_GOALS = [
    'Informar de que 1043 sigue en tránsito, sin inventar entrega.',
    'Pedir el número del otro pedido; no asumir que es 1043.',
    'Conservar 2001 como pedido de devolución y preguntar el motivo.',
    'Usar el motivo aportado para consultar política, elegibilidad y propuesta.',
    'Recuperar el total pagado por 2001, sin confundirlo con el reembolso.',
    'Justificar la propuesta con el motivo y el desglose conservados.',
    'Cambiar a catálogo para consultar el precio actual del producto de 2001.',
]


def inspect_selection(case, turn, events, query=None):
    """Report observable tool selection, not correctness or private reasoning."""
    matches_reference = (1 <= turn <= len(SCENARIOS[case]) and
                         (query is None or query == SCENARIOS[case][turn - 1]))
    expected = EXPECTED_TOOLS[case][turn - 1] if matches_reference else None
    calls = [e['nombre'] for e in events if e['tipo'] == 'herramienta']
    return {
        'turn_goal': TURN_GOALS[turn - 1] if matches_reference else None,
        'expected_tool': expected,
        'expected_amount_centimos': EXPECTED_AMOUNTS[case][turn - 1] if matches_reference else None,
        'called_tools': calls,
        'expected_tool_called': expected in calls if expected else None,
        'note': 'Some turns must ask for missing data. Tool presence is not a correctness grade; history may be reused.',
    }
