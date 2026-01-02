from fastapi import APIRouter, Depends, HTTPException
from ..db import SessionLocal
from .. import models
from pydantic import BaseModel

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TeacherCreate(BaseModel):
    telegram_id: str
    name: str | None = None

@router.post("/teachers")
def create_teacher(payload: TeacherCreate, db=Depends(get_db)):
    t = db.query(models.Teacher).filter_by(telegram_id=payload.telegram_id).first()
    if t:
        raise HTTPException(status_code=400, detail="Teacher exists")
    teacher = models.Teacher(telegram_id=payload.telegram_id, name=payload.name)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return {"id": teacher.id, "telegram_id": teacher.telegram_id}
