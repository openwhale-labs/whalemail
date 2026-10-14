import io
import urllib.error
from unittest.mock import call, patch

import pytest

from triage import llm


def failure(code=503, headers=None):
    return urllib.error.HTTPError(
        "https://example.invalid/chat/completions", code, "test", headers or {},
        io.BytesIO(b"failure"),
    )


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_LLM_API_KEY", "test-key")


def test_503_then_success_reuses_request():
    error = failure(headers={"Retry-After": "4"})
    with patch.object(llm.net, "urlopen_json", side_effect=[
        error, {"choices": [{"message": {"content": "ok"}}]},
    ]) as request, patch.object(llm.time, "sleep") as sleep:
        assert llm.chat([{"role": "user", "content": "test"}]) == "ok"
        assert request.call_count == 2
        assert request.call_args_list[0].args[0] is request.call_args_list[1].args[0]
        sleep.assert_called_once_with(4)
        assert error.fp.closed


def test_exhaustion_keeps_final_error():
    errors = [failure() for _ in range(3)]
    with patch.object(llm.net, "urlopen_json", side_effect=errors) as request:
        with patch.object(llm.time, "sleep") as sleep:
            with pytest.raises(urllib.error.HTTPError) as caught:
                llm.chat([])
            assert caught.value is errors[-1]
            assert request.call_count == 3
            assert sleep.call_args_list == [call(1.5), call(3.0)]
    errors[-1].close()


@pytest.mark.parametrize("code", [400, 401, 402, 403, 429, 500])
def test_other_http_errors_are_not_retried(code):
    error = failure(code)
    with patch.object(llm.net, "urlopen_json", side_effect=error) as request:
        with patch.object(llm.time, "sleep") as sleep:
            with pytest.raises(urllib.error.HTTPError):
                llm.chat([])
            assert request.call_count == 1
            sleep.assert_not_called()
    error.close()


def test_long_cooldown_is_not_shortened():
    error = failure(headers={"Retry-After": "120"})
    with patch.object(llm.net, "urlopen_json", side_effect=error) as request:
        with patch.object(llm.time, "sleep") as sleep:
            with pytest.raises(urllib.error.HTTPError):
                llm.chat([])
            assert request.call_count == 1
            sleep.assert_not_called()
    error.close()
