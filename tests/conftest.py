import os

# Automatically enable integration tests when test harness runs
os.environ.setdefault("ZOMEGA_INTEGRATION", "1")
os.environ.setdefault("RUN_INTEGRATION_TESTS", "1")

# Use project settings
from zomega.config import settings
import zomega.db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if str(zomega.db.engine.url) != settings.database_url:
    zomega.db.engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    zomega.db.SessionLocal = sessionmaker(bind=zomega.db.engine, autoflush=False, expire_on_commit=False)
