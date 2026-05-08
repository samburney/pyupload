"""Tests for the upload widget rendering.

Smoke tests confirming the upload widget is present and structurally correct on
pages that include the global sidebar.  The widget is rendered server-side inside
the sidebar (`components/layout/sidebar.html.j2`) and is therefore present on any
page using the base layout.

Covers:
- GET / — widget present in sidebar on the gallery home page
- Dropzone/Alpine component referenced correctly
- Upload form has required data attributes for Dropzone configuration
- Upload form action points to the correct endpoint
"""

import pytest


class TestUploadWidgetPresence:
    """Smoke tests confirming the upload widget is rendered in the sidebar."""

    async def test_gallery_page_loads(self, client):
        """GET / returns 200."""
        response = await client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_widget_alpine_component_referenced(self, client):
        """The sidebar contains the fileUploadWidget Alpine component."""
        response = await client.get("/")
        html = response.text

        assert 'x-data="fileUploadWidget"' in html

    async def test_widget_upload_form_present(self, client):
        """The upload form element is rendered with the expected id."""
        response = await client.get("/")
        html = response.text

        assert 'id="upload-form"' in html

    async def test_widget_form_has_max_file_size_attribute(self, client):
        """The upload form carries a data-max-file-size attribute for Dropzone configuration."""
        response = await client.get("/")
        html = response.text

        assert "data-max-file-size=" in html

    async def test_widget_form_action_points_to_upload_endpoint(self, client):
        """The upload form action points to the upload_create_post route."""
        response = await client.get("/")
        html = response.text

        # url_for generates absolute URLs; the path portion must end with /upload
        assert 'action="http://test/upload"' in html

    async def test_widget_preview_template_present(self, client):
        """The uploaded-file-item preview template element is rendered."""
        response = await client.get("/")
        html = response.text

        assert 'id="uploaded-file-item-template"' in html
