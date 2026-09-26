import re
from io import BytesIO
from docx import Document

QUESTION_RE = re.compile(r"^\?(\d+)\s*(.+)$")
OPTION_RE = re.compile(r"^([A-D])[\.\)]\s*(.+)$", re.IGNORECASE)
ANSWER_RE = re.compile(r"^(?:ANS\s*:|=)\s*([A-D])\s*$", re.IGNORECASE)

def _validate(q):
    missing = [x for x in "ABCD" if x not in q["options"]]
    if missing:
        raise ValueError(f"Câu {q['number']} thiếu đáp án: {', '.join(missing)}")
    if q["correct_option"] not in {"A", "B", "C", "D"}:
        raise ValueError(f"Câu {q['number']} thiếu dòng đáp án đúng, ví dụ ANS: B")

def _parse_lines(lines):
    questions = []
    current = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        q = QUESTION_RE.match(line)
        if q:
            if current:
                _validate(current)
                questions.append(current)
            current = {
                "number": int(q.group(1)),
                "text": q.group(2).strip(),
                "options": {},
                "correct_option": None,
            }
            continue

        if current is None:
            continue

        opt = OPTION_RE.match(line)
        if opt:
            current["options"][opt.group(1).upper()] = opt.group(2).strip()
            continue

        ans = ANSWER_RE.match(line)
        if ans:
            current["correct_option"] = ans.group(1).upper()
            continue

        if not current["options"]:
            current["text"] += " " + line

    if current:
        _validate(current)
        questions.append(current)

    if not questions:
        raise ValueError("Không tìm thấy câu hỏi theo cú pháp ?1, A., B., C., D., ANS: A")
    return questions

def parse_question_file(filename: str, data: bytes):
    lower = filename.lower()
    if lower.endswith(".txt"):
        return _parse_lines(data.decode("utf-8-sig").splitlines())
    if lower.endswith(".docx"):
        doc = Document(BytesIO(data))
        return _parse_lines([p.text for p in doc.paragraphs])
    raise ValueError("Phiên bản đầu chỉ hỗ trợ .txt và .docx")
