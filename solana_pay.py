"""Solana Pay URL construction and exact SOL/lamport conversion."""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.async_api import AsyncClient

LAMPORTS_PER_SOL = 1_000_000_000
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def lamports_to_sol(amount_lamports: int) -> Decimal:
    """Represent a lamport total in SOL exactly, without binary floats."""
    return Decimal(int(amount_lamports)).scaleb(-9)


def sol_to_lamports(value: str | int | Decimal) -> int:
    """Convert a human-entered SOL amount without using binary floats."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Enter a valid SOL amount.") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    lamports = amount * LAMPORTS_PER_SOL
    if lamports != lamports.to_integral_value():
        raise ValueError("SOL amount can have at most 9 decimal places.")
    return int(lamports)


def create_reference() -> str:
    """Create a unique reference public key; the secret key is discarded."""
    return str(Keypair().pubkey())


def order_memo(order_id: int, reference: str) -> str:
    """Create a unique public memo identifier without exposing private data."""
    return f"CampusCornerOrder-{int(order_id)}-{reference}"


def build_transfer_url(
    merchant_address: str,
    amount_sol: str | Decimal,
    reference: str,
    shop_name: str,
    item_name: str,
    memo: str | None = None,
) -> str:
    """Build a Solana Pay native SOL transfer request URI."""
    try:
        merchant = Pubkey.from_string(merchant_address)
        ref = Pubkey.from_string(reference)
    except ValueError as exc:
        raise ValueError("Merchant and reference must be valid Solana addresses.") from exc
    amount = Decimal(str(amount_sol))
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    params = [
            ("amount", format(amount, "f")),
            ("reference", str(ref)),
            ("label", shop_name),
            ("message", item_name),
        ]
    if memo:
        params.append(("memo", memo))
    query = urlencode(params)
    return f"solana:{merchant}?{query}"


def _instruction_memo(message: dict) -> str | None:
    """Read a memo from parsed or base58 encoded jsonParsed instruction data."""
    for instruction in message.get("instructions") or []:
        program = str(instruction.get("program", "")).lower()
        program_id = instruction.get("programId")
        if program not in {"spl-memo", "memo"} and program_id not in {
            "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
            "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
        }:
            continue
        parsed = instruction.get("parsed")
        if isinstance(parsed, str):
            return parsed
        if isinstance(parsed, dict):
            for key in ("memo", "info"):
                value = parsed.get(key)
                if isinstance(value, str):
                    return value
        encoded = instruction.get("data")
        if encoded:
            try:
                number = 0
                for char in encoded:
                    number = number * 58 + BASE58_ALPHABET.index(char)
                raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
                raw = (b"\x00" * (len(encoded) - len(encoded.lstrip("1")))) + raw
                return raw.decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                continue
    return None


def _transaction_received_payment(
    transaction_json: str,
    reference: str | None,
    merchant: str,
    expected_lamports: int,
    expected_memo: str | None = None,
) -> tuple[bool, str, dict]:
    """Check transaction success and the merchant's integer lamport balance delta."""
    data = json.loads(transaction_json)
    if "result" in data:
        data = data["result"] or {}
    meta = data.get("meta") or {}
    if meta.get("err") is not None:
        return False, "transaction_failed", {"transaction_error": meta.get("err")}
    tx = data.get("transaction") or {}
    message = tx.get("message") or {}
    actual_memo = _instruction_memo(message)
    memo_matches = bool(expected_memo and actual_memo == expected_memo)
    account_keys = message.get("accountKeys") or []
    keys = [entry.get("pubkey") if isinstance(entry, dict) else entry for entry in account_keys]
    if reference and reference not in keys:
        return False, "reference_missing_from_transaction", {"account_key_count": len(keys)}
    if merchant not in keys:
        return False, "merchant_missing_from_transaction", {
            "account_key_count": len(keys), "reference_present": reference in keys if reference else False,
        }
    # A reference-less wallet send is accepted only when the parsed transaction
    # contains an explicit native SOL transfer to this merchant.
    if reference is None:
        instructions = message.get("instructions") or []
        direct_transfer_lamports = 0
        for instruction in instructions:
            parsed = instruction.get("parsed") or {}
            info = parsed.get("info") or {}
            if (instruction.get("program") == "system" and parsed.get("type") == "transfer"
                    and info.get("destination") == merchant):
                direct_transfer_lamports += int(info.get("lamports", 0))
        if direct_transfer_lamports != int(expected_lamports):
            return False, "no_direct_merchant_transfer", {
                "direct_transfer_lamports": direct_transfer_lamports,
                "expected_lamports": int(expected_lamports),
            }
    index = keys.index(merchant)
    before = meta.get("preBalances") or []
    after = meta.get("postBalances") or []
    if index >= len(before) or index >= len(after):
        return False, "merchant_balance_index_missing", {
            "merchant_index": index, "pre_balance_count": len(before), "post_balance_count": len(after)
        }
    pre_lamports = int(before[index])
    post_lamports = int(after[index])
    received_lamports = post_lamports - pre_lamports
    details = {
        "merchant_pre_lamports": pre_lamports,
        "merchant_post_lamports": post_lamports,
        "merchant_received_lamports": received_lamports,
        "expected_lamports": int(expected_lamports),
    }
    if received_lamports < int(expected_lamports):
        return False, "merchant_received_less_than_order_total", details
    details["memo_matches"] = memo_matches
    return True, "verified", details


async def _find_verified_payment(
    order: dict, rpc_url: str, merchant: str, pending_orders: list[dict] | None = None
) -> dict:
    reference = Pubkey.from_string(order["reference"])
    expected_lamports = int(order["amount_lamports"])
    expected_memo = order.get("payment_memo")
    diagnostics = {"signatures_found": [], "checks": [], "failure_reason": "no_signatures_found"}
    async with AsyncClient(rpc_url, timeout=5, commitment="confirmed") as client:
        signatures = await client.get_signatures_for_address(reference, limit=10, commitment="confirmed")
        diagnostics["signatures_found"] = [str(row.signature) for row in signatures.value]
        if signatures.value:
            diagnostics["failure_reason"] = "no_signature_passed_transaction_verification"
        for row in signatures.value:
            if row.err is not None:
                diagnostics["failure_reason"] = "signature_record_has_error"
                diagnostics["checks"].append({
                    "signature": str(row.signature), "accepted": False,
                    "reason": "signature_record_has_error", "transaction_error": str(row.err),
                })
                continue
            signature = row.signature
            try:
                response = await client.get_transaction(
                    signature,
                    encoding="jsonParsed",
                    commitment="confirmed",
                    max_supported_transaction_version=0,
                )
            except Exception as exc:
                diagnostics["failure_reason"] = "transaction_fetch_exception"
                diagnostics["checks"].append({
                    "signature": str(signature), "accepted": False,
                    "reason": "transaction_fetch_exception",
                    "exception": f"{type(exc).__name__}: {exc}",
                })
                continue
            if response.value is None:
                diagnostics["failure_reason"] = "transaction_details_not_available_at_confirmed_commitment"
                diagnostics["checks"].append({
                    "signature": str(signature), "accepted": False,
                    "reason": "transaction_details_not_available_at_confirmed_commitment",
                })
                continue
            try:
                accepted, reason, details = _transaction_received_payment(
                    response.value.to_json(), str(reference), merchant, expected_lamports, expected_memo
                )
            except Exception as exc:
                diagnostics["checks"].append({
                    "signature": str(signature), "accepted": False,
                    "reason": "transaction_response_parse_exception",
                    "exception": f"{type(exc).__name__}: {exc}",
                })
                continue
            check = {"signature": str(signature), "accepted": accepted, "reason": reason, **details}
            diagnostics["checks"].append(check)
            if accepted:
                diagnostics["failure_reason"] = None
                return {"signature": str(signature), **diagnostics}
            diagnostics["failure_reason"] = reason
    # Some wallets or manual-send flows fail to include the Solana Pay reference.
    # Fall back to explicit exact-amount SOL transfers and assign each to the newest
    # matching checkout that existed when the payment landed. Paid orders remain in
    # the history passed by the caller so a claimed transaction cannot be reused.
    # Multiple sends
    # for the same order stay ambiguous instead of being silently selected.
    diagnostics["reference_fallback"] = "not_needed" if diagnostics["signatures_found"] else "no_candidate"
    async with AsyncClient(rpc_url, timeout=5, commitment="confirmed") as client:
        merchant_signatures = await client.get_signatures_for_address(
            Pubkey.from_string(merchant), limit=25, commitment="confirmed"
        )
        try:
            order_time = datetime.fromisoformat(str(order["created_at"])).replace(tzinfo=timezone.utc).timestamp()
        except (ValueError, TypeError):
            order_time = 0
        eligible = []
        for row in merchant_signatures.value:
            block_time = row.block_time
            if row.err is not None or block_time is None or block_time < order_time:
                continue
            try:
                response = await client.get_transaction(
                    row.signature, encoding="jsonParsed", commitment="confirmed",
                    max_supported_transaction_version=0,
                )
                if response.value is None:
                    continue
                accepted, reason, details = _transaction_received_payment(
                    response.value.to_json(), None, merchant, expected_lamports, expected_memo
                )
                if accepted:
                    candidate = {"signature": str(row.signature), "block_time": block_time, **details}
                    if details.get("memo_matches"):
                        diagnostics.setdefault("memo_candidates", []).append(candidate)
                    eligible.append(candidate)
                else:
                    diagnostics["checks"].append({"signature": str(row.signature), "accepted": False,
                                                  "reason": reason, **details})
            except Exception as exc:
                diagnostics["checks"].append({"signature": str(row.signature), "accepted": False,
                                              "reason": "fallback_transaction_error",
                                              "exception": f"{type(exc).__name__}: {exc}"})
        diagnostics["merchant_signatures_scanned"] = len(merchant_signatures.value)
        memo_candidates = diagnostics.get("memo_candidates", [])
        if len(memo_candidates) == 1:
            diagnostics["failure_reason"] = None
            diagnostics["reference_fallback"] = "unique_order_memo_and_transfer_verified"
            return {"signature": memo_candidates[0]["signature"], **diagnostics}
        if len(memo_candidates) > 1:
            diagnostics["failure_reason"] = "multiple_transactions_with_order_memo"
            diagnostics["reference_fallback"] = "ambiguous_duplicate_order_memo"
            return {"signature": None, **diagnostics}
        diagnostics["reference_fallback_candidates"] = eligible
        assigned_candidates = []
        for candidate in eligible:
            orders_at_payment_time = []
            for pending_order in pending_orders or [order]:
                if int(pending_order["amount_lamports"]) != expected_lamports:
                    continue
                try:
                    created = datetime.fromisoformat(str(pending_order["created_at"])).replace(
                        tzinfo=timezone.utc
                    ).timestamp()
                except (ValueError, TypeError):
                    continue
                if created <= candidate["block_time"]:
                    orders_at_payment_time.append((created, int(pending_order["id"])))
            if orders_at_payment_time:
                # The latest matching pending checkout is the best temporal match.
                # Include id as a deterministic tie-breaker for same-second orders.
                candidate["matched_order_id"] = max(orders_at_payment_time)[1]
                assigned_candidates.append(candidate)
        order_candidates = [candidate for candidate in assigned_candidates
                            if candidate["matched_order_id"] == int(order["id"])]
        diagnostics["reference_fallback_candidates"] = assigned_candidates
        if len(order_candidates) == 1:
            diagnostics["failure_reason"] = None
            diagnostics["reference_fallback"] = "unique_exact_transfer_matched_by_order_time"
            return {"signature": order_candidates[0]["signature"], **diagnostics}
        if len(order_candidates) > 1:
            diagnostics["failure_reason"] = "ambiguous_reference_less_payments"
            diagnostics["reference_fallback"] = "multiple_transfers_match_same_order"
            return {"signature": None, **diagnostics}
        if eligible and not assigned_candidates:
            diagnostics["failure_reason"] = "reference_missing_order_match_ambiguous"
            diagnostics["reference_fallback"] = "no_pending_order_matched_payment_time"
        diagnostics["reference_fallback"] = "no_verified_transfer"
    return {"signature": None, **diagnostics}


def find_verified_payment(
    order: dict, rpc_url: str, merchant: str, pending_orders: list[dict] | None = None
) -> dict:
    """Return payment signature and diagnostics for Flask's synchronous boundary."""
    return asyncio.run(_find_verified_payment(order, rpc_url, merchant, pending_orders))
