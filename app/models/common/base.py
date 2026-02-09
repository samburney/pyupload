from tortoise import fields
from datetime import datetime


# when mixins are used with Model subclasses
class _ModelBase:
    """Base type for mixins to reference Model methods."""
    pass


class TimestampMixin(_ModelBase):
    """Mixin for timestamp fields."""

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class SerializerTimestampMixin(_ModelBase):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: datetime
