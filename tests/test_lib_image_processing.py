"""Tests for app/lib/image_processing.py functions."""

import pytest
import tempfile
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image as Pillow

from app.lib.image_processing import (
    make_image_metadata,
    process_uploaded_image,
    ImageProcessingError,
    ImageInvalidError,
)
from app.models.images import Image, ImageMetadata
from app.models.users import User
from app.models.uploads import Upload
from app.lib.config import get_app_config

config = get_app_config()


class TestMakeImageMetadata:
    """Test image metadata extraction."""

    @pytest.mark.asyncio
    async def test_extract_jpeg_metadata(self, db):
        """Test metadata extraction from JPEG image."""
        # Create a real JPEG image
        img = Pillow.new("RGB", (640, 480), color="red")
        jpeg_bytes = BytesIO()
        img.save(jpeg_bytes, format="JPEG")
        jpeg_bytes.seek(0)

        # Create user and upload
        user = await User.create(
            username="jpeguser",
            email="jpeg@example.com",
            password="hashedpass",
        )

        # Save test image to file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(jpeg_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            # Create upload record pointing to temp file
            upload = await Upload.create(
                user=user,
                description="JPEG test",
                name="jpeg_test",
                cleanname="jpeg",
                originalname="test.jpg",
                ext="jpg",
                size=jpeg_bytes.getvalue().__sizeof__(),
                type="image/jpeg",
                extra="0",
            )

            # Mock filepath property to point to our test image
            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                metadata = await make_image_metadata(upload)

                assert metadata is not None
                assert metadata.width == 640
                assert metadata.height == 480
                assert metadata.channels == 3  # RGB
                assert metadata.bits == 24  # 8 bits per channel * 3 channels
                assert metadata.type == "jpeg"

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extract_png_metadata(self, db):
        """Test metadata extraction from PNG image."""
        # Create a real PNG image with transparency
        img = Pillow.new("RGBA", (800, 600), color=(255, 0, 0, 128))
        png_bytes = BytesIO()
        img.save(png_bytes, format="PNG")
        png_bytes.seek(0)

        user = await User.create(
            username="pnguser",
            email="png@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="PNG test",
                name="png_test",
                cleanname="png",
                originalname="test.png",
                ext="png",
                size=png_bytes.getvalue().__sizeof__(),
                type="image/png",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                metadata = await make_image_metadata(upload)

                assert metadata is not None
                assert metadata.width == 800
                assert metadata.height == 600
                assert metadata.channels == 4  # RGBA
                assert metadata.bits == 32  # 8 bits per channel * 4 channels
                assert metadata.type == "png"

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extract_gif_metadata(self, db):
        """Test metadata extraction from GIF image."""
        # Create a real GIF image
        img = Pillow.new("RGB", (320, 240), color="blue")
        gif_bytes = BytesIO()
        img.save(gif_bytes, format="GIF")
        gif_bytes.seek(0)

        user = await User.create(
            username="gifuser",
            email="gif@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
            tmp.write(gif_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="GIF test",
                name="gif_test",
                cleanname="gif",
                originalname="test.gif",
                ext="gif",
                size=gif_bytes.getvalue().__sizeof__(),
                type="image/gif",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                metadata = await make_image_metadata(upload)

                assert metadata is not None
                assert metadata.width == 320
                assert metadata.height == 240
                assert metadata.type == "gif"

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extract_webp_metadata(self, db):
        """Test metadata extraction from WebP image."""
        try:
            # Create a real WebP image
            img = Pillow.new("RGB", (1024, 768), color="green")
            webp_bytes = BytesIO()
            img.save(webp_bytes, format="WEBP")
            webp_bytes.seek(0)
        except Exception:
            # Skip if WebP support not available
            pytest.skip("WebP support not available")

        user = await User.create(
            username="webpuser",
            email="webp@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
            tmp.write(webp_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="WebP test",
                name="webp_test",
                cleanname="webp",
                originalname="test.webp",
                ext="webp",
                size=webp_bytes.getvalue().__sizeof__(),
                type="image/webp",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                metadata = await make_image_metadata(upload)

                assert metadata is not None
                assert metadata.width == 1024
                assert metadata.height == 768
                assert metadata.type == "webp"

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_metadata_has_all_required_fields(self, db):
        """Test that returned metadata has all required fields."""
        img = Pillow.new("RGB", (100, 100), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        user = await User.create(
            username="fieldsuser",
            email="fields@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="Fields test",
                name="fields_test",
                cleanname="fields",
                originalname="test.jpg",
                ext="jpg",
                size=img_bytes.getvalue().__sizeof__(),
                type="image/jpeg",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                metadata = await make_image_metadata(upload)

                # Verify all required fields exist
                assert hasattr(metadata, "upload_id")
                assert hasattr(metadata, "type")
                assert hasattr(metadata, "width")
                assert hasattr(metadata, "height")
                assert hasattr(metadata, "bits")
                assert hasattr(metadata, "channels")

                # Verify they are not None
                assert metadata.type is not None
                assert metadata.width is not None
                assert metadata.height is not None
                assert metadata.bits is not None
                assert metadata.channels is not None

                # Verify types
                assert isinstance(metadata.width, int)
                assert isinstance(metadata.height, int)
                assert isinstance(metadata.bits, int)
                assert isinstance(metadata.channels, int)

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_color_depth_rgb(self, db):
        """Test color depth detection for RGB images."""
        img = Pillow.new("RGB", (200, 200), color="black")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        user = await User.create(
            username="rgbuser",
            email="rgb@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="RGB test",
                name="rgb_test",
                cleanname="rgb",
                originalname="test.jpg",
                ext="jpg",
                size=img_bytes.getvalue().__sizeof__(),
                type="image/jpeg",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                metadata = await make_image_metadata(upload)

                # RGB: 3 channels, 8 bits per channel = 24 bits total
                assert metadata.channels == 3
                assert metadata.bits == 24

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_color_depth_rgba(self, db):
        """Test color depth detection for RGBA images."""
        img = Pillow.new("RGBA", (150, 150), color=(0, 0, 0, 255))
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        user = await User.create(
            username="rgbauser",
            email="rgba@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="RGBA test",
                name="rgba_test",
                cleanname="rgba",
                originalname="test.png",
                ext="png",
                size=img_bytes.getvalue().__sizeof__(),
                type="image/png",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                metadata = await make_image_metadata(upload)

                # RGBA: 4 channels, 8 bits per channel = 32 bits total
                assert metadata.channels == 4
                assert metadata.bits == 32

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_invalid_image_data_handled_gracefully(self, db):
        """Test that invalid image data is handled gracefully."""
        user = await User.create(
            username="invaliduser",
            email="invalid@example.com",
            password="hashedpass",
        )

        # Create a file with invalid image data
        invalid_data = b"This is not an image file at all"
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(invalid_data)
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="Invalid test",
                name="invalid_test",
                cleanname="invalid",
                originalname="not_image.jpg",
                ext="jpg",
                size=len(invalid_data),
                type="image/jpeg",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                # Should raise ImageInvalidError, not crash
                with pytest.raises(ImageInvalidError) as exc_info:
                    await make_image_metadata(upload)

                assert "not a valid image" in str(exc_info.value)

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_corrupted_image_data_handled_gracefully(self, db):
        """Test that corrupted image data is handled gracefully."""
        # Create valid PNG header but corrupt data
        corrupted_data = b"\x89PNG\r\n\x1a\n" + b"corrupted" * 100

        user = await User.create(
            username="corruptuser",
            email="corrupt@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(corrupted_data)
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="Corrupt test",
                name="corrupt_test",
                cleanname="corrupt",
                originalname="corrupted.png",
                ext="png",
                size=len(corrupted_data),
                type="image/png",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                # Should raise ImageInvalidError, not crash
                with pytest.raises(ImageInvalidError):
                    await make_image_metadata(upload)

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_metadata_extraction_performance(self, db):
        """Test that metadata extraction completes within performance target."""
        # Create a 2MB-ish JPEG image
        img = Pillow.new("RGB", (4000, 3000), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG", quality=85)
        img_bytes.seek(0)

        user = await User.create(
            username="perfuser",
            email="perf@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="Performance test",
                name="perf_test",
                cleanname="perf",
                originalname="performance.jpg",
                ext="jpg",
                size=img_bytes.getvalue().__sizeof__(),
                type="image/jpeg",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                start = time.time()
                metadata = await make_image_metadata(upload)
                elapsed = time.time() - start

                # Should complete within 100ms for typical images
                assert elapsed < 0.1, f"Image processing took {elapsed:.3f}s, expected < 0.1s"
                assert metadata is not None

        finally:
            tmp_path.unlink(missing_ok=True)


class TestProcessUploadedImage:
    """Test image processing and database record creation."""

    @pytest.mark.asyncio
    async def test_process_uploaded_image_creates_record(self, db):
        """Test that process_uploaded_image creates Image database record."""
        img = Pillow.new("RGB", (640, 480), color="blue")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        user = await User.create(
            username="procuser",
            email="proc@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="Process test",
                name="proc_test",
                cleanname="proc",
                originalname="process.jpg",
                ext="jpg",
                size=img_bytes.getvalue().__sizeof__(),
                type="image/jpeg",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                image = await process_uploaded_image(upload)

                # Verify Image record was created
                assert image is not None
                assert image.id is not None
                assert image.upload_id == upload.id
                assert image.width == 640
                assert image.height == 480
                assert image.type == "jpeg"

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_process_uploaded_image_stores_metadata(self, db):
        """Test that process_uploaded_image stores all metadata correctly."""
        img = Pillow.new("RGBA", (800, 600), color=(255, 128, 64, 200))
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        user = await User.create(
            username="metauser",
            email="meta@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes.getvalue())
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="Metadata store test",
                name="meta_test",
                cleanname="meta",
                originalname="metadata.png",
                ext="png",
                size=img_bytes.getvalue().__sizeof__(),
                type="image/png",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                image = await process_uploaded_image(upload)

                # Verify all metadata is stored
                assert image.width == 800
                assert image.height == 600
                assert image.bits == 32
                assert image.channels == 4
                assert image.type == "png"

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_process_uploaded_image_invalid_image_raises_error(self, db):
        """Test that processing invalid image raises ImageProcessingError."""
        user = await User.create(
            username="badimguser",
            email="badimg@example.com",
            password="hashedpass",
        )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"not an image")
            tmp_path = Path(tmp.name)

        try:
            upload = await Upload.create(
                user=user,
                description="Bad image test",
                name="badimg_test",
                cleanname="badimg",
                originalname="badimage.jpg",
                ext="jpg",
                size=12,
                type="image/jpeg",
                extra="0",
            )

            with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: tmp_path)):
                # Should raise ImageInvalidError for invalid image files
                with pytest.raises(ImageInvalidError):
                    await process_uploaded_image(upload)

        finally:
            tmp_path.unlink(missing_ok=True)


class TestImageProcessingIntegration:
    """Integration tests for image processing with upload pipeline."""

    @pytest.mark.asyncio
    async def test_image_processing_called_after_successful_upload(self, db):
        """Test that image processing is called as part of upload pipeline."""
        # This is implicitly tested by test_lib_file_storage.py integration tests
        # which call process_uploaded_file and verify Image records are created
        pass
