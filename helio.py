import aiohttp, backoff, time
from settings import SETTINGS

# Helius batch parse endpoint (v0 transactions) example
HELIUS_PARSE_URL = "https://api.helius.xyz/v0/transactions?api-key="

@backoff.on_exception(backoff.expo, (aiohttp.ClientError, TimeoutError), max_time=60)
async def helius_parse(signatures: list[str]) -> list[dict]:
    if not signatures:
        return []
    url = HELIUS_PARSE_URL + SETTINGS.helius_key
    # Helius expects a list of signatures as the request body for v0/transactions?api-key=KEY
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=signatures, timeout=30) as r:
            if r.status != 200:
                return []
            return await r.json()

# Extract compact swap summary from Helius enriched tx
# Returns list of {address, ts, sig, in: {mint, qty}, out: {mint, qty}, usd_value}

def summarize_helius_tx(tx: dict, tracked_address: str) -> list[dict]:
    out = []
    sig = tx.get("signature") or tx.get("txHash") or None
    ts = tx.get("timestamp") or int(time.time())

    # Helius v0 response format is complex; try to find swap events and nativeTransfers
    # We'll look for 'events' -> 'swap' or 'swap' within logs
    events = tx.get("events") or {}
    swaps = events.get("swap") or []

    # If no explicit swap events, try to inspect "instructions" for token transfers (best-effort)
    for ev in swaps:
        # Helius swap event often includes user / owner
        user = ev.get("user") or ev.get("owner") or ""
        if not user:
            continue
        if user.lower() != tracked_address.lower():
            continue
        # Determine input and output tokens
        token_inputs = ev.get("tokenInputs") or []
        token_outputs = ev.get("tokenOutputs") or []
        def pick_token(arr):
            if not arr:
                return {"mint": None, "qty": 0.0}
            t = arr[0]
            return {"mint": t.get("mint"), "qty": float(t.get("amount") or 0)}
        _in = pick_token(token_inputs)
        _out = pick_token(token_outputs)
        out.append({"address": tracked_address, "ts": ts, "sig": sig, "in": _in, "out": _out})

    return out
