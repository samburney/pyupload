import textwrap

from typing import IO
from tempfile import SpooledTemporaryFile
from PIL import Image as Pillow, ImageDraw, ImageText, ImageFont
from fastapi.responses import Response, StreamingResponse, HTMLResponse

from app.lib.config import logger
from app.lib.helpers import IMAGE_CONVERSION_DST_FORMATS, split_filename


# User validation exceptions
class UserQuotaExceeded(Exception):
    """Exception raised when a user exceeds their upload quotas."""
    pass

class UserFileTypeNotAllowed(Exception):
    """Exception raised when a user uploads a disallowed file type."""
    pass

class NotAuthorisedError(Exception):
    """Raised when a user is not authorised to access a file."""
    pass

# Image processing exceptions
class ImageInvalidError(Exception):
    """Exception raised when an uploaded file is not a valid image."""
    pass

class ImageProcessingError(Exception):
    """Exception raised for errors in image metadata processing."""
    pass


def supports_error_image(filename: str) -> bool:
    """Return True when error responses can be rendered as an image for this filename."""
    ext = split_filename(filename)[1].lower()
    return bool(ext and f".{ext}" in IMAGE_CONVERSION_DST_FORMATS)


def error_response_for_get(
    *,
    filename: str,
    error_title: str,
    error_message: str,
    status_code: int,
) -> Response:
    """Return image error responses only for supported image conversion formats."""
    if supports_error_image(filename):
        try:
            return get_error_image_response(
                error_title=error_title,
                error_message=error_message,
                filename=filename,
                status_code=status_code,
            )
        except ImageProcessingError:
            logger.warning(
                "Falling back to HTML error response for unsupported image format: %s",
                filename,
            )
    return HTMLResponse(status_code=status_code)


def generate_error_image(error_title: str, error_message: str, format: str = 'JPEG', width: int = 320, height: int = 320) -> IO[bytes]:
    """Generate an in-memory image containing a formatted error title and message.

    Args:
        error_title: Short heading to render near the top of the image.
        error_message: Detailed error message rendered below the title.
        format: Output image format (for example, JPEG or PNG).
        width: Output image width in pixels.
        height: Output image height in pixels.

    Returns:
        A seeked binary file-like object containing encoded image bytes.
    """
    # Create blank image
    image_obj: Pillow.Image = Pillow.new(mode='RGB', size=(width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image_obj)

    # Confirm output format is support
    if f".{format.lower()}" not in IMAGE_CONVERSION_DST_FORMATS:
        raise ImageProcessingError(f"Error creating error message image: Format {format} is not supported.")

    # Write text to image
    header_text = 'pyupload image processing error'
    header_font = ImageFont.load_default(size=16)
    header_bbox = header_font.getbbox(text=header_text)
    header_pos_x: int = round((width - header_bbox[2])/2)
    header_pos_y: int = 10
    draw.rectangle((0, header_pos_y - 2, width, header_bbox[3] + header_pos_y + 2), fill=(255, 0, 0))
    draw.text((header_pos_x, header_pos_y), text=header_text, fill=(255, 255, 255), font=header_font)

    title_max_chars = 16
    title_font = ImageFont.load_default(36)
    title_text = ImageText.Text(text='\n'.join(textwrap.wrap(error_title, width=title_max_chars)), font=title_font)
    title_bbox = title_text.get_bbox()
    title_pos_x: int = round((width - title_bbox[2])/2)
    title_pos_y: int = header_pos_y + int(header_bbox[3] * 2)
    draw.text((title_pos_x, title_pos_y), text=title_text, fill=(0, 0, 0), font=title_font)

    message_max_chars = 32
    message_font = ImageFont.load_default(size=20)
    message_text = ImageText.Text(text='\n'.join(textwrap.wrap(error_message, width=message_max_chars)), font=message_font)
    message_bbox = message_text.get_bbox()
    message_pos_x: int = round((width - message_bbox[2])/2)
    message_pos_y: int = title_pos_y + int(title_bbox[3] + 30)
    draw.text((message_pos_x, message_pos_y), text=message_text, fill=(0, 0, 0), font=message_font)

    # Save image as bytes
    image_bytes: IO[bytes] = SpooledTemporaryFile(mode='w+b')
    image_obj.save(image_bytes, format=format.upper(), quality=80)
    image_bytes.seek(0)

    return image_bytes


def get_error_image_response(error_title: str, error_message: str, filename: str, status_code: int = 400) -> Response:
    """Build a streaming image HTTP response for /get endpoint error states.

    The target image format is inferred from the filename extension so clients
    requesting converted images receive a compatible error payload.
    """
    # Get requested format from supplied filename
    format = split_filename(filename)[1].upper()
    if format == 'JPG':
        format = 'JPEG'

    # Confirm output format is supported
    if not supports_error_image(filename):
        raise ImageProcessingError(f"Error creating error message image: Format {format} is not supported.")

    # Make error message image
    error_image_bytes = generate_error_image(error_title=error_title, error_message=error_message, format=format)

    # Return streaming file response
    response = StreamingResponse(error_image_bytes, media_type=IMAGE_CONVERSION_DST_FORMATS['.' + format.lower()], status_code=status_code)
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    response.headers["Cache-Control"] = f"public, max-age=60"

    return response
