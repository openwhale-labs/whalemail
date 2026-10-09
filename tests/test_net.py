import io
import unittest
import urllib.error
import urllib.request
from unittest.mock import call, patch

import net
from adapters.gmail.gmail_reader import client


def error(code):
    return urllib.error.HTTPError(
        "https://example.invalid/messages/test", code, "test", {}, io.BytesIO(b"failure")
    )


class ServerRetryTests(unittest.TestCase):
    @patch("net.time.sleep")
    @patch("net.urllib.request.urlopen")
    def test_opted_in_read_recovers_from_backend_error(self, urlopen, sleep):
        failure = error(500)
        urlopen.side_effect = [failure, io.BytesIO(b'{"ok": true}')]
        result = net.urlopen_json(
            urllib.request.Request("https://example.invalid", method="GET"),
            retry_server_errors=True,
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(failure.fp.closed)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1.5)

    @patch("net.time.sleep")
    @patch("net.urllib.request.urlopen")
    def test_exhaustion_preserves_final_failure(self, urlopen, sleep):
        failures = [error(503) for _ in range(3)]
        urlopen.side_effect = failures
        with self.assertRaises(urllib.error.HTTPError) as caught:
            net.urlopen_json(
                urllib.request.Request("https://example.invalid"),
                retry_server_errors=True,
            )
        self.assertIs(caught.exception, failures[-1])
        self.assertFalse(failures[-1].fp.closed)
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1.5), call(3.0)])
        failures[-1].close()

    def test_writes_authentication_and_opt_out_are_not_retried(self):
        for method, status, enabled in [
            ("POST", 500, True), ("GET", 401, True),
            ("GET", 403, True), ("GET", 500, False),
        ]:
            with self.subTest(method=method, status=status, enabled=enabled):
                failure = error(status)
                with patch("net.urllib.request.urlopen", side_effect=failure) as open_mock:
                    with patch("net.time.sleep") as sleep:
                        with self.assertRaises(urllib.error.HTTPError):
                            net.urlopen_json(
                                urllib.request.Request("https://example.invalid", method=method),
                                retry_server_errors=enabled,
                            )
                        self.assertEqual(open_mock.call_count, 1)
                        sleep.assert_not_called()
                failure.close()

    @patch("net.urlopen_json", return_value={})
    def test_only_gmail_reads_opt_in(self, request):
        client.get_message("test-token", "test-id")
        self.assertTrue(request.call_args.kwargs["retry_server_errors"])
        client._post("test-token", "/drafts", {})
        self.assertNotIn("retry_server_errors", request.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
