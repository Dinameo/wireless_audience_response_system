"""Teacher-owned classes, subjects, enrollment and immutable exam rosters."""
import pymysql
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator


class NamedIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)

    @field_validator('code', 'name')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Không được để trống')
        return value


class CourseIn(BaseModel):
    subject_id: int = Field(gt=0)


class ClassIn(NamedIn):
    subject_id: int | None = Field(default=None, gt=0)


def init_workspace(database):
    with database() as db:
        for sql in [
            """CREATE TABLE IF NOT EXISTS classes (
                id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                teacher_id INT UNSIGNED NOT NULL, code VARCHAR(30) NOT NULL,
                name VARCHAR(120) NOT NULL,
                UNIQUE KEY uq_class_owner_code(teacher_id,code),
                FOREIGN KEY(teacher_id) REFERENCES teachers(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS subjects (
                id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                teacher_id INT UNSIGNED NOT NULL, code VARCHAR(30) NOT NULL,
                name VARCHAR(120) NOT NULL,
                UNIQUE KEY uq_subject_owner_code(teacher_id,code),
                FOREIGN KEY(teacher_id) REFERENCES teachers(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS class_subjects (
                id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                class_id INT UNSIGNED NOT NULL, subject_id INT UNSIGNED NOT NULL,
                UNIQUE KEY uq_class_subject(class_id,subject_id),
                FOREIGN KEY(class_id) REFERENCES classes(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS enrollments (
                course_id INT UNSIGNED NOT NULL, student_id INT UNSIGNED NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE, PRIMARY KEY(course_id,student_id),
                FOREIGN KEY(course_id) REFERENCES class_subjects(id),
                FOREIGN KEY(student_id) REFERENCES students(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS exam_students (
                exam_id INT UNSIGNED NOT NULL, student_id INT UNSIGNED NOT NULL,
                mssv VARCHAR(30) NOT NULL, name VARCHAR(120) NOT NULL, device_id VARCHAR(40) NOT NULL,
                PRIMARY KEY(exam_id,student_id), FOREIGN KEY(exam_id) REFERENCES exams(id),
                FOREIGN KEY(student_id) REFERENCES students(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS question_students (
                question_id INT UNSIGNED NOT NULL, student_id INT UNSIGNED NOT NULL,
                mssv VARCHAR(30) NOT NULL, name VARCHAR(120) NOT NULL, device_id VARCHAR(40) NOT NULL,
                PRIMARY KEY(question_id,student_id), FOREIGN KEY(question_id) REFERENCES questions(id),
                FOREIGN KEY(student_id) REFERENCES students(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS workspace_migrations (
                version VARCHAR(40) PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB""",
            """CREATE TABLE IF NOT EXISTS device_presence (
                student_id INT UNSIGNED PRIMARY KEY,
                protocol ENUM('BLE','USB','WIFI','SIMULATED') NOT NULL,
                gateway_id VARCHAR(64) NOT NULL, connected BOOLEAN NOT NULL,
                rssi SMALLINT NULL,
                last_seen DATETIME(3) NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS device_credentials (
                student_id INT UNSIGNED PRIMARY KEY,
                token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            """CREATE TABLE IF NOT EXISTS device_reports (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                student_id INT UNSIGNED NOT NULL,
                protocol ENUM('BLE','USB','WIFI','SIMULATED') NOT NULL,
                connected BOOLEAN NOT NULL,
                rssi SMALLINT NULL,
                received_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                INDEX idx_device_reports_student_time(student_id,received_at),
                FOREIGN KEY(student_id) REFERENCES students(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
        ]:
            db.execute(sql)
        for table, column, definition in [
            ('students', 'teacher_id', 'INT UNSIGNED NULL'),
            ('students', 'revision', 'INT UNSIGNED NOT NULL DEFAULT 0'),
            ('students', 'preferred_protocol', "ENUM('BLE','WIFI') NOT NULL DEFAULT 'BLE'"),
            ('exams', 'course_id', 'INT UNSIGNED NULL'),
            ('exams', 'revision', 'INT UNSIGNED NOT NULL DEFAULT 0'),
            ('exams', 'time_limit_seconds', 'INT UNSIGNED NULL'),
            ('exams', 'deadline_at', 'DATETIME(3) NULL'),
            ('questions', 'course_id', 'INT UNSIGNED NULL'),
            ('device_presence', 'exam_id', 'INT UNSIGNED NULL'),
            ('device_reports', 'exam_id', 'INT UNSIGNED NULL'),
        ]:
            db.execute('SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s', (table, column))
            if not db.fetchone():
                db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        for table, name, sql in [
            ('students', 'fk_student_owner', 'ALTER TABLE students ADD CONSTRAINT fk_student_owner FOREIGN KEY(teacher_id) REFERENCES teachers(id)'),
            ('exams', 'fk_exam_course', 'ALTER TABLE exams ADD CONSTRAINT fk_exam_course FOREIGN KEY(course_id) REFERENCES class_subjects(id)'),
            ('questions', 'fk_question_course', 'ALTER TABLE questions ADD CONSTRAINT fk_question_course FOREIGN KEY(course_id) REFERENCES class_subjects(id)'),
        ]:
            db.execute('SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=%s AND CONSTRAINT_NAME=%s', (table, name))
            if not db.fetchone():
                db.execute(sql)
        db.execute("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='students' AND INDEX_NAME='uq_student_owner_mssv'")
        if not db.fetchone():
            db.execute('ALTER TABLE students ADD UNIQUE KEY uq_student_owner_mssv(teacher_id,mssv)')
        db.execute("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='students' AND INDEX_NAME='uq_students_mssv'")
        if db.fetchone():
            db.execute('ALTER TABLE students DROP INDEX uq_students_mssv')
        db.execute("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='students' AND INDEX_NAME='uq_students_device_id'")
        if db.fetchone():
            db.execute('ALTER TABLE students DROP INDEX uq_students_device_id')

    # Only a sole teacher present at migration may inherit shared legacy data.
    # A later registration must never be able to claim unowned records.
    with database() as db:
        db.execute("SELECT version FROM workspace_migrations WHERE version='teacher-workspace-v1' FOR UPDATE")
        if db.fetchone():
            return
        db.execute('SELECT id FROM teachers ORDER BY id LIMIT 2')
        teachers = db.fetchall()
        db.execute('SELECT COUNT(*) AS count FROM students WHERE teacher_id IS NULL')
        legacy_students = db.fetchone()['count']
        db.execute('SELECT COUNT(*) AS count FROM questions WHERE course_id IS NULL')
        legacy_questions = db.fetchone()['count']
        db.execute('SELECT COUNT(*) AS count FROM exams WHERE course_id IS NULL')
        legacy_exams = db.fetchone()['count']
        if len(teachers) == 1 and (legacy_students or legacy_questions or legacy_exams):
            teacher = teachers[0]['id']
            db.execute("INSERT INTO classes(teacher_id,code,name) VALUES(%s,'LEGACY','Lớp hiện tại') ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)", (teacher,))
            class_id = db.lastrowid
            db.execute("INSERT INTO subjects(teacher_id,code,name) VALUES(%s,'LEGACY','Môn hiện tại') ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)", (teacher,))
            subject_id = db.lastrowid
            db.execute('INSERT INTO class_subjects(class_id,subject_id) VALUES(%s,%s) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)', (class_id, subject_id))
            course = db.lastrowid
            db.execute('UPDATE students SET teacher_id=%s WHERE teacher_id IS NULL', (teacher,))
            db.execute('UPDATE exams SET course_id=%s WHERE course_id IS NULL', (course,))
            db.execute('UPDATE questions SET course_id=%s WHERE course_id IS NULL', (course,))
            db.execute('INSERT IGNORE INTO enrollments(course_id,student_id) SELECT %s,id FROM students WHERE teacher_id=%s', (course, teacher))
            db.execute("""INSERT IGNORE INTO exam_students(exam_id,student_id,mssv,name,device_id)
                SELECT e.id,s.id,s.mssv,s.name,s.device_id FROM exams e CROSS JOIN students s
                WHERE e.course_id=%s AND s.teacher_id=%s AND e.status<>'draft'""", (course, teacher))
            db.execute("""INSERT IGNORE INTO question_students(question_id,student_id,mssv,name,device_id)
                SELECT q.id,s.id,s.mssv,s.name,s.device_id FROM questions q CROSS JOIN students s
                WHERE q.course_id=%s AND q.exam_id IS NULL AND s.teacher_id=%s AND q.status<>'draft'""", (course, teacher))
        db.execute("INSERT INTO workspace_migrations(version) VALUES('teacher-workspace-v1')")


def init_class_students(database):
    """Adopt existing course rosters as class rosters without touching exam history."""
    with database() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS class_students (
            class_id INT UNSIGNED NOT NULL, student_id INT UNSIGNED NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            PRIMARY KEY(class_id,student_id),
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(student_id) REFERENCES students(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''')
        db.execute("SELECT version FROM workspace_migrations WHERE version='class-students-v1' FOR UPDATE")
        if db.fetchone():
            return
        db.execute('''INSERT IGNORE INTO class_students(class_id,student_id)
            SELECT DISTINCT cs.class_id,en.student_id FROM enrollments en
            JOIN class_subjects cs ON cs.id=en.course_id
            JOIN classes c ON c.id=cs.class_id
            JOIN students s ON s.id=en.student_id AND s.teacher_id=c.teacher_id
            WHERE en.active=TRUE''')
        db.execute('''INSERT INTO enrollments(course_id,student_id,active)
            SELECT cs.id,cls.student_id,TRUE FROM class_students cls
            JOIN class_subjects cs ON cs.class_id=cls.class_id WHERE cls.active=TRUE
            ON DUPLICATE KEY UPDATE active=TRUE''')
        db.execute("INSERT INTO workspace_migrations(version) VALUES('class-students-v1')")


def init_exam_devices(database):
    """Keep physical devices reusable; exam_students owns each attempt's assignment."""
    with database() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS devices (
            teacher_id INT UNSIGNED NOT NULL,
            device_id VARCHAR(40) NOT NULL,
            protocol ENUM('BLE','WIFI') NOT NULL DEFAULT 'BLE',
            token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(teacher_id,device_id), UNIQUE KEY uq_device_token(token_hash),
            FOREIGN KEY(teacher_id) REFERENCES teachers(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''')
        db.execute("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='students' AND INDEX_NAME='uq_student_owner_device'")
        if db.fetchone():
            db.execute("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='students' AND INDEX_NAME='idx_student_owner_device'")
            if not db.fetchone():
                db.execute('ALTER TABLE students ADD KEY idx_student_owner_device(teacher_id,device_id)')
            db.execute('ALTER TABLE students DROP INDEX uq_student_owner_device')
        db.execute("SELECT COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='students' AND COLUMN_NAME='device_id'")
        if db.fetchone()['COLUMN_DEFAULT'] is None:
            db.execute("ALTER TABLE students ALTER COLUMN device_id SET DEFAULT ''")
        db.execute("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='exam_students' AND INDEX_NAME='uq_exam_device'")
        if not db.fetchone():
            db.execute('ALTER TABLE exam_students ADD UNIQUE KEY uq_exam_device(exam_id,device_id)')
    with database() as db:
        db.execute("SELECT version FROM workspace_migrations WHERE version='exam-devices-v1' FOR UPDATE")
        if db.fetchone():
            return
        db.execute('''INSERT IGNORE INTO devices(teacher_id,device_id)
            SELECT DISTINCT teacher_id,device_id FROM students
            WHERE teacher_id IS NOT NULL AND device_id<>%s''', ('',))
        db.execute('''INSERT IGNORE INTO devices(teacher_id,device_id)
            SELECT DISTINCT c.teacher_id,es.device_id FROM exam_students es
            JOIN exams e ON e.id=es.exam_id JOIN class_subjects cs ON cs.id=e.course_id
            JOIN classes c ON c.id=cs.class_id WHERE es.device_id<>%s''', ('',))
        db.execute('''SELECT s.teacher_id,s.device_id,dc.token_hash FROM device_credentials dc
            JOIN students s ON s.id=dc.student_id
            WHERE s.teacher_id IS NOT NULL AND s.device_id<>%s ORDER BY dc.created_at DESC''', ('',))
        for row in db.fetchall():
            db.execute('''UPDATE devices SET protocol='WIFI',token_hash=%s
                WHERE teacher_id=%s AND device_id=%s AND token_hash IS NULL''',
                (row['token_hash'], row['teacher_id'], row['device_id']))
        db.execute("INSERT INTO workspace_migrations(version) VALUES('exam-devices-v1')")


def init_student_device_protocol(database):
    """Infer existing ESP32 preferences once; later teacher choices remain untouched."""
    with database() as db:
        db.execute("SELECT version FROM workspace_migrations WHERE version='student-device-protocol-v1' FOR UPDATE")
        if db.fetchone():
            return
        db.execute('''UPDATE students s JOIN devices d
            ON d.teacher_id=s.teacher_id AND d.device_id=s.device_id
            SET s.preferred_protocol='WIFI'
            WHERE d.protocol='WIFI' AND d.token_hash IS NOT NULL''')
        db.execute("INSERT INTO workspace_migrations(version) VALUES('student-device-protocol-v1')")


def teacher_id(request):
    return request.state.teacher['id']


def own_class(db, class_id, owner, lock=False):
    db.execute('SELECT id,code,name FROM classes WHERE id=%s AND teacher_id=%s' +
               (' FOR UPDATE' if lock else ''), (class_id, owner))
    row = db.fetchone()
    if not row:
        raise HTTPException(404, 'Không tìm thấy lớp')
    return row


def class_idle(db, class_id):
    db.execute('''SELECT q.id FROM questions q JOIN class_subjects cs ON cs.id=q.course_id
        WHERE cs.class_id=%s AND q.status='open' LIMIT 1 FOR UPDATE''', (class_id,))
    if db.fetchone():
        raise HTTPException(409, 'Lớp đang thi. Hãy kết thúc bài thi trước khi đổi danh sách sinh viên.')


def own_course(db, course_id, owner, lock=False):
    db.execute('''SELECT cs.id,cs.class_id,cs.subject_id,c.name AS class_name,
        s.name AS subject_name,c.teacher_id FROM class_subjects cs
        JOIN classes c ON c.id=cs.class_id JOIN subjects s ON s.id=cs.subject_id
        WHERE cs.id=%s AND c.teacher_id=%s AND s.teacher_id=%s''' + (' FOR UPDATE' if lock else ''), (course_id, owner, owner))
    row = db.fetchone()
    if not row:
        raise HTTPException(404, 'Không tìm thấy lớp–môn hoặc bạn không có quyền')
    return row


def own_exam(db, exam_id, owner, lock=False):
    db.execute('''SELECT e.* FROM exams e JOIN class_subjects cs ON cs.id=e.course_id
        JOIN classes c ON c.id=cs.class_id WHERE e.id=%s AND c.teacher_id=%s''' + (' FOR UPDATE' if lock else ''), (exam_id, owner))
    row = db.fetchone()
    if not row:
        raise HTTPException(404, 'Không tìm thấy bài thi')
    return row


def own_question(db, question_id, owner, lock=False):
    db.execute('''SELECT q.* FROM questions q JOIN class_subjects cs ON cs.id=q.course_id
        JOIN classes c ON c.id=cs.class_id WHERE q.id=%s AND c.teacher_id=%s''' + (' FOR UPDATE' if lock else ''), (question_id, owner))
    row = db.fetchone()
    if not row:
        raise HTTPException(404, 'Không tìm thấy câu hỏi')
    return row


def course_idle(db, course_id):
    db.execute("SELECT id FROM questions WHERE course_id=%s AND status='open' LIMIT 1 FOR UPDATE", (course_id,))
    if db.fetchone():
        raise HTTPException(409, 'Không thể thay đổi danh sách khi lớp–môn đang thi. Hãy kết thúc lượt thi trước.')


def purge_question(db, question_id):
    """Delete a question and its submissions/roster in the caller's transaction."""
    db.execute('DELETE FROM answers WHERE question_id=%s', (question_id,))
    db.execute('DELETE FROM question_students WHERE question_id=%s', (question_id,))
    db.execute('DELETE FROM questions WHERE id=%s', (question_id,))


def purge_exam(db, exam_id):
    """Delete an exam and all dependent records in the caller's transaction."""
    db.execute('SELECT id FROM questions WHERE exam_id=%s FOR UPDATE', (exam_id,))
    question_ids = [row['id'] for row in db.fetchall()]
    db.execute('DELETE FROM device_reports WHERE exam_id=%s', (exam_id,))
    db.execute('DELETE FROM device_presence WHERE exam_id=%s', (exam_id,))
    for question_id in question_ids:
        purge_question(db, question_id)
    db.execute('DELETE FROM exam_students WHERE exam_id=%s', (exam_id,))
    db.execute('DELETE FROM exams WHERE id=%s', (exam_id,))


def purge_course(db, course_id):
    """Remove a class–subject, returning student IDs that may become orphaned."""
    db.execute('''SELECT student_id FROM enrollments WHERE course_id=%s
        UNION SELECT es.student_id FROM exam_students es JOIN exams e ON e.id=es.exam_id WHERE e.course_id=%s
        UNION SELECT qs.student_id FROM question_students qs JOIN questions q ON q.id=qs.question_id WHERE q.course_id=%s''',
        (course_id, course_id, course_id))
    candidates = {row['student_id'] for row in db.fetchall()}
    db.execute('SELECT id FROM exams WHERE course_id=%s FOR UPDATE', (course_id,))
    for exam in db.fetchall():
        purge_exam(db, exam['id'])
    db.execute('SELECT id FROM questions WHERE course_id=%s AND exam_id IS NULL FOR UPDATE', (course_id,))
    for question in db.fetchall():
        purge_question(db, question['id'])
    db.execute('DELETE FROM enrollments WHERE course_id=%s', (course_id,))
    db.execute('DELETE FROM class_subjects WHERE id=%s', (course_id,))
    return candidates


def purge_orphan_students(db, candidates, owner):
    """Keep teacher-owned profiles still used by another class or old result."""
    for student_id in sorted(candidates):
        db.execute('''SELECT s.id FROM students s WHERE s.id=%s AND s.teacher_id=%s
            AND NOT EXISTS(SELECT 1 FROM enrollments en WHERE en.student_id=s.id)
            AND NOT EXISTS(SELECT 1 FROM class_students cls WHERE cls.student_id=s.id)
            AND NOT EXISTS(SELECT 1 FROM exam_students es WHERE es.student_id=s.id)
            AND NOT EXISTS(SELECT 1 FROM question_students qs WHERE qs.student_id=s.id)
            AND NOT EXISTS(SELECT 1 FROM answers a WHERE a.student_id=s.id) FOR UPDATE''',
            (student_id, owner))
        if not db.fetchone():
            continue
        db.execute('DELETE FROM device_credentials WHERE student_id=%s', (student_id,))
        db.execute('DELETE FROM device_presence WHERE student_id=%s', (student_id,))
        db.execute('DELETE FROM device_reports WHERE student_id=%s', (student_id,))
        db.execute('DELETE FROM students WHERE id=%s AND teacher_id=%s', (student_id, owner))


def configure_workspace(app, database, changed):
    router = APIRouter(prefix='/api')

    @router.get('/classes')
    def classes(request: Request):
        with database() as db:
            db.execute('SELECT id,code,name FROM classes WHERE teacher_id=%s ORDER BY name,id', (teacher_id(request),))
            return db.fetchall()

    @router.get('/subjects')
    def subjects(request: Request):
        with database() as db:
            db.execute('SELECT id,code,name FROM subjects WHERE teacher_id=%s ORDER BY name,id', (teacher_id(request),))
            return db.fetchall()

    def named_routes(table, create_model):
        async def create(item: create_model, request: Request):
            try:
                with database() as db:
                    if table == 'classes' and item.subject_id is not None:
                        db.execute('SELECT id FROM subjects WHERE id=%s AND teacher_id=%s',
                                   (item.subject_id, teacher_id(request)))
                        if not db.fetchone():
                            raise HTTPException(404, 'Không tìm thấy môn học trong tài khoản của bạn')
                    db.execute(f'INSERT INTO {table}(teacher_id,code,name) VALUES(%s,%s,%s)', (teacher_id(request), item.code, item.name))
                    ident = db.lastrowid
                    result = {'id': ident, **item.model_dump()}
                    if table == 'classes' and item.subject_id is not None:
                        db.execute('INSERT INTO class_subjects(class_id,subject_id) VALUES(%s,%s)',
                                   (ident, item.subject_id))
                        result['course_id'] = db.lastrowid
            except pymysql.err.IntegrityError:
                raise HTTPException(409, 'Mã đã tồn tại trong tài khoản của bạn')
            await changed(teacher_id(request))
            return result

        async def edit(record_id: int, item: NamedIn, request: Request):
            try:
                with database() as db:
                    db.execute(f'SELECT id FROM {table} WHERE id=%s AND teacher_id=%s FOR UPDATE', (record_id, teacher_id(request)))
                    if not db.fetchone():
                        raise HTTPException(404, 'Không tìm thấy dữ liệu')
                    db.execute(f'UPDATE {table} SET code=%s,name=%s WHERE id=%s', (item.code, item.name, record_id))
            except pymysql.err.IntegrityError:
                raise HTTPException(409, 'Mã đã tồn tại trong tài khoản của bạn')
            await changed(teacher_id(request))
            return {'id': record_id, **item.model_dump()}

        async def delete(record_id: int, request: Request):
            with database() as db:
                db.execute(f'SELECT id FROM {table} WHERE id=%s AND teacher_id=%s FOR UPDATE', (record_id, teacher_id(request)))
                if not db.fetchone():
                    raise HTTPException(404, 'Không tìm thấy dữ liệu')
                if table == 'classes':
                    db.execute('SELECT student_id FROM class_students WHERE class_id=%s FOR UPDATE', (record_id,))
                    candidates = {row['student_id'] for row in db.fetchall()}
                    db.execute('SELECT id FROM class_subjects WHERE class_id=%s FOR UPDATE', (record_id,))
                    courses = [row['id'] for row in db.fetchall()]
                    for course_id in courses:
                        candidates.update(purge_course(db, course_id))
                    db.execute('DELETE FROM class_students WHERE class_id=%s', (record_id,))
                    db.execute('DELETE FROM classes WHERE id=%s', (record_id,))
                    purge_orphan_students(db, candidates, teacher_id(request))
                    result = {'deleted': True, 'courses_deleted': len(courses)}
                else:
                    db.execute('SELECT id FROM class_subjects WHERE subject_id=%s LIMIT 1 FOR UPDATE', (record_id,))
                    if db.fetchone():
                        raise HTTPException(409, 'Môn còn được gắn với lớp. Hãy gỡ liên kết trước khi xóa môn.')
                    db.execute('DELETE FROM subjects WHERE id=%s', (record_id,))
                    result = {'deleted': True}
            await changed(teacher_id(request))
            return result

        router.add_api_route('/'+table, create, methods=['POST'], status_code=201)
        router.add_api_route('/'+table+'/{record_id}', edit, methods=['PATCH'])
        router.add_api_route('/'+table+'/{record_id}', delete, methods=['DELETE'])

    named_routes('classes', ClassIn)
    named_routes('subjects', NamedIn)

    @router.get('/classes/{class_id}/courses')
    def courses(class_id: int, request: Request):
        with database() as db:
            db.execute('SELECT id FROM classes WHERE id=%s AND teacher_id=%s', (class_id, teacher_id(request)))
            if not db.fetchone():
                raise HTTPException(404, 'Không tìm thấy lớp')
            db.execute('''SELECT cs.id,cs.class_id,cs.subject_id,s.code,s.name FROM class_subjects cs
                JOIN subjects s ON s.id=cs.subject_id WHERE cs.class_id=%s ORDER BY s.name,cs.id''', (class_id,))
            return db.fetchall()

    @router.post('/classes/{class_id}/courses', status_code=201)
    async def add_course(class_id: int, item: CourseIn, request: Request):
        try:
            with database() as db:
                for table, ident in [('classes', class_id), ('subjects', item.subject_id)]:
                    db.execute(f'SELECT id FROM {table} WHERE id=%s AND teacher_id=%s FOR UPDATE', (ident, teacher_id(request)))
                    if not db.fetchone():
                        raise HTTPException(404, 'Không tìm thấy lớp hoặc môn')
                db.execute('INSERT INTO class_subjects(class_id,subject_id) VALUES(%s,%s)', (class_id, item.subject_id))
                ident = db.lastrowid
                db.execute('''INSERT INTO enrollments(course_id,student_id,active)
                    SELECT %s,student_id,TRUE FROM class_students WHERE class_id=%s AND active=TRUE
                    ON DUPLICATE KEY UPDATE active=TRUE''', (ident, class_id))
        except pymysql.err.IntegrityError:
            raise HTTPException(409, 'Môn này đã được thêm vào lớp')
        await changed(teacher_id(request))
        return {'id': ident, 'class_id': class_id, 'subject_id': item.subject_id}

    @router.delete('/courses/{course_id}')
    async def delete_course(course_id: int, request: Request):
        with database() as db:
            own_course(db, course_id, teacher_id(request), True)
            for table in ['exams', 'questions']:
                db.execute(f'SELECT 1 FROM {table} WHERE course_id=%s LIMIT 1', (course_id,))
                if db.fetchone():
                    raise HTTPException(409, 'Chỉ gỡ môn chưa có bài thi hoặc câu hỏi để bảo vệ lịch sử')
            db.execute('DELETE FROM enrollments WHERE course_id=%s', (course_id,))
            db.execute('DELETE FROM class_subjects WHERE id=%s', (course_id,))
        await changed(teacher_id(request))
        return {'deleted': True}

    app.include_router(router)
