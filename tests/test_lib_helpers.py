"""Tests for app/lib/helpers.py functions."""

import pytest
from app.lib.helpers import (
    is_bool,
    validate_mime_types,
    split_filename,
    make_clean_filename,
    make_unique_filename,
)


class TestIsBool:
    """Test the is_bool utility function."""

    def test_returns_true_for_string_true(self):
        """Test that string 'true' returns True."""
        assert is_bool("true") is True

    def test_returns_true_for_string_yes(self):
        """Test that string 'yes' returns True."""
        assert is_bool("yes") is True

    def test_returns_true_for_string_on(self):
        """Test that string 'on' returns True."""
        assert is_bool("on") is True

    def test_returns_true_for_string_1(self):
        """Test that string '1' returns True."""
        assert is_bool("1") is True

    def test_returns_true_for_int_1(self):
        """Test that integer 1 returns True."""
        assert is_bool(1) is True

    def test_returns_true_for_bool_true(self):
        """Test that boolean True returns True."""
        assert is_bool(True) is True

    def test_returns_true_with_whitespace(self):
        """Test that strings with surrounding whitespace return correct value."""
        assert is_bool("  true  ") is True
        assert is_bool(" yes ") is True

    def test_returns_true_case_insensitive(self):
        """Test that comparison is case-insensitive."""
        assert is_bool("TRUE") is True
        assert is_bool("True") is True
        assert is_bool("YES") is True

    def test_returns_false_for_string_false(self):
        """Test that string 'false' returns False."""
        assert is_bool("false") is False

    def test_returns_false_for_string_no(self):
        """Test that string 'no' returns False."""
        assert is_bool("no") is False

    def test_returns_false_for_string_off(self):
        """Test that string 'off' returns False."""
        assert is_bool("off") is False

    def test_returns_false_for_string_0(self):
        """Test that string '0' returns False."""
        assert is_bool("0") is False

    def test_returns_false_for_int_0(self):
        """Test that integer 0 returns False."""
        assert is_bool(0) is False

    def test_returns_false_for_bool_false(self):
        """Test that boolean False returns False."""
        assert is_bool(False) is False

    def test_returns_false_for_arbitrary_string(self):
        """Test that arbitrary strings return False."""
        assert is_bool("random") is False
        assert is_bool("maybe") is False


class TestValidateMimeTypes:
    """Test MIME type validation function."""

    def test_validates_wildcard(self):
        """Test that wildcard '*' passes validation."""
        assert validate_mime_types("*") is True

    def test_validates_single_mime_type(self):
        """Test that single MIME type passes validation."""
        assert validate_mime_types("image/jpeg") is True
        assert validate_mime_types("application/pdf") is True
        assert validate_mime_types("text/plain") is True

    def test_validates_comma_separated_types(self):
        """Test that comma-separated MIME types pass validation."""
        assert validate_mime_types("image/jpeg,image/png") is True
        assert validate_mime_types("image/jpeg, image/png, application/pdf") is True

    def test_validates_with_whitespace(self):
        """Test MIME types with surrounding whitespace."""
        assert validate_mime_types(" image/jpeg ") is True
        assert validate_mime_types("image/jpeg , image/png") is True

    def test_validates_types_with_plus_sign(self):
        """Test MIME types with plus sign like application/vnd.api+json."""
        assert validate_mime_types("application/vnd.api+json") is True

    def test_validates_types_with_hyphen(self):
        """Test MIME types with hyphens."""
        assert validate_mime_types("application/x-bzip2") is True
        assert validate_mime_types("application/x-tar") is True

    def test_validates_types_with_dot(self):
        """Test MIME types with dots."""
        assert validate_mime_types("application/vnd.oasis.opendocument.text") is True

    def test_rejects_empty_string(self):
        """Test that empty string fails validation."""
        assert validate_mime_types("") is False
        assert validate_mime_types("   ") is False

    def test_rejects_none_value(self):
        """Test that None value fails validation."""
        assert validate_mime_types(None) is False

    def test_rejects_invalid_format(self):
        """Test that invalid MIME type format fails validation."""
        assert validate_mime_types("invalid") is False
        assert validate_mime_types("image") is False
        assert validate_mime_types("///") is False

    def test_rejects_missing_subtype(self):
        """Test that missing subtype fails validation."""
        assert validate_mime_types("image/") is False
        assert validate_mime_types("/jpeg") is False

    def test_rejects_invalid_in_list(self):
        """Test that one invalid type in list fails validation."""
        assert validate_mime_types("image/jpeg,invalid,image/png") is False
        assert validate_mime_types("image/jpeg, , image/png") is False


class TestSplitFilename:
    """Test filename splitting function."""

    def test_splits_simple_filename(self):
        """Test splitting simple filename with extension."""
        name, ext = split_filename("document.txt")
        assert name == "document"
        assert ext == "txt"

    def test_splits_filename_with_dots(self):
        """Test splitting filename with multiple dots."""
        name, ext = split_filename("my.document.txt")
        assert name == "my.document"
        assert ext == "txt"

    def test_handles_no_extension(self):
        """Test handling filename without extension."""
        name, ext = split_filename("README")
        assert name == "README"
        assert ext == ""

    def test_handles_multipart_tar_gz(self):
        """Test that .tar.gz is recognized as multipart extension."""
        name, ext = split_filename("archive.tar.gz")
        assert name == "archive"
        assert ext == "tar.gz"

    def test_handles_multipart_tar_bz2(self):
        """Test that .tar.bz2 is recognized as multipart extension."""
        name, ext = split_filename("backup.tar.bz2")
        assert name == "backup"
        assert ext == "tar.bz2"

    def test_handles_multipart_tar_xz(self):
        """Test that .tar.xz is recognized as multipart extension."""
        name, ext = split_filename("data.tar.xz")
        assert name == "data"
        assert ext == "tar.xz"

    def test_handles_multipart_tar_zstd(self):
        """Test that .tar.zstd is recognized as multipart extension."""
        name, ext = split_filename("snapshot.tar.zstd")
        assert name == "snapshot"
        assert ext == "tar.zstd"

    def test_strips_whitespace(self):
        """Test that surrounding whitespace is stripped."""
        name, ext = split_filename("  document.txt  ")
        assert name == "document"
        assert ext == "txt"

    def test_case_insensitive_multipart_detection(self):
        """Test that multipart extension detection is case-insensitive."""
        name, ext = split_filename("archive.TAR.GZ")
        assert name == "archive"
        assert ext == "tar.gz"

    def test_hidden_file(self):
        """Test handling of hidden files (starting with dot)."""
        name, ext = split_filename(".gitignore")
        # rsplit('.', 1) splits on the dot, so name='' and ext='gitignore'
        assert name == ""
        assert ext == "gitignore"


class TestMakeCleanFilename:
    """Test filename cleaning function."""

    def test_removes_special_characters(self):
        """Test that special characters are replaced with underscores."""
        clean = make_clean_filename("my-document!")
        assert clean == "my_document"

    def test_converts_to_lowercase(self):
        """Test that filename is converted to lowercase."""
        clean = make_clean_filename("MyDocument")
        assert clean == "mydocument"

    def test_removes_spaces(self):
        """Test that spaces are replaced with underscores."""
        clean = make_clean_filename("my document")
        assert clean == "my_document"

    def test_handles_underscores(self):
        """Test that underscores are preserved."""
        clean = make_clean_filename("my_document")
        assert clean == "my_document"

    def test_removes_duplicate_underscores(self):
        """Test that duplicate underscores are collapsed to single."""
        clean = make_clean_filename("my__document")
        assert clean == "my_document"

    def test_removes_leading_underscores(self):
        """Test that leading underscores are stripped."""
        clean = make_clean_filename("_mydocument")
        assert clean == "mydocument"

    def test_removes_trailing_underscores(self):
        """Test that trailing underscores are stripped."""
        clean = make_clean_filename("mydocument_")
        assert clean == "mydocument"

    def test_handles_numbers(self):
        """Test that numbers are preserved."""
        clean = make_clean_filename("document123")
        assert clean == "document123"

    def test_cleans_mixed_input(self):
        """Test cleaning filename with multiple issues."""
        clean = make_clean_filename("  _My-Document!_  ")
        assert clean == "my_document"

    def test_alphanumeric_only(self):
        """Test that result contains only alphanumeric and underscores."""
        clean = make_clean_filename("!@#$%^&*()document")
        assert all(c.isalnum() or c == '_' for c in clean)


class TestMakeUniqueFilename:
    """Test unique filename generation function."""

    def test_returns_string(self):
        """Test that unique filename is returned as string."""
        unique = make_unique_filename("document.txt")
        assert isinstance(unique, str)

    def test_removes_extension(self):
        """Test that file extension is NOT included in unique filename.
        
        Extensions are stored separately in the Upload model's 'ext' field.
        """
        unique = make_unique_filename("document.txt")
        assert not unique.endswith(".txt")
        assert not "." in unique

    def test_includes_clean_name(self):
        """Test that clean filename is included."""
        unique = make_unique_filename("MyDocument.txt")
        assert unique.startswith("mydocument_")

    def test_includes_datestamp(self):
        """Test that datestamp is included in format YYYYMMDD-HHMMSS."""
        unique = make_unique_filename("test.txt")
        # Format (no extension): test_YYYYMMDD-HHMMSS_uuid
        parts = unique.split("_")
        assert len(parts) >= 3  # test, date, uuid
        # The datestamp part should be in parts[-2]: YYYYMMDD-HHMMSS (15 chars)
        assert len(parts[-2]) == 15  # YYYYMMDD-HHMMSS
        assert "-" in parts[-2]  # Contains the dash

    def test_includes_uuid(self):
        """Test that 8-char UUID is included."""
        unique = make_unique_filename("test.txt")
        parts = unique.rsplit(".", 1)[0].split("_")  # Remove .txt and split
        uuid_part = parts[-1]
        assert len(uuid_part) == 8
        assert all(c in "0123456789abcdef" for c in uuid_part)

    def test_collision_resistance(self):
        """Test that multiple calls produce different filenames."""
        unique1 = make_unique_filename("document.txt")
        unique2 = make_unique_filename("document.txt")
        assert unique1 != unique2

    def test_handles_multipart_extensions(self):
        """Test that multipart extensions are NOT included in unique filename.
        
        The extension is handled separately by split_filename and stored in the model's 'ext' field.
        """
        unique = make_unique_filename("archive.tar.gz")
        assert not unique.endswith(".tar.gz")
        assert not unique.endswith(".gz")

    def test_handles_no_extension(self):
        """Test handling filename without extension."""
        unique = make_unique_filename("README")
        assert not unique.endswith(".")
        assert "_" in unique  # Should still have separator

    def test_sanitizes_input_filename(self):
        """Test that input filename is sanitized during processing."""
        unique = make_unique_filename("My-Document!.txt")
        # Should start with clean version of "my_document"
        assert unique.startswith("my_document_")

    def test_returns_valid_clean_pattern(self):
        """Test that returned filename matches expected pattern."""
        from app.models.uploads import UNIQUE_FILENAME_PATTERN
        import re
        
        unique = make_unique_filename("test-document.txt")
        # The unique filename has no extension, so use as-is
        
        # Should match the pattern: [clean_name]_YYYYMMDD-HHMMSS_[uuid]
        pattern = re.compile(r'^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?_\d{8}-\d{6}_[a-f0-9]{8}$')
        assert pattern.match(unique), f"Filename {unique} doesn't match pattern"
