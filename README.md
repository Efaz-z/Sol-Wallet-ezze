# Sol_Wallet_Bot — Lightweight Solana Wallet Telegram Bot

This repository contains a compact Telegram bot that works only with Solana wallets. It stores only small aggregates and tracked-wallet lists and fetches live data from Solana RPC, Helius, and DexScreener.

## Quickstart (Ubuntu)

1. Install system packages
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
```

2. Clone & install
```bash
git clone <this-repo> sol_wallet_bot && cd sol_wallet_bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env, fill API_ID, API_HASH, BOT_TOKEN, HELIUS_API_KEY
```

3. Run locally
```bash
python3 main.py
```

4. Deploy as systemd service (example)
```bash
sudo mkdir -p /opt/sol_wallet_bot
sudo rsync -av --exclude .venv ./ /opt/sol_wallet_bot/
cd /opt/sol_wallet_bot
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
sudo cp systemd/solana-wallet-bot.service /etc/systemd/system/solana-wallet-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now solana-wallet-bot
sudo journalctl -u solana-wallet-bot -f
```

## Design notes
- Stores only `tracked_wallets`, `wallet_aggregates`, `wallet_positions`, and `recent_events` (pruned).
- No raw tx or price candles are persisted.
- Aggregates updated in compact form on each parsed transaction.
- Scales well for modest user counts with SQLite; move to Postgres for >100k users.

## Extending
- Use WebSockets for push subscriptions to Helius/QuickNode for lower latency.
- Wire HelloMoon or other analytics for trending/toptraders endpoints.
- Add rate-limiting and batching to reduce API calls.
