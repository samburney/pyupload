"""Tests for app/ui/common/gallery.py — context filter helpers.

Covers:
- _resolve_path_context_filter: tag path → Q(tags__id=...)
- _resolve_path_context_filter: collection path → Q(collections__id=...)
- _resolve_path_context_filter: /uploads with user → Q(user=user)
- _resolve_path_context_filter: /uploads without user → Q(id__in=[]) safe no-op
- _resolve_path_context_filter: unrecognised path → None (no filter)
- _resolve_path_context_filter: stale tag (deleted) → Q(id__in=[]) safe no-op
- _resolve_path_context_filter: stale collection (deleted) → Q(id__in=[]) safe no-op
- get_request_context_filter (via HTTP): no HX-Current-URL → no filter (all uploads)
- get_request_context_filter (via HTTP): gallery URL → no filter
- get_request_context_filter (via HTTP): tag URL → scoped to tag
- get_request_context_filter (via HTTP): collection URL → scoped to collection
- get_request_context_filter (via HTTP): /uploads URL → scoped to current user
"""

from app.models.collections import Collection
from app.models.tags import Tag
from app.models.uploads import Upload
from app.models.users import User
from app.lib.auth import create_access_token
from app.ui.common.gallery import _resolve_path_context_filter


def _auth(user) -> dict:
    return {"access_token": create_access_token({"sub": user.username})}


def _upload_data(user, suffix: str) -> dict:
    return {
        "user": user,
        "description": f"gallery ctx test {suffix}",
        "name": f"gctx{suffix}_20250301-000000_a1b2c3d4",
        "cleanname": f"gctx{suffix}",
        "originalname": f"gctx{suffix}.txt",
        "ext": "txt",
        "size": abs(hash(suffix)) % 1000 + 1,
        "type": "text/plain",
        "extra": "0",
        "private": 0,
    }


# ---------------------------------------------------------------------------
# _resolve_path_context_filter (unit tests — DB required for lookups)
# ---------------------------------------------------------------------------

class TestResolvePathContextFilter:
    """Direct unit tests for _resolve_path_context_filter."""

    async def test_tag_path_returns_q_for_existing_tag(self, db):
        """A /tags/view/{name} path returns Q(tags__id=...) for a real tag."""
        owner = await User.create(username="rpf-tagowner", email="rpf-tagowner@e.com", password="pw", is_registered=True)
        tag = await Tag.create(name="rpf-real-tag")
        upload = await Upload.create(**_upload_data(owner, "rpftagged"))
        await upload.tags.add(tag)
        untagged = await Upload.create(**_upload_data(owner, "rpfuntagged"))

        q = await _resolve_path_context_filter(f"/tags/view/{tag.name}")
        assert q is not None
        results = await Upload.filter(q)
        ids = {u.id for u in results}
        assert upload.id in ids
        assert untagged.id not in ids

    async def test_collection_path_returns_q_for_existing_collection(self, db):
        """A /collections/view/{name_unique} path returns Q(collections__id=...) for a real collection."""
        owner = await User.create(username="rpf-colowner", email="rpf-colowner@e.com", password="pw", is_registered=True)
        col = await Collection.create(user=owner, name="RPF Col", name_unique="rpf-col")
        upload = await Upload.create(**_upload_data(owner, "rpfcoled"))
        await upload.collections.add(col)
        other = await Upload.create(**_upload_data(owner, "rpfnotcoled"))

        q = await _resolve_path_context_filter(f"/collections/view/{col.name_unique}")
        assert q is not None
        results = await Upload.filter(q)
        ids = {u.id for u in results}
        assert upload.id in ids
        assert other.id not in ids

    async def test_unknown_path_returns_none(self, db):
        """/gallery and other unrecognised paths return None (no context filter)."""
        assert await _resolve_path_context_filter("/gallery") is None
        assert await _resolve_path_context_filter("/") is None
        assert await _resolve_path_context_filter("/profile") is None

    async def test_stale_tag_returns_empty_q(self, db):
        """A tag path whose tag has been deleted returns Q(id__in=[]) — no uploads match."""
        owner = await User.create(username="rpf-stalетag", email="rpf-staletag@e.com", password="pw", is_registered=True)
        await Upload.create(**_upload_data(owner, "rpfstale"))

        q = await _resolve_path_context_filter("/tags/view/deleted-tag-xyz")
        assert q is not None
        results = await Upload.filter(q)
        assert len(results) == 0

    async def test_stale_collection_returns_empty_q(self, db):
        """A collection path whose collection has been deleted returns Q(id__in=[]) — no uploads match."""
        owner = await User.create(username="rpf-stalecol", email="rpf-stalecol@e.com", password="pw", is_registered=True)
        await Upload.create(**_upload_data(owner, "rpfcstale"))

        q = await _resolve_path_context_filter("/collections/view/deleted-col-xyz")
        assert q is not None
        results = await Upload.filter(q)
        assert len(results) == 0

    async def test_uploads_path_with_user_returns_q_for_that_user(self, db):
        """A /uploads path with a user returns Q scoped to that user's uploads."""
        owner = await User.create(username="rpf-upowner", email="rpf-upowner@e.com", password="pw", is_registered=True)
        other = await User.create(username="rpf-upother", email="rpf-upother@e.com", password="pw", is_registered=True)
        owned = await Upload.create(**_upload_data(owner, "rpfupowned"))
        not_owned = await Upload.create(**_upload_data(other, "rpfupother"))

        q = await _resolve_path_context_filter("/uploads", owner)
        assert q is not None
        results = await Upload.filter(q)
        ids = {u.id for u in results}
        assert owned.id in ids
        assert not_owned.id not in ids

    async def test_uploads_path_without_user_returns_empty_q(self, db):
        """A /uploads path with no user returns Q(id__in=[]) — no uploads match."""
        owner = await User.create(username="rpf-upanon", email="rpf-upanon@e.com", password="pw", is_registered=True)
        await Upload.create(**_upload_data(owner, "rpfupanon"))

        q = await _resolve_path_context_filter("/uploads", None)
        assert q is not None
        results = await Upload.filter(q)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# get_request_context_filter (integration tests via /gallery/update-selected)
# ---------------------------------------------------------------------------

class TestGetRequestContextFilter:
    """Integration tests for get_request_context_filter via the selection endpoint.

    Uses POST /gallery/update-selected with varying HX-Current-URL headers to
    verify that context is applied (or not) correctly.
    """

    async def _make_tagged_upload(self, user, tag, suffix):
        upload = await Upload.create(**_upload_data(user, suffix))
        await upload.tags.add(tag)
        return upload

    async def _make_collection_upload(self, user, col, suffix):
        upload = await Upload.create(**_upload_data(user, suffix))
        await upload.collections.add(col)
        return upload

    async def test_no_hx_current_url_applies_no_context_filter(self, client):
        """Without HX-Current-URL, super-select affects all user uploads."""
        user = await User.create(username="gcf-nourl", email="gcf-nourl@e.com", password="pw", is_registered=True)
        tag = await Tag.create(name="gcf-nourl-tag")
        u1 = await self._make_tagged_upload(user, tag, "gcfnourl1")
        u2 = await Upload.create(**_upload_data(user, "gcfnourl2"))
        client.cookies = _auth(user)

        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers={"hx-request": "true"},
        )
        assert response.status_code == 200
        assert "2 Uploads Selected" in response.text

    async def test_gallery_url_applies_no_context_filter(self, client):
        """HX-Current-URL pointing to /gallery applies no filter."""
        user = await User.create(username="gcf-gallery", email="gcf-gallery@e.com", password="pw", is_registered=True)
        u1 = await Upload.create(**_upload_data(user, "gcfgal1"))
        u2 = await Upload.create(**_upload_data(user, "gcfgal2"))
        client.cookies = _auth(user)

        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers={"hx-request": "true", "HX-Current-URL": "http://test/gallery"},
        )
        assert response.status_code == 200
        assert "2 Uploads Selected" in response.text

    async def test_tag_url_scopes_super_select_to_tag(self, client):
        """HX-Current-URL for a tag view scopes super-select to that tag only."""
        user = await User.create(username="gcf-tag", email="gcf-tag@e.com", password="pw", is_registered=True)
        tag = await Tag.create(name="gcf-scoped-tag")
        await self._make_tagged_upload(user, tag, "gcftag1")
        await Upload.create(**_upload_data(user, "gcftag2"))  # untagged
        client.cookies = _auth(user)

        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers={"hx-request": "true", "HX-Current-URL": f"http://test/tags/view/{tag.name}"},
        )
        assert response.status_code == 200
        # Single selection renders upload detail sidebar (not the "N Uploads Selected" aggregate view)
        assert "Uploads Selected" not in response.text
        assert user.username in response.text

    async def test_collection_url_scopes_super_select_to_collection(self, client):
        """HX-Current-URL for a collection view scopes super-select to that collection only."""
        user = await User.create(username="gcf-col", email="gcf-col@e.com", password="pw", is_registered=True)
        col = await Collection.create(user=user, name="GCF Col", name_unique="gcf-col")
        await self._make_collection_upload(user, col, "gcfcol1")
        await Upload.create(**_upload_data(user, "gcfcol2"))  # not in collection
        client.cookies = _auth(user)

        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers={"hx-request": "true", "HX-Current-URL": f"http://test/collections/view/{col.name_unique}"},
        )
        assert response.status_code == 200
        # Single selection renders upload detail sidebar (not the "N Uploads Selected" aggregate view)
        assert "Uploads Selected" not in response.text
        assert user.username in response.text

    async def test_stale_tag_url_returns_no_uploads(self, client):
        """When HX-Current-URL references a deleted tag, no uploads are matched (safe no-op)."""
        user = await User.create(username="gcf-staletag", email="gcf-staletag@e.com", password="pw", is_registered=True)
        await Upload.create(**_upload_data(user, "gcfstaletag1"))
        client.cookies = _auth(user)

        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers={"hx-request": "true", "HX-Current-URL": "http://test/tags/view/nonexistent-tag"},
        )
        assert response.status_code == 403

    async def test_stale_collection_url_returns_no_uploads(self, client):
        """When HX-Current-URL references a deleted collection, no uploads are matched (safe no-op)."""
        user = await User.create(username="gcf-stalecol", email="gcf-stalecol@e.com", password="pw", is_registered=True)
        await Upload.create(**_upload_data(user, "gcfstalecol1"))
        client.cookies = _auth(user)

        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers={"hx-request": "true", "HX-Current-URL": "http://test/collections/view/nonexistent-col"},
        )
        assert response.status_code == 403

    async def test_uploads_url_scopes_super_select_to_current_user(self, client):
        """HX-Current-URL pointing to /uploads scopes super-select to the current user's uploads only."""
        user = await User.create(username="gcf-uploads", email="gcf-uploads@e.com", password="pw", is_registered=True)
        other = await User.create(username="gcf-uploads-other", email="gcf-uploads-other@e.com", password="pw", is_registered=True)
        await Upload.create(**_upload_data(user, "gcfup1"))
        await Upload.create(**_upload_data(user, "gcfup2"))
        await Upload.create(**_upload_data(other, "gcfupother"))
        client.cookies = _auth(user)

        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers={"hx-request": "true", "HX-Current-URL": "http://test/uploads"},
        )
        assert response.status_code == 200
        assert "2 Uploads Selected" in response.text
