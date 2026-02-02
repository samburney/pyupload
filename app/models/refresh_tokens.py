from datetime import datetime, timezone

from tortoise import fields, models

from app.lib.config import get_app_config
from app.models.common.base import TimestampMixin


config = get_app_config()


# Refresh Token database model
class RefreshToken(models.Model, TimestampMixin):
    """Model for storing JWT refresh tokens with revocation support."""
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="refresh_tokens", on_delete=fields.CASCADE)
    token_hash = fields.CharField(max_length=64, db_index=True)  # SHA256 hash (64 hex chars)
    expires_at = fields.DatetimeField()
    revoked = fields.BooleanField(default=False)

    class Meta:  # type: ignore[override]
        table = "refresh_tokens"

    async def revoke(self) -> bool:
        """Revoke this refresh token."""
        self.revoked = True
        await self.save()
        return True

    def is_valid(self) -> bool:
        """Check if this token is valid (not expired, not revoked, not deleted).
        
        Returns:
            True if valid, False otherwise
        """
        now = datetime.now(timezone.utc)
        return (
            not self.revoked
            and self.expires_at > now
        )

    @classmethod
    async def revoke_all_for_user(
        cls,
        user_id: int
    ) -> int:
        """Revoke all refresh tokens for a specific user.
        
        Useful for logout-all or security scenarios.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Number of tokens revoked
        """
        tokens = await cls.filter(
            user_id=user_id,
            revoked=False
        ).all()
        
        for token in tokens:
            token.revoked = True
            await token.save()
        
        return len(tokens)

    @classmethod
    async def cleanup_expired(cls) -> int:
        """Delete expired refresh tokens.
        
        Should be run periodically as a maintenance task.
        
        Returns:
            Number of tokens deleted
        """
        now = datetime.now(timezone.utc)
        expired_tokens = await cls.filter(expires_at__lt=now).all()
        
        count = len(expired_tokens)
        for token in expired_tokens:
            await token.delete()
        
        return count

