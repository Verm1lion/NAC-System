from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from database import init_db, init_redis, close_connections
from routes import auth, authorize, accounting, users, sessions
from routes import stats, register


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

# CORS — Dashboard'un API'ye erisebilmesi icin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static dosyalar (dashboard.html vs.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Router'lari bagla
app.include_router(auth.router, tags=["Authentication"])
app.include_router(authorize.router, tags=["Authorization"])
app.include_router(accounting.router, tags=["Accounting"])
app.include_router(users.router, tags=["Users"])
app.include_router(sessions.router, tags=["Sessions"])
app.include_router(stats.router, tags=["Stats"])
app.include_router(register.router, tags=["Register"])


@app.get("/health")
def health_check():
    """Docker healthcheck icin kullanilan endpoint."""
    return {"status": "ok"}


@app.get("/dashboard")
def dashboard():
    """NAC Monitoring Dashboard — tarayicida ac."""
    return FileResponse("static/dashboard.html")
