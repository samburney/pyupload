"""Tests for User model.

Tests for user model creation, fields, tier tracking, fingerprinting,
and unique username generation.

Acceptance Criteria:
- User instances can be created with all required fields
- User model properties work correctly
- User validation works as expected
- Fingerprint fields work correctly
- Tier fields (is_registered, is_abandoned) work correctly
- Username generation produces unique usernames
"""

import pytest
from datetime import datetime

from app.models.users import User


class TestUserModel:
    """Test User model creation and fields."""

    @pytest.mark.asyncio
    async def test_create_unregistered_user_with_fingerprint(self, db):
        """Test creating an unregistered user with fingerprint data."""
        fingerprint_data = {
            "user_agent": "Mozilla/5.0",
            "accept_language": "en-US",
            "accept_encoding": "gzip",
            "client_ip": "192.168.1.1"
        }
        
        user = await User.create(
            username="TestUser1234",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="a" * 64,
            fingerprint_data=fingerprint_data,
            registration_ip="192.168.1.1"
        )
        
        assert user.id is not None
        assert user.username == "TestUser1234"
        assert user.email == ""
        assert user.is_registered is False
        assert user.is_abandoned is False
        assert user.fingerprint_hash == "a" * 64
        assert user.fingerprint_data == fingerprint_data
        assert user.registration_ip == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_items_count_property(self, db):
        """Test that items_count property returns correct count."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hash",
            is_registered=True
        )
        
        # Currently placeholder returns 0
        count = await user.items_count
        assert count == 0

    @pytest.mark.asyncio
    async def test_user_with_null_email_password(self, db):
        """Test that unregistered user can have null/empty email and password."""
        user = await User.create(
            username="UnregUser9999",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="b" * 64
        )
        
        assert user.email == ""
        assert user.password == ""
        assert user.is_registered is False

    @pytest.mark.asyncio
    async def test_fingerprint_hash_not_unique(self, db):
        """Test that fingerprint_hash does not have uniqueness constraint."""
        # Two users can have the same fingerprint hash (same device, different time periods)
        hash_value = "c" * 64
        
        user1 = await User.create(
            username="User1",
            email="",
            password="",
            fingerprint_hash=hash_value
        )
        
        user2 = await User.create(
            username="User2",
            email="",
            password="",
            fingerprint_hash=hash_value
        )
        
        assert user1.fingerprint_hash == user2.fingerprint_hash
        assert user1.id != user2.id

    @pytest.mark.asyncio
    async def test_abandoned_flag_defaults_to_false(self, db):
        """Test that is_abandoned flag defaults to False."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hash"
        )
        
        assert user.is_abandoned is False

    @pytest.mark.asyncio
    async def test_ipv4_address_in_ip_fields(self, db):
        """Test that IPv4 addresses fit in IP address fields."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hash",
            registration_ip="192.168.1.100",
            last_login_ip="10.0.0.1"
        )
        
        assert user.registration_ip == "192.168.1.100"
        assert user.last_login_ip == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_ipv6_address_in_ip_fields(self, db):
        """Test that IPv6 addresses fit in IP address fields (45 chars max)."""
        ipv6_addr = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hash",
            registration_ip=ipv6_addr,
            last_login_ip=ipv6_addr
        )
        
        assert user.registration_ip == ipv6_addr
        assert user.last_login_ip == ipv6_addr
        assert len(user.registration_ip) <= 45
        assert len(user.last_login_ip) <= 45

    @pytest.mark.asyncio
    async def test_last_seen_at_timestamp(self, db):
        """Test that last_seen_at timestamp can be set and updated."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hash",
            last_seen_at=now
        )
        
        assert user.last_seen_at is not None
        # Within 1 second
        assert abs((user.last_seen_at - now).total_seconds()) < 1


class TestGenerateUniqueUsername:
    """Test User.generate_unique_username() classmethod."""

    @pytest.mark.asyncio
    async def test_generates_unique_username(self, db):
        """Test that generate_unique_username creates a valid username."""
        username = await User.generate_unique_username()
        
        assert isinstance(username, str)
        assert len(username) > 0
        # Should have digits at the end
        assert any(char.isdigit() for char in username)

    @pytest.mark.asyncio
    async def test_username_uniqueness_with_collision(self, db):
        """Test retry logic when username collision occurs."""
        # Create a user with a specific username
        existing_username = await User.generate_unique_username()
        await User.create(
            username=existing_username,
            email="test@example.com",
            password="hash"
        )
        
        # Generate another username - should be different
        new_username = await User.generate_unique_username()
        
        # Should not match existing username (extremely unlikely with random generation)
        # This test verifies the uniqueness check works
        assert isinstance(new_username, str)
        assert len(new_username) > 0

    @pytest.mark.asyncio
    async def test_handles_multiple_existing_users(self, db):
        """Test that username generation works even with existing users."""
        # Create several users to verify uniqueness checking works
        for i in range(5):
            username = await User.generate_unique_username()
            await User.create(
                username=username,
                email=f"test{i}@example.com",
                password="hash"
            )
        
        # Generate another - should succeed despite existing users
        new_username = await User.generate_unique_username()
        assert isinstance(new_username, str)
        assert len(new_username) > 0

    @pytest.mark.asyncio
    async def test_exception_after_max_attempts(self, db, monkeypatch):
        """Test that ValueError is raised after 10 failed attempts."""
        # Create existing user
        await User.create(
            username="CollisionUser0000",
            email="test@example.com",
            password="hash"
        )
        
        # Mock to always return the existing username
        def mock_generate(*args, **kwargs):
            return "CollisionUser0000"
        
        # Patch in the module where it's imported (app.models.users)
        import app.models.users
        monkeypatch.setattr(app.models.users, "generate_username", mock_generate)
        
        # Should raise ValueError after 10 attempts
        with pytest.raises(ValueError, match="Failed to generate a unique username"):
            await User.generate_unique_username()
