import unittest

from scripts.docs_screenshot_preflight import PreflightError, validate_capabilities


class DocsScreenshotPreflightTest(unittest.TestCase):
    def test_accepts_public_read_only_capabilities(self) -> None:
        validate_capabilities({"auth_disabled": False, "can_write_results": False})

    def test_rejects_auth_disabled_capture_target(self) -> None:
        with self.assertRaisesRegex(PreflightError, "CONBENCH_AUTH_DISABLED=false"):
            validate_capabilities({"auth_disabled": True, "can_write_results": True})

    def test_rejects_write_capable_capture_target(self) -> None:
        with self.assertRaisesRegex(PreflightError, "public read-only product mode"):
            validate_capabilities({"auth_disabled": False, "can_write_results": True})

    def test_rejects_incomplete_capabilities_response(self) -> None:
        with self.assertRaisesRegex(PreflightError, "expected auth_disabled=false"):
            validate_capabilities({"can_write_results": False})


if __name__ == "__main__":
    unittest.main()
