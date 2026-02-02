from tortoise import fields


# when mixins are used with Model subclasses
class _ModelBase:
    """Base type for mixins to reference Model methods."""
    pass


class TimestampMixin(_ModelBase):
    """Mixin for timestamp fields."""

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
