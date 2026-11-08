# Campus Corner Store — Solana Pay Demo

A Flask e-commerce demo for a campus shop. Customers browse products, add them to a cart, and pay in SOL through a Solana Pay QR code. The app is configured for **Solana devnet only** and stores orders in SQLite.

## Requirements

- Python 3.11 or newer
- A Phantom wallet configured for Solana devnet
- Devnet SOL in the Phantom wallet for the payment and transaction fee
- A devnet wallet address for the merchant

## Setup

Open a terminal in the project directory and create a virtual environment.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and replace the merchant address placeholder with the **public devnet wallet address** that should receive payments:

```dotenv
SOLANA_NETWORK=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
MERCHANT_WALLET_ADDRESS=YOUR_DEVNET_WALLET_PUBLIC_ADDRESS
SHOP_NAME=Campus Corner Store
DATABASE_PATH=orders.db
```

Keep `SOLANA_NETWORK` set to `devnet` and use a devnet RPC URL. The app rejects other networks. Never put a wallet recovery phrase or private key in `.env`; this app only needs the merchant's public address.

## Get devnet SOL and configure Phantom

1. In Phantom, enable developer settings and switch the Solana network to **Devnet**. Phantom’s menu wording can vary by version.
2. Copy the Phantom public address and use it as `MERCHANT_WALLET_ADDRESS` if that wallet should receive the store payments. You can use a different devnet wallet as the customer.
3. Fund the customer wallet with devnet SOL from the [Solana devnet faucet](https://faucet.solana.com/). Devnet SOL is for testing and has no mainnet value.
4. Confirm Phantom is still on Devnet before testing. The app and the wallet must use the same network.

## Run the app

With the virtual environment activated:

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Flask creates `orders.db` on first run. The database is local and is ignored by git.

## Test a payment

1. Add a product to the cart and choose **Checkout with Solana Pay**.
2. Keep the checkout page open. It displays the order total, QR code, and Solana Pay URL.
3. Refresh the checkout page if it was already open before updating the app; this ensures it displays the latest QR request.
4. In Phantom on your phone, scan the checkout QR and review the recipient and SOL amount before approving.
5. Keep the checkout page open. It polls devnet and should show a receipt after the transaction is confirmed and verified.
6. Check the receipt’s transaction link in Solana Explorer with the **Devnet** cluster selected.

The transfer request includes an order reference and a unique order memo. The app verifies that the transaction succeeded and that the merchant received the order amount. Some wallet sends may omit the reference; the app can match a direct transfer when the amount and order timing identify one unambiguous checkout. If multiple payments could match, the order stays pending rather than crediting the wrong payment. See the Flask terminal output for `PAYMENT_*` diagnostics.

Do not pay an order again just because its page is still waiting. Check the order history and its devnet Explorer transaction first. Repeated transfers of the same amount can make it impossible to tell which payment was intended for an older pending order.

## Pages

- `/` — shop catalog, product search, and categories
- `/products/<product_id>` — product details
- `/cart` — cart and checkout entry point
- `/orders/<id>` — QR checkout, live status, and receipt
- `/orders` — order history
- `/dashboard` — total verified devnet sales and paid order count
- `/api/orders/<id>/status` — JSON status endpoint used by checkout polling

## Project files

- `app.py` — Flask routes and server-rendered pages
- `solana_pay.py` — Solana Pay URL creation, SOL/lamport conversion, and payment verification
- `db.py` — SQLite order persistence
- `products.py` — product catalog and asset mapping
- `templates/` — Jinja HTML templates
- `static/` — CSS, browser polling JavaScript, and product images
- `assets/` — source product images
- `.env.example` — devnet configuration template

## Dependencies

Pinned versions are listed in `requirements.txt`: Flask, `solana`, `solders`, `qrcode` with Pillow, and `python-dotenv`.
