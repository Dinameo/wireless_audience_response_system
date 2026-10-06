"""Multi-device BLE quiz gateway for the nRF52840 quiz sketch.

Run on the Linux host (not inside Docker): python ble_gateway.py
BLE is unencrypted here; use in a trusted classroom for testing, not as a
tamper-resistant examination system.
"""
import argparse
import asyncio
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError


SERVICE_UUID = "6a2f7ad9-2c64-4f13-8a7e-5b5a0a660d6e"
TX_UUID = "d1484dd8-6d20-4d49-a6f1-4638f9d44c25"  # notify from board
RX_UUID = "b0f9c817-2d2b-4f28-9ae5-5dd6ca5f5d48"  # write to board
LOG = logging.getLogger("ble-gateway")


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class WebApi:
    def __init__(self, base_url, key):
        self.base_url = base_url.rstrip("/")
        self.key = key

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(
            self.base_url + path,
            data=data,
            headers={"X-Gateway-Key": self.key, "Content-Type": "application/json"},
            method="GET" if data is None else "POST",
        )
        try:
            with urlopen(req, timeout=5) as response:
                return json.load(response)
        except HTTPError as error:
            raise ApiError(error.code, error.read().decode("utf-8", "replace")) from error
        except URLError as error:
            raise ApiError(0, str(error)) from error

    async def current(self):
        try:
            return await asyncio.to_thread(self.request, "/api/gateway/current")
        except ApiError as error:
            if error.code == 409:
                return None
            raise

    async def presence(self, question_id, device_id, connected):
        return await asyncio.to_thread(self.request, "/api/gateway/presence", {
            "question_id": question_id, "device_id": device_id,
            "protocol": "BLE", "gateway_id": "linux-ble-gateway",
            "connected": connected, "rssi": None,
        })

    async def online(self, device_id, gateway_id, connected):
        return await asyncio.to_thread(self.request, "/api/gateway/online", {
            "device_id": device_id, "gateway_id": gateway_id, "connected": connected,
        })

    async def answer(self, question_id, device_id, choice, sequence):
        return await asyncio.to_thread(self.request, "/api/answers", {
            "question_id": question_id, "device_id": device_id,
            "choice": choice, "sequence": sequence,
        })


class Session:
    def __init__(self, client, api, address, claimed_ids):
        self.client = client
        self.api = api
        self.address = address
        self.claimed_ids = claimed_ids
        self.gateway_id = "linux-ble-gateway:" + address
        self.queue = asyncio.Queue()
        self.device_id = None
        self.accepted = False
        self.question_id = None  # captured when NEXT was written, never re-read for ANS
        self.answered = False
        self.sequence = 0
        self.last_presence = 0.0
        self.last_online = 0.0
        self.last_reject_question = None

    def notification(self, _sender, data):
        message = bytes(data).decode("ascii", "replace").strip()
        self.queue.put_nowait(message)

    async def command(self, value):
        await self.client.write_gatt_char(RX_UUID, value.encode("ascii"), response=True)
        LOG.info("BLE -> %s", value)

    async def handle_message(self, message):
        if message.startswith("ID:"):
            candidate = message[3:].strip()
            if not candidate or len(candidate) > 40:
                await self.command("REJECT")
                return
            if candidate == self.device_id:
                return  # firmware repeats its ID until the exam starts
            LOG.info("BLE <- %s", message)
            if self.claimed_ids.get(candidate, self.address) != self.address:
                LOG.warning("Duplicate device ID %s from %s; rejected", candidate, self.address)
                await self.command("REJECT")
                return
            if self.device_id != candidate:
                if self.device_id and self.claimed_ids.get(self.device_id) == self.address:
                    del self.claimed_ids[self.device_id]
                self.device_id = candidate
                self.claimed_ids[candidate] = self.address
                self.accepted = False
                self.question_id = None
                self.last_reject_question = None
                self.last_online = 0.0
            return

        LOG.info("BLE <- %s", message)
        if not message.startswith("ANS:") or len(message) != 5:
            return
        choice = message[4]
        if choice not in "ABCD" or not self.accepted or self.question_id is None or self.answered:
            LOG.warning("Ignored answer outside an open slot: %s", message)
            return
        # Never ask /current here: the question may have auto-advanced meanwhile.
        captured_id = self.question_id
        try:
            await self.api.answer(captured_id, self.device_id, choice, self.sequence)
        except ApiError as error:
            LOG.warning("Web rejected answer for question %s: HTTP %s %s",
                        captured_id, error.code, error)
            # No ACK: a rejected/late answer must not look successful on the board.
            return
        self.answered = True
        self.sequence += 1
        await self.command("ACK")
        LOG.info("Accepted %s = %s for question %s", self.device_id, choice, captured_id)

    async def sync_question(self):
        now = asyncio.get_running_loop().time()
        if self.device_id is not None and now - self.last_online >= 5:
            await self.api.online(self.device_id, self.gateway_id, True)
            self.last_online = now
        current = await self.api.current()
        if current is None:
            if self.accepted and self.question_id is not None:
                await self.command("REJECT")  # end-of-exam also stops blinking
                self.accepted = False
                self.question_id = None
            return
        qid = current["question_id"]
        if self.device_id is None:
            return
        if not self.accepted:
            if self.last_reject_question == qid:
                return
            try:
                await self.api.presence(qid, self.device_id, True)
            except ApiError as error:
                if error.code == 403:
                    await self.command("REJECT")
                    self.last_reject_question = qid
                    LOG.warning("Device %s not in this exam roster", self.device_id)
                    return
                raise
            await self.command("ACCEPT")
            self.accepted = True
            self.last_presence = asyncio.get_running_loop().time()
        if self.question_id != qid:
            await self.command("NEXT")
            self.question_id = qid
            self.answered = False
            LOG.info("Question %s is open for %s", qid, self.device_id)
        now = asyncio.get_running_loop().time()
        if now - self.last_presence >= 5:
            try:
                await self.api.presence(qid, self.device_id, True)
                self.last_presence = now
            except ApiError as error:
                if error.code == 409:
                    return  # question may have advanced during the request
                raise

    async def run(self):
        await self.client.start_notify(TX_UUID, self.notification)
        LOG.info("Notifications enabled; waiting for ID")
        try:
            while self.client.is_connected:
                try:
                    message = await asyncio.wait_for(self.queue.get(), timeout=0.8)
                    await self.handle_message(message)
                except asyncio.TimeoutError:
                    pass
                try:
                    await self.sync_question()
                except ApiError as error:
                    LOG.warning("Web API HTTP %s: %s", error.code, error)
                    await asyncio.sleep(2)
        finally:
            if self.device_id and self.claimed_ids.get(self.device_id) == self.address:
                del self.claimed_ids[self.device_id]
            if self.device_id:
                try:
                    await self.api.online(self.device_id, self.gateway_id, False)
                except ApiError:
                    pass
            if self.accepted and self.question_id is not None and self.device_id:
                try:
                    await self.api.presence(self.question_id, self.device_id, False)
                except ApiError:
                    pass


async def connect_device(device, api, address, claimed_ids, ready):
    try:
        LOG.info("Connecting to %s (%s)", device.name, address)
        async with BleakClient(device, timeout=15) as client:
            if not any(service.uuid.lower() == SERVICE_UUID for service in client.services):
                LOG.warning("Wrong firmware on %s: Quiz service UUID absent", address)
                return
            ready.set()
            await Session(client, api, address, claimed_ids).run()
    except (BleakError, OSError, TimeoutError, RuntimeError) as error:
        LOG.warning("BLE connection failed for %s: %s", address, error)
    finally:
        ready.set()


async def gateway(args):
    api = WebApi(args.server, args.key)
    while True:
        try:
            current = await api.current()
            LOG.info("Web ready; current question: %s", current)
            break
        except ApiError as error:
            if error.code == 401:
                raise SystemExit(f"Web API error HTTP {error.code}: {error}") from error
            LOG.warning("Web unavailable (HTTP %s); retrying: %s", error.code, error)
            await asyncio.sleep(5)

    tasks = {}     # BLE address -> independent connection/session task
    retry_after = {}
    claimed_ids = {}  # one active BLE address per logical student device ID
    loop = asyncio.get_running_loop()
    LOG.info("Scanning for BLE_QUIZ_CLIENT (up to %s concurrent boards)",
             args.max_connections)
    while True:
        now = loop.time()
        for address, task in list(tasks.items()):
            if task.done():
                try:
                    task.result()
                except Exception:
                    LOG.exception("Unexpected gateway error for %s", address)
                del tasks[address]
                retry_after[address] = now + 10
        if len(tasks) >= args.max_connections:
            await asyncio.sleep(2)
            continue
        try:
            # Stop scanning before each connection attempt. Some adapters cannot
            # establish a connection while actively scanning.
            found = await BleakScanner.discover(timeout=5, return_adv=True,
                                                scanning_mode="active")
        except (BleakError, OSError, RuntimeError) as error:
            LOG.warning("BLE scanner failed; retrying: %s", error)
            await asyncio.sleep(3)
            continue
        for device, advertisement in found.values():
            address = device.address
            name = advertisement.local_name or device.name
            if args.address:
                if address.lower() != args.address.lower():
                    continue
            elif name != "BLE_QUIZ_CLIENT":
                continue
            if address in tasks or loop.time() < retry_after.get(address, 0):
                continue
            if len(tasks) >= args.max_connections:
                break
            ready = asyncio.Event()
            tasks[address] = asyncio.create_task(
                connect_device(device, api, address, claimed_ids, ready))
            try:
                await asyncio.wait_for(ready.wait(), timeout=18)
            except asyncio.TimeoutError:
                LOG.warning("Connection setup timed out for %s", address)
        await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Bridge nRF52840 Quiz BLE clients to web")
    parser.add_argument("--server", default=os.getenv("SERVER_URL", "http://localhost:8000"))
    parser.add_argument("--key", default=os.getenv("GATEWAY_KEY"))
    parser.add_argument("--address", help="Optional BLE address, useful with multiple boards")
    parser.add_argument("--max-connections", type=int, default=8,
                        help="Maximum simultaneous BLE boards on this adapter (default: 8)")
    args = parser.parse_args()
    if not args.key:
        parser.error("Set GATEWAY_KEY to the same value as the web container")
    if args.max_connections < 1:
        parser.error("--max-connections must be at least 1")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(gateway(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
