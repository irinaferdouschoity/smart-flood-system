from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Hosted copy ships the database compressed (flood.db.gz); unpack it once on first start.
_DB, _DBGZ = PROJECT_ROOT / "flood.db", PROJECT_ROOT / "flood.db.gz"
if not _DB.exists() and _DBGZ.exists():
    import gzip, shutil
    with gzip.open(_DBGZ, "rb") as _src, open(_DB, "wb") as _dst:
        shutil.copyfileobj(_src, _dst)


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'flood.db'}"
    earthdata_token: str | None = None
    nasa_power_timeout: int = 60
    imerg_timeout: int = 120
    # Automatic NASA POWER download into MySQL (see backend/main.py)
    auto_sync_nasa: bool = True
    auto_sync_hours: int = 6
    history_start: str = '2020-01-01'
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / '.env'), extra='ignore')
settings = Settings()
