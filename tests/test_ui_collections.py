"""Tests for collection management endpoints.

- GET  /collections                                 - Collections gallery index page
- GET  /collections/view/{name}                     - Individual collection uploads gallery
- POST /collections/view/{name_unique}/update-selected - Multiselect sidebar for a collection view
- POST /collections/suggestions                     - Search and filter collections for selected uploads
- POST /collections                                 - Create and link a new collection to selected uploads
- PATCH /collections                                - Toggle a single collection on or off for selected uploads
"""

from app.models.collections import Collection
from app.models.users import User
from app.models.uploads import Upload
from app.lib.auth import create_access_token


def _auth(user) -> dict:
    return {"access_token": create_access_token({"sub": user.username})}


def _htmx() -> dict:
    return {"hx-request": "true"}


# ---------------------------------------------------------------------------
# Collection endpoint helpers
# ---------------------------------------------------------------------------

def _col_upload_data(user, suffix: str = "") -> dict:
    """Minimal Upload.create kwargs for collection endpoint tests."""
    return {
        "user": user,
        "description": f"col test {suffix}",
        "name": f"colfile{suffix}_20250301-000000_a1b2c3d4",
        "cleanname": f"colfile{suffix}",
        "originalname": f"colfile{suffix}.txt",
        "ext": "txt",
        "size": 10,
        "type": "text/plain",
        "extra": "0",
    }


class TestCollectionSearchEndpoint:
    """Tests for POST /collections/suggestions."""

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/collections/suggestions", data={"collection_search": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when none of the selected uploads exist."""
        user = await User.create(username="cse404", email="cse404@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/collections/suggestions", data={"collection_search": "foo", "selected_ids": "999999"})
        assert response.status_code == 404

    async def test_returns_html_with_matching_collections(self, client):
        """Returns filtered collections matching the query string."""

        user = await User.create(username="csematch", email="csematch@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "sematch"))
        await Collection.create(user=user, name="Python Pics", name_unique="python-pics")
        await Collection.create(user=user, name="Pyupload Tests", name_unique="pyupload-tests")
        await Collection.create(user=user, name="Unrelated", name_unique="unrelated")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/collections/suggestions", data={"collection_search": "py", "selected_ids": str(upload.id)})
        assert response.status_code == 200
        html = response.text
        assert "Python Pics" in html
        assert "Pyupload Tests" in html
        assert "Unrelated" not in html

    async def test_already_linked_collection_rendered_as_checked(self, client):
        """Collections already linked to the upload are rendered as checked; unlinked ones are not."""

        user = await User.create(username="cseexcl", email="cseexcl@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "seexcl"))
        already = await Collection.create(user=user, name="Already Added", name_unique="already-added")
        await Collection.create(user=user, name="Available", name_unique="available")
        await upload.collections.add(already)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/collections/suggestions", data={"collection_search": "", "selected_ids": str(upload.id)})
        assert response.status_code == 200
        html = response.text
        # Already linked collection is rendered as a checked checkbox
        assert "Already Added" in html
        assert f'value="{already.id}" checked' in html or f'value="{already.id}"\n                        checked' in html
        # Unlinked collection appears without checked
        assert "Available" in html


class TestCollectionAddEndpoint:
    """Tests for POST /collections."""

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/collections", data={"collection_search": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when none of the selected uploads exist."""
        user = await User.create(username="cadd404", email="cadd404@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/collections", data={"collection_search": "foo", "selected_ids": "999999"})
        assert response.status_code == 404

    async def test_creates_collection_and_returns_201(self, client):
        """Successfully adding a new collection returns 201 with updated HTML."""
        user = await User.create(username="caddsucc", email="caddsucc@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "addsucc"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/collections", data={"collection_search": "New Collection", "selected_ids": str(upload.id)})
        assert response.status_code == 201
        assert "text/html" in response.headers.get("content-type", "")

    async def test_collection_persisted_and_linked(self, client):
        """The new collection is saved to the database and linked to the upload."""

        user = await User.create(username="cadddb", email="cadddb@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "adddb"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        await client.post("/collections", data={"collection_search": "Persisted", "selected_ids": str(upload.id)})

        col = await Collection.get_or_none(name="Persisted", user=user)
        assert col is not None
        await upload.fetch_related("collections")
        assert any(c.id == col.id for c in upload.collections)

    async def test_any_authenticated_user_can_add_collection(self, client):
        """Any authenticated user may add their own collection to a readable upload."""

        owner = await User.create(username="caddanyowner", email="caddanyowner@example.com", password="pw", is_registered=True)
        other = await User.create(username="caddanyother", email="caddanyother@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(owner, "addany"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post("/collections", data={"collection_search": "Other User Col", "selected_ids": str(upload.id)})
        assert response.status_code == 201

        col = await Collection.get_or_none(name="Other User Col", user=other)
        assert col is not None


class TestCollectionPatchEndpoint:
    """Tests for PATCH /collections.

    The endpoint toggles a single collection on or off for all selected uploads.
    Payload must include collection_id (int) and state (bool).
    """

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.patch("/collections", data={"collection_id": "1", "state": "true"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when none of the selected uploads exist."""

        user = await User.create(username="cpatch404", email="cpatch404@example.com", password="pw", is_registered=True)
        col = await Collection.create(user=user, name="Col", name_unique="col-p404")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/collections", data={"collection_id": str(col.id), "state": "true", "selected_ids": "999999"})
        assert response.status_code == 404

    async def test_returns_400_for_unknown_collection_id(self, client):
        """Returns 400 when the collection ID is unknown or not owned by the user."""
        user = await User.create(username="cpatch400", email="cpatch400@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patch400"))
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/collections", data={"collection_id": "999999", "state": "true", "selected_ids": str(upload.id)})
        assert response.status_code == 400

    async def test_state_true_adds_collection_to_upload(self, client):
        """Sending state=True links the collection to all selected uploads."""

        user = await User.create(username="cpatchadd", email="cpatchadd@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patchadd"))
        col = await Collection.create(user=user, name="To Add", name_unique="to-add")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/collections", data={"collection_id": str(col.id), "state": "true", "selected_ids": str(upload.id)})
        assert response.status_code == 202

        await upload.fetch_related("collections")
        assert any(c.id == col.id for c in upload.collections)

    async def test_state_false_removes_collection_from_upload(self, client):
        """Sending state=False unlinks only the targeted collection; others are untouched."""

        user = await User.create(username="cpatchrm", email="cpatchrm@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patchrm"))
        col_keep = await Collection.create(user=user, name="Keep", name_unique="keep-rm")
        col_remove = await Collection.create(user=user, name="Remove", name_unique="remove-rm")
        await upload.collections.add(col_keep)
        await upload.collections.add(col_remove)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/collections", data={"collection_id": str(col_remove.id), "state": "false", "selected_ids": str(upload.id)})
        assert response.status_code == 202

        await upload.fetch_related("collections")
        col_ids = [c.id for c in upload.collections]
        assert col_remove.id not in col_ids
        assert col_keep.id in col_ids

    async def test_returns_400_for_collection_owned_by_other_user(self, client):
        """Collections owned by another user are rejected and not added."""

        owner = await User.create(username="cpermown", email="cpermown@example.com", password="pw", is_registered=True)
        other = await User.create(username="cpermoth", email="cpermoth@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(owner, "perm"))
        other_col = await Collection.create(user=other, name="Other Col", name_unique="other-col-perm")

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/collections", data={"collection_id": str(other_col.id), "state": "true", "selected_ids": str(upload.id)})
        assert response.status_code == 400

        await upload.fetch_related("collections")
        assert all(c.id != other_col.id for c in upload.collections)

    async def test_state_true_is_idempotent_for_already_linked_collection(self, client):
        """Sending state=True for an already-linked collection succeeds without error."""
        user = await User.create(username="cpatchidem", email="cpatchidem@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patchidem"))
        col = await Collection.create(user=user, name="Already Linked", name_unique="already-linked-idem")
        await upload.collections.add(col)

        client.cookies = _auth(user)

        response = await client.patch("/collections", data={"collection_id": str(col.id), "state": "true", "selected_ids": str(upload.id)})
        assert response.status_code == 202

        await upload.fetch_related("collections")
        assert any(c.id == col.id for c in upload.collections)


# ---------------------------------------------------------------------------
# GET /collections
# ---------------------------------------------------------------------------

class TestCollectionsIndexGet:
    """Tests for GET /collections - collections gallery index page."""

    async def test_returns_303_for_anonymous_user(self, client):
        """Anonymous users cannot access collections - redirect to login page."""
        response = await client.get("/collections")
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_200_for_authenticated_user(self, client):
        """Authenticated users can access the collections index."""
        user = await User.create(username="cidxauth", email="cidxauth@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        response = await client.get("/collections")
        assert response.status_code == 200

    async def test_shows_own_collections_for_authenticated_user(self, client):
        """Authenticated user sees their own collections listed."""
        user = await User.create(username="cidxown", email="cidxown@example.com", password="pw", is_registered=True)
        await Collection.create(user=user, name="My Collection", name_unique="my-collection-idx")
        client.cookies = _auth(user)
        response = await client.get("/collections")
        assert response.status_code == 200
        assert "My Collection" in response.text

    async def test_does_not_show_other_users_collections(self, client):
        """A user's collection index does not include collections owned by other users."""
        owner = await User.create(username="cidxowner", email="cidxowner@example.com", password="pw", is_registered=True)
        viewer = await User.create(username="cidxviewer", email="cidxviewer@example.com", password="pw", is_registered=True)
        await Collection.create(user=owner, name="Owners Collection", name_unique="owners-collection-idx")
        client.cookies = _auth(viewer)
        response = await client.get("/collections")
        assert response.status_code == 200
        assert "Owners Collection" not in response.text


# ---------------------------------------------------------------------------
# GET /collections/view/{name}
# ---------------------------------------------------------------------------

class TestCollectionsViewGet:
    """Tests for GET /collections/view/{name} - individual collection uploads gallery."""

    async def _make_collection_with_upload(self, user, col_name, col_slug, suffix="", private=0) -> tuple[Collection, Upload]:
        col = await Collection.create(user=user, name=col_name, name_unique=col_slug)
        upload = await Upload.create(**_col_upload_data(user, suffix))
        await upload.collections.add(col)
        if private:
            upload.private = private
            await upload.save()
        return col, upload

    async def test_returns_404_for_nonexistent_collection(self, client):
        """A slug that does not exist returns 404."""
        user = await User.create(username="cv404user", email="cv404user@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        response = await client.get("/collections/view/no-such-collection")
        assert response.status_code == 404

    async def test_returns_200_for_authenticated_user_viewing_collection(self, client):
        """An authenticated user can view a collection."""
        user = await User.create(username="cvpub", email="cvpub@example.com", password="pw", is_registered=True)
        col, _ = await self._make_collection_with_upload(user, "Public Col", "public-col-view", "cvpub")
        client.cookies = _auth(user)
        response = await client.get(f"/collections/view/{col.name_unique}")
        assert response.status_code == 200

    async def test_returns_200_empty_state_for_collection_with_no_readable_uploads(self, client):
        """A collection with no uploads visible to the viewer returns 200 with an empty-state message."""
        owner = await User.create(username="cvempty", email="cvempty@example.com", password="pw", is_registered=True)
        viewer = await User.create(username="cvemptyvw", email="cvemptyvw@example.com", password="pw", is_registered=True)
        col, _ = await self._make_collection_with_upload(owner, "Private Col", "private-col-view", "cvempty", private=1)
        client.cookies = _auth(viewer)
        response = await client.get(f"/collections/view/{col.name_unique}")
        assert response.status_code == 200
        assert "no uploads" in response.text.lower() or "nothing" in response.text.lower()

    async def test_owner_sees_private_uploads_in_collection(self, client):
        """The collection owner can view their own private uploads within the collection."""
        user = await User.create(username="cvprivown", email="cvprivown@example.com", password="pw", is_registered=True)
        col, _ = await self._make_collection_with_upload(user, "Private Col", "private-col-own", "cvprivown", private=1)
        client.cookies = _auth(user)
        response = await client.get(f"/collections/view/{col.name_unique}")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# POST /gallery/update-selected (collection context via HX-Current-URL)
# ---------------------------------------------------------------------------

class TestCollectionsHandleSelectedUploadPost:
    """Tests for collection-scoped selection via POST /gallery/update-selected.

    The consolidated selection handler derives context from the HX-Current-URL
    header. When that URL matches /collections/view/{name_unique}, results are
    scoped to that collection.

    Access levels verified:
    - Non-HTMX request → 400
    - Unauthenticated → redirect to login
    - Stale collection (deleted after page load) → safe no-op, no uploads matched
    - Owner with uploads in collection → 200 sidebar
    - Super-select scoping: only uploads in the collection are included
    - Deselected uploads excluded within collection scope
    """

    async def _make_collection_upload(self, user, col, suffix="") -> Upload:
        upload = await Upload.create(**_col_upload_data(user, suffix))
        await upload.collections.add(col)
        return upload

    def _htmx_col(self, name_unique: str) -> dict:
        return {"hx-request": "true", "HX-Current-URL": f"http://test/collections/view/{name_unique}"}

    async def test_returns_400_without_htmx_header(self, client):
        """Non-HTMX requests are rejected with 400."""
        user = await User.create(username="cus400", email="cus400@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        response = await client.post("/gallery/update-selected", data={"selected_ids": []})
        assert response.status_code == 400

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        col = await Collection.create(
            user=await User.create(username="cusunauth", email="cusunauth@example.com", password="pw", is_registered=True),
            name="Unauth Col", name_unique="col-us-unauth",
        )
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": []},
            headers=self._htmx_col(col.name_unique),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_stale_collection_returns_no_uploads(self, client):
        """A collection deleted after page load resolves to an empty selection (safe no-op)."""
        user = await User.create(username="cus404", email="cus404@example.com", password="pw", is_registered=True)
        client.cookies = _auth(user)
        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers=self._htmx_col("no-such-collection"),
        )
        assert response.status_code == 403

    async def test_owner_with_collection_upload_receives_sidebar(self, client):
        """Owner selecting their collection upload gets a 200 sidebar response."""
        user = await User.create(username="cus200", email="cus200@example.com", password="pw", is_registered=True)
        col = await Collection.create(user=user, name="Col 200", name_unique="col-us-200")
        upload = await self._make_collection_upload(user, col, "cus200a")
        client.cookies = _auth(user)
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": [upload.id]},
            headers=self._htmx_col(col.name_unique),
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_super_select_scoped_to_collection_excludes_other_uploads(self, client):
        """Super-select only includes uploads belonging to the collection, not all user uploads."""
        user = await User.create(username="cusscope", email="cusscope@example.com", password="pw", is_registered=True)
        col = await Collection.create(user=user, name="Scoped Col", name_unique="col-us-scoped")
        await self._make_collection_upload(user, col, "cusscopea")
        await Upload.create(**_col_upload_data(user, "cusscopeb"))  # not in collection

        client.cookies = _auth(user)
        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true"},
            headers=self._htmx_col(col.name_unique),
        )
        assert response.status_code == 200
        # Single selection renders upload detail sidebar (not the "N Uploads Selected" aggregate view)
        assert "Uploads Selected" not in response.text
        assert user.username in response.text

    async def test_super_select_deselected_ids_respected_within_collection_scope(self, client):
        """Deselected uploads are excluded from super-select within collection scope."""
        user = await User.create(username="cusdesel", email="cusdesel@example.com", password="pw", is_registered=True)
        col = await Collection.create(user=user, name="Desel Col", name_unique="col-us-desel")
        await self._make_collection_upload(user, col, "cusdesela")
        upload_b = await self._make_collection_upload(user, col, "cusdeselb")

        client.cookies = _auth(user)
        response = await client.post(
            "/gallery/update-selected",
            data={"super_selected": "true", "deselected_ids": [upload_b.id]},
            headers=self._htmx_col(col.name_unique),
        )
        assert response.status_code == 200
        # Single selection renders upload detail sidebar (not the "N Uploads Selected" aggregate view)
        assert "Uploads Selected" not in response.text
        assert user.username in response.text
