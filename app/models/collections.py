from tortoise import fields, models

from app.models.common.base import TimestampMixin


class Collection(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    name = fields.CharField(max_length=255)
    name_unique = fields.CharField(max_length=255)

    class Meta:  # type: ignore[override]
        table = "collections"


class CollectionUpload(models.Model):
    collection_id = fields.IntField()
    upload_id = fields.IntField()

    class Meta:  # type: ignore[override]
        table = "collection_upload"
