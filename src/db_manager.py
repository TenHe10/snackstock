from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from config import DB_DIR, DB_PATH, SCHEMA_PATH


@dataclass
class Product:
    barcode: str
    name: str
    category: str
    purchase_price: float
    retail_price: float
    min_stock: int


@dataclass
class CartItem:
    barcode: str
    quantity: int


class InventoryDB:
    def __init__(self, db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH):
        self.db_path = db_path
        self.schema_path = schema_path
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _transaction(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._transaction() as conn:
            schema_sql = self.schema_path.read_text(encoding="utf-8")
            conn.executescript(schema_sql)

    def upsert_product(self, product: Product) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO products (barcode, name, category, purchase_price, retail_price, min_stock)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(barcode) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    purchase_price = excluded.purchase_price,
                    retail_price = excluded.retail_price,
                    min_stock = excluded.min_stock
                """,
                (
                    product.barcode,
                    product.name,
                    product.category,
                    product.purchase_price,
                    product.retail_price,
                    product.min_stock,
                ),
            )

    def get_product(self, barcode: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM products WHERE barcode = ?",
                (barcode,),
            ).fetchone()

    def list_products_with_stock(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    p.barcode,
                    p.name,
                    p.category,
                    p.purchase_price,
                    p.retail_price,
                    p.min_stock,
                    COALESCE(SUM(l.change_qty), 0) AS current_stock
                FROM products p
                LEFT JOIN stock_logs l ON l.barcode = p.barcode
                GROUP BY p.barcode
                ORDER BY p.name
                """
            ).fetchall()

    def get_current_stock(self, barcode: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(change_qty), 0) AS qty FROM stock_logs WHERE barcode = ?",
                (barcode,),
            ).fetchone()
        return int(row["qty"])

    def stock_in(
        self,
        barcode: str,
        quantity: int,
        stock_type: str = "采购",
        batch_no: str | None = None,
        expiry_date: str | None = None,
    ) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if not self.get_product(barcode):
            raise ValueError("product not found")

        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO stock_logs (barcode, change_qty, type)
                VALUES (?, ?, ?)
                """,
                (barcode, quantity, stock_type),
            )

            if batch_no and expiry_date:
                conn.execute(
                    """
                    INSERT INTO expiry_management (barcode, batch_no, expiry_date, current_qty)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(barcode, batch_no, expiry_date) DO UPDATE SET
                        current_qty = current_qty + excluded.current_qty
                    """,
                    (barcode, batch_no, expiry_date, quantity),
                )

    def stock_out(self, cart_items: Iterable[CartItem], stock_type: str = "销售") -> dict[str, float]:
        items = [item for item in cart_items if item.quantity > 0]
        if not items:
            raise ValueError("cart is empty")

        revenue = 0.0
        cost = 0.0

        with self._transaction() as conn:
            for item in items:
                product = conn.execute(
                    "SELECT * FROM products WHERE barcode = ?",
                    (item.barcode,),
                ).fetchone()
                if not product:
                    raise ValueError(f"product not found: {item.barcode}")

                stock = conn.execute(
                    "SELECT COALESCE(SUM(change_qty), 0) AS qty FROM stock_logs WHERE barcode = ?",
                    (item.barcode,),
                ).fetchone()["qty"]
                if stock < item.quantity:
                    raise ValueError(f"库存不足: {product['name']} (当前 {stock})")

                conn.execute(
                    """
                    INSERT INTO stock_logs (barcode, change_qty, type)
                    VALUES (?, ?, ?)
                    """,
                    (item.barcode, -item.quantity, stock_type),
                )
                self._consume_expiry_batches(
                    conn=conn,
                    barcode=item.barcode,
                    quantity=item.quantity,
                )

                revenue += float(product["retail_price"]) * item.quantity
                cost += float(product["purchase_price"]) * item.quantity

        return {
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "profit": round(revenue - cost, 2),
        }

    def get_low_stock_products(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    p.barcode,
                    p.name,
                    p.min_stock,
                    COALESCE(SUM(l.change_qty), 0) AS current_stock
                FROM products p
                LEFT JOIN stock_logs l ON l.barcode = p.barcode
                GROUP BY p.barcode
                HAVING current_stock < p.min_stock
                ORDER BY current_stock ASC
                """
            ).fetchall()

    def get_expiring_batches(self, within_days: int) -> list[sqlite3.Row]:
        target_date = date.today().toordinal() + within_days
        end = date.fromordinal(target_date).isoformat()
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    e.barcode,
                    p.name,
                    e.batch_no,
                    e.expiry_date,
                    e.current_qty
                FROM expiry_management e
                JOIN products p ON p.barcode = e.barcode
                WHERE e.current_qty > 0
                  AND e.expiry_date <= ?
                ORDER BY e.expiry_date ASC
                """,
                (end,),
            ).fetchall()

    def get_daily_summary(self, for_date: date | None = None) -> dict[str, float]:
        day = (for_date or date.today()).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE
                        WHEN l.type = '销售' THEN -l.change_qty * p.retail_price
                        ELSE 0
                    END), 0) AS revenue,
                    COALESCE(SUM(CASE
                        WHEN l.type = '采购' THEN l.change_qty * p.purchase_price
                        ELSE 0
                    END), 0) AS purchase_cost,
                    COALESCE(SUM(CASE
                        WHEN l.type = '销售' THEN -l.change_qty * (p.retail_price - p.purchase_price)
                        ELSE 0
                    END), 0) AS gross_profit
                FROM stock_logs l
                JOIN products p ON p.barcode = l.barcode
                WHERE DATE(l.timestamp) = ?
                """,
                (day,),
            ).fetchone()

        return {
            "revenue": round(float(row["revenue"]), 2),
            "purchase_cost": round(float(row["purchase_cost"]), 2),
            "gross_profit": round(float(row["gross_profit"]), 2),
        }

    def _consume_expiry_batches(self, conn: sqlite3.Connection, barcode: str, quantity: int) -> None:
        """
        Consume tracked batches in FIFO-by-expiry order.
        If part of stock has no batch info, that remainder stays untracked.
        """
        remaining = quantity
        rows = conn.execute(
            """
            SELECT barcode, batch_no, expiry_date, current_qty
            FROM expiry_management
            WHERE barcode = ? AND current_qty > 0
            ORDER BY expiry_date ASC, batch_no ASC
            """,
            (barcode,),
        ).fetchall()

        for row in rows:
            if remaining <= 0:
                break
            consume = min(remaining, int(row["current_qty"]))
            conn.execute(
                """
                UPDATE expiry_management
                SET current_qty = current_qty - ?
                WHERE barcode = ? AND batch_no = ? AND expiry_date = ?
                """,
                (consume, row["barcode"], row["batch_no"], row["expiry_date"]),
            )
            remaining -= consume

    def get_daily_transactions(self, for_date: date | None = None) -> list[sqlite3.Row]:
        day = (for_date or date.today()).isoformat()
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    l.timestamp,
                    l.type,
                    l.barcode,
                    p.name,
                    l.change_qty,
                    p.purchase_price,
                    p.retail_price
                FROM stock_logs l
                JOIN products p ON p.barcode = l.barcode
                WHERE DATE(l.timestamp) = ?
                ORDER BY l.timestamp ASC, l.id ASC
                """,
                (day,),
            ).fetchall()
