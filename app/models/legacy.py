from tortoise import fields, models

class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=64)
    email = fields.CharField(max_length=255)
    password = fields.CharField(max_length=60)
    created_at = fields.DatetimeField() # Manual timestamp to match legacy behavior
    updated_at = fields.DatetimeField()
    remember_token = fields.CharField(max_length=100)

    class Meta:
        table = "users"

class Upload(models.Model):
    id = fields.IntField(pk=True)
    user_id = fields.IntField() # Using raw int to match legacy FK behavior
    filegroup_id = fields.IntField(default=0)
    description = fields.CharField(max_length=255)
    name = fields.CharField(max_length=255)
    cleanname = fields.CharField(max_length=255)
    originalname = fields.CharField(max_length=255)
    ext = fields.CharField(max_length=10)
    size = fields.IntField()
    type = fields.CharField(max_length=255)
    extra = fields.CharField(max_length=32)
    created_at = fields.DatetimeField()
    updated_at = fields.DatetimeField()
    viewed = fields.IntField(default=0)
    private = fields.IntField(default=0) # tinyint(1) in MySQL

    class Meta:
        table = "uploads"

class Image(models.Model):
    id = fields.IntField(pk=True)
    upload_id = fields.IntField() # Using raw int
    type = fields.CharField(max_length=255)
    width = fields.IntField()
    height = fields.IntField()
    bits = fields.IntField()
    channels = fields.IntField()
    created_at = fields.DatetimeField()
    updated_at = fields.DatetimeField()

    class Meta:
        table = "images"

class Collection(models.Model):
    id = fields.IntField(pk=True)
    user_id = fields.IntField()
    name = fields.CharField(max_length=255)
    name_unique = fields.CharField(max_length=255)
    created_at = fields.DatetimeField()
    updated_at = fields.DatetimeField()

    class Meta:
        table = "collections"

class Tag(models.Model):
    id = fields.IntField(pk=True)
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
