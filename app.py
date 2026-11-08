"""Server-rendered desktop-first campus shop with Solana devnet checkout."""

import base64
import io
import logging
import os
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import qrcode
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from solders.pubkey import Pubkey

import db
from products import CATEGORIES, PRODUCT_BY_ID, PRODUCTS
from solana_pay import (
    build_transfer_url, create_reference, find_verified_payment, lamports_to_sol,
    order_memo, sol_to_lamports,
)

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "local-demo-only-change-me")
    network = os.getenv("SOLANA_NETWORK", "").lower()
    if network != "devnet":
        raise RuntimeError("Set SOLANA_NETWORK=devnet in .env; this demo only supports devnet.")
    rpc_url = os.getenv("SOLANA_RPC_URL", "")
    if "devnet" not in rpc_url.lower():
        raise RuntimeError("Set SOLANA_RPC_URL to a devnet endpoint in .env.")
    merchant_address = os.getenv("MERCHANT_WALLET_ADDRESS", "").strip()
    try:
        merchant_valid = bool(merchant_address) and str(Pubkey.from_string(merchant_address)) == merchant_address
    except ValueError:
        merchant_valid = False
    if merchant_address == "REPLACE_WITH_YOUR_DEVNET_WALLET_ADDRESS":
        merchant_valid = False

    app.config.update(
        SHOP_NAME=os.getenv("SHOP_NAME", "Campus Corner Store"),
        MERCHANT_WALLET_ADDRESS=merchant_address,
        MERCHANT_WALLET_VALID=merchant_valid,
        SOLANA_NETWORK=network,
    )
    db.init_db()

    @app.context_processor
    def shared_template_data():
        cart = session.get("cart", {})
        cart_count = sum(int(quantity) for quantity in cart.values())
        _, cart_total = cart_lines()
        return {"cart_count": cart_count, "cart_total_lamports": cart_total,
                "shop_name": app.config["SHOP_NAME"], "categories": CATEGORIES}

    @app.template_filter("sol")
    def lamports_to_sol(value):
        return f"{Decimal(int(value)) / Decimal(1_000_000_000):.9f}"

    def cart_lines():
        cart = session.get("cart", {})
        lines = []
        total_lamports = 0
        for product_id, quantity in cart.items():
            product = PRODUCT_BY_ID.get(product_id)
            if not product:
                continue
            quantity = max(1, min(99, int(quantity)))
            price_lamports = sol_to_lamports(product["price"])
            line = {**product, "quantity": quantity, "price_lamports": price_lamports,
                    "subtotal_lamports": price_lamports * quantity}
            total_lamports += line["subtotal_lamports"]
            lines.append(line)
        return lines, total_lamports

    def create_checkout(items: list[dict], total_lamports: int, item_name: str):
        if not app.config["MERCHANT_WALLET_VALID"]:
            flash("Add a valid Solana wallet public address to MERCHANT_WALLET_ADDRESS in .env.", "error")
            return None
        reference = create_reference()
        return db.create_order(item_name, total_lamports, reference, items)

    @app.get("/")
    def index():
        query = request.args.get("q", "").strip().lower()
        selected_categories = request.args.getlist("category") or ["All"]
        category = selected_categories[-1]
        sort = request.args.get("sort", "featured")
        max_price_text = request.args.get("max_price", "")
        listing = [product for product in PRODUCTS if "All" in selected_categories or product["category"] in selected_categories]
        listing = [product for product in listing if query in product["name"].lower() or query in product["description"].lower()]
        try:
            candidate_price = Decimal(max_price_text) if max_price_text else None
            max_price = candidate_price if candidate_price is not None and candidate_price.is_finite() and candidate_price >= 0 else None
        except Exception:
            max_price = None
        if max_price is not None:
            listing = [product for product in listing if Decimal(product["price"]) <= max_price]
        if sort == "price-low":
            listing.sort(key=lambda product: Decimal(product["price"]))
        elif sort == "price-high":
            listing.sort(key=lambda product: Decimal(product["price"]), reverse=True)
        elif sort == "name":
            listing.sort(key=lambda product: product["name"].lower())
        return render_template(
            "index.html", products=PRODUCTS, categories=CATEGORIES, listing=listing,
            query=query, selected_category=category, selected_categories=selected_categories,
            selected_sort=sort, max_price=max_price_text,
            featured=PRODUCT_BY_ID["campus-notebook"],
            popular=[product for product in PRODUCTS if product["popular"]],
            cheap=[product for product in PRODUCTS if Decimal(product["price"]) < Decimal("0.005")],
        )

    @app.get("/products/<product_id>")
    def product_detail(product_id: str):
        product = PRODUCT_BY_ID.get(product_id)
        if not product:
            abort(404)
        related = [item for item in PRODUCTS if item["category"] == product["category"] and item["id"] != product_id][:4]
        if len(related) < 4:
            related += [item for item in PRODUCTS if item["id"] != product_id and item not in related][:4-len(related)]
        return render_template("product.html", product=product, related=related)

    @app.post("/checkout/buy-now/<product_id>")
    def buy_now(product_id: str):
        product = PRODUCT_BY_ID.get(product_id)
        if not product:
            abort(404)
        try:
            quantity = max(1, min(99, int(request.form.get("quantity", "1"))))
        except ValueError:
            quantity = 1
        unit_lamports = sol_to_lamports(product["price"])
        item = {"id": product["id"], "name": product["name"], "image": product["image"],
                "category": product["category"], "quantity": quantity,
                "price_lamports": unit_lamports, "subtotal_lamports": unit_lamports * quantity}
        order_id = create_checkout([item], item["subtotal_lamports"], f"{product['name']} ×{quantity}")
        if order_id is None:
            return redirect(url_for("product_detail", product_id=product_id))
        return redirect(url_for("order_page", order_id=order_id))

    @app.post("/cart/add/<product_id>")
    def add_to_cart(product_id: str):
        if product_id not in PRODUCT_BY_ID:
            abort(404)
        quantity = request.form.get("quantity", "1")
        try:
            quantity = max(1, min(99, int(quantity)))
        except ValueError:
            quantity = 1
        cart = session.get("cart", {})
        cart[product_id] = min(99, int(cart.get(product_id, 0)) + quantity)
        session["cart"] = cart
        lines, total = cart_lines()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": True, "cart_count": sum(int(value) for value in cart.values()),
                            "cart_total_lamports": total, "message": "Added to cart"})
        flash("Added to your cart.", "success")
        return redirect(request.form.get("next") or url_for("product_detail", product_id=product_id))

    @app.get("/cart")
    def cart_page():
        lines, total_lamports = cart_lines()
        return render_template("cart.html", lines=lines, total_lamports=total_lamports)

    @app.post("/cart/update")
    def update_cart():
        product_id = request.form.get("product_id", "")
        if product_id not in PRODUCT_BY_ID:
            abort(404)
        try:
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            quantity = 1
        cart = session.get("cart", {})
        if quantity < 1:
            cart.pop(product_id, None)
        else:
            cart[product_id] = min(quantity, 99)
        session["cart"] = cart
        return redirect(url_for("cart_page"))

    @app.post("/cart/remove/<product_id>")
    def remove_from_cart(product_id: str):
        cart = session.get("cart", {})
        cart.pop(product_id, None)
        session["cart"] = cart
        return redirect(url_for("cart_page"))

    @app.post("/checkout")
    def checkout():
        lines, total_lamports = cart_lines()
        if not lines:
            flash("Your cart is empty. Add something from the shop first.", "error")
            return redirect(url_for("index"))
        order_items = [
            {"id": line["id"], "name": line["name"], "image": line["image"],
             "category": line["category"], "quantity": line["quantity"],
             "price_lamports": line["price_lamports"], "subtotal_lamports": line["subtotal_lamports"]}
            for line in lines
        ]
        summary = " + ".join(f"{line['name']} ×{line['quantity']}" for line in lines)
        order_id = create_checkout(order_items, total_lamports, summary[:120])
        if order_id is None:
            return redirect(url_for("cart_page"))
        session["cart"] = {}
        return redirect(url_for("order_page", order_id=order_id))

    # Keep the original simple order form endpoint available for quick demos.
    @app.post("/orders")
    def create_order_route():
        item_name = request.form.get("item_name", "").strip()
        try:
            lamports = sol_to_lamports(request.form.get("amount_sol", ""))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("index"))
        if not item_name or len(item_name) > 120:
            flash("Enter an item name (up to 120 characters).", "error")
            return redirect(url_for("index"))
        order_id = create_checkout([], lamports, item_name)
        if order_id is None:
            return redirect(url_for("index"))
        return redirect(url_for("order_page", order_id=order_id))

    @app.get("/orders")
    def orders_page():
        return render_template("orders.html", orders=db.list_orders())

    @app.get("/dashboard")
    def dashboard():
        stats = db.dashboard_stats()
        return render_template("dashboard.html", stats=stats, orders=db.list_orders(10))

    @app.get("/orders/<int:order_id>")
    def order_page(order_id: int):
        order = db.get_order(order_id)
        if not order:
            abort(404)
        order["amount_sol"] = lamports_to_sol(order["amount_lamports"])
        order["payment_memo"] = order_memo(order["id"], order["reference"])
        pay_url = None
        qr_data_uri = None
        if app.config["MERCHANT_WALLET_VALID"]:
            pay_url = build_transfer_url(
                merchant_address, order["amount_sol"], order["reference"],
                app.config["SHOP_NAME"], order["item_name"], order["payment_memo"],
            )
            pay_query = parse_qs(urlsplit(pay_url).query)
            url_reference = pay_query.get("reference", [None])[0]
            url_memo = pay_query.get("memo", [None])[0]
            url_amount = pay_query.get("amount", [None])[0]
            expected_amount_sol = lamports_to_sol(order["amount_lamports"])
            try:
                url_amount_lamports = sol_to_lamports(url_amount) if url_amount is not None else None
            except ValueError:
                url_amount_lamports = None
            reference_matches = url_reference == order["reference"]
            memo_matches = url_memo == order["payment_memo"]
            amount_matches = url_amount_lamports == int(order["amount_lamports"])
            if not reference_matches or not amount_matches or not memo_matches:
                app.logger.error(
                    "PAYMENT_URL_MISMATCH order_id=%s order_reference=%s url_reference=%s "
                    "reference_matches=%s memo_matches=%s expected_lamports=%s expected_amount_sol=%s "
                    "url_amount_sol=%s url_amount_lamports=%s amount_matches=%s",
                    order["id"], order["reference"], url_reference, reference_matches, memo_matches,
                    order["amount_lamports"], expected_amount_sol, url_amount, url_amount_lamports, amount_matches,
                )
                abort(500)
            app.logger.info(
                "PAYMENT_URL_OK order_id=%s reference=%s expected_lamports=%s amount_sol=%s",
                order["id"], order["reference"], order["amount_lamports"], url_amount,
            )
            qr = qrcode.make(pay_url)
            image_buffer = io.BytesIO()
            qr.save(image_buffer, format="PNG")
            qr_data_uri = "data:image/png;base64," + base64.b64encode(image_buffer.getvalue()).decode("ascii")
        return render_template(
            "order.html", order=order, pay_url=pay_url, qr_data_uri=qr_data_uri,
            status_url=url_for("order_status", order_id=order["id"]),
        )

    @app.get("/api/orders/<int:order_id>/status")
    def order_status(order_id: int):
        order = db.get_order(order_id)
        if not order:
            return jsonify({"error": "Order not found"}), 404
        if order["status"] == "paid":
            return jsonify({"status": "paid", "signature": order["signature"]})
        if not app.config["MERCHANT_WALLET_VALID"]:
            return jsonify({"status": "pending", "message": "Merchant wallet is not configured."})
        order["payment_memo"] = order_memo(order["id"], order["reference"])
        app.logger.info(
            "PAYMENT_STATUS_START order_id=%s reference=%s expected_lamports=%s commitment=confirmed",
            order_id, order["reference"], order["amount_lamports"],
        )
        try:
            # Include paid orders too so a previously claimed transfer can never be
            # reassigned to an older pending order on a later poll.
            result = find_verified_payment(order, rpc_url, merchant_address, db.list_orders(1000))
            app.logger.info(
                "PAYMENT_SIGNATURES order_id=%s reference=%s signatures=%s",
                order_id, order["reference"], result["signatures_found"],
            )
            for check in result["checks"]:
                app.logger.info("PAYMENT_VERIFY_CHECK order_id=%s result=%s", order_id, check)
            if result.get("reference_fallback"):
                app.logger.info(
                    "PAYMENT_REFERENCE_FALLBACK order_id=%s outcome=%s candidates=%s orders=%s",
                    order_id, result["reference_fallback"],
                    result.get("reference_fallback_candidates", []),
                    result.get("orders_matching_candidate", []),
                )
            signature = result["signature"]
            if signature:
                db.mark_order_paid(order_id, signature)
                app.logger.info(
                    "PAYMENT_VERIFIED order_id=%s reference=%s signature=%s expected_lamports=%s",
                    order_id, order["reference"], signature, order["amount_lamports"],
                )
                return jsonify({"status": "paid", "signature": signature})
            app.logger.warning(
                "PAYMENT_NOT_VERIFIED order_id=%s reference=%s expected_lamports=%s reason=%s",
                order_id, order["reference"], order["amount_lamports"], result["failure_reason"],
            )
            return jsonify({"status": "pending"})
        except Exception as exc:
            app.logger.exception(
                "PAYMENT_RPC_EXCEPTION order_id=%s reference=%s expected_lamports=%s exception=%s: %s",
                order_id, order["reference"], order["amount_lamports"], type(exc).__name__, exc,
            )
            return jsonify({"status": "pending", "rpc_error": True})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
