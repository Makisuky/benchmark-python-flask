import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import pool

app = Flask(__name__)

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "orders_db")

db_pool = None


def get_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=30,
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
        )
    return db_pool


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body is required"}), 400

    customer_id = data.get("customerId")
    items = data.get("items")

    if not customer_id or not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "customerId and non-empty items list are required"}), 400

    total_amount = Decimal("0.00")
    items_count = 0
    parsed_items = []

    try:
        for item in items:
            product_id = item["productId"]
            quantity = int(item["quantity"])
            price = Decimal(str(item["price"]))

            if quantity <= 0 or price < 0:
                return jsonify({"error": "Invalid quantity or price"}), 400

            total_amount += price * quantity
            items_count += quantity
            parsed_items.append((product_id, quantity, price))
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid item format: {str(e)}"}), 400

    order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
    conn = None
    connection_pool = get_db_pool()

    try:
        conn = connection_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (order_id, customer_id, total_amount, items_count)
                VALUES (%s, %s, %s, %s)
                RETURNING created_at;
                """,
                (order_id, customer_id, total_amount, items_count),
            )
            created_at = cur.fetchone()[0]

            order_items_values = [
                (order_id, prod_id, qty, prc) for prod_id, qty, prc in parsed_items
            ]
            cur.executemany(
                """
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (%s, %s, %s, %s);
                """,
                order_items_values,
            )
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

    processed_at = (
        created_at.isoformat()
        if hasattr(created_at, "isoformat")
        else datetime.now(timezone.utc).isoformat()
    )

    return (
        jsonify(
            {
                "orderId": order_id,
                "customerId": customer_id,
                "totalAmount": float(round(total_amount, 2)),
                "itemsCount": items_count,
                "processedAt": processed_at,
            }
        ),
        201,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
