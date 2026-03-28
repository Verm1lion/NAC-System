import psycopg2
import psycopg2.pool
import redis
from config import DATABASE_URL, REDIS_HOST, REDIS_PORT
import logging

logger = logging.getLogger(__name__)

# PostgreSQL connection pool
db_pool = None

# Redis client
redis_client = None


def init_db():
    """PostgreSQL baglanti havuzunu olusturur."""
    global db_pool
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL
        )
        logger.info("PostgreSQL baglanti havuzu olusturuldu.")
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL baglanti hatasi: {e}")
        raise


def get_db():
    """Pool'dan bir baglanti alir."""
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)


def init_redis():
    """Redis client'i olusturur."""
    global redis_client
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )
        redis_client.ping()
        logger.info("Redis baglandisi basarili.")
    except redis.ConnectionError as e:
        logger.error(f"Redis baglanti hatasi: {e}")
        raise


def get_redis():
    """Redis client'i doner."""
    return redis_client


def close_connections():
    """Tum baglantilari kapatir."""
    global db_pool, redis_client
    if db_pool:
        db_pool.closeall()
        logger.info("PostgreSQL baglantilari kapatildi.")
    if redis_client:
        redis_client.close()
        logger.info("Redis baglantisi kapatildi.")
