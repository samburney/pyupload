import magic

from pathlib import Path
from typing import BinaryIO
from tempfile import SpooledTemporaryFile
from fastapi import UploadFile

from app.lib.config import logger
from app.lib.helpers import split_filename


def get_filename(file: UploadFile | BinaryIO | SpooledTemporaryFile, filename: str | None = None) -> str:
    """Get the filename from UploadFile or BinaryIO or SpooledTemporaryFile."""
    if filename is None and hasattr(file, 'filename') and getattr(file, 'filename') is not None:
        filename = getattr(file, 'filename')
    elif filename is None:
        raise ValueError("Uploaded file must have a filename.")

    if filename is None:
        raise RuntimeError("Filename cannot be None.")

    return filename


def get_file_instance(file: UploadFile | BinaryIO | SpooledTemporaryFile) -> BinaryIO | SpooledTemporaryFile:
    """Get a file-like object from UploadFile or BinaryIO.

    Returns the underlying binary file object, handling import path variations
    and different file-like object types.
    """
    if type(file).__name__ == 'UploadFile' and hasattr(file, 'file'):
        return getattr(file, 'file')
    elif isinstance(file, SpooledTemporaryFile):
        return file
    elif hasattr(file, 'read') and hasattr(file, 'seek'):
        return file  # type: ignore
    else:
        raise TypeError("Supplied value must be a BinaryIO, UploadFile, or SpooledTemporaryFile")


def get_file_size(file: BinaryIO | UploadFile | SpooledTemporaryFile) -> int:
    """Get the size of the uploaded file in bytes."""
    file_inst: BinaryIO | SpooledTemporaryFile = get_file_instance(file)

    current_pos = file_inst.tell()
    file_inst.seek(0, 2)
    size = file_inst.tell()
    file_inst.seek(current_pos)

    return size


async def get_file_mime_type(file: UploadFile | BinaryIO | SpooledTemporaryFile) -> str:
    """Get the MIME type of the uploaded file."""
    file_size = get_file_size(file)
    if file_size == 0:
        raise ValueError("Cannot determine MIME type of empty file.")

    read_len = min(1024, file_size)

    if type(file).__name__ == 'UploadFile' and hasattr(file, 'file'):
        await file.seek(0)  # type: ignore
        data = await file.read(read_len)  # type: ignore
        mime_type = magic.from_buffer(data, mime=True)
        await file.seek(0)  # type: ignore
    else:
        current_pos = file.tell()  # type: ignore
        file.seek(0)  # type: ignore
        data = file.read(read_len)  # type: ignore
        mime_type = magic.from_buffer(data, mime=True)  # type: ignore
        file.seek(current_pos)  # type: ignore

    return mime_type


def delete_file(filepath: Path) -> bool:
    """Delete the file at filepath and any cached variants.

    Cached variants are matched by glob: filepath.parent / "cache" / "{stem}-*".
    """
    deleted = False

    # Delete file from storage
    try:
        if filepath.exists():
            filepath.unlink()
            deleted = True
        else:
            logger.warning(f"File not found for deletion: {filepath}")
    except Exception as e:
        logger.error(f"Failed to delete file {filepath}: {e}")

    # Delete cached variants
    cache_dir = filepath.parent / "cache"
    filename_stem = split_filename(filepath.name)[0]
    if cache_dir.is_dir():
        for cached_file in cache_dir.glob(f"{filename_stem}-*"):
            try:
                cached_file.unlink()
            except Exception as e:
                logger.error(f"Failed to delete cached file {cached_file}: {e}")

    return deleted
