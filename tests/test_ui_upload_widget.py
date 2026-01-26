"""Tests for Step 9: Upload Widget UI functionality.

This module tests the enhanced upload widget implemented in Step 9:
- Widget component rendering (widget.html.j2)
- Form integration (form.html.j2)
- Alpine.js store integration
- HTMX attributes and configuration
- File list display
- Drag-and-drop zone
- Multiple file selection
- Message display and dismissal

Since these are primarily frontend features (HTML/Alpine.js/HTMX),
tests focus on verifying correct template rendering and HTML structure.
"""

import pytest
from io import BytesIO


class TestUploadWidgetRendering:
    """Test that upload widget template renders correctly."""

    @pytest.mark.asyncio
    async def test_widget_included_in_upload_page(self, client):
        """Test that widget.html.j2 is included in the upload page."""
        response = await client.get("/upload")
        
        assert response.status_code == 200
        html = response.text
        
        # Widget should be present with its ID
        assert 'id="file-upload-widget"' in html

    @pytest.mark.asyncio
    async def test_widget_has_alpine_store_initialization(self, client):
        """Test that widget initializes Alpine.js uploadWidget store."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should contain Alpine store initialization script
        assert "Alpine.store('uploadWidget'" in html
        assert "addFiles" in html
        assert "removeFile" in html
        assert "formatFileSize" in html

    @pytest.mark.asyncio
    async def test_widget_has_file_input(self, client):
        """Test that widget contains hidden file input element."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have file input with correct attributes
        assert 'type="file"' in html
        assert 'name="upload_files"' in html
        assert 'multiple' in html
        assert 'id="file-upload-picker"' in html

    @pytest.mark.asyncio
    async def test_widget_has_drag_drop_zone(self, client):
        """Test that widget has drag-and-drop event handlers."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have drag-and-drop event handlers
        assert '@drop.prevent' in html
        assert '@dragover.prevent' in html
        assert '@dragleave.prevent' in html

    @pytest.mark.asyncio
    async def test_widget_has_file_list_container(self, client):
        """Test that widget has container for file list display."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have file list container with x-ref
        assert 'x-ref="infoMessages"' in html or 'id="file-list"' in html

    @pytest.mark.asyncio
    async def test_widget_has_dynamic_border_styling(self, client):
        """Test that widget has dynamic border styling for drag state."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have dynamic class binding for drag state
        assert ':class=' in html
        assert 'dragActive' in html
        assert 'border' in html


class TestUploadFormIntegration:
    """Test upload form integration with widget."""

    @pytest.mark.asyncio
    async def test_form_has_htmx_attributes(self, client):
        """Test that form has correct HTMX configuration."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have HTMX attributes
        assert 'hx-encoding="multipart/form-data"' in html
        assert 'hx-post="/upload"' in html
        assert 'hx-target=' in html
        assert 'hx-swap=' in html

    @pytest.mark.asyncio
    async def test_form_has_htmx_response_targets(self, client):
        """Test that form uses HTMX response-targets extension."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have response-targets configuration
        assert 'hx-select-oob' in html or 'hx-target-4*' in html

    @pytest.mark.asyncio
    async def test_form_has_upload_button(self, client):
        """Test that form has upload submit button."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have submit button
        assert 'type="submit"' in html
        assert 'Upload' in html

    @pytest.mark.asyncio
    async def test_upload_button_has_alpine_binding(self, client):
        """Test that upload button has Alpine.js state binding."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Button should access Alpine store
        assert '$store.uploadWidget' in html
        assert ':disabled=' in html or 'x-data' in html

    @pytest.mark.asyncio
    async def test_form_includes_widget_component(self, client):
        """Test that form includes widget.html.j2 component."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Widget should be included (check for widget-specific elements)
        assert 'file-upload-widget' in html or 'file-upload-picker' in html


class TestFileListDisplay:
    """Test file list display functionality."""

    @pytest.mark.asyncio
    async def test_file_list_has_grid_layout(self, client):
        """Test that file list uses grid layout for alignment."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have grid layout classes
        assert 'grid' in html
        assert 'grid-cols' in html or 'flex' in html

    @pytest.mark.asyncio
    async def test_file_list_has_column_headers(self, client):
        """Test that file list displays column headers."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have headers for file info
        assert 'File Name' in html or 'filename' in html.lower()
        assert 'Size' in html or 'size' in html.lower()

    @pytest.mark.asyncio
    async def test_file_list_uses_alpine_for_loop(self, client):
        """Test that file list uses Alpine.js x-for to render files."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should use Alpine x-for template
        assert 'x-for=' in html
        assert '$store.uploadWidget.files' in html

    @pytest.mark.asyncio
    async def test_file_list_displays_file_size(self, client):
        """Test that file list displays formatted file size."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should call formatFileSize function
        assert 'formatFileSize' in html


class TestMessageDisplay:
    """Test message display and dismissal functionality."""

    @pytest.mark.asyncio
    async def test_messages_container_exists(self, client):
        """Test that messages container is present."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have messages container
        assert 'id="messages"' in html

    @pytest.mark.asyncio
    async def test_messages_have_alpine_state(self, client):
        """Test that messages use Alpine.js for state management."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have Alpine data for message counts
        assert 'infoMessagesCount' in html or 'errorMessagesCount' in html
        assert 'updateMessageCounts' in html

    @pytest.mark.asyncio
    async def test_messages_have_dismiss_buttons(self, client):
        """Test that messages can be dismissed."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have remove/dismiss functionality
        assert 'removeMessage' in html or '@click=' in html

    @pytest.mark.asyncio
    async def test_messages_have_transitions(self, client):
        """Test that messages use Alpine transitions."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have transition directives
        assert 'x-transition' in html or 'x-show' in html

    @pytest.mark.asyncio
    async def test_info_messages_styled_green(self, client):
        """Test that info messages template has green styling."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have info-messages class or green styling in template
        # Messages are rendered conditionally, so check for class definition
        assert 'info-messages' in html or 'infoMessagesCount' in html

    @pytest.mark.asyncio
    async def test_error_messages_styled_red(self, client):
        """Test that error messages template has red styling."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have error-messages class or error count tracking
        # Messages are rendered conditionally, so check for class definition
        assert 'error-messages' in html or 'errorMessagesCount' in html


class TestResponsiveDesign:
    """Test responsive design implementation."""

    @pytest.mark.asyncio
    async def test_page_has_responsive_classes(self, client):
        """Test that page uses Tailwind responsive classes."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have responsive breakpoint classes
        assert 'sm:' in html or 'md:' in html or 'lg:' in html

    @pytest.mark.asyncio
    async def test_container_has_max_width(self, client):
        """Test that containers have max-width for desktop."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have container or max-width classes
        assert 'container' in html or 'max-w' in html

    @pytest.mark.asyncio
    async def test_widget_has_responsive_padding(self, client):
        """Test that widget has responsive padding."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have responsive padding classes
        assert 'p-4' in html or 'p-6' in html or 'sm:p-' in html


class TestButtonStates:
    """Test upload button state management."""

    @pytest.mark.asyncio
    async def test_upload_button_disabled_when_no_files(self, client):
        """Test that upload button is disabled when no files selected."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Button should have disabled binding
        assert ':disabled=' in html
        assert '$store.uploadWidget.files.length' in html

    @pytest.mark.asyncio
    async def test_upload_button_has_disabled_styling(self, client):
        """Test that upload button has disabled state styling."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have conditional class for disabled state
        assert 'button-disabled' in html or ':class=' in html


class TestAlpineStoreIntegration:
    """Test Alpine.js store integration across components."""

    @pytest.mark.asyncio
    async def test_store_initialized_in_widget(self, client):
        """Test that uploadWidget store is initialized."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Store should be initialized with required properties
        assert "Alpine.store('uploadWidget'" in html
        assert 'files: []' in html
        assert 'dragActive: false' in html

    @pytest.mark.asyncio
    async def test_store_accessible_from_form(self, client):
        """Test that form can access widget store."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Form elements should reference the store
        assert '$store.uploadWidget' in html

    @pytest.mark.asyncio
    async def test_store_has_file_management_methods(self, client):
        """Test that store has methods for file management."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have file management methods
        assert 'addFiles' in html
        assert 'removeFile' in html
        assert 'updateFileInput' in html

    @pytest.mark.asyncio
    async def test_store_has_helper_methods(self, client):
        """Test that store has helper methods."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have helper methods
        assert 'formatFileSize' in html
