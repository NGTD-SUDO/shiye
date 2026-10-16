"""数据库引擎与会话管理"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    """SQLite 需要手动开启外键与忙碌等待（避免写锁冲突）"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=8000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有模型继承此类"""


def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_migration(engine) -> None:
    """SQLite 不支持 ALTER COLUMN 的完整特性，这里只做「加列」迁移。
    create_all 不会修改已有表，所以需要手动加列。
    """
    from sqlalchemy import text
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(pages)")).fetchall()]
        if "structured_text" not in cols:
            conn.execute(text("ALTER TABLE pages ADD COLUMN structured_text TEXT"))
            conn.commit()
