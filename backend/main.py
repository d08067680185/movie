import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import init_db, AsyncSessionLocal
from api.search import router as search_router
from api.admin import router as admin_router
from api.tmdb import router as tmdb_router
from config import settings
from spiders.scheduler import run_all_spiders
from utils import backup_db
from api.admin import run_link_check

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def seed_demo_data():
    # 演示数据已禁用，使用 TMDb 爬虫导入真实数据
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_demo_data()

    scheduler.add_job(
        run_all_spiders,
        "interval",
        hours=settings.SPIDER_INTERVAL_HOURS,
        id="crawl_all",
    )
    scheduler.add_job(
        lambda: asyncio.create_task(asyncio.to_thread(backup_db)),
        "cron",
        hour=3,
        minute=0,
        id="daily_backup",
    )
    scheduler.add_job(
        lambda: asyncio.create_task(run_link_check(settings.LINK_CHECK_BATCH_SIZE)),
        "interval",
        hours=settings.LINK_CHECK_INTERVAL_HOURS,
        id="check_links_scheduled",
        next_run_time=datetime.now() + timedelta(minutes=5),
    )
    scheduler.start()
    logger.info("Scheduler started")

    yield

    scheduler.shutdown()


app = FastAPI(
    title="影视资源搜索",
    description="多源影视资源聚合搜索平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(admin_router)
app.include_router(tmdb_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "影视资源搜索 API", "docs": "/docs"}
