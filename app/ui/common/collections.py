from pydantic import ConfigDict

from tortoise.expressions import Q
from tortoise_serializer import ContextType

from app.models.common.pagination import PaginationParams
from app.models.collections import Collection, CollectionSerializer
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User, UserSerializer

from app.ui.common.gallery import (
    SelectionDetail,
    GalleryPaginationDefaultParams,
    get_selection_detail,
)
from app.ui.common.uploads import readable_upload_queryset, writable_upload_queryset


class CollectionPaginationDefaultParams(GalleryPaginationDefaultParams):
    """Default pagination parameters for the collections page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "name"
    sort_order: str = "asc"
    page_size: int = 12


class CollectionSelectionDetail(CollectionSerializer):
    """A `CollectionSerializer` with `SelectionDetail` computed"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    selection_detail: SelectionDetail
    user: UserSerializer
    is_owner: bool

    # Resolve standard `Upload` models here to reduce model bloat
    readable_upload_models: list[Upload]
    writable_upload_models: list[Upload] | None = None

    # Allow lazy fetching of full `UploadSerializer` models
    readable_uploads: list[UploadSerializer] | None = None
    writable_uploads: list[UploadSerializer] | None = None
    
    @classmethod
    async def resolve_user(cls, instance: Collection, context: ContextType) -> UserSerializer:
        user_model = User.get(id=instance.user_id)  # type: ignore[attr-defined]
        user = await UserSerializer.from_single_queryset(user_model)

        return user

    @classmethod
    async def resolve_is_owner(cls, instance: Collection, context: ContextType) -> bool:
        user = context.get("user")
        if user is None:
            return False
        return instance.user_id == user.id  # type: ignore[attr-defined]

    @classmethod
    async def resolve_selection_detail(cls, instance: Collection, context: ContextType) -> SelectionDetail:
        """Build a SelectionDetail from the collection's associated uploads."""

        user = context.get("user")
        uploads: list[Upload] = await cls.resolve_readable_upload_models(instance, context)

        if not uploads:
            return SelectionDetail.empty()

        return await get_selection_detail(uploads=uploads, user=user)

    @classmethod
    async def resolve_readable_upload_models(cls, instance: Collection, context: ContextType) -> list[Upload]:
        """Fetch uploads for this collection readable by the current user (public + user's own private)."""

        user = context.get("user")
        qs = readable_upload_queryset(user, Q(collections__id=instance.id)).prefetch_related(*UPLOAD_PREFETCH_MODELS)
        return await qs.all()

    async def fetch_writable_upload_models(self, user: User) -> list[Upload]:
        """Fetch and cache Upload models for this collection owned by the given user."""

        if self.writable_upload_models is None:
            qs = writable_upload_queryset(user, Q(collections__id=self.id)).prefetch_related(*UPLOAD_PREFETCH_MODELS)
            self.writable_upload_models = await qs.all()

        return self.writable_upload_models

    async def fetch_readable_uploads(self, user: User | None, pagination: PaginationParams | None = None) -> list[UploadSerializer]:
        """Lazy fetch `UploadSerializer` for this collection readable by the current user (public + user's own private)."""

        if self.readable_uploads is None:
            qs = readable_upload_queryset(user, Q(collections__id=self.id), pagination)
            self.readable_uploads = await UploadSerializer.from_queryset(qs.prefetch_related(*UPLOAD_PREFETCH_MODELS))
        return self.readable_uploads

    async def fetch_writable_uploads(self) -> list[UploadSerializer]:
        """Lazy fetch `UploadSerializer` for this collection owned by (and thus writable by) the current user."""

        if self.writable_uploads is None:
            self.writable_uploads = []
            if self.writable_upload_models:
                self.writable_uploads = [await UploadSerializer.from_tortoise_orm(u) for u in self.writable_upload_models]

        return self.writable_uploads
