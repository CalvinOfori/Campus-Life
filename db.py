"""SQLite persistence for checkout orders."""

import os
import json
import sqlite3
from pathlib import Path


def _database_path() -> str:
    return os.getenv("DATABASE_PATH", "orders.db")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    path = Path(_database_path())
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                amount_lamports INTEGER NOT NULL,
                reference TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                signature TEXT,
                items_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(orders)")}
        if "items_json" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN items_json TEXT NOT NULL DEFAULT '[]'")


def create_order(item_name: str, amount_lamports: int, reference: str, items: list | None = None) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO orders (item_name, amount_lamports, reference, items_json) VALUES (?, ?, ?, ?)",
            (item_name, amount_lamports, reference, json.dumps(items or [])),
        )
        return int(cursor.lastrowid)


def get_order(order_id: int):
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        order = dict(row)
        order["items"] = json.loads(order.pop("items_json", "[]"))
        return order


def list_recent_orders(limit: int = 10):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        orders = []
        for row in rows:
            order = dict(row)
            order["items"] = json.loads(order.pop("items_json", "[]"))
            orders.append(order)
        return orders


def mark_order_paid(order_id: int, signature: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE orders SET status = 'paid', signature = ? WHERE id = ? AND status = 'pending'",
            (signature, order_id),
        )


def list_orders(limit: int = 30):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        orders = []
        for row in rows:
            order = dict(row)
            order["items"] = json.loads(order.pop("items_json", "[]"))
            orders.append(order)
        return orders


def list_pending_orders():
    """Return pending orders for safe matching of wallet sends without a reference."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at, id"
        ).fetchall()
        orders = []
        for row in rows:
            order = dict(row)
            order["items"] = json.loads(order.pop("items_json", "[]"))
            orders.append(order)
        return orders


def dashboard_stats() -> dict:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COALESCE(SUM(amount_lamports), 0) AS sales_lamports, COUNT(*) AS paid_count "
            "FROM orders WHERE status = 'paid'"
        ).fetchone()
        return {"sales_lamports": int(row["sales_lamports"]), "paid_count": int(row["paid_count"])}
