"""Offline tests: host radio commands, strict protocol, and authenticated API."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request

import host_radio
import radio_api


class RadioCommandTests(unittest.TestCase):
    def test_status_distinguishes_power_from_connection(self):
        def command(*args):
            if args == ('nmcli', 'radio', 'wifi'):
                return 'enabled'
            if args[0] == 'nmcli':
                return 'wlp0s20f3:wifi:connected:Classroom\nenp1s0:ethernet:connected:LAN'
            return 'Controller AA:BB (public)\n\tPowered: yes'

        with patch.object(host_radio, 'command', side_effect=command):
            result = host_radio.status()
        self.assertTrue(result['wifi']['connected'])
        self.assertEqual(result['wifi']['connection'], 'Classroom')
        self.assertTrue(result['ble']['available'])
        self.assertTrue(result['ble']['enabled'])

    def test_set_calls_only_fixed_allowlisted_command(self):
        before = {'available': True, 'enabled': False}
        with patch.object(host_radio, 'wifi_status', return_value=before), \
             patch.object(host_radio, 'status', return_value={'wifi': before, 'ble': {}}), \
             patch.object(host_radio, 'command') as command:
            host_radio.dispatch({'operation': 'set', 'radio': 'wifi', 'enabled': True})
            command.assert_called_once_with('nmcli', 'radio', 'wifi', 'on')
        with self.assertRaises(ValueError):
            host_radio.dispatch({'operation': 'set', 'radio': 'shell', 'enabled': True})
        with self.assertRaises(ValueError):
            host_radio.dispatch({'operation': 'set', 'radio': 'wifi', 'enabled': 'true'})

    def test_no_adapter_is_not_toggleable(self):
        with patch.object(host_radio, 'ble_status', return_value={'available': False, 'enabled': None}), \
             patch.object(host_radio, 'command') as command:
            with self.assertRaises(ValueError):
                host_radio.dispatch({'operation': 'set', 'radio': 'ble', 'enabled': True})
            command.assert_not_called()


class RadioApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        radio_api.configure_radio_api(app, lambda cookie: {'id': 1} if cookie == 'valid' else None)
        included = next(route.original_router for route in app.routes
                        if hasattr(route, 'original_router'))
        self.get_status = next(route.endpoint for route in included.routes
                               if route.path == '/api/host-radio')
        self.change_radio = next(route.endpoint for route in included.routes
                                 if route.path == '/api/host-radio/{radio}')
        self.status = {'wifi': {'available': True, 'enabled': True},
                       'ble': {'available': True, 'enabled': False}}

    @staticmethod
    def request(cookie='', origin=''):
        headers = [(b'host', b'testserver')]
        if cookie:
            headers.append((b'cookie', ('classroom_session=' + cookie).encode()))
        if origin:
            headers.append((b'origin', origin.encode()))
        return Request({'type': 'http', 'method': 'POST', 'path': '/api/host-radio/wifi',
                        'scheme': 'http', 'server': ('testserver', 80),
                        'client': ('testclient', 12345), 'query_string': b'', 'headers': headers})

    def test_requires_login_and_same_origin_for_mutation(self):
        with self.assertRaises(HTTPException) as unauthenticated:
            self.get_status(self.request())
        self.assertEqual(unauthenticated.exception.status_code, 401)
        with self.assertRaises(HTTPException) as unauthenticated:
            self.change_radio('wifi', radio_api.RadioChange(enabled=False), self.request())
        self.assertEqual(unauthenticated.exception.status_code, 401)
        with patch.object(radio_api, 'radio_call', return_value=self.status) as radio_call:
            with self.assertRaises(HTTPException) as foreign:
                self.change_radio('wifi', radio_api.RadioChange(enabled=False),
                                  self.request('valid', 'http://evil.example'))
            self.assertEqual(foreign.exception.status_code, 403)
            radio_call.assert_not_called()

    def test_status_and_valid_toggle(self):
        with patch.object(radio_api, 'radio_call', return_value=self.status) as radio_call:
            response = self.get_status(self.request('valid'))
            self.assertTrue(response['wifi']['enabled'])
            response = self.change_radio('ble', radio_api.RadioChange(enabled=True),
                                         self.request('valid', 'http://testserver'))
            self.assertTrue(response['service_available'])
            self.assertEqual(radio_call.call_args.args[1],
                             {'operation': 'set', 'radio': 'ble', 'enabled': True})


if __name__ == '__main__':
    unittest.main()
