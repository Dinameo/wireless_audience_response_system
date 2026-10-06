import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'ble-classroom'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as app_module


class AuthFeatureRoutesTest(unittest.TestCase):
    def flatten_routes(self, routes):
        paths = set()
        for route in routes:
            if hasattr(route, 'path'):
                paths.add(route.path)
            elif hasattr(route, 'original_router'):
                paths |= self.flatten_routes(route.original_router.routes)
            elif hasattr(route, 'routes'):
                paths |= self.flatten_routes(route.routes)
        return paths

    def test_teacher_account_routes_exist(self):
        paths = self.flatten_routes(app_module.app.routes)
        self.assertIn('/api/auth/change-password', paths)
        self.assertIn('/api/auth/profile', paths)
        self.assertIn('/api/auth/logout-all', paths)


if __name__ == '__main__':
    unittest.main()
