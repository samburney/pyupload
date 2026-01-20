from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.models.users import mark_abandoned
from app.models.refresh_tokens import RefreshToken

from app.lib.config import logger


scheduler = AsyncIOScheduler()


async def cleanup_tokens():
    """Clean up expired tokens"""
    expired = await RefreshToken.cleanup_expired()
    logger.info(f"Cleanup: {expired} expired tokens removed.")

# Schedule to trigger one the hour every hour with jitter up to 300 seconds
scheduler.add_job(cleanup_tokens, 'cron', hour='*', minute=0, jitter=300)


async def cleanup_abandoned_users():
    """Clean up abandoned users who never completed registration"""
    # Mark abandoned users and get count
    try:
        abandoned_count = await mark_abandoned()
    except Exception as e:
        logger.error(f"Cleanup: Error during abandoned user cleanup: {e}")

    # TODO: Implement deletion of files owned by abandoned users, and marked as private.

    logger.info(f"Cleanup: {abandoned_count} abandoned users marked.")

# Schedule to trigger one the hour every hour with jitter up to 300 seconds
scheduler.add_job(cleanup_abandoned_users, 'cron', hour='*', minute=0, jitter=300)


