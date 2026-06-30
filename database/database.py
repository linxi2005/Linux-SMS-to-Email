from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from database.models import Base
from utils.config import DATA_DIR, ensure_runtime_dirs

DB_PATH = DATA_DIR / "sms.db"
_engine = None
SessionLocal = scoped_session(sessionmaker(autoflush=False, autocommit=False))


def get_database_url() -> str:
    ensure_runtime_dirs()
    return "sqlite:///{}".format(Path(DB_PATH).as_posix())


def init_db() -> None:
    global _engine
    ensure_runtime_dirs()
    _engine = create_engine(
        get_database_url(),
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    SessionLocal.configure(bind=_engine)
    Base.metadata.create_all(bind=_engine)


def get_engine():
    global _engine
    if _engine is None:
        init_db()
    return _engine


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
