from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from .db import Base
import datetime

# --- Пользователи ---

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # SaaS поля
    subscription_end_date = Column(DateTime, nullable=True) # Дата окончания подписки
    subscription_plan = Column(String, default="FREE")      # FREE, PRO, PREMIUM

    # Связи
    students = relationship("Student", back_populates="teacher")
    groups = relationship("Group", back_populates="teacher")
    lessons = relationship("Lesson", back_populates="teacher")
    homeworks = relationship("Homework", back_populates="teacher")
    saas_payments = relationship("SaaSPayment", back_populates="teacher")
    student_payments = relationship("StudentPayment", back_populates="teacher")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Финансы ученика
    balance = Column(Integer, default=0)  # Баланс
    price_per_lesson = Column(Integer, nullable=True) # Персональная ставка

    teacher = relationship("Teacher", back_populates="students")
    groups = relationship("GroupStudent", back_populates="student")
    submissions = relationship("HomeworkSubmission", back_populates="student")
    parents = relationship("ParentStudent", back_populates="student")
    payments = relationship("StudentPayment", back_populates="student")


class Parent(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    students_link = relationship("ParentStudent", back_populates="parent")


class ParentStudent(Base):
    __tablename__ = "parent_students"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)

    parent = relationship("Parent", back_populates="students_link")
    student = relationship("Student", back_populates="parents")


# --- Группы ---

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("Teacher", back_populates="groups")
    students = relationship("GroupStudent", back_populates="group")
    lessons = relationship("Lesson", back_populates="group")


class GroupStudent(Base):
    __tablename__ = "group_students"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)

    group = relationship("Group", back_populates="students")
    student = relationship("Student", back_populates="groups")


# --- Расписание ---

class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    topic = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("Teacher", back_populates="lessons")
    group = relationship("Group", back_populates="lessons")
    student = relationship("Student")


# --- Домашние задания ---

class Homework(Base):
    __tablename__ = "homeworks"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    max_score = Column(Integer, nullable=True)
    grading_type = Column(String(20), default="points")
    saved_in_library = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("Teacher", back_populates="homeworks")
    assignments = relationship("HomeworkAssignment", back_populates="homework")


class HomeworkAssignment(Base):
    __tablename__ = "homework_assignments"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homeworks.id"), nullable=False)
    assigned_to_type = Column(String(10))  # student/group/multi
    assigned_to_id = Column(Integer, nullable=True)
    assigned_to_ids = Column(JSON, nullable=True)  # для multi: список ID учеников
    deadline = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    homework = relationship("Homework", back_populates="assignments")
    submissions = relationship("HomeworkSubmission", back_populates="assignment")


class HomeworkSubmission(Base):
    __tablename__ = "homework_submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("homework_assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String, default="assigned")  # assigned, submitted, graded, overdue
    score_value = Column(Integer, nullable=True)
    score_percent = Column(Integer, nullable=True)
    teacher_comment = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    assignment = relationship("HomeworkAssignment", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")


# --- SaaS Финансы (Подписки учителей) ---

class SaaSPayment(Base):
    """Оплаты учителей за подписку"""
    __tablename__ = "saas_payments"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    amount = Column(Integer, nullable=False) # Сумма
    currency = Column(String, default="RUB")
    provider_payment_id = Column(String, unique=True, nullable=False) # ID (симуляция или реальный)
    status = Column(String, default="pending") # pending, succeeded, canceled
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("Teacher", back_populates="saas_payments")


# --- Финансы учеников ---

class StudentPayment(Base):
    """Платежи учеников учителю"""
    __tablename__ = "student_payments"

    id = Column(Integer, primary_key=True, index=True)
    # 1. Добавляем teacher_id
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    
    amount = Column(Integer, nullable=False)
    # 2. Добавляем lessons_added
    lessons_added = Column(Integer, default=0) 
    
    date = Column(DateTime, default=datetime.datetime.utcnow)
    comment = Column(String, nullable=True)

    # Связи
    # 3. Добавляем связь с учителем, чтобы работало teacher.student_payments
    teacher = relationship("Teacher", back_populates="student_payments")
    student = relationship("Student", back_populates="payments")