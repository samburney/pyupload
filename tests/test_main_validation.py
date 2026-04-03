"""Tests for validation error handling in app/main.py exception handlers.

The /get/ endpoint accepts an optional ?download= query parameter that must be
a boolean. These tests verify that invalid values produce content-negotiated
error responses: an image/jpeg error image for image requests, and an HTML
error page for non-image requests. An empty value is treated as download=1 via
a 307 redirect.

Covers:
- GET /get/{id}/{filename}?download= — empty value redirects to download=1
- GET /get/{id}/{filename}?download=<invalid> — 422 with image/jpeg for image requests
- GET /get/{id}/{filename}?download=<invalid> — 422 with text/html for non-image requests
"""



class TestGetValidationExceptionHandling:
    """Validation error handling for the /get/ file serving endpoint."""

    async def test_empty_download_query_redirects_to_download_1(self, client):
        """An empty ?download= value is redirected to ?download=1 (307)."""
        response = await client.get("/get/1/example.jpg?download=", follow_redirects=False)

        assert response.status_code == 307
        assert "download=1" in response.headers["location"]

    async def test_invalid_download_query_returns_image_error_for_image_request(self, client):
        """A non-boolean ?download= value for an image URL returns 422 as image/jpeg."""
        response = await client.get("/get/1/example.jpg?download=notabool")

        assert response.status_code == 422
        assert response.headers.get("content-type") == "image/jpeg"

    async def test_invalid_download_query_returns_html_error_for_non_image_request(self, client):
        """A non-boolean ?download= value for a non-image URL returns 422 as text/html."""
        response = await client.get("/get/1/example.txt?download=notabool")

        assert response.status_code == 422
        assert "text/html" in response.headers.get("content-type", "")
        assert "Error 422: Unprocessable Content" in response.text
