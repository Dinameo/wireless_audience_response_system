from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    stt: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    student_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    text: Mapped[str] = mapped_column(String(1000))
    option_a: Mapped[str] = mapped_column(String(1000))
    option_b: Mapped[str] = mapped_column(String(1000))
    option_c: Mapped[str] = mapped_column(String(1000))
    option_d: Mapped[str] = mapped_column(String(1000))
    correct_option: Mapped[str] = mapped_column(String(1))

class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="created")
    current_question_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("session_id", "remote_no", name="uq_session_remote"),
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("quiz_sessions.id"), index=True)
    remote_no: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)

class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (
        UniqueConstraint("session_id", "question_number", "remote_no", name="uq_answer_once"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("quiz_sessions.id"), index=True)
    question_number: Mapped[int] = mapped_column(Integer, index=True)
    remote_no: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    selected_option: Mapped[str] = mapped_column(String(1))
    seq_no: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
