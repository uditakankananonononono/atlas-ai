import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

DATABASE_URL = os.getenv("ATLAS_DATABASE_URL", "sqlite:///./atlas.db")
_engine_kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
