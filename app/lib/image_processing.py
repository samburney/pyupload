from typing import TYPE_CHECKING

from PIL import Image as Pillow, UnidentifiedImageError

from app.models.images import Image, ImageMetadata

if TYPE_CHECKING:
    from app.models.uploads import Upload


class ImageInvalidError(Exception):
    """Exception raised when an uploaded file is not a valid image."""
    pass

class ImageProcessingError(Exception):
    """Exception raised for errors in image metadata processing."""
    pass


async def make_image_metadata(upload: "Upload") -> ImageMetadata:
    """Build metadata for an uploaded file."""
    
    # Get upload filepath
    filepath = upload.filepath

    # Attempt to open as an image and extract metadata
    try:
        image_object = Pillow.open(filepath)
    except (UnidentifiedImageError, OSError):
        raise ImageInvalidError("Uploaded file is not a valid image.")
    
    # Extract image metadata
    # Get image type from MIME type if not able to be determined from format
    if image_object.format:
        type: str = image_object.format.lower()
    else:
        type: str = upload.type.split('/')[-1].lower()

    width: int = image_object.width
    height: int = image_object.height
    channels: int = len(image_object.getbands())

    # Attempt to get bitdepth from image info
    if "bitdepth" in image_object.info:
        bits_per_channel: int = image_object.info["bitdepth"]
        bits: int = bits_per_channel * channels
    else:
        # Fallback based on common modes
        mode = image_object.mode
        if mode == "1":  # 1-bit pixels, black and white
            bits = 1 * channels
        elif mode == "I" or mode == "F": # Fixed 32 bit pixels
            bits = 32
        else:  # Default to 8 bits per channel
            bits = 8 * channels

    # Additional metadata extraction (if needed)
    animated: bool = getattr(image_object, "is_animated", False)
    frames: int = getattr(image_object, "n_frames", 1)
    transparency: bool = getattr(image_object, "has_transparency_data", False)

    # Build and return ImageMetadata object
    metadata = ImageMetadata(
        upload_id=upload.id,
        type=type,
        width=width,
        height=height,
        bits=bits,
        channels=channels,
        animated=animated,
        frames=frames,
        transparency=transparency,
    )

    return metadata


async def process_uploaded_image(upload: "Upload") -> Image:
    """Process an uploaded image and return its metadata."""
    # Build image metadata
    try:
        image_metadata = await make_image_metadata(upload)
    except ImageInvalidError as e:
        # Pass through invalid image errors
        raise e
    except Exception as e:
        raise ImageProcessingError(f"Failed to build image metadata: {e}")

    # Create Image record in database
    try:
        image = await Image.create(
            upload=upload,
            type=image_metadata.type,
            width=image_metadata.width,
            height=image_metadata.height,
            bits=image_metadata.bits,
            channels=image_metadata.channels,
        )
    except Exception as e:
        raise ImageProcessingError(f"Failed to create Image record in database: {e}")

    return image
