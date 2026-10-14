"""Offline checks for multi-board identity and pre-exam connection reporting."""
import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from ble_gateway import (PDF_CHARACTERISTIC_UUID, PDF_PROFILE, PDF_SERVICE_UUID,
                         RX_UUID, SPLIT_PROFILE, SERVICE_UUID, Session, TX_UUID,
                         ApiError, select_profile)
from exam_api import BleOnlineIn, ble_authorization


class FakeClient:
    def __init__(self):
        self.commands = []
        self.write_uuids = []

    async def write_gatt_char(self, uuid, data, response):
        assert response
        self.write_uuids.append(uuid)
        self.commands.append(data.decode("ascii"))


class FakeApi:
    def __init__(self):
        self.online_reports = []
        self.current_question = None
        self.presence_reports = []
        self.answers = []
        self.reject_presence = False
        self.reject_authorization = False

    async def authorize(self, device_id):
        return {'authorized': not self.reject_authorization,
                'reason': 'not_in_roster' if self.reject_authorization else 'known_device'}

    async def online(self, device_id, gateway_id, connected, profile=None, authorized=False):
        self.online_reports.append((device_id, gateway_id, connected, profile, authorized))

    async def current(self):
        return self.current_question

    async def presence(self, question_id, device_id, connected):
        if self.reject_presence:
            raise ApiError(403, "not in roster")
        self.presence_reports.append((question_id, device_id, connected))

    async def answer(self, question_id, device_id, choice, sequence):
        self.answers.append((question_id, device_id, choice, sequence))


def service(uuid, *characteristics):
    return SimpleNamespace(uuid=uuid, characteristics=[
        SimpleNamespace(uuid=characteristic, properties=properties)
        for characteristic, properties in characteristics
    ])


class GattProfileTests(unittest.TestCase):
    def test_existing_two_characteristic_firmware_is_supported(self):
        services = [service(SERVICE_UUID, (TX_UUID, ["notify"]),
                            (RX_UUID, ["write"]))]
        self.assertEqual(select_profile(services), SPLIT_PROFILE)

    def test_pdf_single_characteristic_firmware_is_supported(self):
        services = [service(PDF_SERVICE_UUID,
                            (PDF_CHARACTERISTIC_UUID, ["notify", "write"]))]
        self.assertEqual(select_profile(services), PDF_PROFILE)

    def test_same_name_without_complete_quiz_gatt_is_rejected(self):
        self.assertIsNone(select_profile([service(PDF_SERVICE_UUID,
            (PDF_CHARACTERISTIC_UUID, ["notify"]))]))

    def test_web_accepts_only_known_gatt_profile_labels(self):
        report = BleOnlineIn(device_id="STUDENT_001", gateway_id="linux-ble-gateway:AA:03",
                             connected=True, gatt_profile="pdf", authorized=True)
        self.assertEqual(report.gatt_profile, "pdf")
        self.assertTrue(report.authorized)
        with self.assertRaises(ValidationError):
            BleOnlineIn(device_id="STUDENT_001", gateway_id="linux-ble-gateway:AA:03",
                        connected=True, gatt_profile="unknown")


class GatewayIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_boards_have_independent_sessions_before_exam(self):
        claims = {}
        api = FakeApi()
        first = Session(FakeClient(), api, "AA:01", claims)
        second = Session(FakeClient(), api, "AA:02", claims)
        await first.handle_message("ID:BLE-001")
        await second.handle_message("ID:BLE-002")
        await first.sync_question()
        await second.sync_question()
        self.assertEqual(claims, {
            "BLE-001": "AA:01",
            "BLE-002": "AA:02",
        })
        self.assertEqual(api.online_reports, [
            ("BLE-001", "linux-ble-gateway:AA:01", True, "split", True),
            ("BLE-002", "linux-ble-gateway:AA:02", True, "split", True),
        ])
        self.assertEqual(first.client.commands, ["ACCEPT"])
        self.assertEqual(second.client.commands, ["ACCEPT"])

    async def test_duplicate_id_is_rejected(self):
        claims = {"BLE-001": "AA:01"}
        client = FakeClient()
        second = Session(client, FakeApi(), "AA:02", claims)
        await second.handle_message("ID:BLE-001")
        self.assertIsNone(second.device_id)
        self.assertEqual(client.commands, ["REJECT"])

    async def test_pdf_client_accepts_id_then_waits_for_next_and_acks_answer(self):
        api = FakeApi()
        client = FakeClient()
        session = Session(client, api, "AA:03", {}, PDF_PROFILE)
        await session.handle_message("ID:STUDENT_001")
        await session.sync_question()
        self.assertEqual(client.commands, ["ACCEPT"])  # Authentication precedes NEXT.
        self.assertEqual(api.online_reports[-1][-2:], ("pdf", True))

        api.current_question = {"question_id": 143, "exam_id": 8, "position": 1}
        await session.sync_question()
        self.assertEqual(client.commands, ["ACCEPT", "NEXT"])
        self.assertEqual(client.write_uuids, [PDF_CHARACTERISTIC_UUID] * 2)
        self.assertIn((143, "STUDENT_001", True), api.presence_reports)

        await session.handle_message("ANS:A")
        await session.handle_message("ANS:B")
        self.assertEqual(api.answers, [(143, "STUDENT_001", "A", 0)])
        self.assertEqual(client.commands[-1], "ACK")

        api.current_question = None
        await session.sync_question()
        self.assertEqual(client.commands[-1], "DISCONNECT")

    async def test_pdf_client_is_rejected_when_not_in_exam_roster(self):
        api = FakeApi()
        api.current_question = {"question_id": 143, "exam_id": 8, "position": 1}
        api.reject_authorization = True
        client = FakeClient()
        session = Session(client, api, "AA:03", {}, PDF_PROFILE)
        await session.handle_message("ID:STUDENT_001")
        await session.sync_question()
        self.assertEqual(client.commands, ["REJECT"])
        self.assertFalse(session.accepted)

    async def test_rejected_id_can_be_accepted_after_registration(self):
        api = FakeApi()
        api.reject_authorization = True
        client = FakeClient()
        session = Session(client, api, "AA:04", {})
        await session.handle_message("ID:NEW-BOARD")
        self.assertEqual(client.commands, ["REJECT"])
        api.reject_authorization = False
        session.last_auth_attempt = 0
        await session.handle_message("ID:NEW-BOARD")
        self.assertEqual(client.commands, ["REJECT", "ACCEPT"])
        self.assertTrue(session.accepted)

    async def test_running_session_rejects_revoked_id_before_next(self):
        api = FakeApi()
        client = FakeClient()
        session = Session(client, api, "AA:05", {})
        await session.handle_message("ID:BLE-005")
        api.reject_authorization = True
        api.current_question = {"question_id": 144, "exam_id": 8, "position": 1}
        session.last_online = 0
        await session.sync_question()
        self.assertEqual(client.commands, ["ACCEPT", "REJECT"])
        self.assertFalse(session.accepted)


class BleAuthorizationTests(unittest.TestCase):
    class FakeDB:
        def __init__(self, registered=True, question=None, in_roster=True):
            self.registered = registered
            self.question = question
            self.in_roster = in_roster
            self.result = None
            self.device_params = None

        def execute(self, sql, params=None):
            if 'FROM devices' in sql:
                self.device_params = params
                self.result = {'1': 1} if self.registered else None
            elif 'FROM questions' in sql:
                self.result = self.question
            elif 'FROM exam_students' in sql or 'FROM question_students' in sql:
                self.result = {'1': 1} if self.in_roster else None
            else:
                raise AssertionError(sql)

        def fetchone(self):
            return self.result

    def test_known_ble_board_is_accepted_before_exam(self):
        result = ble_authorization(self.FakeDB(), 'STUDENT_001')
        self.assertEqual(result, {'authorized': True, 'reason': 'known_device'})

    def test_unknown_board_is_rejected(self):
        result = ble_authorization(self.FakeDB(registered=False), 'NOT-REGISTERED')
        self.assertEqual(result['reason'], 'unknown_device')

    def test_open_exam_rejects_board_outside_roster(self):
        db = self.FakeDB(question={'id': 143, 'exam_id': 8, 'teacher_id': 7}, in_roster=False)
        result = ble_authorization(db, 'BLE-002')
        self.assertEqual(result['reason'], 'not_in_roster')
        self.assertEqual(db.device_params, (7, 'BLE-002'))

    def test_open_exam_accepts_assigned_board(self):
        db = self.FakeDB(question={'id': 143, 'exam_id': 8, 'teacher_id': 7}, in_roster=True)
        self.assertTrue(ble_authorization(db, 'BLE-001')['authorized'])


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
