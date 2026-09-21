from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import engine_from_config,pool
from app.core.database import Base
# Import route/module registry so mapped tables are registered in Base.metadata.
from app.modules import registry as _registry  # noqa: F401
from app.core import schema as _schema  # noqa: F401
from app.modules.m20_general_cognitive_worker.sql_repository import Base as GCWBase
config=context.config
if config.config_file_name and config.get_section("loggers"):
 fileConfig(config.config_file_name,disable_existing_loggers=False)
config.set_main_option("sqlalchemy.url",os.getenv("ATLAS_DATABASE_URL",config.get_main_option("sqlalchemy.url")))
target_metadata=[Base.metadata, GCWBase.metadata]
def run_migrations_offline():
 context.configure(url=config.get_main_option("sqlalchemy.url"),target_metadata=target_metadata,literal_binds=True,compare_type=True)
 with context.begin_transaction():context.run_migrations()
def run_migrations_online():
 connectable=engine_from_config(config.get_section(config.config_ini_section),prefix="sqlalchemy.",poolclass=pool.NullPool)
 with connectable.connect() as connection:
  context.configure(connection=connection,target_metadata=target_metadata,compare_type=True)
  with context.begin_transaction():context.run_migrations()
run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
