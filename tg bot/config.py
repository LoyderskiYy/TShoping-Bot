import os
from typing import List, Optional
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Список ID администраторов Telegram через запятую, например: 12345678,87654321
ADMIN_IDS_RAW: str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: List[int] = [
    int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()
]

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "shop.db")
DATABASE_URL: str = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# Дефолтный кошелек BTC (можно переопределить через админ-панель бота в любой момент)
DEFAULT_BTC_WALLET: str = os.getenv("DEFAULT_BTC_WALLET", "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")

# Минимальная сумма пополнения в рублях
MIN_DEPOSIT_RUB: float = float(os.getenv("MIN_DEPOSIT_RUB", "100.0"))

# Прокси для обхода блокировки api.telegram.org (например, socks5://127.0.0.1:10808 или http://proxy:port)
PROXY_URL: Optional[str] = os.getenv("PROXY_URL", "").strip() or None

# Время жизни заявки на пополнение в минутах
DEPOSIT_LIFETIME_MINUTES: int = int(os.getenv("DEPOSIT_LIFETIME_MINUTES", "120"))

# Веб-админ панель
WEB_ADMIN_HOST: str = os.getenv("WEB_ADMIN_HOST", "0.0.0.0")
WEB_ADMIN_PORT: int = int(os.getenv("WEB_ADMIN_PORT", "8000"))
WEB_ADMIN_PASSWORD: str = os.getenv("WEB_ADMIN_PASSWORD", "admin123")

