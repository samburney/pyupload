"""
Tests for Image Tortoise ORM model.

Validates:
- Image model creation and persistence
- Foreign key relationship to Upload model
- Model table mapping and field defaults
- TimestampMixin functionality
- Image metadata fields (type, width, height, bits, channels)
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.models.users import User
from app.models.uploads import Upload
from app.models.images import Image


class TestImageModel:
    """Test Image Tortoise ORM model."""

    @pytest.mark.asyncio
    async def test_image_model_creation(self, db):
        """Test Image model creation succeeds."""
        # Create user and upload first
        user = await User.create(
            username="imageuser",
            email="image@example.com",
            password="hashed_password_image",
            fingerprint_hash="fp-hash-image",
        )

        upload = await Upload.create(
            user=user,
            description="Image test upload",
            name="image_20250124-063307_a1b2c3d4",
            cleanname="image",
            originalname="photo.jpg",
            ext="jpg",
            size=102400,
            type="image/jpeg",
            extra="0",
        )

        # Create image record
        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=1920,
            height=1080,
            bits=24,
            channels=3,
        )

        assert image.id is not None
        assert image.upload_id == upload.id
        assert image.type == "image/jpeg"
        assert image.width == 1920
        assert image.height == 1080
        assert image.bits == 24
        assert image.channels == 3

    @pytest.mark.asyncio
    async def test_image_model_all_fields_persist(self, db):
        """Test Image model persists all required fields."""
        user = await User.create(
            username="imageuser2",
            email="image2@example.com",
            password="hashed_password_image2",
            fingerprint_hash="fp-hash-image2",
        )

        upload = await Upload.create(
            user=user,
            description="Test upload 2",
            name="image2_20250124-063307_b2c3d4e5",
            cleanname="image2",
            originalname="photo2.png",
            ext="png",
            size=204800,
            type="image/png",
            extra="0",
        )

        # Create image with all fields
        original_data = {
            "upload": upload,
            "type": "image/png",
            "width": 800,
            "height": 600,
            "bits": 32,
            "channels": 4,
        }

        image = await Image.create(**original_data)

        # Retrieve from database and verify all fields
        retrieved = await Image.get(id=image.id)
        assert retrieved.upload_id == upload.id
        assert retrieved.type == "image/png"
        assert retrieved.width == 800
        assert retrieved.height == 600
        assert retrieved.bits == 32
        assert retrieved.channels == 4

    @pytest.mark.asyncio
    async def test_image_model_upload_relationship(self, db):
        """Test Image model upload foreign key relationship."""
        user = await User.create(
            username="imageuser3",
            email="image3@example.com",
            password="hashed_password_image3",
            fingerprint_hash="fp-hash-image3",
        )

        upload = await Upload.create(
            user=user,
            description="Upload for relationship test",
            name="reltest_20250124-063307_c3d4e5f6",
            cleanname="reltest",
            originalname="photo3.jpg",
            ext="jpg",
            size=51200,
            type="image/jpeg",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=640,
            height=480,
            bits=24,
            channels=3,
        )

        # Verify relationship works
        assert image.upload_id == upload.id
        
        # Retrieve and verify relationship is intact
        retrieved_image = await Image.get(id=image.id)
        assert retrieved_image.upload_id == upload.id

    @pytest.mark.asyncio
    async def test_image_model_table_mapping(self, db):
        """Test Image model maps correctly to images table."""
        user = await User.create(
            username="imageuser4",
            email="image4@example.com",
            password="hashed_password_image4",
            fingerprint_hash="fp-hash-image4",
        )

        upload = await Upload.create(
            user=user,
            description="Upload for table mapping test",
            name="tabletest_20250124-063307_d4e5f6a7",
            cleanname="tabletest",
            originalname="photo4.png",
            ext="png",
            size=102400,
            type="image/png",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/png",
            width=1024,
            height=768,
            bits=32,
            channels=4,
        )

        # Verify we can retrieve by querying all
        all_images = await Image.all()
        assert len(all_images) > 0
        assert any(i.id == image.id for i in all_images)

    @pytest.mark.asyncio
    async def test_image_model_timestamp_mixin_created_at(self, db):
        """Test Image model TimestampMixin created_at tracking."""
        user = await User.create(
            username="imageuser5",
            email="image5@example.com",
            password="hashed_password_image5",
            fingerprint_hash="fp-hash-image5",
        )

        upload = await Upload.create(
            user=user,
            description="Upload for timestamp test",
            name="tstest_20250124-063307_e5f6a7b8",
            cleanname="tstest",
            originalname="photo5.jpg",
            ext="jpg",
            size=76800,
            type="image/jpeg",
            extra="0",
        )

        before = datetime.now(timezone.utc)
        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=512,
            height=384,
            bits=24,
            channels=3,
        )
        after = datetime.now(timezone.utc)

        # created_at should be between before and after, within reasonable bounds
        assert image.created_at is not None
        assert before <= image.created_at <= after + timedelta(seconds=1)

    @pytest.mark.asyncio
    async def test_image_model_timestamp_mixin_updated_at(self, db):
        """Test Image model TimestampMixin updated_at tracking."""
        user = await User.create(
            username="imageuser6",
            email="image6@example.com",
            password="hashed_password_image6",
            fingerprint_hash="fp-hash-image6",
        )

        upload = await Upload.create(
            user=user,
            description="Upload for updated_at test",
            name="updatetest_20250124-063307_f6a7b8c9",
            cleanname="updatetest",
            originalname="photo6.gif",
            ext="gif",
            size=38400,
            type="image/gif",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/gif",
            width=256,
            height=192,
            bits=8,
            channels=3,
        )

        # Both should exist and be close to equal on creation
        assert image.created_at is not None
        assert image.updated_at is not None
        # updated_at should be >= created_at
        assert image.updated_at >= image.created_at

    @pytest.mark.asyncio
    async def test_multiple_images_for_single_upload(self, db):
        """Test that a single upload can have multiple Image records (one-to-many)."""
        user = await User.create(
            username="imageuser7",
            email="image7@example.com",
            password="hashed_password_image7",
            fingerprint_hash="fp-hash-image7",
        )

        upload = await Upload.create(
            user=user,
            description="Upload for multi-image test",
            name="multiimage_20250124-063307_a7b8c9d0",
            cleanname="multiimage",
            originalname="multi.jpg",
            ext="jpg",
            size=204800,
            type="image/jpeg",
            extra="0",
        )

        # Create multiple Image records for same upload
        images = []
        for i in range(3):
            image = await Image.create(
                upload=upload,
                type="image/jpeg",
                width=640 + (i * 100),
                height=480 + (i * 100),
                bits=24,
                channels=3,
            )
            images.append(image)

        # Verify all images are associated with the same upload
        assert len(images) == 3
        assert all(img.upload_id == upload.id for img in images)

    @pytest.mark.asyncio
    async def test_image_metadata_fields_rgb(self, db):
        """Test image model with RGB metadata (3 channels, 24 bits)."""
        user = await User.create(
            username="imageuser8",
            email="image8@example.com",
            password="hashed_password_image8",
            fingerprint_hash="fp-hash-image8",
        )

        upload = await Upload.create(
            user=user,
            description="RGB image test",
            name="rgb_20250124-063307_b8c9d0e1",
            cleanname="rgb",
            originalname="rgb.jpg",
            ext="jpg",
            size=153600,
            type="image/jpeg",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=1280,
            height=960,
            bits=24,
            channels=3,
        )

        assert image.bits == 24
        assert image.channels == 3

    @pytest.mark.asyncio
    async def test_image_metadata_fields_rgba(self, db):
        """Test image model with RGBA metadata (4 channels, 32 bits)."""
        user = await User.create(
            username="imageuser9",
            email="image9@example.com",
            password="hashed_password_image9",
            fingerprint_hash="fp-hash-image9",
        )

        upload = await Upload.create(
            user=user,
            description="RGBA image test",
            name="rgba_20250124-063307_c9d0e1f2",
            cleanname="rgba",
            originalname="rgba.png",
            ext="png",
            size=204800,
            type="image/png",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/png",
            width=1920,
            height=1440,
            bits=32,
            channels=4,
        )

        assert image.bits == 32
        assert image.channels == 4

    @pytest.mark.asyncio
    async def test_image_metadata_fields_grayscale(self, db):
        """Test image model with grayscale metadata (1 channel, 8 bits)."""
        user = await User.create(
            username="imageuser10",
            email="image10@example.com",
            password="hashed_password_image10",
            fingerprint_hash="fp-hash-image10",
        )

        upload = await Upload.create(
            user=user,
            description="Grayscale image test",
            name="gray_20250124-063307_d0e1f2a3",
            cleanname="gray",
            originalname="gray.jpg",
            ext="jpg",
            size=76800,
            type="image/jpeg",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=640,
            height=480,
            bits=8,
            channels=1,
        )

        assert image.bits == 8
        assert image.channels == 1

    @pytest.mark.asyncio
    async def test_image_model_cascade_delete_on_upload_delete(self, db):
        """Test that Image records are deleted when Upload is deleted (CASCADE)."""
        user = await User.create(
            username="imageuser11",
            email="image11@example.com",
            password="hashed_password_image11",
            fingerprint_hash="fp-hash-image11",
        )

        upload = await Upload.create(
            user=user,
            description="Upload for cascade delete test",
            name="cascade_20250124-063307_e1f2a3b4",
            cleanname="cascade",
            originalname="cascade.jpg",
            ext="jpg",
            size=102400,
            type="image/jpeg",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=800,
            height=600,
            bits=24,
            channels=3,
        )

        image_id = image.id

        # Verify image exists
        assert await Image.get(id=image_id) is not None

        # Delete the upload
        await upload.delete()

        # Image should be automatically deleted due to CASCADE
        image_count = await Image.filter(id=image_id).count()
        assert image_count == 0

    @pytest.mark.asyncio
    async def test_image_various_dimensions(self, db):
        """Test image model with various dimension sizes."""
        user = await User.create(
            username="imageuser12",
            email="image12@example.com",
            password="hashed_password_image12",
            fingerprint_hash="fp-hash-image12",
        )

        test_cases = [
            (100, 100),      # Small square
            (640, 480),      # VGA
            (1280, 720),     # HD
            (1920, 1080),    # Full HD
            (3840, 2160),    # 4K
            (1, 1),          # Minimal size
        ]

        for width, height in test_cases:
            upload = await Upload.create(
                user=user,
                description=f"Image {width}x{height}",
                name=f"dim_{width}x{height}_20250124-063307_{width:04x}{height:04x}",
                cleanname=f"dim_{width}x{height}",
                originalname=f"img_{width}x{height}.jpg",
                ext="jpg",
                size=0,
                type="image/jpeg",
                extra="0",
            )

            image = await Image.create(
                upload=upload,
                type="image/jpeg",
                width=width,
                height=height,
                bits=24,
                channels=3,
            )

            assert image.width == width
            assert image.height == height


class TestImageModelIntegration:
    """Integration tests for Image model with Upload relationships."""

    @pytest.mark.asyncio
    async def test_multiple_uploads_with_images(self, db):
        """Test multiple uploads each with associated image records."""
        user = await User.create(
            username="multi_image_user",
            email="multi@example.com",
            password="hashed_password_multi",
            fingerprint_hash="fp-hash-multi",
        )

        # Create multiple uploads with images
        for i in range(3):
            upload = await Upload.create(
                user=user,
                description=f"Upload {i+1}",
                name=f"multi{i+1}_20250124-063307_{i:08x}",
                cleanname=f"multi{i+1}",
                originalname=f"img{i+1}.jpg",
                ext="jpg",
                size=100000,
                type="image/jpeg",
                extra="0",
            )

            image = await Image.create(
                upload=upload,
                type="image/jpeg",
                width=640 + (i * 100),
                height=480 + (i * 100),
                bits=24,
                channels=3,
            )

        # Verify all images were created
        all_images = await Image.all()
        assert len(all_images) >= 3

    @pytest.mark.asyncio
    async def test_image_query_by_upload(self, db):
        """Test querying images filtered by upload."""
        user = await User.create(
            username="query_user",
            email="query@example.com",
            password="hashed_password_query",
            fingerprint_hash="fp-hash-query",
        )

        upload = await Upload.create(
            user=user,
            description="Upload with query test",
            name="query_20250124-063307_deadbeef",
            cleanname="query",
            originalname="query.jpg",
            ext="jpg",
            size=102400,
            type="image/jpeg",
            extra="0",
        )

        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=800,
            height=600,
            bits=24,
            channels=3,
        )

        # Query images for this upload
        images = await Image.filter(upload=upload)
        assert len(images) == 1
        assert images[0].id == image.id

