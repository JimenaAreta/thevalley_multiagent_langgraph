"""Demo data, business rules and conversation storage in SQLite."""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / 'data' / 'tienda.db'


class Store:
    def __init__(self, path=DEFAULT_DB_PATH):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS productos (
                    id TEXT PRIMARY KEY, nombre TEXT, precio_centimos INTEGER, stock INTEGER);
                CREATE TABLE IF NOT EXISTS pedidos (
                    id TEXT PRIMARY KEY, cliente TEXT, producto TEXT, estado TEXT,
                    entrega TEXT, factura TEXT);
                CREATE TABLE IF NOT EXISTS pagos_demo (
                    pedido TEXT PRIMARY KEY, precio_original_centimos INTEGER NOT NULL,
                    descuento_centimos INTEGER NOT NULL, envio_centimos INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS conversaciones (
                    id TEXT PRIMARY KEY, arquitectura TEXT, mensajes TEXT);
                CREATE TABLE IF NOT EXISTS ejecuciones (
                    id INTEGER PRIMARY KEY, conversacion TEXT, datos TEXT);
                CREATE TABLE IF NOT EXISTS devoluciones (
                    id INTEGER PRIMARY KEY, pedido TEXT UNIQUE NOT NULL,
                    motivo TEXT NOT NULL, importe_centimos INTEGER NOT NULL,
                    estado TEXT NOT NULL, reembolso_estado TEXT NOT NULL,
                    creada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            ''')
            db.executemany('INSERT OR IGNORE INTO productos VALUES (?,?,?,?)', [
                ('P1', 'Auriculares inalámbricos', 5990, 12),
                ('P2', 'Teclado mecánico', 8990, 0),
                ('P3', 'Ratón ergonómico', 3490, 25)])
            db.executemany('INSERT OR IGNORE INTO pedidos VALUES (?,?,?,?,?,?)', [
                ('1042', 'Cliente demo', 'P1', 'entregado', '2026-10-16', 'F-1042'),
                ('1043', 'Cliente demo', 'P3', 'en tránsito', '2026-10-20', 'F-1043'),
                ('1044', 'Otro cliente', 'P2', 'preparando', '2026-10-22', 'F-1044'),
                ('2001', 'Cliente demo', 'P1', 'entregado', '2026-10-18', 'F-2001')])

            # Historical prices are independent of current catalog prices.
            db.executemany('INSERT OR IGNORE INTO pagos_demo VALUES (?,?,?,?)', [
                ('1042', 5990, 1000, 490), ('1043', 3490, 0, 490),
                ('2001', 6990, 1000, 490)])

    def payment_breakdown(self, order_id):
        if 'error' in self.get_order(order_id):
            return {'error': 'Pedido no encontrado para el cliente demo'}
        with self.connect() as db:
            row = db.execute('SELECT * FROM pagos_demo WHERE pedido=?', (order_id,)).fetchone()
        if row is None:
            return {'error': 'No hay desglose de pago para este pedido'}
        data = dict(row)
        data['producto_pagado_centimos'] = data['precio_original_centimos'] - data['descuento_centimos']
        data['total_pagado_centimos'] = data['producto_pagado_centimos'] + data['envio_centimos']
        return {**data, 'moneda': 'EUR', 'simulacion': True}

    def return_policy(self, kind):
        policies = {
            'damaged': {'politica': 'DEMO-DANO-1', 'reintegrar_envio': True,
                       'coste_devolucion_centimos': 0},
            'change_of_mind': {'politica': 'DEMO-DESIST-1', 'reintegrar_envio': False,
                              'coste_devolucion_centimos': 500},
        }
        if kind not in policies:
            return {'error': 'Tipo desconocido: usa damaged o change_of_mind'}
        return {**policies[kind], 'kind': kind, 'requiere_entregado': True,
                'base': 'precio efectivamente pagado tras descuentos',
                'alcance': 'Reglas ficticias para este ejercicio, no una política comercial real'}

    def calculate_refund(self, order_id, kind):
        data = self.get_order(order_id)
        if 'error' in data:
            return data
        policy = self.return_policy(kind)
        if 'error' in policy:
            return policy
        if data['estado'] != 'entregado':
            return {'order_id': order_id, 'elegible_demo': False,
                    'reason': 'El pedido debe estar entregado', 'registrada': False}
        payment = self.payment_breakdown(order_id)
        if 'error' in payment:
            return payment
        shipping = payment['envio_centimos'] if policy['reintegrar_envio'] else 0
        estimate_cost = policy['coste_devolucion_centimos']
        return {'order_id': order_id, 'elegible_demo': True, 'politica': policy['politica'],
                'precio_original_centimos': payment['precio_original_centimos'],
                'descuento_centimos': payment['descuento_centimos'],
                'producto_pagado_centimos': payment['producto_pagado_centimos'],
                'envio_reintegrado_centimos': shipping, 'coste_devolucion_centimos': estimate_cost,
                'importe_reembolso_centimos': max(0, payment['producto_pagado_centimos'] + shipping - estimate_cost),
                'moneda': 'EUR', 'registrada': False, 'simulacion': True}

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def products(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM productos')]

    def get_order(self, order_id):
        with self.connect() as db:
            row = db.execute('''SELECT p.*, a.nombre, a.precio_centimos
                FROM pedidos p JOIN productos a ON a.id=p.producto
                WHERE p.id=? AND p.cliente='Cliente demo' ''', (order_id,)).fetchone()
            return dict(row) if row else {'error': 'Pedido no encontrado para el cliente demo'}

    def save(self, session_id, architecture, messages, metrics):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO conversaciones VALUES (?,?,?)',
                       (session_id, architecture, json.dumps(messages, ensure_ascii=False)))
            cursor = db.execute('INSERT INTO ejecuciones(conversacion,datos) VALUES (?,?)',
                                (session_id, json.dumps(metrics, ensure_ascii=False)))
            metrics['ejecucion_id'] = cursor.lastrowid
            db.execute('UPDATE ejecuciones SET datos=? WHERE id=?',
                       (json.dumps(metrics, ensure_ascii=False), cursor.lastrowid))

    def save_review(self, execution_id, review):
        fields = ('completa', 'correcta', 'acciones_respaldadas')
        if any(review.get(c) not in ('pendiente', 'sí', 'no') for c in fields):
            raise ValueError('Valor de revisión inválido')
        with self.connect() as db:
            row = db.execute('SELECT datos FROM ejecuciones WHERE id=?', (execution_id,)).fetchone()
            if row is None:
                raise ValueError('Ejecución desconocida')
            data = json.loads(row['datos'])
            data.update({c: review[c] for c in fields})
            data['observaciones'] = review.get('observaciones', '')
            values = [review[c] for c in fields]
            data['calidad'] = ('no apta' if data.get('error') or 'no' in values else
                                'apta' if all(v == 'sí' for v in values) else 'pendiente')
            db.execute('UPDATE ejecuciones SET datos=? WHERE id=?',
                       (json.dumps(data, ensure_ascii=False), execution_id))
            return data

    def initiate_return(self, order_id, reason):
        """Register a simulated return and refund once per order. No real money is moved.

Requires an order ID and a reason. Repeated requests return the existing record."""
        if not reason.strip():
            return {'error': 'Indica el motivo de la devolución'}
        with self.connect() as db:
            # Serialize the check and write across processes.
            db.execute('BEGIN IMMEDIATE')
            data = db.execute('''SELECT p.estado, a.precio_centimos FROM pedidos p
                JOIN productos a ON a.id=p.producto
                WHERE p.id=? AND p.cliente='Cliente demo' ''', (order_id,)).fetchone()
            if data is None:
                return {'error': 'Pedido no encontrado para el cliente demo'}
            existing = db.execute('SELECT * FROM devoluciones WHERE pedido=?',
                                    (order_id,)).fetchone()
            repeated = existing is not None
            if existing is None:
                if data['estado'] != 'entregado':
                    return {'error': 'Solo se admiten pedidos entregados en esta simulación'}
                db.execute('''INSERT INTO devoluciones
                    (pedido, motivo, importe_centimos, estado, reembolso_estado)
                    VALUES (?, ?, ?, 'registrada', 'completado_simulado')''',
                    (order_id, reason.strip(), data['precio_centimos']))
                existing = db.execute('SELECT * FROM devoluciones WHERE pedido=?',
                                        (order_id,)).fetchone()
            result = dict(existing)
            result.update(devolucion_id=f"DEV-{existing['id']}",
                             reembolso_id=f"REE-{existing['id']}",
                             moneda='EUR', registrada=True, simulacion=True,
                             ya_existia=repeated)
            return result

    def load(self, session_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM conversaciones WHERE id=?', (session_id,)).fetchone()
            return dict(row) if row else None

    def sessions(self, architecture):
        legacy_names = {'single': 'unico', 'network': 'red', 'subagents': 'herramientas'}
        with self.connect() as db:
            return [r['id'] for r in db.execute(
                'SELECT id FROM conversaciones WHERE arquitectura IN (?, ?) ORDER BY rowid DESC',
                (architecture, legacy_names.get(architecture, architecture)))]

    def executions(self):
        with self.connect() as db:
            return [json.loads(r['datos']) for r in db.execute('SELECT datos FROM ejecuciones')]
