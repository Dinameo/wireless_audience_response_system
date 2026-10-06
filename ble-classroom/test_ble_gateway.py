"""Offline checks for multi-board identity and pre-exam connection reporting."""
import unittest

from ble_gateway import Session


class FakeClient:
    def __init__(self):
        self.commands = []

    async def write_gatt_char(self, _uuid, data, response):
        assert response
        self.commands.append(data.decode("ascii"))


class FakeApi:
    def __init__(self):
        self.online_reports = []

    async def online(self, device_id, gateway_id, connected):
        self.online_reports.append((device_id, gateway_id, connected))

    async def current(self):
        return None


class GatewayIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_boards_have_independent_sessions_before_exam(self):
        claims = {}
        api = FakeApi()
        first = Session(FakeClient(), api, "AA:01", claims)
        second = Session(FakeClient(), api, "AA:02", claims)
        await first.handle_message("ID:NRF-0000000000000001")
        await second.handle_message("ID:NRF-0000000000000002")
        await first.sync_question()
        await second.sync_question()
        self.assertEqual(claims, {
            "NRF-0000000000000001": "AA:01",
            "NRF-0000000000000002": "AA:02",
        })
        self.assertEqual(api.online_reports, [
            ("NRF-0000000000000001", "linux-ble-gateway:AA:01", True),
            ("NRF-0000000000000002", "linux-ble-gateway:AA:02", True),
        ])

    async def test_duplicate_id_is_rejected(self):
        claims = {"NRF-0000000000000001": "AA:01"}
        client = FakeClient()
        second = Session(client, FakeApi(), "AA:02", claims)
        await second.handle_message("ID:NRF-0000000000000001")
        self.assertIsNone(second.device_id)
        self.assertEqual(client.commands, ["REJECT"])


class ExamRetakeTests(unittest.TestCase):
    def test_reset_exam_for_restart_clears_old_attempts(self):
        from exam_api import reset_exam_for_restart

        class FakeDB:
            def __init__(self):
                self.calls = []

            def execute(self, sql, params=None):
                self.calls.append((sql, params))

            def fetchall(self):
                return [{"id": 10}, {"id": 11}]

        db = FakeDB()
        reset_exam_for_restart(db, 42)

        self.assertTrue(any("DELETE FROM answers" in sql for sql, _ in db.calls))
        self.assertTrue(any("DELETE FROM exam_students" in sql for sql, _ in db.calls))
        self.assertTrue(any("UPDATE questions SET status='draft'" in sql for sql, _ in db.calls))
        self.assertTrue(any("UPDATE exams SET status='draft'" in sql for sql, _ in db.calls))


if __name__ == "__main__":
    unittest.main()
