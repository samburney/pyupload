"""Tests for mark_abandoned() logic in app/models/users.py.

- Old unregistered users are marked abandoned and their fingerprint hash cleared
- Recent users, registered users, and already-abandoned users are not affected
- Fingerprint data is retained for audit purposes after abandonment
"""

from app.models.users import User, mark_abandoned


class TestMarkAbandoned:
    """Test mark_abandoned() function."""

    async def test_marks_old_unregistered_users_as_abandoned(self, db):
        """Test that old unregistered users are marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)

        # Create an old unregistered user
        old_user = await User.create(
            username="OldUser",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="d" * 64
        )

        # Run abandonment cleanup
        count = await mark_abandoned()

        # Refresh from database
        await old_user.refresh_from_db()

        assert count == 1
        assert old_user.is_abandoned is True
        assert old_user.fingerprint_hash is None

    async def test_preserves_recent_unregistered_users(self, db):
        """Test that recent unregistered users are not marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        recent_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days - 1)

        # Create a recent unregistered user
        recent_user = await User.create(
            username="RecentUser",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=recent_date,
            fingerprint_hash="e" * 64
        )

        # Run abandonment cleanup
        count = await mark_abandoned()

        # Refresh from database
        await recent_user.refresh_from_db()

        assert count == 0
        assert recent_user.is_abandoned is False
        assert recent_user.fingerprint_hash is not None

    async def test_skips_registered_users(self, db):
        """Test that registered users are never marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)

        # Create an old registered user
        registered_user = await User.create(
            username="RegisteredUser",
            email="registered@example.com",
            password="hash",
            is_registered=True,
            is_abandoned=False,
            last_seen_at=cutoff_date
        )

        # Run abandonment cleanup
        count = await mark_abandoned()

        # Refresh from database
        await registered_user.refresh_from_db()

        assert count == 0
        assert registered_user.is_abandoned is False

    async def test_skips_already_abandoned_users(self, db):
        """Test that already abandoned users are skipped (idempotent)."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)

        # Create an already abandoned user
        abandoned_user = await User.create(
            username="AlreadyAbandoned",
            email="",
            password="",
            is_registered=False,
            is_abandoned=True,
            last_seen_at=cutoff_date
        )

        # Run abandonment cleanup
        count = await mark_abandoned()

        assert count == 0

    async def test_clears_fingerprint_on_abandonment(self, db):
        """Test that fingerprint is cleared when user is marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)

        # Create old user with fingerprint
        user = await User.create(
            username="UserWithFingerprint",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="f" * 64,
            fingerprint_data={"user_agent": "Mozilla/5.0"}
        )

        # Run abandonment cleanup
        await mark_abandoned()

        # Refresh from database
        await user.refresh_from_db()

        # Fingerprint hash should be cleared, but fingerprint_data retained
        assert user.fingerprint_hash is None
        assert user.fingerprint_data is not None
        assert user.fingerprint_data["user_agent"] == "Mozilla/5.0"

    async def test_returns_accurate_count(self, db):
        """Test that function returns accurate count of abandoned users."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)

        # Create multiple old unregistered users
        for i in range(5):
            await User.create(
                username=f"OldUser{i}",
                email="",
                password="",
                is_registered=False,
                is_abandoned=False,
                last_seen_at=cutoff_date,
                fingerprint_hash=f"{i}" * 64
            )

        # Run abandonment cleanup
        count = await mark_abandoned()

        assert count == 5

    async def test_idempotent_multiple_runs(self, db):
        """Test that running cleanup multiple times is safe (idempotent)."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)

        # Create old unregistered user
        await User.create(
            username="OldUser",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="g" * 64
        )

        # Run cleanup first time
        count1 = await mark_abandoned()
        assert count1 == 1

        # Run cleanup second time
        count2 = await mark_abandoned()
        assert count2 == 0  # No more users to abandon

    async def test_retains_fingerprint_data_for_audit(self, db):
        """Test that fingerprint_data is retained for record-keeping."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config

        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)

        fingerprint_data = {
            "user_agent": "Mozilla/5.0",
            "accept_language": "en-US",
            "accept_encoding": "gzip",
            "client_ip": "192.168.1.1"
        }

        user = await User.create(
            username="UserForAudit",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="h" * 64,
            fingerprint_data=fingerprint_data
        )

        await mark_abandoned()
        await user.refresh_from_db()

        # fingerprint_data should be retained
        assert user.fingerprint_data == fingerprint_data
        assert user.fingerprint_hash is None
