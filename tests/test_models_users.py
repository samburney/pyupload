"""Tests for app/models/users.py — User model.

Validates:
- User.create: all required fields, unregistered users with fingerprint data
- User properties: uploads_count, images_count
- IP address fields: IPv4 and IPv6 support
- is_abandoned flag: defaults to False
- fingerprint_hash: non-unique (multiple users may share a hash)
- last_seen_at: nullable timestamp
- User.generate_unique_username: returns unique strings, retries on collision,
  raises ValueError after 10 failed attempts
"""

import pytest
import app.models.users
from datetime import datetime, timezone

from app.models.users import User


class TestUserModel:
    """Tests for User model creation and field behaviour."""

    async def test_create_unregistered_user_with_fingerprint(self, db):
        """An unregistered user can be created with fingerprint data."""
        fingerprint_data = {
            "user_agent": "Mozilla/5.0",
            "accept_language": "en-US",
            "accept_encoding": "gzip",
            "client_ip": "192.168.1.1",
        }

        user = await User.create(
            username="TestUser1234",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="a" * 64,
            fingerprint_data=fingerprint_data,
            registration_ip="192.168.1.1",
        )

        assert user.id is not None
        assert user.username == "TestUser1234"
        assert user.email == ""
        assert user.is_registered is False
        assert user.is_abandoned is False
        assert user.fingerprint_hash == "a" * 64
        assert user.fingerprint_data == fingerprint_data
        assert user.registration_ip == "192.168.1.1"

    async def test_uploads_count_is_zero_for_new_user(self, db):
        """uploads_count returns 0 for a user with no uploads."""
        user = await User.create(username="testuser", email="test@example.com", password="hash", is_registered=True)

        assert await user.uploads_count == 0

    async def test_images_count_is_zero_for_new_user(self, db):
        """images_count returns 0 for a user with no images."""
        user = await User.create(username="testimagesuser", email="testimages@example.com", password="hash", is_registered=True)

        assert await user.images_count == 0

    async def test_unregistered_user_can_have_empty_email_and_password(self, db):
        """Unregistered users may have empty email and password fields."""
        user = await User.create(username="UnregUser9999", email="", password="", is_registered=False, fingerprint_hash="b" * 64)

        assert user.email == ""
        assert user.password == ""
        assert user.is_registered is False

    async def test_fingerprint_hash_is_not_unique(self, db):
        """Multiple users may share the same fingerprint_hash (no uniqueness constraint)."""
        hash_value = "c" * 64

        user1 = await User.create(username="User1", email="", password="", fingerprint_hash=hash_value)
        user2 = await User.create(username="User2", email="", password="", fingerprint_hash=hash_value)

        assert user1.fingerprint_hash == user2.fingerprint_hash
        assert user1.id != user2.id

    async def test_is_abandoned_defaults_to_false(self, db):
        """is_abandoned defaults to False on new users."""
        user = await User.create(username="testuser", email="test@example.com", password="hash")

        assert user.is_abandoned is False

    async def test_ipv4_address_in_ip_fields(self, db):
        """IPv4 addresses are stored correctly in registration_ip and last_login_ip."""
        user = await User.create(
            username="testuser", email="test@example.com", password="hash",
            registration_ip="192.168.1.100", last_login_ip="10.0.0.1",
        )

        assert user.registration_ip == "192.168.1.100"
        assert user.last_login_ip == "10.0.0.1"

    async def test_ipv6_address_in_ip_fields(self, db):
        """IPv6 addresses fit within the 45-character IP field limit."""
        ipv6_addr = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        user = await User.create(
            username="testuser", email="test@example.com", password="hash",
            registration_ip=ipv6_addr, last_login_ip=ipv6_addr,
        )

        assert user.registration_ip == ipv6_addr
        assert user.last_login_ip == ipv6_addr
        assert len(user.registration_ip) <= 45
        assert len(user.last_login_ip) <= 45

    async def test_last_seen_at_timestamp_is_stored(self, db):
        """last_seen_at is stored and retrieved correctly."""
        now = datetime.now(timezone.utc)

        user = await User.create(username="testuser", email="test@example.com", password="hash", last_seen_at=now)

        assert user.last_seen_at is not None
        assert abs((user.last_seen_at - now).total_seconds()) < 1


class TestGenerateUniqueUsername:
    """Tests for User.generate_unique_username()."""

    async def test_generates_a_valid_username_string(self, db):
        """generate_unique_username returns a non-empty string."""
        username = await User.generate_unique_username()

        assert isinstance(username, str)
        assert len(username) > 0

    async def test_generated_username_contains_digits(self, db):
        """Generated username includes a numeric suffix."""
        username = await User.generate_unique_username()

        assert any(char.isdigit() for char in username)

    async def test_generates_unique_username_with_existing_users(self, db):
        """generate_unique_username works even when users already exist."""
        for i in range(5):
            username = await User.generate_unique_username()
            await User.create(username=username, email=f"test{i}@example.com", password="hash")

        new_username = await User.generate_unique_username()
        assert isinstance(new_username, str)
        assert len(new_username) > 0

    async def test_raises_after_max_collision_attempts(self, db, monkeypatch):
        """ValueError is raised after 10 consecutive username collisions."""
        await User.create(username="CollisionUser0000", email="test@example.com", password="hash")

        monkeypatch.setattr(app.models.users, "generate_username", lambda *args, **kwargs: "CollisionUser0000")

        with pytest.raises(ValueError, match="Failed to generate a unique username"):
            await User.generate_unique_username()
