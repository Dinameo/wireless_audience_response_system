import unittest

from exam_api import retake_root, unique_retake_title


class FakeExamCursor:
    def __init__(self, titles):
        self.titles = titles
        self.found = None

    def execute(self, sql, values):
        course_id, title = values[:2]
        exclude_id = values[2] if len(values) > 2 else None
        self.found = next(({'id': exam_id} for exam_id, course, name in self.titles
                           if course == course_id and name.casefold() == title.casefold()
                           and exam_id != exclude_id), None)

    def fetchone(self):
        return self.found


class ExamTitleTests(unittest.TestCase):
    def test_repeated_retake_suffix_is_removed(self):
        self.assertEqual(retake_root('iot26 · Thi lại · Thi lại'), ('iot26', 2))
        self.assertEqual(retake_root('iot26 · Thi lại (2)'), ('iot26', 1))

    def test_retake_uses_one_label_and_next_free_number(self):
        db = FakeExamCursor([(11, 6, 'iot26 · Thi lại'), (15, 6, 'iot26 · Thi lại (2)'),
                             (20, 7, 'iot26 · Thi lại (3)')])
        self.assertEqual(unique_retake_title(db, 6, 'iot26 · Thi lại · Thi lại'),
                         'iot26 · Thi lại (3)')

    def test_long_source_title_stays_within_database_limit(self):
        title = unique_retake_title(FakeExamCursor([]), 6, 'x' * 200)
        self.assertEqual(len(title), 200)
        self.assertTrue(title.endswith(' · Thi lại'))


if __name__ == '__main__':
    unittest.main()
