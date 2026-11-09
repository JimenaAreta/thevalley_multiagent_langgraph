"""Business tools shared by every architecture."""
from typing import Literal



from langchain_core.tools import tool

def create_tools(store):
    @tool
    def query_catalog() -> list[dict]:
        """Read product names, prices in euro cents and available stock."""
        return store.products()

    @tool
    def query_catalog_price(order_id: str) -> dict:
        """Read the CURRENT catalog price of an order's product, not the historical price or payment."""
        order = store.get_order(order_id)
        if 'error' in order:
            return order
        return {'order_id': order_id, 'amount_type': 'current_catalog_price',
                'amount_centimos': order['precio_centimos'], 'moneda': 'EUR'}

    @tool
    def query_order_price(order_id: str) -> dict:
        """Read the HISTORICAL product price before discounts and shipping, not the total paid."""
        payment = store.payment_breakdown(order_id)
        if 'error' in payment:
            return payment
        return {'order_id': order_id, 'amount_type': 'historical_product_price',
                'amount_centimos': payment['precio_original_centimos'], 'moneda': 'EUR'}

    @tool
    def query_order(order_id: str) -> dict:
        """Read order status, delivery date and product for the current customer."""
        return store.get_order(order_id)

    @tool
    def query_invoice(order_id: str) -> dict:
        """Read the invoice reference and historical payment breakdown for an order."""
        data = store.get_order(order_id)
        if 'error' in data:
            return data
        payment = store.payment_breakdown(order_id)
        if 'error' in payment:
            return payment
        return {'id': data['id'], 'factura': data['factura'], **payment}

    @tool
    def check_return(order_id: str, reason: str) -> dict:
        """Check return eligibility without registering a return or refund."""
        if not reason.strip():
            return {'error': 'Indica el motivo de la devolución'}
        data = store.get_order(order_id)
        if 'error' in data:
            return data
        return {'order_id': order_id, 'reason': reason,
                'elegible_demo': data['estado'] == 'entregado',
                'registrada': False}

    @tool
    def query_payment(order_id: str) -> dict:
        """Read the historical price, discount and shipping paid, in euro cents."""
        return store.payment_breakdown(order_id)

    @tool
    def query_policy(kind: Literal['damaged', 'change_of_mind']) -> dict:
        """Read the fictional return policy for damage or a change of mind."""
        return store.return_policy(kind)

    @tool
    def calculate_refund(order_id: str, kind: Literal['damaged', 'change_of_mind']) -> dict:
        """Calculate a proposal using historical payments and demo rules. Never register or pay it."""
        return store.calculate_refund(order_id, kind)

    return {
        'catalog': [query_catalog, query_catalog_price], 'orders': [query_order],
        'billing': [query_invoice, query_order_price, query_payment],
        'returns': [check_return, query_policy, query_payment, calculate_refund],
    }
