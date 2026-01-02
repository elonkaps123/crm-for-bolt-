from fastapi import FastAPI
from .db import engine, Base
from . import models
from .api import v1
import os

app = FastAPI(title="Bit-Fotutors API")

# Создать таблицы при старте (для dev)
Base.metadata.create_all(bind=engine)

app.include_router(v1.router, prefix="/api/v1")
