from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# =========================================================================
# 👇 ЭТО ДОЛЖНО БЫТЬ В САМОМ ВЕРХУ (до импорта app.db)
# Это добавляет папку проекта в пути Python, чтобы он видел папку "app"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# =========================================================================

# Загружаем переменные из .env
load_dotenv()

# Импорт моделей
from app.db import Base
from app import models

# Конфигурация Alembic
config = context.config
fileConfig(config.config_file_name)

# Указываем метаданные
target_metadata = Base.metadata

# 👇 ИСПРАВЛЕННАЯ ФУНКЦИЯ (добавили return)
def get_url():
    return os.getenv("DATABASE_URL")

def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()