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
from api.livesearch import router as livesearch_router
from api.downloads import router as downloads_router, cleanup_expired_downloads
from config import settings
from spiders.scheduler import run_all_spiders
from utils import backup_db, send_telegram
from api.admin import run_link_check, record_disk_usage_snapshot
from auth import migrate_plaintext_password
from ratelimit import sweep_all_limiters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def seed_demo_data():
    # 演示数据已禁用，使用 TMDb 爬虫导入真实数据
    pass


async def run_daily_backup():
    dest = await asyncio.to_thread(backup_db)
    if dest is None:
        logger.error("每日备份完整性校验失败")
        await send_telegram("⚠️ <b>数据库备份失败</b>\n今日自动备份的完整性校验未通过，已删除坏文件，请尽快检查")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_demo_data()
    migrate_plaintext_password(settings)

    scheduler.add_job(
        run_all_spiders,
        "interval",
        hours=settings.SPIDER_INTERVAL_HOURS,
        id="crawl_all",
        # IntervalTrigger 默认"添加即执行"——不设置的话每次重启后端都会立刻
        # 触发一次全量爬虫(实测:配置TMDB_API_KEY后每次重启会静默多导入
        # 上百部电影)，容易让人误判"数据怎么变了"。延后10分钟，等服务稳定
        # 再跑，且和下面的链接检测任务错开时间。
        next_run_time=datetime.now() + timedelta(minutes=10),
    )
    scheduler.add_job(
        lambda: asyncio.create_task(run_daily_backup()),
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
    scheduler.add_job(
        lambda: asyncio.create_task(cleanup_expired_downloads()),
        "interval",
        hours=1,
        id="cleanup_downloads",
        next_run_time=datetime.now() + timedelta(minutes=15),
    )
    scheduler.add_job(
        sweep_all_limiters,
        "interval",
        hours=1,
        id="sweep_ratelimiters",
        next_run_time=datetime.now() + timedelta(minutes=20),
    )
    scheduler.add_job(
        lambda: asyncio.create_task(record_disk_usage_snapshot()),
        "cron",
        hour=3,
        minute=30,
        id="disk_usage_snapshot",
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

app.include_router(search_router)
app.include_router(admin_router)
app.include_router(tmdb_router)
app.include_router(livesearch_router)
app.include_router(downloads_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "影视资源搜索 API", "docs": "/docs"}
