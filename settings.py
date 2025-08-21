from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    api_id: int = int(os.getenv("API_ID", 0))
    api_hash: str = os.getenv("API_HASH", "")
    bot_token: str = os.getenv("BOT_TOKEN", "")

    primary_rpc: str = os.getenv("PRIMARY_RPC_URL", "https://api.mainnet-beta.solana.com")
    fallback_rpc: str = os.getenv("FALLBACK_RPC_URL", "https://rpc.ankr.com/solana")
    quicknode_rpc: str = os.getenv("QUICKNODE_RPC_URL", "")
    hellomoon_rpc: str = os.getenv("HELLOMOON_RPC_URL", "")

    ws_rpc: str = os.getenv("WS_RPC_URL", "wss://api.mainnet-beta.solana.com")

    helius_key: str = os.getenv("HELIUS_API_KEY", "")

    sqlite_path: str = os.getenv("SQLITE_PATH", "./bot.db")
    owner_user_id: int = int(os.getenv("OWNER_USER_ID", 0))

SETTINGS = Settings()
