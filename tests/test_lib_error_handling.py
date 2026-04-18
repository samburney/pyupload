import pytest

from fastapi.responses import HTMLResponse, StreamingResponse

from app.lib.error_handling import (
    ImageProcessingError,
    supports_error_image,
    get_error_image_response,
)
from app.ui.common.responses import error_response_for_get


class TestSupportsErrorImage:
    def test_returns_true_for_supported_extension(self):
        assert supports_error_image("photo.jpg") is True
        assert supports_error_image("photo.JPEG") is True

    def test_returns_false_for_unsupported_extension(self):
        assert supports_error_image("document.txt") is False
        assert supports_error_image("filename_without_ext") is False


class TestGetErrorImageResponse:
    def test_returns_streaming_image_response(self):
        response = get_error_image_response(
            error_title="Error 404",
            error_message="Not found",
            filename="missing.jpg",
            status_code=404,
        )

        assert isinstance(response, StreamingResponse)
        assert response.status_code == 404
        assert response.media_type == "image/jpeg"
        assert "inline; filename=missing.jpg" == response.headers["Content-Disposition"]

    def test_raises_for_unsupported_extension(self):
        with pytest.raises(ImageProcessingError):
            get_error_image_response(
                error_title="Error 404",
                error_message="Not found",
                filename="missing.txt",
                status_code=404,
            )


class TestErrorResponseForGet:
    async def test_returns_html_response_for_non_image(self):
        response = await error_response_for_get(
            filename="missing.txt",
            error_title="Error 404",
            error_message="Not found",
            status_code=404,
        )

        assert isinstance(response, HTMLResponse)
        assert response.status_code == 404

    async def test_returns_image_response_for_supported_image(self):
        response = await error_response_for_get(
            filename="missing.jpg",
            error_title="Error 404",
            error_message="Not found",
            status_code=404,
        )

        assert isinstance(response, StreamingResponse)
        assert response.status_code == 404
        assert response.media_type == "image/jpeg"
