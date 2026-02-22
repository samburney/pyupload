"""Tests for app/lib/image_processing.py functions."""

import pytest
import tempfile
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image as Pillow

from app.lib.image_processing import (
    count_gif_frames,
    do_image_rotation,
    get_image_as_jpeg,
    get_image_bytes,
    get_processed_image_path,
    handle_image_resize,
    handle_image_rotation,
    handle_multiframe_image_obj,
    make_image_metadata,
    make_image_filename_metadata,
    mime_type_to_image_format,
    process_uploaded_image,
    ImageProcessingError,
    ImageInvalidError,
)
from app.models.images import Image, ImageMetadata, ProcessedImageMetadata
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


class TestImageFilenameMetadataValidation:
    """Validation tests for processed image metadata generation."""

    @pytest.mark.asyncio
    async def test_make_image_filename_metadata_raises_when_image_metadata_missing(self, db):
        """Image processing requests must fail if related image metadata does not exist."""
        user = await User.create(
            username="missingimgmeta",
            email="missingimgmeta@example.com",
            password="hashedpass",
        )

        upload = await Upload.create(
            user=user,
            description="Missing image metadata",
            name="missing_meta",
            cleanname="missing_meta",
            originalname="missing_meta.jpg",
            ext="jpg",
            size=123,
            type="image/jpeg",
            extra="0",
        )

        with pytest.raises(ImageProcessingError, match="No image metadata found for upload"):
            await make_image_filename_metadata(upload, "missing_meta-320x0.jpg")


class _DummyImagesRelation:
    """Minimal relation helper for tests that don't need DB-backed QuerySets."""

    def __init__(self, first_result):
        self._first_result = first_result

    def all(self):
        return self

    async def first(self):
        return self._first_result


class TestGetImageBytes:
    """Tests for get_image_bytes new processing branches."""

    @pytest.mark.asyncio
    async def test_get_image_bytes_writes_jpeg_for_processed_request(self):
        """Processed JPEG requests should return non-empty converted bytes."""
        img = Pillow.new("RGB", (64, 64), color="orange")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp, format="PNG")
            tmp_path = Path(tmp.name)

        upload = SimpleNamespace(filepath=tmp_path, images=_DummyImagesRelation(object()))
        processed_metadata = ProcessedImageMetadata(
            upload_id=1,
            type="png",
            width=64,
            height=64,
            bits=24,
            channels=3,
            requested_props={"width": None, "height": None, "type": "image/jpeg"},
            mime_type="image/png",
            new_type="jpeg",
            new_mime_type="image/jpeg",
            resized=False,
        )

        try:
            with patch("app.lib.image_processing.make_image_filename_metadata", new=AsyncMock(return_value=processed_metadata)):
                image_bytes = await get_image_bytes(upload, "demo.jpg")
                payload = image_bytes.read()

            assert len(payload) > 0
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_get_image_bytes_raises_for_unsupported_output_type(self):
        """Unsupported output types should raise NotImplementedError."""
        img = Pillow.new("RGB", (32, 32), color="purple")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp, format="PNG")
            tmp_path = Path(tmp.name)

        upload = SimpleNamespace(filepath=tmp_path, images=_DummyImagesRelation(object()))
        processed_metadata = ProcessedImageMetadata(
            upload_id=1,
            type="png",
            width=32,
            height=32,
            bits=24,
            channels=3,
            requested_props={"width": None, "height": None, "type": "image/tiff"},
            mime_type="image/png",
            new_type="tiff",
            new_mime_type="image/tiff",
            resized=False,
        )

        try:
            with patch("app.lib.image_processing.make_image_filename_metadata", new=AsyncMock(return_value=processed_metadata)):
                with pytest.raises(NotImplementedError, match="not yet implemented"):
                    await get_image_bytes(upload, "demo.tiff")
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_get_image_bytes_writes_png_for_processed_request(self):
        """Processed PNG requests should return non-empty PNG bytes."""
        img = Pillow.new("RGB", (32, 32), color="teal")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp, format="PNG")
            tmp_path = Path(tmp.name)

        upload = SimpleNamespace(filepath=tmp_path, images=_DummyImagesRelation(object()))
        processed_metadata = ProcessedImageMetadata(
            upload_id=1,
            type="png",
            width=32,
            height=32,
            bits=24,
            channels=3,
            requested_props={"width": None, "height": None, "type": "image/png"},
            mime_type="image/png",
            new_type="png",
            new_mime_type="image/png",
            resized=True,
        )

        try:
            with patch("app.lib.image_processing.make_image_filename_metadata", new=AsyncMock(return_value=processed_metadata)):
                image_bytes = await get_image_bytes(upload, "demo.png")
                payload = image_bytes.read()

            assert len(payload) > 0
            assert payload.startswith(b"\x89PNG")
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_get_image_bytes_writes_gif_for_processed_request(self):
        """Processed GIF requests should return non-empty GIF bytes."""
        img = Pillow.new("RGB", (32, 32), color="cyan")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp, format="PNG")
            tmp_path = Path(tmp.name)

        upload = SimpleNamespace(filepath=tmp_path, images=_DummyImagesRelation(object()))
        processed_metadata = ProcessedImageMetadata(
            upload_id=1,
            type="png",
            width=32,
            height=32,
            bits=24,
            channels=3,
            requested_props={"width": None, "height": None, "type": "image/gif"},
            mime_type="image/png",
            new_type="gif",
            new_mime_type="image/gif",
            resized=False,
        )

        try:
            with patch("app.lib.image_processing.make_image_filename_metadata", new=AsyncMock(return_value=processed_metadata)):
                image_bytes = await get_image_bytes(upload, "demo.gif")
                payload = image_bytes.read()

            assert len(payload) > 0
            assert payload.startswith((b"GIF87a", b"GIF89a"))
        finally:
            tmp_path.unlink(missing_ok=True)


class TestGetImageAsJpeg:
    """Tests for JPEG conversion helper paths."""

    def test_get_image_as_jpeg_handles_la_images(self):
        """LA mode images should be composited and encoded as JPEG successfully."""
        image_obj = Pillow.new("LA", (20, 20), color=(200, 100))

        image_bytes = get_image_as_jpeg(image_obj, None)
        payload = image_bytes.read()

        assert len(payload) > 0


class TestGifFrameHandling:
    """Tests for GIF frame counting and animated resize prerequisites."""

    def test_count_gif_frames_returns_full_count(self):
        """Two-frame GIFs should report a frame count of 2."""
        frame1 = Pillow.new("RGBA", (10, 10), color=(255, 0, 0, 255))
        frame2 = Pillow.new("RGBA", (10, 10), color=(0, 255, 0, 255))

        image_bytes = BytesIO()
        frame1.save(
            image_bytes,
            format="GIF",
            save_all=True,
            append_images=[frame2],
            duration=100,
            loop=0,
        )
        image_bytes.seek(0)

        gif_obj = Pillow.open(image_bytes)
        assert count_gif_frames(gif_obj) == 2


def _make_animated_gif_bytes(size=(40, 40)) -> BytesIO:
    """Create an in-memory animated GIF (2 frames) and return the buffer."""
    frame1 = Pillow.new("RGBA", size, color=(255, 0, 0, 255))
    frame2 = Pillow.new("RGBA", size, color=(0, 255, 0, 255))
    buf = BytesIO()
    frame1.save(
        buf,
        format="GIF",
        save_all=True,
        append_images=[frame2],
        duration=100,
        loop=0,
    )
    buf.seek(0)
    return buf


class TestHandleMultiframeImageObj:
    """Tests for handle_multiframe_image_obj return value contract."""

    def test_returns_none_for_non_gif(self):
        """Non-GIF images should return None."""
        img = Pillow.new("RGB", (20, 20), color="red")
        result = handle_multiframe_image_obj(img)
        assert result is None

    def test_returns_none_for_single_frame_gif(self):
        """Single-frame GIFs should return None."""
        frame = Pillow.new("RGBA", (10, 10), color=(255, 0, 0, 255))
        buf = BytesIO()
        frame.save(buf, format="GIF")
        buf.seek(0)
        gif_obj = Pillow.open(buf)
        result = handle_multiframe_image_obj(gif_obj)
        assert result is None

    def test_returns_list_of_frames_for_animated_gif(self):
        """Animated GIFs should return a list with one entry per frame."""
        gif_obj = Pillow.open(_make_animated_gif_bytes())
        result = handle_multiframe_image_obj(gif_obj)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_returned_frames_are_independent_copies(self):
        """Each frame in the returned list must be an independent copy."""
        gif_obj = Pillow.open(_make_animated_gif_bytes())
        result = handle_multiframe_image_obj(gif_obj)
        assert result is not None
        assert result[0] is not result[1]


class TestHandleImageResize:
    """Tests for handle_image_resize."""

    def test_resizes_single_frame_image(self):
        """Single-frame images should be returned as a single resized Image."""
        img = Pillow.new("RGB", (100, 80), color="blue")
        result = handle_image_resize(img, 50, 40)
        assert not isinstance(result, list)
        assert result.size == (50, 40)

    def test_resizes_all_frames_of_animated_gif(self):
        """Each frame of an animated GIF should be resized to the target dimensions."""
        gif_obj = Pillow.open(_make_animated_gif_bytes(size=(40, 40)))
        result = handle_image_resize(gif_obj, 20, 20)
        assert isinstance(result, list)
        assert len(result) == 2
        for frame in result:
            assert frame.size == (20, 20)


class TestProcessedImageCacheBehavior:
    """Tests for processed-image cache behavior in non-debug mode."""

    @pytest.mark.asyncio
    async def test_get_processed_image_path_uses_existing_cache_when_not_debug(self, tmp_path):
        """When debug is disabled and cache exists, processing should not rerun."""
        user_dir = tmp_path / "user_1"
        user_dir.mkdir(parents=True, exist_ok=True)
        source_path = user_dir / "source.png"
        source_path.write_bytes(b"source")

        upload = SimpleNamespace(name="demo", filepath=source_path, type="image/png")
        processed_metadata = ProcessedImageMetadata(
            upload_id=1,
            type="png",
            width=64,
            height=64,
            bits=24,
            channels=3,
            requested_props={"width": 64, "height": 64, "type": "image/png"},
            mime_type="image/png",
            new_type="png",
            new_mime_type="image/png",
            resized=True,
        )

        cache_path = user_dir / "cache" / "demo-64_64.png"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"cached")

        with patch("app.lib.image_processing.config.debug", False):
            with patch("app.lib.image_processing.make_image_filename_metadata", new=AsyncMock(return_value=processed_metadata)):
                with patch("app.lib.image_processing.get_image_bytes", new=AsyncMock(return_value=BytesIO(b"new-data"))) as get_image_bytes_mock:
                    result = await get_processed_image_path(upload, "demo-64x64.png")

        assert result == cache_path
        get_image_bytes_mock.assert_not_awaited()
        assert cache_path.read_bytes() == b"cached"

    @pytest.mark.asyncio
    async def test_get_processed_image_path_builds_cache_when_missing_and_not_debug(self, tmp_path):
        """When debug is disabled and cache is missing, processing should populate cache."""
        user_dir = tmp_path / "user_1"
        user_dir.mkdir(parents=True, exist_ok=True)
        source_path = user_dir / "source.png"
        source_path.write_bytes(b"source")

        upload = SimpleNamespace(name="demo", filepath=source_path, type="image/png")
        processed_metadata = ProcessedImageMetadata(
            upload_id=1,
            type="png",
            width=64,
            height=64,
            bits=24,
            channels=3,
            requested_props={"width": 64, "height": 64, "type": "image/png"},
            mime_type="image/png",
            new_type="png",
            new_mime_type="image/png",
            resized=True,
        )

        cache_path = user_dir / "cache" / "demo-64_64.png"
        if cache_path.exists():
            cache_path.unlink()

        with patch("app.lib.image_processing.config.debug", False):
            with patch("app.lib.image_processing.make_image_filename_metadata", new=AsyncMock(return_value=processed_metadata)):
                with patch("app.lib.image_processing.get_image_bytes", new=AsyncMock(return_value=BytesIO(b"new-data"))) as get_image_bytes_mock:
                    result = await get_processed_image_path(upload, "demo-64x64.png")

        assert result == cache_path
        get_image_bytes_mock.assert_awaited_once()
        assert cache_path.exists()
        assert cache_path.read_bytes() == b"new-data"


class TestMimeTypeToImageFormat:
    """Tests for mime_type_to_image_format."""

    @pytest.mark.asyncio
    async def test_jpeg_returns_jpeg(self):
        """image/jpeg must map to PIL format string 'JPEG'."""
        result = await mime_type_to_image_format("image/jpeg")
        assert result == "JPEG"

    @pytest.mark.asyncio
    async def test_png_returns_png(self):
        result = await mime_type_to_image_format("image/png")
        assert result == "PNG"

    @pytest.mark.asyncio
    async def test_gif_returns_gif(self):
        result = await mime_type_to_image_format("image/gif")
        assert result == "GIF"

    @pytest.mark.asyncio
    async def test_unsupported_type_raises_image_processing_error(self):
        """Unsupported MIME types must raise ImageProcessingError, not KeyError."""
        with pytest.raises(ImageProcessingError):
            await mime_type_to_image_format("image/tiff")


class TestHandleImageRotation:
    """Tests for handle_image_rotation."""

    def test_rotates_single_frame_image(self, tmp_path):
        """A landscape image rotated 90° with expand=True should have swapped dimensions."""
        img = Pillow.new("RGB", (100, 60), color="red")
        img_path = tmp_path / "test.jpg"
        img.save(str(img_path), format="JPEG")

        upload = SimpleNamespace(filepath=img_path)
        result = handle_image_rotation(upload, 90)

        assert not isinstance(result, list)
        assert result.size == (60, 100)

    def test_rotates_all_frames_of_animated_gif(self, tmp_path):
        """Each frame of an animated GIF should be rotated and returned as a list."""
        gif_bytes = _make_animated_gif_bytes(size=(40, 20))
        img_path = tmp_path / "test.gif"
        img_path.write_bytes(gif_bytes.read())

        upload = SimpleNamespace(filepath=img_path)
        result = handle_image_rotation(upload, 90)

        assert isinstance(result, list)
        assert len(result) == 2
        for frame in result:
            assert frame.size == (20, 40)

    def test_180_rotation_preserves_dimensions(self, tmp_path):
        """A 180° rotation should preserve the original dimensions."""
        img = Pillow.new("RGB", (100, 60), color="blue")
        img_path = tmp_path / "test.jpg"
        img.save(str(img_path), format="JPEG")

        upload = SimpleNamespace(filepath=img_path)
        result = handle_image_rotation(upload, 180)

        assert result.size == (100, 60)


class TestDoImageRotation:
    """Tests for do_image_rotation."""

    async def _create_upload_with_image(self, username, email, width=100, height=60):
        """Helper: create a DB-backed upload + Image record and return the prefetched upload."""
        user = await User.create(username=username, email=email, password="pw")
        upload = await Upload.create(
            user=user,
            description="",
            name="testrot",
            cleanname="testrot",
            originalname="testrot.jpg",
            ext="jpg",
            size=1000,
            type="image/jpeg",
            extra="0",
        )
        await Image.create(upload=upload, type="jpeg", width=width, height=height, bits=24, channels=3)
        return await Upload.get(id=upload.id).prefetch_related("images")

    @pytest.mark.asyncio
    async def test_raises_value_error_on_invalid_angle(self, db, tmp_path):
        """Angles outside [90, 180, 270] must raise ValueError."""
        upload = await self._create_upload_with_image("rotinvalid", "rotinvalid@example.com")
        img_path = tmp_path / "test.jpg"
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            with pytest.raises(ValueError, match="Invalid rotation angle"):
                await do_image_rotation(upload, 45)

    @pytest.mark.asyncio
    async def test_raises_when_no_image_metadata(self, db, tmp_path):
        """Uploads with no Image record must raise ImageProcessingError."""
        user = await User.create(username="rotnoimg", email="rotnoimg@example.com", password="pw")
        upload = await Upload.create(
            user=user, description="", name="noimg", cleanname="noimg",
            originalname="noimg.jpg", ext="jpg", size=100, type="image/jpeg", extra="0",
        )
        upload = await Upload.get(id=upload.id).prefetch_related("images")

        img_path = tmp_path / "test.jpg"
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            with pytest.raises(ImageProcessingError, match="No image metadata"):
                await do_image_rotation(upload, 90)

    @pytest.mark.asyncio
    async def test_90_degree_rotation_swaps_dimensions(self, db, tmp_path):
        """Metadata returned after a 90° rotation must have width and height swapped."""
        upload = await self._create_upload_with_image("rot90", "rot90@example.com", width=100, height=60)
        img_path = tmp_path / "test.jpg"
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            result = await do_image_rotation(upload, 90)

        assert result.width == 60
        assert result.height == 100

    @pytest.mark.asyncio
    async def test_270_degree_rotation_swaps_dimensions(self, db, tmp_path):
        upload = await self._create_upload_with_image("rot270", "rot270@example.com", width=100, height=60)
        img_path = tmp_path / "test.jpg"
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            result = await do_image_rotation(upload, 270)

        assert result.width == 60
        assert result.height == 100

    @pytest.mark.asyncio
    async def test_180_degree_rotation_preserves_dimensions(self, db, tmp_path):
        upload = await self._create_upload_with_image("rot180", "rot180@example.com", width=100, height=60)
        img_path = tmp_path / "test.jpg"
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            result = await do_image_rotation(upload, 180)

        assert result.width == 100
        assert result.height == 60

    @pytest.mark.asyncio
    async def test_overwrites_source_file(self, db, tmp_path):
        """The source image file must be replaced with the rotated version."""
        upload = await self._create_upload_with_image("rotfile", "rotfile@example.com")
        img_path = tmp_path / "test.jpg"
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")
        original_bytes = img_path.read_bytes()

        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            await do_image_rotation(upload, 90)

        assert img_path.read_bytes() != original_bytes

    @pytest.mark.asyncio
    async def test_clears_matching_cache_files(self, db, tmp_path):
        """Cached processed images matching the upload name must be deleted after rotation."""
        upload = await self._create_upload_with_image("rotcache", "rotcache@example.com")
        img_path = tmp_path / "testrot.jpg"
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "testrot-100_60.jpg"
        cache_file.write_bytes(b"cached-data")
        unrelated_file = cache_dir / "other-100_60.jpg"
        unrelated_file.write_bytes(b"other-cached")

        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            await do_image_rotation(upload, 90)

        assert not cache_file.exists()
        assert unrelated_file.exists()  # Unrelated cache files must not be deleted
