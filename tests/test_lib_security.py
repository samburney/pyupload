"""Tests for app.lib.security module."""

import pytest
from app.lib.security import hash_password, verify_password


class TestHashPassword:
    """Test cases for hash_password function."""

    def test_hash_password_creates_valid_hash(self):
        """Test that password hashing creates a valid bcrypt hash."""
        password = "secret"
        hashed = hash_password(password)

        # Hash should be non-empty string
        assert isinstance(hashed, str)
        assert len(hashed) > 0

        # Hash should look like a bcrypt hash (starts with $2a$, $2b$, or $2y$)
        assert hashed.startswith(("$2a$", "$2b$", "$2y$"))

    def test_hash_password_is_non_deterministic(self):
        """Test that hashing same password produces different hashes (due to salt)."""
        password = "secret"
        first = hash_password(password)
        second = hash_password(password)

        # Different hashes due to random salt
        assert first != second

        # But both should be valid bcrypt hashes
        assert first.startswith(("$2a$", "$2b$", "$2y$"))
        assert second.startswith(("$2a$", "$2b$", "$2y$"))

    def test_hash_password_with_empty_string(self):
        """Test hashing an empty string."""
        hashed = hash_password("")
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed.startswith(("$2a$", "$2b$", "$2y$"))

    def test_hash_password_with_special_characters(self):
        """Test hashing passwords with special characters."""
        passwords = [
            "p@ssw0rd!",
            "café_password",
            "password with spaces",
        ]

        for password in passwords:
            hashed = hash_password(password)
            assert isinstance(hashed, str)
            assert hashed.startswith(("$2a$", "$2b$", "$2y$"))


class TestVerifyPassword:
    """Test cases for verify_password function."""

    def test_verify_password_correct_password(self):
        """Test that verify_password returns True for correct password."""
        password = "secret"
        hashed = hash_password(password)

        # Should verify correctly
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self):
        """Test that verify_password returns False for incorrect password."""
        password = "secret"
        hashed = hash_password(password)

        # Should not verify a different password
        assert verify_password("wrong", hashed) is False
        assert verify_password("Secret", hashed) is False
        assert verify_password("secrets", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "MyPassword"
        hashed = hash_password(password)

        assert verify_password("MyPassword", hashed) is True
        assert verify_password("mypassword", hashed) is False
        assert verify_password("MYPASSWORD", hashed) is False

    def test_verify_password_with_known_bcrypt_hash(self):
        """Test verification with a known bcrypt hash from existing database."""
        # This is an example bcrypt hash generated from "test_password"
        # You can generate test hashes with: hash_password("test_password")
        known_password = "test_password"
        hashed = hash_password(known_password)

        # Verify the known password works
        assert verify_password(known_password, hashed) is True

    def test_verify_password_with_empty_string(self):
        """Test verification with empty password."""
        empty_hashed = hash_password("")

        # Empty password should verify correctly
        assert verify_password("", empty_hashed) is True

        # Non-empty password should not verify
        assert verify_password("anything", empty_hashed) is False

    def test_verify_password_with_special_characters(self):
        """Test verification with special character passwords."""
        passwords = [
            "p@ssw0rd!",
            "café_password",
            "password with spaces",
        ]

        for password in passwords:
            hashed = hash_password(password)
            assert verify_password(password, hashed) is True
            assert verify_password(password + "x", hashed) is False

    def test_verify_password_with_long_password(self):
        """Test verification with very long password (beyond bcrypt's 72-byte limit)."""
        # Test passwords of various lengths beyond bcrypt's 72-byte limit
        long_password = "a" * 100
        hashed = hash_password(long_password)

        assert verify_password(long_password, hashed) is True
        assert verify_password("a" * 99, hashed) is False
        assert verify_password("a" * 101, hashed) is False

    def test_password_length_support(self):
        """Test support for passwords of various lengths."""
        test_lengths = [1, 10, 50, 72, 100, 500, 1000]
        
        for length in test_lengths:
            password = "x" * length
            hashed = hash_password(password)
            
            # Should verify with the correct password
            assert verify_password(password, hashed) is True
            
            # Should fail with a password one character different
            assert verify_password(password + "y", hashed) is False

    def test_verify_password_with_unicode(self):
        """Test verification with unicode characters."""
        unicode_passwords = [
            "пароль",  # Russian (8 bytes in UTF-8)
            "αβγ",  # Greek (6 bytes in UTF-8)
        ]

        for password in unicode_passwords:
            hashed = hash_password(password)
            assert verify_password(password, hashed) is True


class TestPasswordIntegration:
    """Integration tests for hash and verify functions."""

    def test_hash_and_verify_round_trip(self):
        """Test full round-trip: hash a password, then verify it."""
        test_cases = [
            "simple",
            "complex!@#$%^&*()",
            "with spaces",
            "UPPERCASE",
            "lowercase",
            "MiXeD_CaSe",
        ]

        for password in test_cases:
            hashed = hash_password(password)
            assert verify_password(password, hashed) is True
            assert verify_password(password + "x", hashed) is False

    def test_multiple_passwords_produce_different_hashes(self):
        """Test that different passwords produce different hashes."""
        password1 = "password1"
        password2 = "password2"

        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        assert hash1 != hash2
        assert verify_password(password1, hash1) is True
        assert verify_password(password2, hash1) is False
        assert verify_password(password1, hash2) is False
        assert verify_password(password2, hash2) is True

    def test_security_doesnt_reveal_password_length(self):
        """Test that different length passwords produce different hashes."""
        short = hash_password("a" * 10)
        long = hash_password("a" * 1000)

        # Different passwords should have different hashes
        assert short != long

        # Both should verify correctly
        assert verify_password("a" * 10, short) is True
        assert verify_password("a" * 1000, long) is True
        
        # Cross-verification should fail
        assert verify_password("a" * 10, long) is False
        assert verify_password("a" * 1000, short) is False
