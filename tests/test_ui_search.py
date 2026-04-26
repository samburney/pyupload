"""Tests for app/ui/search.py - Search endpoint.

Covers:
- GET /search                  - Index page with no query: renders search form
- GET /search?query=foo        - Results page (full page for non-HTMX, partial for HTMX)
- Visibility rules: public uploads appear for anonymous users
- Visibility rules: private uploads are hidden from anonymous and other users
- Visibility rules: private uploads are visible to their owner
- Query matching: description, originalname, tag name
- Empty results return 200 with no upload cards
"""

from app.models.collections import Collection
from app.models.tags import Tag
from app.models.uploads import Upload
from app.models.users import User
from app.lib.auth import create_access_token


def _auth(user) -> dict:
    return {"access_token": create_access_token({"sub": user.username})}


def _htmx() -> dict:
    return {"HX-Request": "true"}


def _upload_data(user, suffix: str = "", private: int = 0, **overrides) -> dict:
    base = {
        "user": user,
        "description": f"search test {suffix}",
        "name": f"srchfile{suffix}_20250301-000000_a1b2c3d4",
        "cleanname": f"srchfile{suffix}",
        "originalname": f"srchfile{suffix}.txt",
        "ext": "txt",
        "size": 10,
        "type": "text/plain",
        "extra": "0",
        "private": private,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# GET /search (no query — index page)
# ---------------------------------------------------------------------------

class TestSearchIndexPage:
    """GET /search with no query parameter renders the search form."""

    async def test_returns_200_for_anonymous_user(self, client):
        """Anonymous users can access the search page."""
        response = await client.get("/search")
        assert response.status_code == 200

    async def test_returns_200_for_authenticated_user(self, client):
        """Authenticated users can access the search page."""
        user = await User.create(username="srchidx", email="srchidx@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        response = await client.get("/search")
        assert response.status_code == 200

    async def test_renders_search_form(self, client):
        """Response includes a search query input."""
        response = await client.get("/search")
        assert 'name="query"' in response.text

    async def test_returns_full_page_layout(self, client):
        """The index page returns the full HTML layout."""
        response = await client.get("/search")
        assert "<html" in response.text


# ---------------------------------------------------------------------------
# GET /search?query=... (results)
# ---------------------------------------------------------------------------

class TestSearchResultsPage:
    """GET /search?query=... returns upload results."""

    async def test_returns_200_for_anonymous_user(self, client):
        """Anonymous users receive a 200 for a query with no results."""
        response = await client.get("/search?query=xyznonexistent99999")
        assert response.status_code == 200

    async def test_full_page_request_returns_full_layout(self, client):
        """Non-HTMX requests return the full HTML page."""
        response = await client.get("/search?query=anything")
        assert response.status_code == 200
        assert "<html" in response.text

    async def test_htmx_request_returns_partial(self, client):
        """HTMX requests return the results partial without the base layout."""
        user = await User.create(username="srchhtmx", email="srchhtmx@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        await Upload.create(**_upload_data(user, "htmx", description="htmx search partial test"))

        response = await client.get("/search?query=htmx+search+partial+test", headers=_htmx())
        assert response.status_code == 200
        assert "<html" not in response.text

    async def test_empty_results_returns_200(self, client):
        """A query that matches nothing returns 200 with no upload cards."""
        response = await client.get("/search?query=absolutelynoexistentquery99999")
        assert response.status_code == 200
        assert "gallery-card-" not in response.text

    async def test_matches_upload_by_description(self, client):
        """Uploads matching the query in their description appear in results."""
        user = await User.create(username="srchdesc", email="srchdesc@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        match = await Upload.create(**_upload_data(user, "desc", description="uniquesrchdesctarget789"))
        other = await Upload.create(**_upload_data(user, "nodesc"))

        response = await client.get("/search?query=uniquesrchdesctarget789")
        assert response.status_code == 200
        assert f"gallery-card-{match.id}" in response.text
        assert f"gallery-card-{other.id}" not in response.text

    async def test_matches_upload_by_tag(self, client):
        """Uploads tagged with a name matching the query appear in results."""
        user = await User.create(username="srchtag", email="srchtag@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        tag = await Tag.create(name="srch-unique-tag-xyz")
        match = await Upload.create(**_upload_data(user, "tagged"))
        await match.tags.add(tag)
        other = await Upload.create(**_upload_data(user, "notagsrch"))

        response = await client.get("/search?query=srch-unique-tag-xyz")
        assert response.status_code == 200
        assert f"gallery-card-{match.id}" in response.text
        assert f"gallery-card-{other.id}" not in response.text

    async def test_matches_upload_by_originalname(self, client):
        """Uploads matching the query in their originalname appear in results."""
        user = await User.create(username="srchorig", email="srchorig@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        match = await Upload.create(**_upload_data(user, "orig", originalname="uniquesrchorigname999.txt"))
        other = await Upload.create(**_upload_data(user, "noorig"))

        response = await client.get("/search?query=uniquesrchorigname999")
        assert response.status_code == 200
        assert f"gallery-card-{match.id}" in response.text
        assert f"gallery-card-{other.id}" not in response.text


# ---------------------------------------------------------------------------
# Visibility rules
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Super-select availability
# ---------------------------------------------------------------------------

class TestSearchSuperSelect:
    """Super-select control is only available when a search scope is active."""

    async def test_results_page_enables_super_select(self, client):
        """A results page with a query renders the super-select control."""
        user = await User.create(username="srchss", email="srchss@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        await Upload.create(**_upload_data(user, "ss", description="srchsstarget999"))

        response = await client.get("/search?query=srchsstarget999")
        assert response.status_code == 200
        assert "enableSuperSelect" in response.text

    async def test_index_page_does_not_enable_super_select(self, client):
        """The search index page (no query) never renders the super-select control."""
        response = await client.get("/search")
        assert response.status_code == 200
        assert "enableSuperSelect" not in response.text

    async def test_htmx_partial_enables_super_select(self, client):
        """The HTMX results partial also includes the super-select control."""
        user = await User.create(username="srchssht", email="srchssht@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        await Upload.create(**_upload_data(user, "ssht", description="srchsshtarget999"))

        response = await client.get("/search?query=srchsshtarget999", headers=_htmx())
        assert response.status_code == 200
        assert "enableSuperSelect" in response.text


class TestSearchVisibility:
    """Search results respect the standard readable-upload visibility rules."""

    async def test_public_uploads_visible_to_anonymous(self, client):
        """Public uploads matching the query are visible to anonymous users."""
        user = await User.create(username="srchpub", email="srchpub@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_upload_data(user, "pub", private=0, description="srchpublic999unique"))

        response = await client.get("/search?query=srchpublic999unique")
        assert response.status_code == 200
        assert f"gallery-card-{upload.id}" in response.text

    async def test_private_uploads_hidden_from_anonymous(self, client):
        """Private uploads are not visible to anonymous users."""
        user = await User.create(username="srchpriv", email="srchpriv@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_upload_data(user, "priv", private=1, description="srchprivate999unique"))

        response = await client.get("/search?query=srchprivate999unique")
        assert response.status_code == 200
        assert f"gallery-card-{upload.id}" not in response.text

    async def test_private_uploads_visible_to_owner(self, client):
        """An authenticated user's own private uploads appear in their search results."""
        user = await User.create(username="srchown", email="srchown@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        upload = await Upload.create(**_upload_data(user, "own", private=1, description="srchownpriv999unique"))

        response = await client.get("/search?query=srchownpriv999unique")
        assert response.status_code == 200
        assert f"gallery-card-{upload.id}" in response.text

    async def test_private_uploads_hidden_from_other_user(self, client):
        """Private uploads belonging to another user are not returned."""
        owner = await User.create(username="srchother", email="srchother@example.com", password="pw", is_registered=True)
        viewer = await User.create(username="srchviewer", email="srchviewer@example.com", password="pw", is_registered=True)
        client.cookies = _auth(viewer)
        upload = await Upload.create(**_upload_data(owner, "oth", private=1, description="srchotherpvt999unique"))

        response = await client.get("/search?query=srchotherpvt999unique")
        assert response.status_code == 200
        assert f"gallery-card-{upload.id}" not in response.text
