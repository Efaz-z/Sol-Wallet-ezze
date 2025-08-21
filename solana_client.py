from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey
from typing import Optional
from settings import SETTINGS
import asyncio

class SolClient:
    def __init__(self):
        self.primary = AsyncClient(SETTINGS.primary_rpc)
        self.fallback = AsyncClient(SETTINGS.fallback_rpc)

    async def get_balance_sol(self, address: str) -> Optional[float]:
        lamports = None
        for c in (self.primary, self.fallback):
            try:
                resp = await c.get_balance(PublicKey(address))
                if resp and resp.get("result"):
                    lamports = resp["result"]["value"]
                    break
            except Exception:
                continue
        return (lamports or 0)/1_000_000_000

    async def get_signatures(self, address: str, before: Optional[str]=None, limit: int=50):
        # Returns list of signature dicts (newest first)
        last = None
        for c in (self.primary, self.fallback):
            try:
                resp = await c.get_signatures_for_address(PublicKey(address), before=before, limit=limit)
                if resp and resp.get("result") is not None:
                    last = resp["result"]
                    break
            except Exception:
                continue
        return last or []

    async def close(self):
        await self.primary.close()
        await self.fallback.close()
