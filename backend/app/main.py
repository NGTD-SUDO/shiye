"""拾页后端 API — 入口（FastAPI）"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import app.models  # noqa: F401  # 注册全部模型
from app.config import (
    CORS_ALLOW_ORIGINS,
    DEEPSEEK_API_KEY,
    DEV_MODE,
    INVITE_CODE,
    LOG_LEVEL,
    OCR_PROVIDER,
    UPLOAD_DIR,
    validate_runtime_config,
)
from app.database import Base, engine, ensure_schema_migration
from app.legal_content import LEGAL_HTML
from app.routers import ai, auth, chapters, files, pages, search, subjects
from app.services import fts
from app.services.ocr_service import ocr_processor

# ============ 日志配置（启动时配一次）============
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时先校验配置（不合法 → 进程起不来，在 create_all 之前）
    validate_runtime_config()
    Base.metadata.create_all(bind=engine)
    ensure_schema_migration(engine)
    fts.ensure_fts(engine)
    ocr_processor.start()  # 启动 worker 线程 + 恢复未完成任务

    # 启动日志（一次）：版本、DEV_MODE、邀请码状态、OCR provider、AI 可用状态、CORS 白名单、存储目录
    cors_origins = [o.strip() for o in CORS_ALLOW_ORIGINS.split(",") if o.strip()] if CORS_ALLOW_ORIGINS else []
    _logger.info(
        "拾页后端启动 v0.1.0 | DEV_MODE=%s | 邀请码=%s | OCR=%s | AI=%s | CORS白名单=%s | 存储目录=%s",
        "开启" if DEV_MODE else "关闭",
        "已启用" if INVITE_CODE else "未启用",  # 只报状态，不打印码本身
        OCR_PROVIDER,
        "可用" if DEEPSEEK_API_KEY else "未配置",  # 只报状态，不打印密钥
        cors_origins if cors_origins else "未配置（不注册CORS）",
        str(UPLOAD_DIR),
    )

    yield
    ocr_processor.stop()


app = FastAPI(title="拾页 API", version="0.1.0", lifespan=lifespan)

# ============ CORS 条件注册 ============
# CORS 只影响浏览器（Flutter Web/调试），不影响 App 客户端
_cors_origins = [o.strip() for o in CORS_ALLOW_ORIGINS.split(",") if o.strip()] if CORS_ALLOW_ORIGINS else []
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,  # 只允许白名单，不再与 * 同用
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
# 为空则不注册 CORS 中间件（App 原生 HTTP 不受 CORS 影响，内测不需要开）

app.include_router(auth.router)
app.include_router(subjects.router)
app.include_router(chapters.router)
app.include_router(pages.router)
app.include_router(search.router)
app.include_router(files.router)
app.include_router(ai.router)


# ============ 全局异常处理器 ============
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未预期异常，返回 500 + 通用中文文案

    响应体绝不包含堆栈/文件路径/异常类名；完整堆栈写服务端日志。
    """
    _logger.exception("未预期异常: %s %s -> %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


# ============ 请求日志中间件 ============
@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    """记录 方法 路径 状态码 耗时ms；脱敏：不记 Authorization 头、不记 query 的 s（签名）与 e"""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # 脱敏：query 里的 s（签名）与 e（过期时间）不记录
    # 只记路径，不记完整 query
    path = request.url.path

    _logger.info(
        "%s %s %d %.0fms",
        request.method,
        path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/")
def root():
    return {"message": "拾页 API 运行中", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ============ 法律文档合页（T12 收尾，公开无需登录）============
# - 内容源：`legal/web/index.html`（4 份法律文档合页，自包含），以常量形式内联在
#   `app/legal_content.py`（生成脚本逐字产出，说明见该文件头部）
# - **公开**：应用商店审核需要能直接打开，所以不加鉴权（与业务路由不同）
# - `include_in_schema=False`：法律页不必出现在 OpenAPI 文档里
# - 邮箱在内容里已实体化为 `&#64;`：Cloudflare 免费隧道的邮箱混淆会把裸邮箱改写成
#   `[email protected]`，那样法律页就等于没有有效联系方式
@app.get("/legal", include_in_schema=False)
def legal_page():
    """4 份法律文档合页（公开，无需登录）"""
    return HTMLResponse(content=LEGAL_HTML, media_type="text/html; charset=utf-8")
