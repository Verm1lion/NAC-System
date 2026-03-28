from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import init_db, init_redis, close_connections
from routes import auth, authorize, accounting, users, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama baslarken DB ve Redis baglantilarini kurar,
    kapanirken temizler."""
    init_db()
    init_redis()
    yield
    close_connections()


app = FastAPI(
    title="NAC Policy Engine",
    description="FreeRADIUS ile entegre calisan Network Access Control policy engine",
    version="1.0.0",
    lifespan=lifespan
)

# Router'lari bagla
app.include_router(auth.router, tags=["Authentication"])
app.include_router(authorize.router, tags=["Authorization"])
app.include_router(accounting.router, tags=["Accounting"])
app.include_router(users.router, tags=["Users"])
app.include_router(sessions.router, tags=["Sessions"])


@app.get("/health")
def health_check():
    """Docker healthcheck icin kullanilan endpoint."""
    return {"status": "ok"}
