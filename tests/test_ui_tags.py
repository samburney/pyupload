"""Tests for app/ui/tags.py - Tag management UI endpoints.

This module tests the FastAPI/Starlette tag endpoints:
- GET  /tags             - Tags gallery index page
- POST /tags/suggestions - Get tag suggestions filtered by query string
- POST /tags/update    - Add a tag to one or more selected uploads
- POST /tags/delete    - Remove a tag from one or more selected uploads

Tests verify:
- GET /tags returns 200 and filters tags by readable-upload visibility
- Authentication enforcement (unauthenticated users redirected to /login)
- Tag suggestions filtering and exclusion of already-selected tag names
- Single and multi-upload tag add/remove via selected_ids
- Tag persistence and removal from database
- Invalid/empty tag name rejection (400)
- Readable-filter semantics: public uploads and owned private uploads are
  accessible; private uploads owned by other users are silently excluded
- ETag and cache headers on the tags index page
"""


from app.models.users import User
from app.models.uploads import Upload
from app.lib.auth import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tag_upload_data(user, suffix: str = "", private: int = 0) -> dict:
    """Minimal Upload.create kwargs for tag endpoint tests."""
    return {
        "user": user,
        "description": f"tag test {suffix}",
        "name": f"tagfile{suffix}_20250301-000000_a1b2c3d4",
        "cleanname": f"tagfile{suffix}",
        "originalname": f"tagfile{suffix}.txt",
        "ext": "txt",
        "size": 10,
        "type": "text/plain",
        "extra": "0",
        "private": private,
    }


# ---------------------------------------------------------------------------
# GET /tags
# ---------------------------------------------------------------------------

class TestTagsIndexEndpoint:
    """Tests for GET /tags - tags gallery index page."""

    async def test_returns_200_for_anonymous_user(self, client):
        """Anonymous users can access the tags index page."""
        response = await client.get("/tags")
        assert response.status_code == 200

    async def test_returns_200_for_authenticated_user(self, client):
        """Authenticated users can access the tags index page."""
        user = await User.create(username="tidxauth", email="tidxauth@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.get("/tags")
        assert response.status_code == 200

    async def test_shows_tag_with_public_upload_for_anonymous(self, client):
        """Tags that have at least one public upload appear for anonymous users."""
        from app.models.tags import Tag

        user = await User.create(username="tidxpub", email="tidxpub@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "idxpub"))
        await Tag.add_or_create_for_upload(upload, "visible-tag")

        response = await client.get("/tags")
        assert response.status_code == 200
        assert "visible-tag" in response.text

    async def test_hides_tag_with_only_private_uploads_for_anonymous(self, client):
        """Tags whose uploads are all private do not appear for anonymous users."""
        from app.models.tags import Tag

        user = await User.create(username="tidxpriv", email="tidxpriv@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "idxpriv", private=1))
        await Tag.add_or_create_for_upload(upload, "hidden-tag")

        response = await client.get("/tags")
        assert response.status_code == 200
        assert "hidden-tag" not in response.text

    async def test_shows_tag_with_private_upload_for_owner(self, client):
        """Authenticated users see tags whose only upload is their own private upload."""
        from app.models.tags import Tag

        user = await User.create(username="tidxown", email="tidxown@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "idxown", private=1))
        await Tag.add_or_create_for_upload(upload, "owners-tag")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.get("/tags")
        assert response.status_code == 200
        assert "owners-tag" in response.text

    async def test_hides_other_users_private_tag_from_authenticated_user(self, client):
        """Tags whose only upload is another user's private upload remain hidden."""
        from app.models.tags import Tag

        owner = await User.create(username="tidxothown", email="tidxothown@example.com", password="pw", is_registered=True)
        viewer = await User.create(username="tidxothview", email="tidxothview@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(owner, "idxoth", private=1))
        await Tag.add_or_create_for_upload(upload, "other-private-tag")

        token = create_access_token({"sub": viewer.username})
        client.cookies = {"access_token": token}

        response = await client.get("/tags")
        assert response.status_code == 200
        assert "other-private-tag" not in response.text

    async def test_pagination_appears_when_over_twelve_tags(self, client):
        """Tags index uses page_size=12; pagination controls appear for more than 12 tags."""
        from app.models.tags import Tag

        user = await User.create(username="tidxpg", email="tidxpg@example.com", password="pw", is_registered=True)
        for i in range(13):
            upload = await Upload.create(**_tag_upload_data(user, f"idxpg{i}"))
            await Tag.add_or_create_for_upload(upload, f"page-tag-{i:02d}")

        response = await client.get("/tags")
        assert response.status_code == 200
        assert "?page=2" in response.text

    async def test_sets_cache_headers(self, client):
        """Tags index response includes ETag, Cache-Control, and Vary headers."""
        response = await client.get("/tags")
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "private, max-age=60, must-revalidate"
        assert response.headers.get("vary") == "Cookie"
        assert response.headers.get("etag", "").startswith('W/"gallery-')

    async def test_returns_304_when_etag_matches(self, client):
        """Tags index returns 304 Not Modified when the client's ETag matches."""
        first = await client.get("/tags")
        etag = first.headers.get("etag")
        assert etag

        second = await client.get("/tags", headers={"If-None-Match": etag})
        assert second.status_code == 304
        assert second.headers.get("etag") == etag
        assert second.headers.get("cache-control") == "private, max-age=60, must-revalidate"


# ---------------------------------------------------------------------------
# POST /tags/suggestions
# ---------------------------------------------------------------------------

class TestTagSuggestionsEndpoint:
    """Tests for POST /tags/suggestions."""

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/tags/suggestions", data={"tag_search": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_204_for_empty_tag_search(self, client):
        """An empty tag_search returns 204 No Content without querying the database."""
        user = await User.create(username="tsugmt204", email="tsugmt204@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/suggestions", data={"tag_search": ""})
        assert response.status_code == 204

    async def test_any_authenticated_user_can_get_suggestions(self, client):
        """Any authenticated user may request tag suggestions."""
        user = await User.create(username="tsugmtany", email="tsugmtany@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/suggestions", data={"tag_search": "foo"})
        assert response.status_code == 200

    async def test_returns_suggestions_matching_query(self, client):
        """Returns tags matching the query string; non-matching tags are excluded."""
        from app.models.tags import Tag

        user = await User.create(username="tsugmtmatch", email="tsugmtmatch@example.com", password="pw", is_registered=True)
        await Tag.create(name="python")
        await Tag.create(name="pyupload")
        await Tag.create(name="unrelated")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/suggestions", data={"tag_search": "py"})
        assert response.status_code == 200
        assert "python" in response.text
        assert "pyupload" in response.text
        assert "unrelated" not in response.text

    async def test_excludes_provided_tag_names(self, client):
        """Tags whose names are in the tag_name list are excluded from suggestions."""
        from app.models.tags import Tag

        user = await User.create(username="tsugmtexcl", email="tsugmtexcl@example.com", password="pw", is_registered=True)
        await Tag.create(name="already-selected")
        await Tag.create(name="also-matching")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/suggestions", data={
            "tag_search": "a",
            "tag_name": ["already-selected"],
        })
        assert response.status_code == 200
        assert "already-selected" not in response.text
        assert "also-matching" in response.text


# ---------------------------------------------------------------------------
# POST /tags/update
# ---------------------------------------------------------------------------

class TestTagUpdateEndpoint:
    """Tests for POST /tags/update."""

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/tags/update", data={"tag_name": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_adds_tag_to_upload_and_returns_200(self, client):
        """Successfully adding a tag returns 200 with HTML."""
        user = await User.create(username="tupdtsucc", email="tupdtsucc@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "updsucc"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/update", data={"tag_name": "newtag", "selected_ids": [upload.id]})
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_tag_persisted_in_database(self, client):
        """The added tag is saved in the database and associated with the upload."""
        user = await User.create(username="tupdtdb", email="tupdtdb@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "upddb"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        await client.post("/tags/update", data={"tag_name": "persisted", "selected_ids": [upload.id]})

        await upload.fetch_related("tags")
        assert any(t.name == "persisted" for t in upload.tags)

    async def test_adds_tag_to_multiple_uploads(self, client):
        """Tag is added to all uploads in selected_ids."""
        user = await User.create(username="tupdtmulti", email="tupdtmulti@example.com", password="pw", is_registered=True)
        upload_a = await Upload.create(**_tag_upload_data(user, "updmulta"))
        upload_b = await Upload.create(**_tag_upload_data(user, "updmultb"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/update", data={
            "tag_name": "shared-tag",
            "selected_ids": [upload_a.id, upload_b.id],
        })
        assert response.status_code == 200

        await upload_a.fetch_related("tags")
        await upload_b.fetch_related("tags")
        assert any(t.name == "shared-tag" for t in upload_a.tags)
        assert any(t.name == "shared-tag" for t in upload_b.tags)

    async def test_any_authenticated_user_can_tag_public_upload(self, client):
        """Any authenticated user may add a tag to a public upload."""
        owner = await User.create(username="tupdtowner", email="tupdtowner@example.com", password="pw", is_registered=True)
        other = await User.create(username="tupdtother", email="tupdtother@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(owner, "updpub"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/update", data={"tag_name": "tagged-by-other", "selected_ids": [upload.id]})
        assert response.status_code == 200

        await upload.fetch_related("tags")
        assert any(t.name == "tagged-by-other" for t in upload.tags)

    async def test_silently_ignores_private_upload_of_another_user(self, client):
        """Private uploads owned by another user are filtered out; response is 200 with no tags."""
        owner = await User.create(username="tupdtpriv", email="tupdtpriv@example.com", password="pw", is_registered=True)
        other = await User.create(username="tupdtprivother", email="tupdtprivother@example.com", password="pw", is_registered=True)
        private_upload = await Upload.create(**{**_tag_upload_data(owner, "updpriv"), "private": 1})

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/update", data={"tag_name": "foo", "selected_ids": [private_upload.id]})
        assert response.status_code == 200

        await private_upload.fetch_related("tags")
        assert all(t.name != "foo" for t in private_upload.tags)

    async def test_returns_400_for_invalid_tag_name(self, client):
        """An invalid tag name (all special characters) returns 400 Bad Request."""
        user = await User.create(username="tupdtbad", email="tupdtbad@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "updbad"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/update", data={"tag_name": "!@#$", "selected_ids": [upload.id]})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /tags/delete
# ---------------------------------------------------------------------------

class TestTagDeleteEndpoint:
    """Tests for POST /tags/delete."""

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/tags/delete", data={"tag_name": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_removes_tag_from_upload_and_returns_200(self, client):
        """Successfully removing a tag returns 200 with HTML."""
        from app.models.tags import Tag

        user = await User.create(username="tdeltnew", email="tdeltnew@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "delsucc"))
        await Tag.add_or_create_for_upload(upload, "removable")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/delete", data={"tag_name": "removable", "selected_ids": [upload.id]})
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_tag_removed_from_database(self, client):
        """The tag association is removed from the database after deletion."""
        from app.models.tags import Tag

        user = await User.create(username="tdeltdb", email="tdeltdb@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "deldb"))
        await Tag.add_or_create_for_upload(upload, "gone")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        await client.post("/tags/delete", data={"tag_name": "gone", "selected_ids": [upload.id]})

        await upload.fetch_related("tags")
        assert all(t.name != "gone" for t in upload.tags)

    async def test_removes_tag_from_multiple_uploads(self, client):
        """Tag is removed from all uploads in selected_ids."""
        from app.models.tags import Tag

        user = await User.create(username="tdeltmulti", email="tdeltmulti@example.com", password="pw", is_registered=True)
        upload_a = await Upload.create(**_tag_upload_data(user, "delmulta"))
        upload_b = await Upload.create(**_tag_upload_data(user, "delmultb"))
        await Tag.add_or_create_for_upload(upload_a, "to-remove")
        await Tag.add_or_create_for_upload(upload_b, "to-remove")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/delete", data={
            "tag_name": "to-remove",
            "selected_ids": [upload_a.id, upload_b.id],
        })
        assert response.status_code == 200

        await upload_a.fetch_related("tags")
        await upload_b.fetch_related("tags")
        assert all(t.name != "to-remove" for t in upload_a.tags)
        assert all(t.name != "to-remove" for t in upload_b.tags)

    async def test_returns_400_for_invalid_tag_name(self, client):
        """An invalid tag name (all special characters) returns 400 Bad Request."""
        user = await User.create(username="tdeltbad", email="tdeltbad@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(user, "delbad"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/tags/delete", data={"tag_name": "!@#$", "selected_ids": [upload.id]})
        assert response.status_code == 400
