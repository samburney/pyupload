"""Tests for app/lib/file_archive.py — FileArchive class."""

import os
import tarfile
import time
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio

from app.lib.file_archive import ArchiveCreationFailure, FileArchive, cleanup_orphaned_archives
from app.models.download_archives import ArchiveFormatsEnum, ArchiveStatusEnum, DownloadArchive
from app.models.uploads import Upload
from app.models.users import User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def dirs(tmp_path):
    """Create isolated archive and upload storage directories."""
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    upload_dir = tmp_path / "uploads" / "user_1"
    upload_dir.mkdir(parents=True)
    return archive_dir, upload_dir


@pytest.fixture
def mock_archive():
    """Minimal valid DownloadArchive mock."""
    m = Mock(spec=DownloadArchive)
    m.filename = "archive_testuser_20260327-193717_abcd1234.zip"
    m.format = ArchiveFormatsEnum.zip
    m.upload_ids = [1, 2]
    return m


@pytest.fixture
def mock_uploads(dirs):
    """Two Upload mocks with real files on disk."""
    _, upload_dir = dirs
    uploads = []
    for i, orig_name in enumerate(["photo1", "photo2"], 1):
        ext = "jpg"
        stem = f"photo{i}_20260327-000000_aabbccdd"
        stored_filename = f"{stem}.{ext}"
        (upload_dir / stored_filename).write_bytes(b"fake image data " + str(i).encode())
        m = Mock(spec=Upload)
        m.id = i
        m.user_id = 1
        m.name = stem
        m.ext = ext
        m.originalname = orig_name
        m.originalname_dot_ext = f"{orig_name}.{ext}"
        m.filepath = upload_dir / stored_filename
        uploads.append(m)
    return uploads


def make_file_archive(mock_archive, mock_uploads, dirs, **kwargs):
    """Construct a FileArchive with config patched."""
    archive_dir, upload_dir = dirs

    with patch("app.lib.file_archive.config") as mock_config:
        mock_config.archive_storage_path = archive_dir
        mock_config.storage_path = upload_dir
        return FileArchive(mock_archive, mock_uploads, **kwargs), archive_dir, upload_dir, mock_config


# ============================================================================
# __init__ validation
# ============================================================================

class TestFileArchiveInit:

    def test_happy_path(self, mock_archive, mock_uploads, dirs):
        """FileArchive initialises without error given valid inputs."""
        make_file_archive(mock_archive, mock_uploads, dirs)

    def test_path_traversal_in_filename_raises(self, mock_archive, mock_uploads, dirs):
        """Filename containing directory components raises ValueError."""
        mock_archive.filename = "../evil/archive.zip"
        with pytest.raises(ValueError, match="directory components"):
            make_file_archive(mock_archive, mock_uploads, dirs)

    def test_archive_exists_as_directory_raises(self, mock_archive, mock_uploads, dirs):
        """If archive_path resolves to a directory, raises IsADirectoryError."""
        archive_dir, _ = dirs
        (archive_dir / mock_archive.filename).mkdir()
        with pytest.raises(IsADirectoryError):
            make_file_archive(mock_archive, mock_uploads, dirs)

    def test_archive_exists_without_overwrite_raises(self, mock_archive, mock_uploads, dirs):
        """Existing archive file without overwrite_existing=True raises ValueError."""
        archive_dir, _ = dirs
        (archive_dir / mock_archive.filename).write_bytes(b"old archive")
        with pytest.raises(ValueError, match="overwrite_existing"):
            make_file_archive(mock_archive, mock_uploads, dirs)

    def test_archive_exists_with_overwrite_allowed(self, mock_archive, mock_uploads, dirs):
        """Existing archive file with overwrite_existing=True does not raise."""
        archive_dir, _ = dirs
        (archive_dir / mock_archive.filename).write_bytes(b"old archive")
        make_file_archive(mock_archive, mock_uploads, dirs, overwrite_existing=True)

    def test_upload_id_mismatch_raises(self, mock_archive, mock_uploads, dirs):
        """Upload list not matching archive upload_ids raises ValueError."""
        mock_archive.upload_ids = [1, 99]  # 99 not in mock_uploads
        with pytest.raises(ValueError, match="upload_ids"):
            make_file_archive(mock_archive, mock_uploads, dirs)

    def test_upload_id_mismatch_error_includes_delta(self, mock_archive, mock_uploads, dirs):
        """Mismatch error message includes the differing IDs."""
        mock_archive.upload_ids = [1, 99]
        with pytest.raises(ValueError, match="99"):
            make_file_archive(mock_archive, mock_uploads, dirs)

    def test_upload_outside_storage_raises(self, mock_archive, mock_uploads, dirs):
        """Upload path resolving outside storage_path raises ValueError."""
        archive_dir, upload_dir = dirs
        traversal_path = upload_dir / ".." / ".." / "etc" / "passwd"
        for upload in mock_uploads:
            upload.filepath = traversal_path

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.storage_path = upload_dir
            with pytest.raises(ValueError, match="outside upload storage"):
                FileArchive(mock_archive, mock_uploads)

    def test_missing_upload_file_raises(self, mock_archive, mock_uploads, dirs):
        """Upload whose file does not exist on disk raises FileNotFoundError."""
        mock_uploads[0].filepath.unlink()
        with pytest.raises(FileNotFoundError):
            make_file_archive(mock_archive, mock_uploads, dirs)


# ============================================================================
# create_archive dispatch
# ============================================================================

class TestCreateArchiveDispatch:

    def test_unsupported_format_raises(self, mock_archive, mock_uploads, dirs):
        """Unsupported format value raises NotImplementedError."""
        mock_archive.format = "unsupported_fmt"
        fa, *_ = make_file_archive(mock_archive, mock_uploads, dirs)
        with pytest.raises(NotImplementedError):
            fa.create_archive()

    @pytest.mark.parametrize("fmt,method", [
        (ArchiveFormatsEnum.zip,      "create_zip_archive"),
        (ArchiveFormatsEnum.tar_gzip, "create_targz_archive"),
        (ArchiveFormatsEnum.tar_bzip, "create_tarbz2_archive"),
        (ArchiveFormatsEnum.tar_xz,   "create_tarxz_archive"),
        (ArchiveFormatsEnum.tar_zstd, "create_tarzstd_archive"),
    ])
    def test_dispatches_to_correct_method(self, mock_archive, mock_uploads, dirs, fmt, method):
        """Each format enum value dispatches to the correct create_*_archive method."""
        mock_archive.format = fmt
        fa, *_ = make_file_archive(mock_archive, mock_uploads, dirs)
        with patch.object(fa, method) as mock_method:
            fa.create_archive()
            mock_method.assert_called_once()


# ============================================================================
# create_zip_archive
# ============================================================================

class TestCreateZipArchive:

    def _build_and_run(self, mock_archive, mock_uploads, dirs):
        """Helper: construct FileArchive and call create_zip_archive, return archive path."""
        archive_dir, upload_dir = dirs

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.storage_path = upload_dir
            fa = FileArchive(mock_archive, mock_uploads)
            fa.create_zip_archive()

        return archive_dir / mock_archive.filename

    def test_creates_zip_file(self, mock_archive, mock_uploads, dirs):
        """create_zip_archive produces a file at archive_path."""
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        assert archive_path.exists()
        assert archive_path.is_file()

    def test_zip_is_valid(self, mock_archive, mock_uploads, dirs):
        """Produced file is a valid ZIP archive."""
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        assert zipfile.is_zipfile(archive_path)

    def test_zip_contains_all_uploads(self, mock_archive, mock_uploads, dirs):
        """ZIP contains one member per upload."""
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        with zipfile.ZipFile(archive_path) as zf:
            assert len(zf.namelist()) == len(mock_uploads)

    def test_zip_uses_original_names(self, mock_archive, mock_uploads, dirs):
        """ZIP member names are the uploads' original filenames (originalname + ext)."""
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
        expected = {u.originalname_dot_ext for u in mock_uploads}
        assert set(names) == expected

    def test_zip_member_content_matches_source(self, mock_archive, mock_uploads, dirs):
        """ZIP member content matches the source file bytes."""
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        with zipfile.ZipFile(archive_path) as zf:
            for upload in mock_uploads:
                source = upload.filepath.read_bytes()
                assert zf.read(upload.originalname_dot_ext) == source

    @pytest.mark.filterwarnings("ignore:Duplicate name:UserWarning")
    def test_zip_duplicate_original_names(self, mock_archive, mock_uploads, dirs):
        """Two uploads with the same originalname_dot_ext are both included (second auto-renamed by zipfile)."""
        mock_uploads[1].originalname_dot_ext = mock_uploads[0].originalname_dot_ext
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        with zipfile.ZipFile(archive_path) as zf:
            assert len(zf.namelist()) == 2


# ============================================================================
# _create_tarball (gz, bz2, xz)
# ============================================================================

class TestCreateTarballArchive:

    def _build_and_run(self, mock_archive, mock_uploads, dirs, method_name):
        """Construct FileArchive, call the given method, return archive path."""
        archive_dir, upload_dir = dirs

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.storage_path = upload_dir
            fa = FileArchive(mock_archive, mock_uploads)
            getattr(fa, method_name)()

        return archive_dir / mock_archive.filename

    @pytest.mark.parametrize("fmt,method,read_mode", [
        (ArchiveFormatsEnum.tar_gzip, "create_targz_archive",  "r:gz"),
        (ArchiveFormatsEnum.tar_bzip, "create_tarbz2_archive", "r:bz2"),
        (ArchiveFormatsEnum.tar_xz,   "create_tarxz_archive",  "r:xz"),
    ])
    def test_creates_file(self, mock_archive, mock_uploads, dirs, fmt, method, read_mode):
        """create_tar*_archive produces a file at archive_path."""
        mock_archive.format = fmt
        mock_archive.filename = f"archive_test_20260327-193717_abcd1234.{fmt.value}"
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs, method)
        assert archive_path.exists() and archive_path.is_file()

    @pytest.mark.parametrize("fmt,method,read_mode", [
        (ArchiveFormatsEnum.tar_gzip, "create_targz_archive",  "r:gz"),
        (ArchiveFormatsEnum.tar_bzip, "create_tarbz2_archive", "r:bz2"),
        (ArchiveFormatsEnum.tar_xz,   "create_tarxz_archive",  "r:xz"),
    ])
    def test_is_valid_tarball(self, mock_archive, mock_uploads, dirs, fmt, method, read_mode):
        """Produced file is a valid tarball readable with the expected compression."""
        mock_archive.format = fmt
        mock_archive.filename = f"archive_test_20260327-193717_abcd1234.{fmt.value}"
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs, method)
        assert tarfile.is_tarfile(archive_path)
        with tarfile.open(archive_path, read_mode) as tf:  # type: ignore[call-overload]
            assert len(tf.getmembers()) == len(mock_uploads)

    @pytest.mark.parametrize("fmt,method,read_mode", [
        (ArchiveFormatsEnum.tar_gzip, "create_targz_archive",  "r:gz"),
        (ArchiveFormatsEnum.tar_bzip, "create_tarbz2_archive", "r:bz2"),
        (ArchiveFormatsEnum.tar_xz,   "create_tarxz_archive",  "r:xz"),
    ])
    def test_uses_original_names(self, mock_archive, mock_uploads, dirs, fmt, method, read_mode):
        """Tarball member names are the uploads' original filenames (originalname + ext)."""
        mock_archive.format = fmt
        mock_archive.filename = f"archive_test_20260327-193717_abcd1234.{fmt.value}"
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs, method)
        with tarfile.open(archive_path, read_mode) as tf:  # type: ignore[call-overload]
            names = tf.getnames()
        assert set(names) == {u.originalname_dot_ext for u in mock_uploads}

    @pytest.mark.parametrize("fmt,method,read_mode", [
        (ArchiveFormatsEnum.tar_gzip, "create_targz_archive",  "r:gz"),
        (ArchiveFormatsEnum.tar_bzip, "create_tarbz2_archive", "r:bz2"),
        (ArchiveFormatsEnum.tar_xz,   "create_tarxz_archive",  "r:xz"),
    ])
    def test_member_content_matches_source(self, mock_archive, mock_uploads, dirs, fmt, method, read_mode):
        """Tarball member content matches the source file bytes."""
        mock_archive.format = fmt
        mock_archive.filename = f"archive_test_20260327-193717_abcd1234.{fmt.value}"
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs, method)
        with tarfile.open(archive_path, read_mode) as tf:  # type: ignore[call-overload]
            for upload in mock_uploads:
                member = tf.extractfile(upload.originalname_dot_ext)
                assert member is not None
                assert member.read() == upload.filepath.read_bytes()


# ============================================================================
# create_tarzstd_archive
# ============================================================================

class TestCreateTarzstdArchive:

    def _build_and_run(self, mock_archive, mock_uploads, dirs):
        archive_dir, upload_dir = dirs

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.storage_path = upload_dir
            mock_config.archive_zstd_level = 3
            fa = FileArchive(mock_archive, mock_uploads)
            fa.create_tarzstd_archive()

        return archive_dir / mock_archive.filename

    @pytest.fixture(autouse=True)
    def set_zstd_filename(self, mock_archive):
        mock_archive.format = ArchiveFormatsEnum.tar_zstd
        mock_archive.filename = "archive_test_20260327-193717_abcd1234.tar.zstd"

    def test_creates_file(self, mock_archive, mock_uploads, dirs):
        """create_tarzstd_archive produces a file at archive_path."""
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        assert archive_path.exists() and archive_path.is_file()

    def test_is_valid_zstd_tarball(self, mock_archive, mock_uploads, dirs):
        """Produced file is a valid zstd-compressed tarball."""
        import zstandard
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        with archive_path.open("rb") as f:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                with tarfile.open(fileobj=reader, mode="r|") as tf:
                    assert len(tf.getmembers()) >= 0  # opens without error

    def test_contains_all_uploads(self, mock_archive, mock_uploads, dirs):
        """Zstd tarball contains one member per upload."""
        import zstandard
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        with archive_path.open("rb") as f:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                with tarfile.open(fileobj=reader, mode="r|") as tf:
                    assert len(tf.getmembers()) == len(mock_uploads)

    def test_uses_original_names(self, mock_archive, mock_uploads, dirs):
        """Zstd tarball member names are the uploads' original filenames (originalname + ext)."""
        import zstandard
        archive_path = self._build_and_run(mock_archive, mock_uploads, dirs)
        with archive_path.open("rb") as f:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                with tarfile.open(fileobj=reader, mode="r|") as tf:
                    names = tf.getnames()
        assert set(names) == {u.originalname_dot_ext for u in mock_uploads}


# ============================================================================
# cleanup_orphaned_archives
# ============================================================================

class TestCleanupOrphanedArchives:

    @pytest_asyncio.fixture
    async def user(self, db):
        return await User.create(
            username="orphanuser",
            email="orphan@example.com",
            password="hashed_password",
            fingerprint_hash="fp-orphan",
        )

    def _make_old_file(self, path: Path) -> Path:
        """Write a file and backdate its mtime by 2 hours."""
        path.write_bytes(b"dummy archive data")
        past = time.time() - 7200
        os.utime(path, (past, past))
        return path

    @pytest.mark.asyncio
    async def test_deletes_orphaned_file(self, db, tmp_path):
        """A file on disk with no DB record older than max_age is deleted."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        orphan = self._make_old_file(archive_dir / "orphan_20260328-000000_aaaa0001.zip")

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.archive_max_age_hours = 1
            count = await cleanup_orphaned_archives()

        assert count == 1
        assert not orphan.exists()

    @pytest.mark.asyncio
    async def test_skips_file_with_db_record(self, user, tmp_path):
        """A file with a matching DB record is not treated as an orphan."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        filename = "archive_known_20260328-000000_bbbb0001.zip"
        self._make_old_file(archive_dir / filename)

        await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.ready,
            filename=filename,
        )

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.archive_max_age_hours = 1
            count = await cleanup_orphaned_archives()

        assert count == 0
        assert (archive_dir / filename).exists()

    @pytest.mark.asyncio
    async def test_skips_file_too_new(self, db, tmp_path):
        """A file younger than max_age is not deleted even without a DB record."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        new_file = archive_dir / "newfile_20260328-000000_cccc0001.zip"
        new_file.write_bytes(b"fresh archive")  # current mtime

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.archive_max_age_hours = 1
            count = await cleanup_orphaned_archives()

        assert count == 0
        assert new_file.exists()

    @pytest.mark.asyncio
    async def test_skips_dot_files(self, db, tmp_path):
        """Dot files are ignored regardless of age or DB record."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        self._make_old_file(archive_dir / ".hidden_file")

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.archive_max_age_hours = 1
            count = await cleanup_orphaned_archives()

        assert count == 0

    @pytest.mark.asyncio
    async def test_skips_directories(self, db, tmp_path):
        """Subdirectories inside the archive storage path are ignored."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        (archive_dir / "subdir").mkdir()

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.archive_max_age_hours = 1
            count = await cleanup_orphaned_archives()

        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_correct_count(self, db, tmp_path):
        """Returns the number of orphaned files deleted."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        for i in range(3):
            self._make_old_file(archive_dir / f"orphan_20260328-000000_dddd{i:04d}.zip")

        with patch("app.lib.file_archive.config") as mock_config:
            mock_config.archive_storage_path = archive_dir
            mock_config.archive_max_age_hours = 1
            count = await cleanup_orphaned_archives()

        assert count == 3
