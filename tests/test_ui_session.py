"""Tests for UI session helpers."""

import json
from types import SimpleNamespace

from app.ui.common.session import get_client_dimensions


def _request_with_window_dimensions(cookie_payload: str | None):
    cookies = {}
    if cookie_payload is not None:
        cookies["window_dimensions"] = cookie_payload
    return SimpleNamespace(cookies=cookies)


class TestGetClientDimensions:
    """Test parsing and breakpoint detection for client dimensions."""

    def test_returns_none_when_cookie_is_missing(self):
        request = _request_with_window_dimensions(None)

        assert get_client_dimensions(request) is None

    def test_returns_dimensions_and_breakpoint_for_valid_cookie(self):
        request = _request_with_window_dimensions(
            json.dumps({"window_width": 1024, "window_height": 768})
        )

        dimensions = get_client_dimensions(request)

        assert dimensions is not None
        assert dimensions["width"] == 1024
        assert dimensions["height"] == 768
        assert dimensions["breakpoint"] == "lg"
        assert dimensions["breakpoint_width"] == 1024

    def test_handles_invalid_json_without_raising(self):
        request = _request_with_window_dimensions("not-json")

        dimensions = get_client_dimensions(request)

        assert dimensions is not None
        assert dimensions["width"] is None
        assert dimensions["height"] is None
        assert dimensions["breakpoint"] is None
        assert dimensions["breakpoint_width"] is None

    def test_handles_cookie_missing_expected_keys(self):
        request = _request_with_window_dimensions(json.dumps({"foo": "bar"}))

        dimensions = get_client_dimensions(request)

        assert dimensions is not None
        assert dimensions["width"] is None
        assert dimensions["height"] is None
        assert dimensions["breakpoint"] is None
        assert dimensions["breakpoint_width"] is None