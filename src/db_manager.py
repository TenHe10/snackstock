from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from config import DB_DIR, DB_PATH, SCHEMA_PATH

DB_SELECTION_FILE = DB_DIR / ".selected_db_path"


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


def load_selected_db_path(default_path: Path = DB_PATH) -> Path:
    if DB_SELECTION_FILE.exists():
        raw = DB_SELECTION_FILE.read_text(encoding="utf-8").strip()
        if raw:
            return Path(raw)
    return default_path


def save_selected_db_path(path: Path) -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DB_SELECTION_FILE.write_text(str(path), encoding="utf-8")


class InventoryDB:
    def __init__(self, db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH):
        self.db_path = Path(db_path)
        self.schema_path = schema_path
        self.archive_dir = self.db_path.parent / "archives"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        DB_DIR.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self._ensure_sales_schema()
        self._ensure_stock_totals_backfilled()
        self._archive_closed_month_logs()

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

    def _ensure_sales_schema(self) -> None:
        with self._transaction() as conn:
            columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(stock_logs)").fetchall()
            }
            if "sale_order_id" not in columns:
                conn.execute("ALTER TABLE stock_logs ADD COLUMN sale_order_id INTEGER")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_due REAL NOT NULL,
                    total_received REAL NOT NULL,
                    discount REAL NOT NULL DEFAULT 0,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    barcode TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_retail_price REAL NOT NULL,
                    unit_purchase_price REAL NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES sales_orders (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sales_orders_timestamp ON sales_orders(timestamp)"
            )

    def _ensure_stock_totals_backfilled(self) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_totals (
                    barcode TEXT PRIMARY KEY,
                    current_qty INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (barcode) REFERENCES products (barcode)
                )
                """
            )

            totals_count = int(conn.execute("SELECT COUNT(1) AS c FROM stock_totals").fetchone()["c"])
            logs_count = int(conn.execute("SELECT COUNT(1) AS c FROM stock_logs").fetchone()["c"])
            if totals_count == 0 and logs_count > 0:
                conn.execute(
                    """
                    INSERT INTO stock_totals(barcode, current_qty)
                    SELECT barcode, COALESCE(SUM(change_qty), 0)
                    FROM stock_logs
                    GROUP BY barcode
                    """
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO stock_totals(barcode, current_qty)
                    SELECT barcode, 0 FROM products
                    """
                )

            # Ensure all products have a row in stock_totals.
            conn.execute(
                """
                INSERT OR IGNORE INTO stock_totals(barcode, current_qty)
                SELECT barcode, 0 FROM products
                """
            )

    def _archive_db_path(self, month_key: str) -> Path:
        # month_key format: YYYY-MM
        return self.archive_dir / f"stock_logs_{month_key.replace('-', '_')}.db"

    def _ensure_archive_schema(self, archive_conn: sqlite3.Connection) -> None:
        archive_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS archived_stock_logs (
                source_id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                barcode TEXT NOT NULL,
                name TEXT NOT NULL,
                change_qty INTEGER NOT NULL,
                purchase_price REAL NOT NULL,
                retail_price REAL NOT NULL,
                sale_order_id INTEGER
            )
            """
        )
        archive_columns = {
            str(row["name"])
            for row in archive_conn.execute("PRAGMA table_info(archived_stock_logs)").fetchall()
        }
        if "sale_order_id" not in archive_columns:
            archive_conn.execute(
                "ALTER TABLE archived_stock_logs ADD COLUMN sale_order_id INTEGER"
            )

    def _archive_closed_month_logs(self) -> None:
        current_month = date.today().strftime("%Y-%m")
        with self._transaction() as conn:
            months = conn.execute(
                """
                SELECT DISTINCT SUBSTR(timestamp, 1, 7) AS month_key
                FROM stock_logs
                WHERE SUBSTR(timestamp, 1, 7) < ?
                ORDER BY month_key ASC
                """,
                (current_month,),
            ).fetchall()

            for row in months:
                month_key = row["month_key"]
                monthly_logs = conn.execute(
                    """
                    SELECT
                        l.id AS source_id,
                        l.timestamp,
                        l.type,
                        l.barcode,
                        p.name,
                        l.change_qty,
                        p.purchase_price,
                        p.retail_price,
                        l.sale_order_id
                    FROM stock_logs l
                    JOIN products p ON p.barcode = l.barcode
                    WHERE SUBSTR(l.timestamp, 1, 7) = ?
                    ORDER BY l.id ASC
                    """,
                    (month_key,),
                ).fetchall()
                if not monthly_logs:
                    continue

                archive_path = self._archive_db_path(month_key)
                archive_conn = sqlite3.connect(archive_path)
                try:
                    self._ensure_archive_schema(archive_conn)
                    archive_conn.executemany(
                        """
                        INSERT OR IGNORE INTO archived_stock_logs
                        (source_id, timestamp, type, barcode, name, change_qty, purchase_price, retail_price, sale_order_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                int(log["source_id"]),
                                str(log["timestamp"]),
                                str(log["type"]),
                                str(log["barcode"]),
                                str(log["name"]),
                                int(log["change_qty"]),
                                float(log["purchase_price"]),
                                float(log["retail_price"]),
                                int(log["sale_order_id"]) if log["sale_order_id"] is not None else None,
                            )
                            for log in monthly_logs
                        ],
                    )
                    archive_conn.commit()
                finally:
                    archive_conn.close()

                conn.execute(
                    "DELETE FROM stock_logs WHERE SUBSTR(timestamp, 1, 7) = ?",
                    (month_key,),
                )

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
            conn.execute(
                """
                INSERT OR IGNORE INTO stock_totals(barcode, current_qty)
                VALUES (?, 0)
                """,
                (product.barcode,),
            )

    def list_product_barcodes(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT barcode FROM products ORDER BY barcode ASC").fetchall()
        return [str(row["barcode"]) for row in rows]

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
                    COALESCE(t.current_qty, 0) AS current_stock
                FROM products p
                LEFT JOIN stock_totals t ON t.barcode = p.barcode
                ORDER BY p.name
                """
            ).fetchall()

    def get_current_stock(self, barcode: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(current_qty, 0) AS qty FROM stock_totals WHERE barcode = ?",
                (barcode,),
            ).fetchone()
        return int(row["qty"]) if row else 0

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
            conn.execute(
                """
                INSERT INTO stock_totals(barcode, current_qty)
                VALUES (?, ?)
                ON CONFLICT(barcode) DO UPDATE SET current_qty = current_qty + excluded.current_qty
                """,
                (barcode, quantity),
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

    def stock_out(
        self,
        cart_items: Iterable[CartItem],
        stock_type: str = "销售",
        received_amount: float | None = None,
    ) -> dict[str, float]:
        items = [item for item in cart_items if item.quantity > 0]
        if not items:
            raise ValueError("cart is empty")

        total_due = 0.0
        cost = 0.0

        with self._transaction() as conn:
            order_lines: list[tuple[str, int, float, float]] = []
            for item in items:
                product = conn.execute(
                    "SELECT * FROM products WHERE barcode = ?",
                    (item.barcode,),
                ).fetchone()
                if not product:
                    raise ValueError(f"product not found: {item.barcode}")

                stock_row = conn.execute(
                    "SELECT COALESCE(current_qty, 0) AS qty FROM stock_totals WHERE barcode = ?",
                    (item.barcode,),
                ).fetchone()
                stock = int(stock_row["qty"]) if stock_row else 0
                if stock < item.quantity:
                    raise ValueError(f"库存不足: {product['name']} (当前 {stock})")

                unit_retail = float(product["retail_price"])
                unit_purchase = float(product["purchase_price"])
                total_due += unit_retail * item.quantity
                cost += unit_purchase * item.quantity
                order_lines.append((item.barcode, int(item.quantity), unit_retail, unit_purchase))

            final_received = round(total_due if received_amount is None else float(received_amount), 2)
            total_due = round(total_due, 2)
            if final_received < 0:
                raise ValueError("实收金额不能小于 0")
            if final_received - total_due > 1e-6:
                raise ValueError("实收金额不能大于应收金额")
            discount = round(total_due - final_received, 2)

            order_cursor = conn.execute(
                """
                INSERT INTO sales_orders (total_due, total_received, discount)
                VALUES (?, ?, ?)
                """,
                (total_due, final_received, discount),
            )
            sale_order_id = int(order_cursor.lastrowid)

            conn.executemany(
                """
                INSERT INTO sales_order_items
                (order_id, barcode, quantity, unit_retail_price, unit_purchase_price)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (sale_order_id, barcode, quantity, unit_retail, unit_purchase)
                    for barcode, quantity, unit_retail, unit_purchase in order_lines
                ],
            )

            for barcode, quantity, _unit_retail, _unit_purchase in order_lines:
                conn.execute(
                    """
                    INSERT INTO stock_logs (barcode, change_qty, type, sale_order_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (barcode, -quantity, stock_type, sale_order_id),
                )
                conn.execute(
                    """
                    INSERT INTO stock_totals(barcode, current_qty)
                    VALUES (?, ?)
                    ON CONFLICT(barcode) DO UPDATE SET current_qty = current_qty + excluded.current_qty
                    """,
                    (barcode, -quantity),
                )
                self._consume_expiry_batches(
                    conn=conn,
                    barcode=barcode,
                    quantity=quantity,
                )

        return {
            "total_due": total_due,
            "total_received": final_received,
            "discount": discount,
            "revenue": final_received,
            "cost": round(cost, 2),
            "profit": round(final_received - cost, 2),
        }

    def get_low_stock_products(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    p.barcode,
                    p.name,
                    p.min_stock,
                    COALESCE(t.current_qty, 0) AS current_stock
                FROM products p
                LEFT JOIN stock_totals t ON t.barcode = p.barcode
                WHERE COALESCE(t.current_qty, 0) < p.min_stock
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

    def _load_main_day_logs(self, day: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    l.id AS source_id,
                    l.timestamp,
                    l.type,
                    l.barcode,
                    p.name,
                    l.change_qty,
                    p.purchase_price,
                    p.retail_price,
                    l.sale_order_id
                FROM stock_logs l
                JOIN products p ON p.barcode = l.barcode
                WHERE DATE(l.timestamp) = ?
                ORDER BY l.timestamp ASC, l.id ASC
                """,
                (day,),
            ).fetchall()

        return [
            {
                "source_id": int(row["source_id"]),
                "timestamp": str(row["timestamp"]),
                "type": str(row["type"]),
                "barcode": str(row["barcode"]),
                "name": str(row["name"]),
                "change_qty": int(row["change_qty"]),
                "purchase_price": float(row["purchase_price"]),
                "retail_price": float(row["retail_price"]),
                "sale_order_id": int(row["sale_order_id"]) if row["sale_order_id"] is not None else None,
            }
            for row in rows
        ]

    def _load_archive_day_logs(self, day: str) -> list[dict[str, Any]]:
        month_key = day[:7]
        archive_path = self._archive_db_path(month_key)
        if not archive_path.exists():
            return []

        archive_conn = sqlite3.connect(archive_path)
        archive_conn.row_factory = sqlite3.Row
        try:
            self._ensure_archive_schema(archive_conn)
            rows = archive_conn.execute(
                """
                SELECT
                    source_id,
                    timestamp,
                    type,
                    barcode,
                    name,
                    change_qty,
                    purchase_price,
                    retail_price,
                    sale_order_id
                FROM archived_stock_logs
                WHERE DATE(timestamp) = ?
                ORDER BY timestamp ASC, source_id ASC
                """,
                (day,),
            ).fetchall()
        finally:
            archive_conn.close()

        return [
            {
                "source_id": int(row["source_id"]),
                "timestamp": str(row["timestamp"]),
                "type": str(row["type"]),
                "barcode": str(row["barcode"]),
                "name": str(row["name"]),
                "change_qty": int(row["change_qty"]),
                "purchase_price": float(row["purchase_price"]),
                "retail_price": float(row["retail_price"]),
                "sale_order_id": int(row["sale_order_id"]) if row["sale_order_id"] is not None else None,
            }
            for row in rows
        ]

    def _load_day_logs(self, for_date: date | None = None) -> list[dict[str, Any]]:
        day = (for_date or date.today()).isoformat()
        merged = self._load_archive_day_logs(day) + self._load_main_day_logs(day)
        merged.sort(key=lambda row: (str(row["timestamp"]), int(row["source_id"])))
        return merged

    def get_daily_summary(self, for_date: date | None = None) -> dict[str, float]:
        logs = self._load_day_logs(for_date=for_date)
        day = (for_date or date.today()).isoformat()

        purchase_cost = 0.0
        legacy_sales_revenue = 0.0
        legacy_sales_cost = 0.0

        for row in logs:
            qty = int(row["change_qty"])
            purchase_price = float(row["purchase_price"])
            retail_price = float(row["retail_price"])
            if row["type"] == "采购":
                purchase_cost += qty * purchase_price
            elif row["type"] == "销售" and row.get("sale_order_id") is None:
                # Backward compatibility for legacy sales before sales_orders existed.
                legacy_sales_revenue += -qty * retail_price
                legacy_sales_cost += -qty * purchase_price

        with self._connect() as conn:
            order_row = conn.execute(
                """
                SELECT COALESCE(SUM(total_received), 0) AS revenue
                FROM sales_orders
                WHERE DATE(timestamp) = ?
                """,
                (day,),
            ).fetchone()
            order_revenue = float(order_row["revenue"])

            order_cost_row = conn.execute(
                """
                SELECT COALESCE(SUM(i.quantity * i.unit_purchase_price), 0) AS order_cost
                FROM sales_orders o
                JOIN sales_order_items i ON i.order_id = o.id
                WHERE DATE(o.timestamp) = ?
                """,
                (day,),
            ).fetchone()
            order_sales_cost = float(order_cost_row["order_cost"])

        revenue = order_revenue + legacy_sales_revenue
        sales_cost = order_sales_cost + legacy_sales_cost
        gross_profit = revenue - sales_cost

        return {
            "revenue": round(revenue, 2),
            "purchase_cost": round(purchase_cost, 2),
            "gross_profit": round(gross_profit, 2),
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

    def get_daily_transactions(self, for_date: date | None = None) -> list[dict[str, Any]]:
        return self._load_day_logs(for_date=for_date)
