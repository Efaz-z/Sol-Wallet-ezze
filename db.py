import aiosqlite, time
from typing import Optional, List, Tuple
from settings import SETTINGS

async def init_db():
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        with open("schema.sql", "r", encoding="utf-8") as f:
            await db.executescript(f.read())
        await db.commit()

async def add_user(user_id: int):
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id, created_at) VALUES(?,?)", (user_id, int(time.time())))
        await db.commit()

async def add_track(user_id: int, address: str, name: Optional[str]):
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO tracked_wallets(user_id,address,name,created_at) VALUES(?,?,?,?)",
            (user_id, address, name, int(time.time()))
        )
        await db.commit()

async def rm_track(user_id: int, address: str) -> int:
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        cur = await db.execute("DELETE FROM tracked_wallets WHERE user_id=? AND address=?", (user_id, address))
        await db.commit()
        return cur.rowcount

async def list_tracks(user_id: int) -> List[Tuple[str, Optional[str]]]:
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        cur = await db.execute("SELECT address, COALESCE(name,'') FROM tracked_wallets WHERE user_id=? ORDER BY created_at DESC", (user_id,))
        return await cur.fetchall()

async def upsert_agg(address: str, **kwargs):
    # Minimal UPSERT helper
    fields = ["last_sig","total_trades","wins","losses","realized_pnl_sol","realized_pnl_usd","best_play_sig","best_play_pnl_usd","best_play_summary","updated_at"]
    cols = ",".join(fields)
    placeholders = ",".join(["?"]*len(fields))
    values = [kwargs.get(k) for k in fields]
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        await db.execute(
            f"INSERT INTO wallet_aggregates(address,{cols}) VALUES(?,{placeholders})\n"
            f"ON CONFLICT(address) DO UPDATE SET " + ",".join([f"{k}=excluded.{k}" for k in fields]),
            [address] + values
        )
        await db.commit()

async def get_agg(address: str):
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        cur = await db.execute("SELECT * FROM wallet_aggregates WHERE address=?", (address,))
        row = await cur.fetchone()
        if not row:
            return None
        # Convert to dict for convenience
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

async def upsert_position(address: str, mint: str, qty: float, avg_cost_usd: float):
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        await db.execute(
            "INSERT INTO wallet_positions(address,mint,qty,avg_cost_usd,updated_at) VALUES(?,?,?,?,?)\n"
            "ON CONFLICT(address,mint) DO UPDATE SET qty=excluded.qty, avg_cost_usd=excluded.avg_cost_usd, updated_at=excluded.updated_at",
            (address, mint, qty, avg_cost_usd, int(time.time()))
        )
        await db.commit()

async def get_position(address: str, mint: str):
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        cur = await db.execute("SELECT qty, avg_cost_usd FROM wallet_positions WHERE address=? AND mint=?", (address, mint))
        row = await cur.fetchone()
        if not row:
            return None
        return {"qty": row[0], "avg_cost_usd": row[1]}

async def add_event(address: str, ts: int, sig: str, summary: str):
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        await db.execute("INSERT INTO recent_events(address,ts,sig,summary) VALUES(?,?,?,?)", (address, ts, sig, summary))
        # prune 90 days
        cutoff = int(time.time()) - 90*24*3600
        await db.execute("DELETE FROM recent_events WHERE ts<?", (cutoff,))
        await db.commit()

async def get_recent_events(address: str, limit: int = 20):
    async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
        cur = await db.execute("SELECT ts, sig, summary FROM recent_events WHERE address=? ORDER BY ts DESC LIMIT ?", (address, limit))
        rows = await cur.fetchall()
        return rows
