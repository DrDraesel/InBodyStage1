"""Exercise the authenticated import-to-review flow in the CI test suite."""
import unittest

from scripts.smoke import main


class HttpSmokeTest(unittest.TestCase):
    def test_import_to_review(self):
        main()


if __name__ == '__main__':
    unittest.main()
