from tortoise import models, fields

from app.models.base import TimestampMixin


class Image(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    upload = fields.ForeignKeyField("models.Upload", related_name="images", on_delete=fields.CASCADE)
    type = fields.CharField(max_length=255)
    width = fields.IntField()
    height = fields.IntField()
    bits = fields.IntField()
    channels = fields.IntField()

    class Meta:
        table = "images"
