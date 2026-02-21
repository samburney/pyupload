"""Integration tests for end-to-end home gallery workflows."""

import pytest

from app.models.images import Image
from app.models.uploads import Upload
from app.models.users import User


class TestGalleryIntegrationWorkflows:
    """Integration coverage for browse/view and pagination workflows."""

    @pytest.mark.anyio
    async def test_browse_gallery_to_view_upload_workflow(self, client, monkeypatch):
        """Step 8 workflow: browse gallery then open an upload view page."""
        monkeypatch.setattr("app.ui.uploads.validate_file_request", lambda upload, user=None: True)
        owner = await User.create(
            password="hashed_password",
            username="integration_gallery_owner",
            email="integration.gallery.owner@test.com",
        )
        upload = await Upload.create(
            user=owner,
            description="Integration Workflow Upload",
            name="integration_workflow_upload",
            cleanname="integration_workflow_upload",
            originalname="integration_workflow_upload.jpg",
            ext="jpg",
            size=2048,
            type="image/jpeg",
            extra="",
            private=0,
        )
        await Image.create(
            upload=upload,
            type="image/jpeg",
            width=1280,
            height=720,
            bits=8,
            channels=3,
        )

        gallery_response = await client.get("/")

        assert gallery_response.status_code == 200
        view_path = f"/view/{upload.id}/{upload.cleanname}.{upload.ext}"
        assert view_path in gallery_response.text

        view_response = await client.get(view_path)

        assert view_response.status_code == 200
        assert "Integration Workflow Upload" in view_response.text
        assert f"/get/{upload.id}/{upload.cleanname}.{upload.ext}" in view_response.text

    @pytest.mark.anyio
    async def test_pagination_workflow_between_pages(self, client):
        """Step 8 workflow: navigate between gallery pages via pagination links."""
        owner = await User.create(
            password="hashed_password",
            username="integration_pagination_owner",
            email="integration.pagination.owner@test.com",
        )

        for index in range(30):
            upload = await Upload.create(
                user=owner,
                description=f"Integration Pagination Item {index:02d}",
                name=f"integration_pagination_item_{index:02d}",
                cleanname=f"integration_pagination_item_{index:02d}",
                originalname=f"integration_pagination_item_{index:02d}.jpg",
                ext="jpg",
                size=2048,
                type="image/jpeg",
                extra="",
                private=0,
            )
            await Image.create(
                upload=upload,
                type="image/jpeg",
                width=1280,
                height=720,
                bits=8,
                channels=3,
            )

        page_1_response = await client.get("/?page=1")

        assert page_1_response.status_code == 200
        assert "aria-label=\"Next page\"" in page_1_response.text
        assert "?page=2" in page_1_response.text

        page_2_response = await client.get("/?page=2")

        assert page_2_response.status_code == 200
        assert "aria-label=\"Previous page\"" in page_2_response.text
        assert "?page=1" in page_2_response.text
        assert "?page=3" not in page_2_response.text

    @pytest.mark.anyio
    async def test_large_dataset_100_plus_uploads_pagination_and_render_scope(self, client):
        """Step 8: verify gallery behavior with 100+ uploads and bounded per-page rendering."""
        owner = await User.create(
            password="hashed_password",
            username="integration_large_dataset_owner",
            email="integration.large.dataset.owner@test.com",
        )

        for index in range(120):
            upload = await Upload.create(
                user=owner,
                description=f"Integration Large Dataset Item {index:03d}",
                name=f"integration_large_dataset_item_{index:03d}",
                cleanname=f"integration_large_dataset_item_{index:03d}",
                originalname=f"integration_large_dataset_item_{index:03d}.jpg",
                ext="jpg",
                size=2048,
                type="image/jpeg",
                extra="",
                private=0,
            )
            await Image.create(
                upload=upload,
                type="image/jpeg",
                width=1280,
                height=720,
                bits=8,
                channels=3,
            )

        page_1_response = await client.get("/?page=1")
        assert page_1_response.status_code == 200
        assert "?page=5" in page_1_response.text
        assert page_1_response.text.count("break-inside-avoid-column") == 24

        page_5_response = await client.get("/?page=5")
        assert page_5_response.status_code == 200
        assert "?page=6" not in page_5_response.text
        assert page_5_response.text.count("break-inside-avoid-column") == 24

    @pytest.mark.anyio
    async def test_responsive_breakpoint_class_coverage_for_grid_and_modal(self, client, monkeypatch):
        """Step 8: verify responsive breakpoint classes exist for gallery and modal views."""
        monkeypatch.setattr("app.ui.uploads.validate_file_request", lambda upload, user=None: True)
        owner = await User.create(
            password="hashed_password",
            username="integration_responsive_owner",
            email="integration.responsive.owner@test.com",
        )
        upload = await Upload.create(
            user=owner,
            description="Integration Responsive Upload",
            name="integration_responsive_upload",
            cleanname="integration_responsive_upload",
            originalname="integration_responsive_upload.jpg",
            ext="jpg",
            size=2048,
            type="image/jpeg",
            extra="",
            private=0,
        )
        await Image.create(
            upload=upload,
            type="image/jpeg",
            width=1280,
            height=720,
            bits=8,
            channels=3,
        )

        gallery_response = await client.get("/")
        assert gallery_response.status_code == 200
        assert "columns-1" in gallery_response.text
        assert "md:columns-2" in gallery_response.text
        assert "xl:columns-3" in gallery_response.text
        assert "2xl:columns-4" in gallery_response.text

        modal_response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}?modal=true")
        assert modal_response.status_code == 200
        assert "sm:p-4" in modal_response.text
        assert "sm:rounded-lg" in modal_response.text
        assert "max-h-[calc(100dvh-1rem)]" in modal_response.text
        assert "sm:max-h-[calc(100dvh-2rem)]" in modal_response.text
        assert "role=\"dialog\"" in modal_response.text
        assert "aria-modal=\"true\"" in modal_response.text
        assert "id=\"modalTitle\"" in modal_response.text
        assert "aria-label=\"Close upload preview\"" in modal_response.text

    @pytest.mark.anyio
    async def test_gallery_links_and_modal_have_accessible_labels(self, client, monkeypatch):
        """Step 8 accessibility: verify card and modal controls expose readable labels."""
        monkeypatch.setattr("app.ui.uploads.validate_file_request", lambda upload, user=None: True)
        owner = await User.create(
            password="hashed_password",
            username="integration_accessible_labels_owner",
            email="integration.accessible.labels.owner@test.com",
        )
        upload = await Upload.create(
            user=owner,
            description="Accessible Labels Upload",
            name="accessible_labels_upload",
            cleanname="accessible_labels_upload",
            originalname="accessible_labels_upload.jpg",
            ext="jpg",
            size=2048,
            type="image/jpeg",
            extra="",
            private=0,
        )
        await Image.create(
            upload=upload,
            type="image/jpeg",
            width=1280,
            height=720,
            bits=8,
            channels=3,
        )

        gallery_response = await client.get("/")
        assert gallery_response.status_code == 200
        assert "Open upload Accessible Labels Upload" in gallery_response.text
        assert "1280x720" in gallery_response.text

        modal_response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}?modal=true")
        assert modal_response.status_code == 200
        assert "aria-label=\"Close upload preview\"" in modal_response.text
