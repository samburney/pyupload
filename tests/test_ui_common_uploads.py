"""Tests for app/ui/common/uploads.py — upload queryset helpers.

Covers:
- readable_upload_queryset: public uploads visible to anonymous users
- readable_upload_queryset: public + own private visible to owner, others' private excluded
- readable_upload_queryset: context_filter scopes results (e.g. by tag)
- readable_upload_queryset: pagination applies offset, limit, and ordering
- writable_upload_queryset: only uploads owned by the given user
- writable_upload_queryset: is a subset of readable (owner's uploads only)
- writable_upload_queryset: context_filter scopes writable results
"""

import pytest
import pytest_asyncio

from tortoise.expressions import Q

from app.models.tags import Tag
from app.models.uploads import Upload
from app.models.common.pagination import PaginationParams
from app.models.users import User
from app.ui.common.uploads import readable_upload_queryset, writable_upload_queryset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_data(user, suffix: str, private: int = 0) -> dict:
    return {
        "user": user,
        "description": f"test {suffix}",
        "name": f"file{suffix}_20250301-000000_a1b2c3d4",
        "cleanname": f"file{suffix}",
        "originalname": f"file{suffix}.txt",
        "ext": "txt",
        "size": suffix.__hash__() % 1000 + 1,
        "type": "text/plain",
        "extra": "0",
        "private": private,
    }


# ---------------------------------------------------------------------------
# readable_upload_queryset
# ---------------------------------------------------------------------------

class TestReadableUploadQueryset:
    """Tests for readable_upload_queryset(user, context_filter, pagination)."""

    async def test_anonymous_sees_only_public_uploads(self, db):
        """Without a user, only public uploads are returned."""
        owner = await User.create(username="rqanon", email="rqanon@example.com", password="pw", is_registered=True)
        pub = await Upload.create(**_upload_data(owner, "rqanonpub", private=0))
        await Upload.create(**_upload_data(owner, "rqanonpriv", private=1))

        results = await readable_upload_queryset(user=None)
        ids = {u.id for u in results}
        assert pub.id in ids

    async def test_anonymous_cannot_see_private_uploads(self, db):
        """Private uploads are hidden from anonymous users."""
        owner = await User.create(username="rqanonhide", email="rqanonhide@example.com", password="pw", is_registered=True)
        priv = await Upload.create(**_upload_data(owner, "rqhidepriv", private=1))

        results = await readable_upload_queryset(user=None)
        ids = {u.id for u in results}
        assert priv.id not in ids

    async def test_owner_sees_own_private_uploads(self, db):
        """Authenticated owner can see their own private uploads."""
        owner = await User.create(username="rqowner", email="rqowner@example.com", password="pw", is_registered=True)
        priv = await Upload.create(**_upload_data(owner, "rqownerpriv", private=1))

        results = await readable_upload_queryset(user=owner)
        ids = {u.id for u in results}
        assert priv.id in ids

    async def test_user_cannot_see_other_users_private_uploads(self, db):
        """A user cannot see private uploads owned by another user."""
        owner = await User.create(username="rqprivown", email="rqprivown@example.com", password="pw", is_registered=True)
        other = await User.create(username="rqprivother", email="rqprivother@example.com", password="pw", is_registered=True)
        priv = await Upload.create(**_upload_data(owner, "rqprivothers", private=1))

        results = await readable_upload_queryset(user=other)
        ids = {u.id for u in results}
        assert priv.id not in ids

    async def test_context_filter_scopes_to_tag(self, db):
        """context_filter=Q(tags__id=...) restricts results to tagged uploads only."""
        owner = await User.create(username="rqctxtag", email="rqctxtag@example.com", password="pw", is_registered=True)
        tag = await Tag.create(name="rq-ctx-tag")
        tagged = await Upload.create(**_upload_data(owner, "rqctxtagged"))
        await tagged.tags.add(tag)
        untagged = await Upload.create(**_upload_data(owner, "rqctxuntagged"))

        results = await readable_upload_queryset(user=owner, context_filter=Q(tags__id=tag.id))
        ids = {u.id for u in results}
        assert tagged.id in ids
        assert untagged.id not in ids

    async def test_pagination_limits_results(self, db):
        """Pagination limits the number of results returned."""
        owner = await User.create(username="rqpaginate", email="rqpaginate@example.com", password="pw", is_registered=True)
        for i in range(5):
            await Upload.create(**_upload_data(owner, f"rqpage{i}"))

        pagination = PaginationParams(page=1, page_size=2, sort_by="id", sort_order="asc")
        results = await readable_upload_queryset(user=owner, pagination=pagination)
        assert len(results) == 2

    async def test_pagination_sort_order_desc(self, db):
        """Pagination sort_order=desc returns results in descending id order."""
        owner = await User.create(username="rqsortdesc", email="rqsortdesc@example.com", password="pw", is_registered=True)
        u1 = await Upload.create(**_upload_data(owner, "rqsortd1"))
        u2 = await Upload.create(**_upload_data(owner, "rqsortd2"))
        u3 = await Upload.create(**_upload_data(owner, "rqsortd3"))

        pagination = PaginationParams(page=1, page_size=10, sort_by="id", sort_order="desc")
        results = await readable_upload_queryset(user=owner, pagination=pagination)
        result_ids = [u.id for u in results]
        assert result_ids.index(u3.id) < result_ids.index(u2.id) < result_ids.index(u1.id)

    async def test_pagination_page_offset(self, db):
        """Page 2 returns the second set of results."""
        owner = await User.create(username="rqpageoff", email="rqpageoff@example.com", password="pw", is_registered=True)
        uploads = [await Upload.create(**_upload_data(owner, f"rqpoff{i}")) for i in range(4)]

        p1 = PaginationParams(page=1, page_size=2, sort_by="id", sort_order="asc")
        p2 = PaginationParams(page=2, page_size=2, sort_by="id", sort_order="asc")
        page1_ids = {u.id for u in await readable_upload_queryset(user=owner, pagination=p1)}
        page2_ids = {u.id for u in await readable_upload_queryset(user=owner, pagination=p2)}
        assert page1_ids.isdisjoint(page2_ids)
        assert page1_ids | page2_ids == {u.id for u in uploads}


# ---------------------------------------------------------------------------
# writable_upload_queryset
# ---------------------------------------------------------------------------

class TestWritableUploadQueryset:
    """Tests for writable_upload_queryset(user, context_filter, pagination)."""

    async def test_returns_only_users_own_uploads(self, db):
        """Only uploads owned by the given user are returned."""
        owner = await User.create(username="wqown", email="wqown@example.com", password="pw", is_registered=True)
        other = await User.create(username="wqother", email="wqother@example.com", password="pw", is_registered=True)
        mine = await Upload.create(**_upload_data(owner, "wqmine"))
        theirs = await Upload.create(**_upload_data(other, "wqtheirs"))

        results = await writable_upload_queryset(user=owner)
        ids = {u.id for u in results}
        assert mine.id in ids
        assert theirs.id not in ids

    async def test_includes_owners_private_uploads(self, db):
        """Owner's private uploads are writable."""
        owner = await User.create(username="wqpriv", email="wqpriv@example.com", password="pw", is_registered=True)
        priv = await Upload.create(**_upload_data(owner, "wqprivown", private=1))

        results = await writable_upload_queryset(user=owner)
        ids = {u.id for u in results}
        assert priv.id in ids

    async def test_is_subset_of_readable(self, db):
        """Writable results are always a subset of readable results for the same user."""
        owner = await User.create(username="wqsubset", email="wqsubset@example.com", password="pw", is_registered=True)
        other = await User.create(username="wqsubsetother", email="wqsubsetother@example.com", password="pw", is_registered=True)
        await Upload.create(**_upload_data(owner, "wqsubown"))
        await Upload.create(**_upload_data(other, "wqsubotherpub", private=0))

        readable_ids = {u.id for u in await readable_upload_queryset(user=owner)}
        writable_ids = {u.id for u in await writable_upload_queryset(user=owner)}
        assert writable_ids.issubset(readable_ids)

    async def test_context_filter_scopes_to_tag(self, db):
        """context_filter restricts writable results to uploads with the given tag."""
        owner = await User.create(username="wqctxtag", email="wqctxtag@example.com", password="pw", is_registered=True)
        tag = await Tag.create(name="wq-ctx-tag")
        tagged = await Upload.create(**_upload_data(owner, "wqctxtagged"))
        await tagged.tags.add(tag)
        untagged = await Upload.create(**_upload_data(owner, "wqctxuntagged"))

        results = await writable_upload_queryset(user=owner, context_filter=Q(tags__id=tag.id))
        ids = {u.id for u in results}
        assert tagged.id in ids
        assert untagged.id not in ids

    async def test_context_filter_excludes_other_users_tagged_uploads(self, db):
        """context_filter does not expose another user's tagged uploads as writable."""
        owner = await User.create(username="wqctxown", email="wqctxown@example.com", password="pw", is_registered=True)
        other = await User.create(username="wqctxoth", email="wqctxoth@example.com", password="pw", is_registered=True)
        tag = await Tag.create(name="wq-shared-tag")
        others_upload = await Upload.create(**_upload_data(other, "wqctxothupload"))
        await others_upload.tags.add(tag)

        results = await writable_upload_queryset(user=owner, context_filter=Q(tags__id=tag.id))
        ids = {u.id for u in results}
        assert others_upload.id not in ids

    async def test_pagination_applies_to_writable_set(self, db):
        """Pagination limits and orders the writable queryset."""
        owner = await User.create(username="wqpage", email="wqpage@example.com", password="pw", is_registered=True)
        for i in range(5):
            await Upload.create(**_upload_data(owner, f"wqpg{i}"))

        pagination = PaginationParams(page=1, page_size=3, sort_by="id", sort_order="asc")
        results = await writable_upload_queryset(user=owner, pagination=pagination)
        assert len(results) == 3