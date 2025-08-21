import asyncio, re, time
from pyrogram import Client, filters
from pyrogram.types import Message
from settings import SETTINGS
from db import init_db, add_user, add_track, rm_track, list_tracks, get_agg, get_recent_events
from solana_client import SolClient
from dex import dexscreener_token
from helio import helius_parse, summarize_helius_tx
from aggregates import apply_swap_event

ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

app = Client(
    name="solana_wallet_bot",
    api_id=SETTINGS.api_id,
    api_hash=SETTINGS.api_hash,
    bot_token=SETTINGS.bot_token
)

SOL = SolClient()

# ---------------- Handlers ----------------

@app.on_message(filters.command(["start"]))
async def cmd_start(_, m: Message):
    if not m.from_user:
        return
    await add_user(m.from_user.id)
    txt = (
        "👋 Welcome! This bot is laser-focused on **Solana**.\n\n"
        "**What I can do**\n"
        "• Send a **token contract address** to get price, liquidity, volume, logo.\n"
        "• /anywallet <address> — live breakdown (SOL+USD), PnL, win rate, best play.\n"
        "• /addwalletrack <address> <name> — start tracking and receive alerts.\n"
        "• /walletlist — see your tracked wallets.\n"
        "• /rmwallet <address> — stop tracking.\n"
        "• /bestplay — top 3 plays across your tracked wallets.\n"
        "• /toptraders <token> — top 5 by PnL for a coin (when available).\n"
        "• /trendingcoin — trending coins (lightweight view).\n\n"
        "Data is fetched live from Solana/DexScreener/Helius. Minimal storage only."
    )
    await m.reply_text(txt)

@app.on_message(filters.command(["walletlist"]))
async def cmd_walletlist(_, m: Message):
    if not m.from_user:
        return
    rows = await list_tracks(m.from_user.id)
    if not rows:
        return await m.reply_text("You aren't tracking any wallets yet. Use /addwalletrack <address> <name>.")
    lines = [f"• {addr} — {name}" for addr, name in rows]
    await m.reply_text("**Tracked wallets:**\n"+ "\n".join(lines))

@app.on_message(filters.command(["addwalletrack"]))
async def cmd_addwalletrack(_, m: Message):
    if not m.from_user:
        return
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /addwalletrack <WalletAddress> <Name>")
    address = parts[1].strip()
    name = " ".join(parts[2:]) if len(parts) > 2 else ""
    if not ADDRESS_RE.match(address):
        return await m.reply_text("Invalid Solana address.")
    await add_track(m.from_user.id, address, name or None)
    await m.reply_text(f"✅ Tracking started for {address} {f'({name})' if name else ''}.")

@app.on_message(filters.command(["rmwallet"]))
async def cmd_rmwallet(_, m: Message):
    if not m.from_user:
        return
    parts = m.text.split()
    if len(parts) != 2:
        return await m.reply_text("Usage: /rmwallet <WalletAddress>")
    address = parts[1].strip()
    deleted = await rm_track(m.from_user.id, address)
    if deleted:
        return await m.reply_text("🗑️ Removed from tracking.")
    await m.reply_text("Nothing to remove.")

@app.on_message(filters.command(["anywallet"]))
async def cmd_anywallet(_, m: Message):
    if not m.from_user:
        return
    parts = m.text.split()
    if len(parts) != 2:
        return await m.reply_text("Usage: /anywallet <WalletAddress>")
    address = parts[1].strip()
    if not ADDRESS_RE.match(address):
        return await m.reply_text("Invalid Solana address.")

    bal_sol = await SOL.get_balance_sol(address)
    agg = await get_agg(address) or {}

    total = int((agg or {}).get("total_trades",0) or 0)
    wins = int((agg or {}).get("wins",0) or 0)
    losses = int((agg or {}).get("losses",0) or 0)
    winrate = (wins/total*100) if total else 0

    realized_sol = float((agg or {}).get("realized_pnl_sol",0) or 0)
    realized_usd = float((agg or {}).get("realized_pnl_usd",0) or 0)

    best_sig = (agg or {}).get("best_play_sig") or "-"
    best_usd = float((agg or {}).get("best_play_pnl_usd",0) or 0)
    best_summary = (agg or {}).get("best_play_summary") or "—"

    events = await get_recent_events(address, limit=5)
    ev_txt = "\n".join([f"• {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(r[0]))} — {r[2]}\n`{r[1]}`" for r in events]) if events else "—"

    txt = (
        f"📊 **Wallet**: `{address}`\n\n"
        f"**Holdings (on-chain)**: {bal_sol:.4f} SOL\n"
        f"**PnL (realized)**: {realized_sol:.4f} SOL / ${realized_usd:.2f}\n"
        f"**Win rate**: {winrate:.2f}% ({wins}W/{losses}L, {total} trades)\n\n"
        f"**Best play**: {best_summary}\n"
        f"Signature: `{best_sig}`\n\n"
        f"**Recent events (compact)**:\n{ev_txt}"
    )
    await m.reply_text(txt)

@app.on_message(filters.command(["bestplay"]))
async def cmd_bestplay(_, m: Message):
    if not m.from_user:
        return
    rows = await list_tracks(m.from_user.id)
    if not rows:
        return await m.reply_text("No tracked wallets.")
    best = []
    for addr, _ in rows:
        agg = await get_agg(addr) or {}
        pnl = float(agg.get("best_play_pnl_usd",0) or 0)
        summary = agg.get("best_play_summary") or ""
        sig = agg.get("best_play_sig") or ""
        best.append((pnl, addr, summary, sig))
    best.sort(key=lambda x: x[0], reverse=True)
    best = best[:3]
    if not best:
        return await m.reply_text("No best plays yet.")
    lines = [f"#{i+1} ${pnl:.2f} — {addr}\n{summary}\n`{sig}`" for i,(pnl,addr,summary,sig) in enumerate(best)]
    await m.reply_text("**Top 3 Best Plays**\n"+ "\n\n".join(lines))

@app.on_message(filters.command(["toptraders"]))
async def cmd_toptraders(_, m: Message):
    parts = m.text.split()
    if len(parts) != 2:
        return await m.reply_text("Usage: /toptraders <TokenAddress>")
    token = parts[1].strip()
    await m.reply_text("Coming soon: top traders per coin via HelloMoon/Helius analytics.")

@app.on_message(filters.command(["trendingcoin"]))
async def cmd_trending(_, m: Message):
    await m.reply_text(
        "Send any **token address** to get live price, market cap, 1h/6h/24h volume.\n"
        "Advanced trending (1h/6h/24h lists) will be added via HelloMoon/Helius analytics."
    )

@app.on_message(filters.text & ~filters.command([]))
async def on_text(_, m: Message):
    text = m.text.strip()
    if not ADDRESS_RE.match(text):
        return
    addr = text
    info = await dexscreener_token(addr)
    if not info:
        return await m.reply_text("Token not found on DexScreener.")
    buys = info.get("buys", {}).get("h1", 0)
    sells = info.get("sells", {}).get("h1", 0)
    txt = (
        f"🪙 **{info.get('name')} ({info.get('symbol')})**\n"
        f"Contract: `{addr}`\n"
        f"Price: ${info.get('priceUsd'):.8f}\n"
        f"Market Cap (FDV): ${info.get('fdv'):.0f}\n"
        f"Liquidity: ${info.get('liquidityUsd'):.0f}\n"
        f"Volume: 1h ${info.get('volume',{}).get('h1',0):.0f} | 6h ${info.get('volume',{}).get('h6',0):.0f} | 24h ${info.get('volume',{}).get('h24',0):.0f}\n"
        f"1h Buys vs Sells: {buys} / {sells}"
    )
    await m.reply_text(txt)

# ---------------- Background polling / tracking ----------------

async def poll_wallet(address: str):
    # Poll latest signatures and parse with Helius, update aggregates
    from db import get_agg, upsert_agg
    before = None
    while True:
        try:
            agg = await get_agg(address) or {}
            last_known = agg.get("last_sig")
            sigs = await SOL.get_signatures(address, limit=25)
            if not sigs:
                await asyncio.sleep(15)
                continue
            sig_list = [s.get("signature") or s.get("signature") for s in sigs]
            # New signatures are at front
            if last_known and last_known in sig_list:
                idx = sig_list.index(last_known)
                new_sigs = sig_list[:idx]
            else:
                new_sigs = sig_list

            if new_sigs:
                # Limit batch size to 20
                batch = new_sigs[:20]
                parsed = await helius_parse(batch)
                for tx in parsed:
                    for ev in summarize_helius_tx(tx, address):
                        await apply_swap_event(ev)
                # Update last_sig to newest
                await upsert_agg(address, last_sig=new_sigs[0], total_trades=agg.get("total_trades",0), wins=agg.get("wins",0), losses=agg.get("losses",0), realized_pnl_sol=agg.get("realized_pnl_sol",0), realized_pnl_usd=agg.get("realized_pnl_usd",0), best_play_sig=agg.get("best_play_sig"), best_play_pnl_usd=agg.get("best_play_pnl_usd",0), best_play_summary=agg.get("best_play_summary"), updated_at=int(time.time()))

            await asyncio.sleep(15)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(20)

async def tracking_manager():
    # Launch one poller per unique tracked wallet (lightweight)
    import aiosqlite
    tasks = {}
    while True:
        try:
            async with aiosqlite.connect(SETTINGS.sqlite_path) as db:
                cur = await db.execute("SELECT DISTINCT address FROM tracked_wallets")
                rows = await cur.fetchall()
                addrs = [r[0] for r in rows]
            # Start tasks for new addresses
            for addr in addrs:
                if addr not in tasks or tasks[addr].done():
                    tasks[addr] = asyncio.create_task(poll_wallet(addr))
            # Cancel tasks for untracked
            for addr in list(tasks.keys()):
                if addr not in addrs:
                    tasks[addr].cancel()
                    tasks.pop(addr, None)
            await asyncio.sleep(30)
        except Exception:
            await asyncio.sleep(30)

async def main():
    await init_db()
    await app.start()
    print("Bot started")
    try:
        await tracking_manager()
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
