import asyncio
import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "ble-classroom"
sys.path.insert(0, str(APP_DIR))

from ble_gateway import ApiError, Session


class FakeClient:
    def __init__(self):
        self.writes = []

    async def write_gatt_char(self, _uuid, data, response):
        assert response
        self.writes.append(data.decode())


class FakeApi:
    def __init__(self):
        self.qid = 10
        self.answers = []
        self.reject_answer = False

    async def current(self):
        return {"question_id": self.qid} if self.qid else None

    async def online(self, device_id, gateway_id, connected):
        return {"device_id": device_id, "gateway_id": gateway_id, "connected": connected}

    async def presence(self, question_id, device_id, connected):
        if device_id != "BTN-01":
            raise ApiError(403, "not enrolled")
        return {"accepted": True}

    async def answer(self, question_id, device_id, choice, sequence):
        self.answers.append((question_id, device_id, choice, sequence))
        if self.reject_answer:
            raise ApiError(409, "closed")
        return {"accepted": True}


class GatewayProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_id_next_answer_ack_and_new_question(self):
        client, api = FakeClient(), FakeApi()
        session = Session(client, api, "AA:01", {})
        await session.handle_message("ID:BTN-01")
        await session.sync_question()
        self.assertEqual(client.writes, ["ACCEPT", "NEXT"])
        await session.handle_message("ANS:C")
        self.assertEqual(api.answers, [(10, "BTN-01", "C", 0)])
        self.assertEqual(client.writes[-1], "ACK")
        await session.handle_message("ANS:A")
        self.assertEqual(len(api.answers), 1)
        api.qid = 11
        await session.sync_question()
        self.assertEqual(client.writes[-1], "NEXT")
        await session.handle_message("ANS:B")
        self.assertEqual(api.answers[-1], (11, "BTN-01", "B", 1))

    async def test_rejected_answer_never_acknowledged(self):
        client, api = FakeClient(), FakeApi()
        session = Session(client, api, "AA:01", {})
        await session.handle_message("ID:BTN-01")
        await session.sync_question()
        api.reject_answer = True
        await session.handle_message("ANS:D")
        self.assertNotIn("ACK", client.writes)

    async def test_unknown_device_is_rejected(self):
        client, api = FakeClient(), FakeApi()
        session = Session(client, api, "AA:01", {})
        await session.handle_message("ID:UNKNOWN")
        await session.sync_question()
        self.assertEqual(client.writes, ["REJECT"])


if __name__ == "__main__":
    unittest.main()
