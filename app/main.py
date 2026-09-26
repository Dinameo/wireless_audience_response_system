import csv
import io
from collections import Counter
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, delete

from .database import Base, engine, SessionLocal
from .models import Student, Question, QuizSession, Assignment, Answer
from .parser import parse_question_file

app = FastAPI(title="NRF52840 Classroom Quiz Server")
templates = Jinja2Templates(directory="app/templates")
Base.metadata.create_all(bind=engine)

class AnswerIn(BaseModel):
    session_id: int
    remote_no: int
    question_number: int
    option: str
    seq_no: int = 0

def db_session():
    return SessionLocal()

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with db_session() as db:
        students = db.scalars(select(Student).order_by(Student.stt)).all()
        questions = db.scalars(select(Question).order_by(Question.number)).all()
        sessions = db.scalars(select(QuizSession).order_by(QuizSession.id.desc())).all()
    return templates.TemplateResponse("index.html", {
        "request": request, "students": students,
        "questions": questions, "sessions": sessions
    })

@app.post("/upload-roster")
async def upload_roster(file: UploadFile = File(...)):
    data = await file.read()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    required = {"stt", "mssv", "ho_ten"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(400, "CSV phải có cột: stt,mssv,ho_ten")

    with db_session() as db:
        db.execute(delete(Student))
        db.commit()
        for row in reader:
            db.add(Student(
                stt=int(row["stt"]),
                student_code=row["mssv"].strip(),
                full_name=row["ho_ten"].strip(),
            ))
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/upload-questions")
async def upload_questions(file: UploadFile = File(...)):
    data = await file.read()
    try:
        parsed = parse_question_file(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    with db_session() as db:
        db.execute(delete(Answer))
        db.execute(delete(Question))
        db.commit()
        for q in parsed:
            db.add(Question(
                number=q["number"], text=q["text"],
                option_a=q["options"]["A"], option_b=q["options"]["B"],
                option_c=q["options"]["C"], option_d=q["options"]["D"],
                correct_option=q["correct_option"],
            ))
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/session/create")
def create_session(name: str = Form(...)):
    with db_session() as db:
        students = db.scalars(select(Student).order_by(Student.stt)).all()
        if not students:
            raise HTTPException(400, "Hãy upload danh sách lớp trước.")
        s = QuizSession(name=name, status="created")
        db.add(s)
        db.flush()
        for st in students:
            db.add(Assignment(session_id=s.id, remote_no=st.stt, student_id=st.id))
        db.commit()
        sid = s.id
    return RedirectResponse(f"/session/{sid}", status_code=303)

@app.get("/session/{session_id}", response_class=HTMLResponse)
def session_page(request: Request, session_id: int):
    with db_session() as db:
        s = db.get(QuizSession, session_id)
        if not s:
            raise HTTPException(404, "Không tìm thấy session.")
        questions = db.scalars(select(Question).order_by(Question.number)).all()
    return templates.TemplateResponse("session.html", {
        "request": request, "session": s, "questions": questions
    })

@app.post("/api/session/{session_id}/question/{question_number}/open")
def open_question(session_id: int, question_number: int):
    with db_session() as db:
        s = db.get(QuizSession, session_id)
        q = db.scalar(select(Question).where(Question.number == question_number))
        if not s or not q:
            raise HTTPException(404, "Session hoặc câu hỏi không tồn tại.")
        s.current_question_number = question_number
        s.status = "running"
        db.commit()
    return {"ok": True, "question_number": question_number}

@app.post("/api/answer")
def receive_answer(payload: AnswerIn):
    option = payload.option.upper().strip()
    if option not in {"A", "B", "C", "D"}:
        raise HTTPException(400, "option phải là A/B/C/D")

    with db_session() as db:
        assignment = db.scalar(select(Assignment).where(
            Assignment.session_id == payload.session_id,
            Assignment.remote_no == payload.remote_no,
        ))
        if not assignment:
            raise HTTPException(404, "Remote chưa được gán cho học sinh.")

        s = db.get(QuizSession, payload.session_id)
        if not s:
            raise HTTPException(404, "Session không tồn tại.")
        if s.current_question_number != payload.question_number:
            raise HTTPException(409, "Câu hỏi này hiện không mở.")

        existing = db.scalar(select(Answer).where(
            Answer.session_id == payload.session_id,
            Answer.question_number == payload.question_number,
            Answer.remote_no == payload.remote_no,
        ))

        if existing:
            if payload.seq_no >= existing.seq_no:
                existing.selected_option = option
                existing.seq_no = payload.seq_no
        else:
            db.add(Answer(
                session_id=payload.session_id,
                question_number=payload.question_number,
                remote_no=payload.remote_no,
                student_id=assignment.student_id,
                selected_option=option,
                seq_no=payload.seq_no,
            ))
        db.commit()
    return {"ok": True}

@app.get("/api/session/{session_id}/answers/{question_number}")
def get_answers(session_id: int, question_number: int):
    with db_session() as db:
        q = db.scalar(select(Question).where(Question.number == question_number))
        if not q:
            raise HTTPException(404, "Không tìm thấy câu hỏi.")
        rows = db.execute(
            select(Answer, Student)
            .join(Student, Student.id == Answer.student_id)
            .where(
                Answer.session_id == session_id,
                Answer.question_number == question_number,
            )
            .order_by(Student.stt)
        ).all()

        counts = Counter(ans.selected_option for ans, _ in rows)
        students = [{
            "stt": st.stt,
            "mssv": st.student_code,
            "ho_ten": st.full_name,
            "remote_no": ans.remote_no,
            "answer": ans.selected_option,
            "correct": ans.selected_option == q.correct_option,
        } for ans, st in rows]

    return {
        "question_number": question_number,
        "correct_option": q.correct_option,
        "counts": {x: counts.get(x, 0) for x in "ABCD"},
        "students": students,
    }

@app.get("/simulate", response_class=HTMLResponse)
def simulate_page(request: Request):
    return templates.TemplateResponse("simulate.html", {"request": request})
