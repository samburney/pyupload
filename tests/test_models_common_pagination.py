"""Tests for PaginationParams.page_url().

Covers:
- Default params produce a minimal URL containing only ?page=N
- Non-default page_size, sort_order, sort_by, infinite_scroll are included
- Params that match declared defaults are omitted
- extra_params are always included regardless of value
- Called without arguments, page_url uses self.page
- Subclass defaults (GalleryPaginationDefaultParams) are respected — params
  matching the subclass default are not included even if they differ from the
  base-class default
"""

from app.models.common.pagination import PaginationParams
from app.ui.common.gallery import GalleryPaginationDefaultParams


class TestPaginationParamsPageUrl:
    """Unit tests for PaginationParams.page_url()."""

    def test_default_params_produces_page_only(self):
        """All params at their declared defaults — only ?page=N appears."""
        p = PaginationParams(count=50)
        assert p.page_url(1) == "?page=1"

    def test_explicit_page_number(self):
        """Explicit page argument is reflected in the URL."""
        p = PaginationParams(count=100)
        assert p.page_url(5) == "?page=5"

    def test_no_arg_uses_self_page(self):
        """Called without arguments, page_url uses the instance's current page."""
        p = PaginationParams(page=4, count=100)
        assert p.page_url() == "?page=4"

    def test_non_default_page_size_included(self):
        """page_size differing from the declared default is included."""
        p = PaginationParams(page_size=20, count=100)
        url = p.page_url(1)
        assert "page_size=20" in url
        assert "page=1" in url

    def test_non_default_sort_order_included(self):
        """sort_order differing from the declared default is included."""
        p = PaginationParams(sort_order="desc", count=100)
        assert "sort_order=desc" in p.page_url(1)

    def test_non_default_sort_by_included(self):
        """sort_by differing from the declared default is included."""
        p = PaginationParams(sort_by="created_at", count=100)
        assert "sort_by=created_at" in p.page_url(1)

    def test_non_default_infinite_scroll_included(self):
        """infinite_scroll=True differs from the False default and is included."""
        p = PaginationParams(infinite_scroll=True, count=100)
        assert "infinite_scroll=True" in p.page_url(1)

    def test_extra_params_always_included(self):
        """extra_params are serialised into the URL regardless of value."""
        p = PaginationParams(count=100, extra_params={"query": "hello"})
        url = p.page_url(1)
        assert "query=hello" in url
        assert "page=1" in url

    def test_extra_params_precede_page(self):
        """extra_params appear before ?page in the serialised URL."""
        p = PaginationParams(count=100, extra_params={"query": "test"})
        url = p.page_url(2)
        assert url.index("query=test") < url.index("page=2")

    def test_subclass_defaults_not_included(self):
        """Params matching the subclass declared defaults are omitted."""
        # GalleryPaginationDefaultParams: sort_by="created_at", sort_order="desc", page_size=24
        p = GalleryPaginationDefaultParams(count=100)
        url = p.page_url(1)
        assert "sort_by" not in url
        assert "sort_order" not in url
        assert "page_size" not in url

    def test_subclass_non_default_included(self):
        """Params differing from the subclass declared default are included."""
        p = GalleryPaginationDefaultParams(sort_by="name", count=100)
        assert "sort_by=name" in p.page_url(1)
