"""Chuyển một lần dữ liệu BLE Classroom từ SQLite cũ sang MySQL."""
import os
import sqlite3
from pathlib import Path

import pymysql


SQLITE_PATH = Path(os.getenv("SQLITE_PATH", "/app/legacy-data/classroom.sqlite3"))


def main():
    if not SQLITE_PATH.is_file():
        raise SystemExit(f"Không tìm thấy SQLite cũ: {SQLITE_PATH}")

    source = sqlite3.connect(SQLITE_PATH)
    source.row_factory = sqlite3.Row
    target = pymysql.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "ble_user"),
        password=os.getenv("DB_PASSWORD", "ble_password"),
        database=os.getenv("DB_NAME", "ble_classroom"),
        charset="utf8mb4",
        autocommit=False,
    )

    try:
        with target.cursor() as cursor:
            counts = {}
            for table in ("students", "questions", "answers"):
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            if any(counts.values()):
                raise SystemExit(
                    "MySQL không trống, dừng migrate để tránh trùng dữ liệu: "
                    + ", ".join(f"{table}={count}" for table, count in counts.items())
                )
            cursor.execute('SELECT id FROM teachers ORDER BY id LIMIT 2')
            owners = cursor.fetchall()
            if len(owners) != 1:
                raise SystemExit('Hãy đăng ký đúng một tài khoản giảng viên trước khi chuyển SQLite để gán quyền sở hữu an toàn.')
            owner = owners[0][0]
            cursor.execute("INSERT INTO classes(teacher_id,code,name) VALUES(%s,'LEGACY','Lớp hiện tại') ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)", (owner,))
            class_id = cursor.lastrowid
            cursor.execute("INSERT INTO subjects(teacher_id,code,name) VALUES(%s,'LEGACY','Môn hiện tại') ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)", (owner,))
            subject_id = cursor.lastrowid
            cursor.execute('INSERT INTO class_subjects(class_id,subject_id) VALUES(%s,%s) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)', (class_id, subject_id))
            course_id = cursor.lastrowid

            students = source.execute(
                "SELECT id, mssv, name, device_id FROM students ORDER BY id"
            ).fetchall()
            questions = source.execute(
                """SELECT id, text, a, b, c, d, correct_choice, points, status
                   FROM questions ORDER BY id"""
            ).fetchall()
            answers = source.execute(
                """SELECT id, question_id, student_id, choice, sequence, submitted_at
                   FROM answers ORDER BY id"""
            ).fetchall()

            cursor.executemany(
                "INSERT INTO students(id,mssv,name,device_id,teacher_id) VALUES(%s,%s,%s,%s,%s)",
                [tuple(row)+(owner,) for row in students],
            )
            cursor.executemany(
                """INSERT INTO questions
                   (id,text,a,b,c,d,correct_choice,points,status,course_id)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [tuple(row)+(course_id,) for row in questions],
            )
            cursor.executemany(
                """INSERT INTO answers
                   (id,question_id,student_id,choice,sequence,submitted_at)
                   VALUES(%s,%s,%s,%s,%s,%s)""",
                [tuple(row) for row in answers],
            )
            cursor.execute('INSERT INTO enrollments(course_id,student_id) SELECT %s,id FROM students WHERE teacher_id=%s', (course_id, owner))
            cursor.execute('INSERT IGNORE INTO class_students(class_id,student_id) SELECT %s,id FROM students WHERE teacher_id=%s', (class_id, owner))
            cursor.execute('''INSERT IGNORE INTO devices(teacher_id,device_id)
                SELECT teacher_id,device_id FROM students WHERE teacher_id=%s AND device_id<>%s''',
                (owner, ''))
            cursor.execute("""INSERT INTO question_students(question_id,student_id,mssv,name,device_id)
                SELECT q.id,s.id,s.mssv,s.name,s.device_id FROM questions q CROSS JOIN students s
                WHERE q.course_id=%s AND s.teacher_id=%s AND q.status<>'draft'""", (course_id, owner))
        target.commit()
        print(
            f"Đã chuyển: {len(students)} sinh viên, "
            f"{len(questions)} câu hỏi, {len(answers)} đáp án."
        )
    except BaseException:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
