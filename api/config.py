import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL
POSTGRES_USER = os.getenv("POSTGRES_USER", "radius")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "radiuspass123")
POSTGRES_DB = os.getenv("POSTGRES_DB", "radius")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD}"

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Rate Limiting
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 dakika
