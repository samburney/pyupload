"""Tests for the upload page widget rendering.

Smoke tests confirming the upload page loads and contains the essential
upload widget elements. Detailed behavioural tests for the upload form
are in test_ui_uploads.py.

Covers:
- GET /uploads — page loads without authentication (public page)
- File input present with correct attributes
- Alpine.js upload store referenced in the page
"""



class TestUploadPageSmoke:
    """Smoke tests for the upload widget page."""

    async def test_upload_page_loads_without_auth(self, client):
        """GET /upload returns 200 without authentication."""
        response = await client.get("/upload")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_upload_page_contains_file_input(self, client):
        """The upload page contains a file input with the expected attributes."""
        response = await client.get("/upload")
        html = response.text

        assert 'type="file"' in html
        assert 'name="upload_files"' in html
        assert 'multiple' in html

    async def test_upload_page_references_alpine_store(self, client):
        """The upload page references the Alpine.js uploadWidget store."""
        response = await client.get("/upload")
        html = response.text

        assert "$store.uploadWidget" in html
