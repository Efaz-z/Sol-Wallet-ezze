PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

-- Users
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  created_at INTEGER NOT NULL
);

-- Tracked wallets per user
CREATE TABLE IF NOT EXISTS tracked_wallets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  address TEXT NOT NULL,
  name TEXT,
  created_at INTEGER NOT NULL,
  UNIQUE(user_id, address)
);

-- Compact per-wallet aggregates (no raw history)
CREATE TABLE IF NOT EXISTS wallet_aggregates (
  address TEXT PRIMARY KEY,
  last_sig TEXT,
  total_trades INTEGER DEFAULT 0,
  wins INTEGER DEFAULT 0,
  losses INTEGER DEFAULT 0,
  realized_pnl_sol REAL DEFAULT 0,
  realized_pnl_usd REAL DEFAULT 0,
  best_play_sig TEXT,
  best_play_pnl_usd REAL DEFAULT 0,
  best_play_summary TEXT,
  updated_at INTEGER
);

-- Minimal per-token positions for avg cost math (small footprint)
CREATE TABLE IF NOT EXISTS wallet_positions (
  address TEXT NOT NULL,
  mint TEXT NOT NULL,
  qty REAL NOT NULL,
  avg_cost_usd REAL NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(address, mint)
);

-- Recent compact events (auto-pruned ≤ 90 days)
CREATE TABLE IF NOT EXISTS recent_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  address TEXT NOT NULL,
  ts INTEGER NOT NULL,
  sig TEXT NOT NULL,
  summary TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_address_ts ON recent_events(address, ts);
