from pathlib import Path
from typing import TYPE_CHECKING, IO
from tempfile import SpooledTemporaryFile
from PIL import Image as Pillow, UnidentifiedImageError

from app.lib.config import logger
from app.lib.helpers import split_filename

from app.models.images import (
    Image,
    ImageMetadata,
    ProcessedImageMetadata,
    IMAGE_PROCESSING_FORMATS,
    IMAGE_CONVERSION_DST_FORMATS,
    IMAGE_SHORT_DIMENSIONS
)


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


def parse_image_filename(filename: str) -> dict | None:
    """Parse an image filename to extract width, height, and extension.
    
    Args:
        filename: The filename to parse
        
    Returns:
        A dictionary containing (width, height, mime_type) or None if invalid
        
    Examples:
        >>> parse_image_filename("image-1920x1080.jpg")
        {'width': '1920', 'height': '1080', 'type': 'image/jpeg'}
        >>> parse_image_filename("image.jpg")
        {'width': None, 'height': None, 'type': 'image/jpeg'}
        >>> parse_image_filename("image") or parse_image_filename("image.txt")
        None
    """
    
    # Split into name and extension
    name, extension = split_filename(filename)

    # Get the mime type from the extension
    if not extension or f".{extension}" not in IMAGE_CONVERSION_DST_FORMATS:
        logger.warning(f"Filename '{filename}' has invalid or unsupported extension for image processing.")
        return None
    else:
        mime_type = IMAGE_CONVERSION_DST_FORMATS[f".{extension}"]

    # Determine file dimension constraints if specified
    # Split filename at hyphen if there is one
    new_width = None
    new_height = None
    parts = name.split('-')
    if len(parts) == 2:
        dimensions = parts[1]

        # If single digit is specified, return as width and height
        if dimensions.isdigit():
            new_width = dimensions
            new_height = dimensions
        
        # If a string is specified we need to do some parsing
        if 'x' in dimensions:
            width, height = dimensions.split('x')
            if width.isdigit():
                new_width = int(width) if int(width) != 0 else None
            if height.isdigit():
                new_height = int(height) if int(height) != 0 else None
        
        # If a short dimension string is specified, return as width and height
        elif dimensions in IMAGE_SHORT_DIMENSIONS:
            new_width, new_height = IMAGE_SHORT_DIMENSIONS[dimensions].split('x')

    if new_height is not None:
        new_height = int(new_height)
    if new_width is not None:
        new_width = int(new_width)

    return {
        'width': new_width,
        'height': new_height,
        'type': mime_type
    }


async def get_image_bytes(upload: "Upload", filename: str) -> IO[bytes]:
    """Get image as bytes for a given upload and filename."""

    image_metadata = await upload.images.all().first()
    image_filename_metadata = await make_image_filename_metadata(upload, filename)

    
    if image_metadata is None:
        raise ImageProcessingError("No image metadata found for upload.")

    # If no processing is required, return the original image bytes
    image_bytes = SpooledTemporaryFile()
    if image_filename_metadata is None:
        with open(upload.filepath, 'rb') as f:
            image_bytes.write(f.read())
            image_bytes.seek(0)
        return image_bytes

    # Process image as required based on filename metadata
    resize = image_filename_metadata.resized
    convert = image_filename_metadata.converted

    if resize or convert:
        image_obj = Pillow.open(upload.filepath)

        # If resize required, resize the image
        if resize:
            image_obj = get_resized_image_obj(
                upload,
                image_filename_metadata.width,
                image_filename_metadata.height,
                maintain_aspect_ratio=False,
            )

        # Return the image bytes in requested format
        output_format = image_filename_metadata.new_type.lower() if image_filename_metadata.new_type else None
        if output_format is None:
            raise ImageProcessingError(f"Cannot process {filename}; No output image type specified for processed image.")

        if output_format == 'jpeg':
            get_image_as_jpeg(image_obj, image_bytes)
        elif f"image/{output_format}" not in IMAGE_CONVERSION_DST_FORMATS.values():
            raise ImageProcessingError(
                f"Cannot process {filename}; Unsupported output image type '{output_format}' for processed image."
        )
        else:
            raise NotImplementedError(f"Cannot process {filename}; processing for output image type '{output_format}' is not yet implemented.")

    # Return the image bytes
    return image_bytes


def get_resized_image_obj(
    upload: "Upload", new_width: int | None, new_height: int | None, maintain_aspect_ratio: bool = True
) -> Pillow.Image:
    """Resize an image to the specified dimensions while optionally maintaining aspect ratio."""

    # Open the original image
    try:
        image_object = Pillow.open(upload.filepath)
    except (UnidentifiedImageError, OSError):
        raise ImageInvalidError("Uploaded file is not a valid image.")

    # If maintaining aspect ratio, calculate new dimensions
    if maintain_aspect_ratio:
        original_width, original_height = image_object.size
        aspect_ratio = original_width / original_height

        if new_width is not None and new_height is not None:
            if aspect_ratio > 1:  # Landscape
                new_height = int(new_width / aspect_ratio)
            else:  # Portrait or square
                new_width = int(new_height * aspect_ratio)

        elif new_width is not None:
            new_height = int(new_width / aspect_ratio)

        elif new_height is not None:
            new_width = int(new_height * aspect_ratio)
    
    # Otherwise, if not maintaining aspect ratio, set any missing dimension to original
    else:
        if new_width is None:
            new_width = image_object.width
        if new_height is None:
            new_height = image_object.height

    # Resize the image and return the new image object
    if new_width != image_object.width or new_height != image_object.height:
        resized_image = image_object.resize((new_width, new_height))
        return resized_image

    # If we're not resizing, return the original image object
    else:
        return image_object


async def make_image_filename_metadata(upload: "Upload", filename: str) -> ProcessedImageMetadata | None:
    """
    Get the metadata for a processed image based on the filename.
    This is used to determine if an image needs to be processed and
    what processing is required.
    
    :param upload: Upload object for the image being requested
    :type upload: Upload
    :param filename: Filename of the image being requested
    :type filename: str
    :return: Metadata for the processed image or None if no processing is required
    :rtype: ImageMetadata | None
    """

    resize: bool = False
    convert: bool = False
    aspect_ratio: float | None = None
    new_width: int | None = None
    new_height: int | None = None

    # Original image metadata
    image_metadata = await upload.images.all().first()
    if image_metadata is None:
        raise ImageProcessingError("No image metadata found for upload.")
    
    # Parse filename for updated image properties
    new_image_props = parse_image_filename(filename)
    if new_image_props is None:
        return None

    # Check if conversion is required and get image format to use
    if new_image_props['type'] is not None and getattr(upload, 'type') in IMAGE_PROCESSING_FORMATS.values():
        if new_image_props['type'] != getattr(upload, 'type'):
            convert = True
        
    else:
        if getattr(upload, 'type') not in IMAGE_PROCESSING_FORMATS.values():
            logger.warning(f"Cannot process {filename}; image type '{getattr(upload, 'type')}' is not supported for processing.")

        new_image_props['type'] = getattr(upload, 'type')

    # Check if resizing is required
    if (new_image_props['width'] is not None and \
        int(new_image_props['width']) < getattr(image_metadata, 'width', 0)) or \
       (new_image_props['height'] is not None and \
        int(new_image_props['height']) < getattr(image_metadata, 'height', 0)):

        resize = True

    # No processing required, return None
    if not resize and not convert:
        return None

    # Determine new image dimensions if resizing is required
    if resize:
        aspect_ratio = round(getattr(image_metadata, "width") / getattr(image_metadata, "height"), 3)
        new_width = new_image_props['width']
        new_height = new_image_props['height']

        # If both width and height are provided, fit resulting image
        # Landscape format
        if aspect_ratio > 1:
            if new_width is not None and new_height is not None:
                new_height = int(new_width / aspect_ratio)
            elif new_width is not None:
                new_height = int(new_width / aspect_ratio)
            elif new_height is not None:
                new_width = int(new_height * aspect_ratio)

        # Portrait format
        elif aspect_ratio < 1:
            if new_width is not None and new_height is not None:
                new_width = int(new_height * aspect_ratio)
            elif new_width is not None:
                new_height = int(new_width / aspect_ratio)
            elif new_height is not None:
                new_width = int(new_height * aspect_ratio)

        # Square format
        else:
            if new_width is not None and new_height is not None:
                new_width = new_height = min(new_width, new_height)
            elif new_width is not None:
                new_height = new_width
            elif new_height is not None:
                new_width = new_height

    # Build and return new image metadata
    output_mime_type = new_image_props['type']
    output_type = output_mime_type.split('/')[-1].lower() if output_mime_type is not None else None

    processed_image_metadata = ProcessedImageMetadata(
        upload_id=upload.id,
        type=getattr(image_metadata, "type"),
        width=new_width or getattr(image_metadata, "width"),
        height=new_height or getattr(image_metadata, "height"),
        bits=getattr(image_metadata, "bits"),
        channels=getattr(image_metadata, "channels"),
        requested_props=new_image_props,
        mime_type=getattr(upload, "type"),
        new_type=output_type,
        new_mime_type=output_mime_type,
        resized=resize,
    )

    return processed_image_metadata
        

async def get_processed_image_path(upload: "Upload", filename: str) -> Path | None:
    """Get the file path of a processed image based on the filename."""

    # Determine if processed image is even required
    processed_image_metadata = await make_image_filename_metadata(upload, filename)

    if processed_image_metadata is not None:
        new_image_width = processed_image_metadata.width
        new_image_height = processed_image_metadata.height
        new_image_type = processed_image_metadata.new_type
        if new_image_type is None:
            new_image_type = getattr(processed_image_metadata, 'type', '').lower()
        if not new_image_type:
            new_image_type = upload.type.split('/')[-1].lower()
        new_image_extension = new_image_type

        # Determine the filename for the processed image in the cache directory
        image_cache_filename = f"{upload.name}-{new_image_width}_{new_image_height}.{new_image_extension}"
        image_cache_filepath = upload.filepath.parent / "cache" / image_cache_filename
        
        # If the processed image doesn't exist, create it and save to the cache directory
        if not image_cache_filepath.exists():
            image_data = await get_image_bytes(upload, filename)
            if image_data is not None:
                image_cache_filepath.parent.mkdir(exist_ok=True)
                with open(image_cache_filepath, 'wb') as f:
                    f.write(image_data.read())

        return image_cache_filepath

    return None


def get_image_as_jpeg(image_obj: Pillow.Image, image_bytes: IO[bytes] | None, quality: int = 80) -> IO[bytes]:
    """Convert an image object to JPEG format and write to output bytes."""
    
    # If no image_bytes provided, create a new in-memory bytes object
    if image_bytes is None:
        image_bytes = SpooledTemporaryFile()
    
    # Handle images with transparency by pasting onto white background before saving as JPEG
    if image_obj.mode in ("RGBA", "LA") or (image_obj.mode == "P" and "transparency" in image_obj.info): # Image with alpha channel
        image_obj = image_obj.convert("RGBA")
        background = Pillow.new("RGB", image_obj.size, (255, 255, 255))
        background.paste(image_obj, mask=image_obj.getchannel(3))  # 3 is the alpha channel
        background.save(image_bytes, format="JPEG", quality=quality)

    # For other images, convert to RGB and save as JPEG
    else:
        image_obj.convert("RGB").save(image_bytes, format="JPEG", quality=quality)
    image_bytes.seek(0)

    return image_bytes
