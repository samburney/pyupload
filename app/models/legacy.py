from tortoise import fields, models


class Collection(models.Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    name = fields.CharField(max_length=255)
    name_unique = fields.CharField(max_length=255)
    created_at = fields.DatetimeField()
    updated_at = fields.DatetimeField()

    class Meta:
        table = "collections"


class Tag(models.Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    created_at = fields.DatetimeField()
    updated_at = fields.DatetimeField()

    class Meta:
        table = "tags"


class CollectionUpload(models.Model):
    collection_id = fields.IntField()
    upload_id = fields.IntField()

    class Meta:
        table = "collection_upload"


class TagUpload(models.Model):
    tag_id = fields.IntField()
    upload_id = fields.IntField()

    class Meta:
        table = "tag_upload"
