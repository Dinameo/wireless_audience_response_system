CREATE TABLE IF NOT EXISTS teachers (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS teacher_sessions (
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    teacher_id INT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    INDEX idx_sessions_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS classes (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    teacher_id INT UNSIGNED NOT NULL,
    code VARCHAR(30) NOT NULL,
    name VARCHAR(120) NOT NULL,
    UNIQUE KEY uq_class_owner_code (teacher_id, code),
    FOREIGN KEY (teacher_id) REFERENCES teachers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subjects (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    teacher_id INT UNSIGNED NOT NULL,
    code VARCHAR(30) NOT NULL,
    name VARCHAR(120) NOT NULL,
    UNIQUE KEY uq_subject_owner_code (teacher_id, code),
    FOREIGN KEY (teacher_id) REFERENCES teachers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS class_subjects (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    class_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    UNIQUE KEY uq_class_subject (class_id, subject_id),
    FOREIGN KEY (class_id) REFERENCES classes(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS exams (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    title VARCHAR(200) NOT NULL,
    status ENUM('draft', 'open', 'closed') NOT NULL DEFAULT 'draft',
    current_position INT UNSIGNED NULL,
    course_id INT UNSIGNED NULL,
    revision INT UNSIGNED NOT NULL DEFAULT 0,
    time_limit_seconds INT UNSIGNED NULL,
    deadline_at DATETIME(3) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_exams_status (status),
    UNIQUE KEY uq_exam_course_title (course_id, title),
    CONSTRAINT fk_exam_course FOREIGN KEY (course_id) REFERENCES class_subjects(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS students (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    mssv VARCHAR(30) NOT NULL,
    name VARCHAR(120) NOT NULL,
    device_id VARCHAR(40) NOT NULL DEFAULT '',
    preferred_protocol ENUM('BLE', 'WIFI') NOT NULL DEFAULT 'BLE',
    teacher_id INT UNSIGNED NULL,
    revision INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_student_owner_mssv (teacher_id, mssv),
    KEY idx_student_owner_device (teacher_id, device_id),
    CONSTRAINT fk_student_owner FOREIGN KEY (teacher_id) REFERENCES teachers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS devices (
    teacher_id INT UNSIGNED NOT NULL,
    device_id VARCHAR(40) NOT NULL,
    protocol ENUM('BLE', 'WIFI') NOT NULL DEFAULT 'BLE',
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (teacher_id, device_id),
    UNIQUE KEY uq_device_token (token_hash),
    FOREIGN KEY (teacher_id) REFERENCES teachers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS enrollments (
    course_id INT UNSIGNED NOT NULL,
    student_id INT UNSIGNED NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (course_id, student_id),
    FOREIGN KEY (course_id) REFERENCES class_subjects(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS class_students (
    class_id INT UNSIGNED NOT NULL,
    student_id INT UNSIGNED NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (class_id, student_id),
    FOREIGN KEY (class_id) REFERENCES classes(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS device_presence (
    student_id INT UNSIGNED PRIMARY KEY,
    exam_id INT UNSIGNED NULL,
    protocol ENUM('BLE', 'USB', 'WIFI', 'SIMULATED') NOT NULL,
    gateway_id VARCHAR(64) NOT NULL,
    connected BOOLEAN NOT NULL,
    rssi SMALLINT NULL,
    last_seen DATETIME(3) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ble_device_inventory (
    device_id VARCHAR(40) NOT NULL PRIMARY KEY,
    gateway_id VARCHAR(64) NOT NULL,
    connected BOOLEAN NOT NULL,
    last_seen DATETIME(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS device_credentials (
    student_id INT UNSIGNED PRIMARY KEY,
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS device_reports (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id INT UNSIGNED NOT NULL,
    exam_id INT UNSIGNED NULL,
    protocol ENUM('BLE', 'USB', 'WIFI', 'SIMULATED') NOT NULL,
    connected BOOLEAN NOT NULL,
    rssi SMALLINT NULL,
    received_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_device_reports_student_time (student_id, received_at),
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS questions (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    text VARCHAR(1000) NOT NULL,
    a VARCHAR(500) NOT NULL,
    b VARCHAR(500) NOT NULL,
    c VARCHAR(500) NOT NULL,
    d VARCHAR(500) NOT NULL,
    correct_choice ENUM('A', 'B', 'C', 'D') NOT NULL,
    points DECIMAL(10,6) NOT NULL,
    status ENUM('draft', 'open', 'closed') NOT NULL DEFAULT 'draft',
    exam_id INT UNSIGNED NULL,
    position INT UNSIGNED NULL,
    course_id INT UNSIGNED NULL,
    open_slot TINYINT GENERATED ALWAYS AS (
        CASE WHEN status = 'open' THEN 1 ELSE NULL END
    ) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY only_one_open_question (open_slot),
    KEY idx_questions_status (status),
    UNIQUE KEY uq_exam_position (exam_id, position),
    CONSTRAINT fk_questions_exam FOREIGN KEY (exam_id) REFERENCES exams (id),
    CONSTRAINT fk_question_course FOREIGN KEY (course_id) REFERENCES class_subjects (id),
    CONSTRAINT chk_questions_points CHECK (points > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS exam_students (
    exam_id INT UNSIGNED NOT NULL,
    student_id INT UNSIGNED NOT NULL,
    mssv VARCHAR(30) NOT NULL,
    name VARCHAR(120) NOT NULL,
    device_id VARCHAR(40) NOT NULL,
    PRIMARY KEY (exam_id, student_id),
    UNIQUE KEY uq_exam_device (exam_id, device_id),
    FOREIGN KEY (exam_id) REFERENCES exams(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS question_students (
    question_id INT UNSIGNED NOT NULL,
    student_id INT UNSIGNED NOT NULL,
    mssv VARCHAR(30) NOT NULL,
    name VARCHAR(120) NOT NULL,
    device_id VARCHAR(40) NOT NULL,
    PRIMARY KEY (question_id, student_id),
    FOREIGN KEY (question_id) REFERENCES questions(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workspace_migrations (
    version VARCHAR(40) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS answers (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    question_id INT UNSIGNED NOT NULL,
    student_id INT UNSIGNED NOT NULL,
    choice ENUM('A', 'B', 'C', 'D') NOT NULL,
    sequence INT UNSIGNED NOT NULL,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_answer_per_student (question_id, student_id),
    KEY idx_answers_student_id (student_id),
    CONSTRAINT fk_answers_question FOREIGN KEY (question_id) REFERENCES questions (id),
    CONSTRAINT fk_answers_student FOREIGN KEY (student_id) REFERENCES students (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
