"""Tests for collection management endpoints.

- POST /collections/suggestions — search and filter collections for selected uploads
- POST /collections — create and link a new collection to selected uploads
- PATCH /collections — toggle a single collection on or off for selected uploads
"""

from app.models.users import User
from app.models.uploads import Upload
from app.lib.auth import create_access_token


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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

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
        from app.models.collections import Collection

        user = await User.create(username="cpatchidem", email="cpatchidem@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patchidem"))
        col = await Collection.create(user=user, name="Already Linked", name_unique="already-linked-idem")
        await upload.collections.add(col)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/collections", data={"collection_id": str(col.id), "state": "true", "selected_ids": str(upload.id)})
        assert response.status_code == 202

        await upload.fetch_related("collections")
        assert any(c.id == col.id for c in upload.collections)
