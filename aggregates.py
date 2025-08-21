import time
from typing import Optional
from db import upsert_agg, get_agg, upsert_position, get_position, add_event
from dex import dexscreener_token

async def price_for_mint(mint: str) -> float:
    # Try DexScreener by token address; return USD price or 0
    try:
        info = await dexscreener_token(mint)
        if info:
            return float(info.get("priceUsd") or 0)
    except Exception:
        pass
    return 0.0

async def apply_swap_event(ev: dict):
    # Update positions and realized PnL with an avg-cost model (lightweight)
    addr = ev["address"]
    ts = int(ev["ts"] or time.time())
    sig = ev.get("sig")

    in_mint = ev["in"].get("mint")
    in_qty = float(ev["in"].get("qty") or 0)
    out_mint = ev["out"].get("mint")
    out_qty = float(ev["out"].get("qty") or 0)

    agg = await get_agg(addr) or {}
    total_trades = int(agg.get("total_trades", 0)) + 1
    wins = int(agg.get("wins", 0))
    losses = int(agg.get("losses", 0))
    realized_usd = float(agg.get("realized_pnl_usd", 0) or 0)
    realized_sol = float(agg.get("realized_pnl_sol", 0) or 0)
    best_play_sig = agg.get("best_play_sig")
    best_play_pnl_usd = float(agg.get("best_play_pnl_usd", 0) or 0)

    # Price lookups (could be 0 if not on DexScreener)
    in_price = await price_for_mint(in_mint) if in_mint else 0.0
    out_price = await price_for_mint(out_mint) if out_mint else 0.0

    # Naive notional values
    in_notional = in_qty * in_price
    out_notional = out_qty * out_price

    # Determine realized PnL: if swapping from token A to token B and reducing a position in A,
    # then realize PnL relative to avg_cost stored in positions. This is simplified.
    pnl_usd = 0.0

    # If out_mint corresponds to a token we previously held and we're decreasing qty, compute realized PnL
    pos = await get_position(addr, out_mint) if out_mint else None
    if pos:
        prev_qty = float(pos.get("qty", 0) or 0)
        prev_avg = float(pos.get("avg_cost_usd", 0) or 0)
        # We treat this event as selling 'out_qty' of out_mint
        if out_qty > 0 and prev_qty > 0:
            sell_qty = min(prev_qty, out_qty)
            proceeds = sell_qty * out_price
            cost_basis = sell_qty * prev_avg
            pnl_usd = proceeds - cost_basis
            # Reduce position
            new_qty = max(0.0, prev_qty - sell_qty)
            # avg_cost remains same if qty>0
            await upsert_position(addr, out_mint, new_qty, prev_avg if new_qty>0 else 0.0)
    else:
        # If no prior position for out_mint and we are receiving out_mint (buy), update avg cost
        if out_qty > 0:
            # treat in_notional as cost for out_qty
            avg_cost = (in_notional / out_qty) if out_qty else 0.0
            await upsert_position(addr, out_mint, out_qty, avg_cost)

    # If we are spending in_mint (selling), update positions for in_mint
    if in_qty > 0:
        pos_in = await get_position(addr, in_mint) if in_mint else None
        if pos_in:
            prev_qty = float(pos_in.get("qty", 0) or 0)
            prev_avg = float(pos_in.get("avg_cost_usd", 0) or 0)
            sell_qty = min(prev_qty, in_qty)
            proceeds = sell_qty * in_price
            cost_basis = sell_qty * prev_avg
            pnl_from_sale = proceeds - cost_basis
            pnl_usd += pnl_from_sale
            new_qty = max(0.0, prev_qty - sell_qty)
            await upsert_position(addr, in_mint, new_qty, prev_avg if new_qty>0 else 0.0)

    # Update aggregate counters
    if pnl_usd > 0:
        wins += 1
    elif pnl_usd < 0:
        losses += 1

    realized_usd += pnl_usd

    if pnl_usd > best_play_pnl_usd:
        best_play_pnl_usd = pnl_usd
        best_play_sig = sig
        best_summary = f"Swap {in_qty:.6g} {in_mint} -> {out_qty:.6g} {out_mint} | PnL ${pnl_usd:.2f}"
    else:
        best_summary = agg.get("best_play_summary") or ""

    await add_event(addr, ts, sig or "", f"SWAP: {in_qty:.6g} {in_mint} -> {out_qty:.6g} {out_mint} | pnl ${pnl_usd:.2f}")

    await upsert_agg(
        addr,
        last_sig=sig,
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        realized_pnl_sol=realized_sol,
        realized_pnl_usd=realized_usd,
        best_play_sig=best_play_sig,
        best_play_pnl_usd=best_play_pnl_usd,
        best_play_summary=best_summary,
        updated_at=int(time.time())
    )
