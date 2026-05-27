import os
from dotenv import load_dotenv

load_dotenv()

# ── Data source switch ────────────────────────────────────────────────────────
# "csv"            : load test CSVs from DATA_DIR (default)
# "production_db"  : connect to existing-system MySQL (read-only)
DATA_SOURCE = os.getenv("DATA_SOURCE", "csv")
DATA_DIR    = os.getenv("DATA_DIR",    "./data")

# ── Production DB (MySQL, read-only) ──────────────────────────────────────────
PROD_DB_HOST     = os.getenv("PROD_DB_HOST")
PROD_DB_PORT     = os.getenv("PROD_DB_PORT", "3306")
PROD_DB_USER     = os.getenv("PROD_DB_USER")
PROD_DB_PASSWORD = os.getenv("PROD_DB_PASSWORD")
PROD_DB_NAME     = os.getenv("PROD_DB_NAME")
