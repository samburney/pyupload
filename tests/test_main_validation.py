import pytest


class TestGetValidationExceptionHandling:
    @pytest.mark.asyncio
    async def test_empty_download_query_redirects_to_download_1(self, client):
        response = await client.get("/get/1/example.jpg?download=", follow_redirects=False)

        assert response.status_code == 307
        assert "download=1" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_invalid_download_query_returns_image_error_for_image_request(self, client):
        response = await client.get("/get/1/example.jpg?download=notabool")

        assert response.status_code == 422
        assert response.headers.get("content-type") == "image/jpeg"

    @pytest.mark.asyncio
    async def test_invalid_download_query_returns_html_error_for_non_image_request(self, client):
        response = await client.get("/get/1/example.txt?download=notabool")

        assert response.status_code == 422
        assert "text/html" in response.headers.get("content-type", "")
        assert "Error 422: Unprocessable Content" in response.text
