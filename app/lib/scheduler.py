from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.models.refresh_tokens import RefreshToken

scheduler = AsyncIOScheduler()

async def cleanup_tokens():
    """Clean up expired and orphaned tokens"""
    expired = await RefreshToken.cleanup_expired()
    print(f"Cleanup: {expired} expired tokens removed.")

# Schedule to trigger one the hour every hour with jitter up to 300 seconds
scheduler.add_job(cleanup_tokens, 'cron', hour='*', minute=0, jitter=300)
