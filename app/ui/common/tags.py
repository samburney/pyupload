from pydantic import ConfigDict

from tortoise.expressions import Q
from tortoise_serializer import ContextType

from app.models.common.pagination import PaginationParams
from app.models.tags import Tag, TagSerializer
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User

from app.ui.common.gallery import (
    SelectionDetail,
    GalleryPaginationDefaultParams,
    get_selection_detail,
)
from app.ui.common.uploads import readable_upload_queryset, writable_upload_queryset


class TagPaginationDefaultParams(GalleryPaginationDefaultParams):
    """Default pagination parameters for the home page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "name"
    sort_order: str = "asc"
    page_size: int = 12


class TagSelectionDetail(TagSerializer):
    """A `TagSerializer` with `SelectionDetail` computed"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    selection_detail: SelectionDetail
    
    # Resolve standard `Upload` models here to reduce model bloat
    readable_upload_models: list[Upload]
    writable_upload_models: list[Upload] | None = None

    # Allow lazy fetching of full `UploadSerializer` models
    readable_uploads: list[UploadSerializer] | None = None
    writable_uploads: list[UploadSerializer] | None = None
    
    @classmethod
    async def resolve_selection_detail(cls, instance: Tag, context: ContextType) -> SelectionDetail:
        """Build a SelectionDetail from the tag's associated uploads."""

        user = context.get("user")
        uploads: list[Upload] = await cls.resolve_readable_upload_models(instance, context)

        if not uploads:
            return SelectionDetail.empty()

        return await get_selection_detail(uploads=uploads, user=user)

    @classmethod
    async def resolve_readable_upload_models(cls, instance: Tag, context: ContextType) -> list[Upload]:
        """Fetch uploads for this tag readable by the current user (public + user's own private)."""

        user = context.get("user")
        qs = readable_upload_queryset(user, Q(tags__id=instance.id)).prefetch_related(*UPLOAD_PREFETCH_MODELS)
        return await qs.all()

    async def fetch_writable_upload_models(self, user: User) -> list[Upload]:
        """Fetch and cache Upload models for this tag owned by the given user."""

        if self.writable_upload_models is None:
            qs = writable_upload_queryset(user, Q(tags__id=self.id)).prefetch_related(*UPLOAD_PREFETCH_MODELS)
            self.writable_upload_models = await qs.all()

        return self.writable_upload_models

    async def fetch_readable_uploads(self, user: User | None, pagination: PaginationParams | None = None) -> list[UploadSerializer]:
        """Lazy fetch `UploadSerializer` for this tag readable by the current user (public + user's own private)."""

        if self.readable_uploads is None:
            qs = readable_upload_queryset(user, Q(tags__id=self.id), pagination)
            self.readable_uploads = await UploadSerializer.from_queryset(qs.prefetch_related(*UPLOAD_PREFETCH_MODELS))
        return self.readable_uploads

    async def fetch_writable_uploads(self) -> list[UploadSerializer]:
        """Lazy fetch `UploadSerializer` for this tag owned by (and thus writable by) the current user."""

        if self.writable_uploads is None:
            self.writable_uploads = []
            if self.writable_upload_models:
                self.writable_uploads = [await UploadSerializer.from_tortoise_orm(u) for u in self.writable_upload_models]

        return self.writable_uploads
