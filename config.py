from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "inventory.db"
SCHEMA_PATH = DB_DIR / "schema.sql"
REPORTS_DIR = BASE_DIR / "reports"

EXPIRY_WARNING_DAYS = 15
