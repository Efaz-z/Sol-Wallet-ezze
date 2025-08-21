import aiohttp

DEX_BASE = "https://api.dexscreener.com/latest/dex/tokens/"

async def dexscreener_token(token_address: str) -> dict | None:
    url = DEX_BASE + token_address
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=15) as r:
            if r.status != 200:
                return None
            data = await r.json()
            pairs = data.get("pairs") or []
            if not pairs:
                return None
            # Choose top pair by liquidity
            def liquidity_usd(pair):
                try:
                    return float((pair.get("liquidity") or {}).get("usd") or 0)
                except Exception:
                    return 0
            pairs.sort(key=liquidity_usd, reverse=True)
            top = pairs[0]
            try:
                price = float(top.get("priceUsd") or 0)
            except Exception:
                price = 0.0
            def safe_float(x):
                try:
                    return float(x or 0)
                except Exception:
                    return 0.0
            return {
                "name": (top.get("baseToken") or {}).get("name") or "",
                "symbol": (top.get("baseToken") or {}).get("symbol") or "",
                "pair": top.get("pairAddress"),
                "priceUsd": price,
                "fdv": safe_float(top.get("fdv") or 0),
                "marketCap": safe_float(top.get("marketCap") or 0),
                "liquidityUsd": safe_float((top.get("liquidity") or {}).get("usd") or 0),
                "volume": {
                    "h1": safe_float((top.get("volume") or {}).get("h1") or 0),
                    "h6": safe_float((top.get("volume") or {}).get("h6") or 0),
                    "h24": safe_float((top.get("volume") or {}).get("h24") or 0),
                },
                "buys": {
                    "h1": int(((top.get("txns") or {}).get("h1") or {}).get("buys",0))
                },
                "sells": {
                    "h1": int(((top.get("txns") or {}).get("h1") or {}).get("sells",0))
                },
                "iconUrl": (top.get("info") or {}).get("imageUrl"),
                "chainId": top.get("chainId"),
                "baseToken": (top.get("baseToken") or {}).get("address"),
            }
