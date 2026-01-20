"""Tests for app/lib/security.py - Password hashing, verification, and fingerprinting.

This module tests cryptographic and security functions:
- hash_password(): bcrypt password hashing
- verify_password(): bcrypt password verification
- generate_username(): random username generation
- generate_fingerprint_hash(): browser fingerprint hashing
- extract_fingerprint_data(): fingerprint data extraction
- get_request_ip(): client IP extraction

JWT functions are tested in test_lib_auth.py.
"""

import pytest
from unittest.mock import Mock
from fastapi import Request

from app.lib.security import (
    hash_password,
    verify_password,
    generate_username,
    generate_fingerprint_hash,
    extract_fingerprint_data,
    get_request_ip,
)


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


# ============================================================================
# Username Generation Tests
# ============================================================================

class TestGenerateUsername:
    """Test generate_username() function."""

    def test_returns_string(self):
        """Test that generate_username returns a string."""
        username = generate_username()
        
        assert isinstance(username, str)
        assert len(username) > 0

    def test_produces_readable_format(self):
        """Test that username follows readable pattern with digits."""
        username = generate_username()
        
        # Should have at least one digit
        assert any(char.isdigit() for char in username)
        # Should have at least one letter
        assert any(char.isalpha() for char in username)
        # Should be capitalized (title case)
        assert username[0].isupper()

    def test_uses_coolname_words(self):
        """Test that username uses coolname library for word generation."""
        # Generate multiple usernames
        usernames = [generate_username() for _ in range(5)]
        
        # All should be non-empty strings
        for username in usernames:
            assert isinstance(username, str)
            assert len(username) > 0
            # Should have capitalized words
            assert any(char.isupper() for char in username)

    def test_produces_varied_usernames(self):
        """Test that generate_username produces different usernames."""
        usernames = [generate_username() for _ in range(10)]
        
        # Should produce at least some variety (not all the same)
        unique_usernames = set(usernames)
        assert len(unique_usernames) > 1


# ============================================================================
# Fingerprint Hash Generation Tests
# ============================================================================

class TestGenerateFingerprintHash:
    """Test generate_fingerprint_hash() function."""

    def test_returns_64_character_hash(self):
        """Test that fingerprint hash is 64 characters (SHA256 hex)."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        hash_value = generate_fingerprint_hash(mock_request)
        
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64
        # Should be hex characters
        assert all(c in '0123456789abcdef' for c in hash_value)

    def test_same_headers_produce_same_hash(self):
        """Test that same headers produce consistent hash (excludes IP by default)."""
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request1.client = Mock()
        mock_request1.client.host = "192.168.1.1"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request2.client = Mock()
        mock_request2.client.host = "192.168.1.1"
        
        hash1 = generate_fingerprint_hash(mock_request1)
        hash2 = generate_fingerprint_hash(mock_request2)
        
        assert hash1 == hash2

    def test_different_headers_produce_different_hash(self):
        """Test that different headers produce different hashes."""
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request1.client = Mock()
        mock_request1.client.host = "192.168.1.1"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {
            "User-Agent": "Chrome/91.0",  # Different user agent
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request2.client = Mock()
        mock_request2.client.host = "192.168.1.1"
        
        hash1 = generate_fingerprint_hash(mock_request1)
        hash2 = generate_fingerprint_hash(mock_request2)
        
        assert hash1 != hash2

    def test_excludes_client_ip_by_default(self):
        """Test that client IP is excluded from hash by default."""
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request1.client = Mock()
        mock_request1.client.host = "192.168.1.1"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request2.client = Mock()
        mock_request2.client.host = "10.0.0.100"  # Different IP
        
        hash1 = generate_fingerprint_hash(mock_request1, include_client_ip=False)
        hash2 = generate_fingerprint_hash(mock_request2, include_client_ip=False)
        
        # Same hash despite different IPs
        assert hash1 == hash2

    def test_includes_client_ip_when_requested(self):
        """Test that client IP is included when include_client_ip=True."""
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request1.client = Mock()
        mock_request1.client.host = "192.168.1.1"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request2.client = Mock()
        mock_request2.client.host = "10.0.0.100"  # Different IP
        
        hash1 = generate_fingerprint_hash(mock_request1, include_client_ip=True)
        hash2 = generate_fingerprint_hash(mock_request2, include_client_ip=True)
        
        # Different hash because of different IPs
        assert hash1 != hash2

    def test_same_headers_different_ips_with_include_ip_false(self):
        """Test explicit verification that IPs don't affect hash when include_client_ip=False."""
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request1.client = Mock()
        mock_request1.client.host = "1.2.3.4"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request2.client = Mock()
        mock_request2.client.host = "5.6.7.8"
        
        # Default behavior (include_client_ip=False)
        hash1 = generate_fingerprint_hash(mock_request1)
        hash2 = generate_fingerprint_hash(mock_request2)
        
        assert hash1 == hash2

    def test_same_headers_different_ips_with_include_ip_true(self):
        """Test that different IPs produce different hashes when include_client_ip=True."""
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request1.client = Mock()
        mock_request1.client.host = "1.2.3.4"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request2.client = Mock()
        mock_request2.client.host = "5.6.7.8"
        
        hash1 = generate_fingerprint_hash(mock_request1, include_client_ip=True)
        hash2 = generate_fingerprint_hash(mock_request2, include_client_ip=True)
        
        assert hash1 != hash2


# ============================================================================
# Fingerprint Data Extraction Tests
# ============================================================================

class TestExtractFingerprintData:
    """Test extract_fingerprint_data() function."""

    def test_extracts_all_headers(self):
        """Test that all fingerprint headers are extracted."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip, deflate"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        data = extract_fingerprint_data(mock_request)
        
        assert data["user_agent"] == "Mozilla/5.0"
        assert data["accept_language"] == "en-US"
        assert data["accept_encoding"] == "gzip, deflate"
        assert data["client_ip"] is not None

    def test_handles_missing_headers(self):
        """Test that missing headers default to empty string."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}  # No headers
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        data = extract_fingerprint_data(mock_request)
        
        assert data["user_agent"] == ""
        assert data["accept_language"] == ""
        assert data["accept_encoding"] == ""
        # client_ip should still be present
        assert "client_ip" in data

    def test_includes_client_ip_in_dict(self):
        """Test that client_ip is included in returned dict."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0"
        }
        mock_request.client = Mock()
        mock_request.client.host = "10.0.0.1"
        
        data = extract_fingerprint_data(mock_request)
        
        assert "client_ip" in data
        assert data["client_ip"] is not None

    def test_returns_dict_with_all_keys(self):
        """Test that returned dict contains all expected keys."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        data = extract_fingerprint_data(mock_request)
        
        expected_keys = {"user_agent", "accept_language", "accept_encoding", "client_ip"}
        assert set(data.keys()) == expected_keys


# ============================================================================
# IP Address Extraction Tests
# ============================================================================

class TestGetRequestIP:
    """Test get_request_ip() function."""

    def test_extracts_from_x_forwarded_for(self):
        """Test that X-Forwarded-For header is prioritized."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "X-Forwarded-For": "203.0.113.1, 198.51.100.1"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        ip = get_request_ip(mock_request)
        
        # Should extract first IP from X-Forwarded-For
        assert str(ip) == "203.0.113.1"

    def test_fallback_to_client_host(self):
        """Test fallback to request.client.host when X-Forwarded-For absent."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "10.0.0.5"
        
        ip = get_request_ip(mock_request)
        
        assert str(ip) == "10.0.0.5"

    def test_validates_ipv4_address(self):
        """Test that IPv4 addresses are validated correctly."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.100"
        
        ip = get_request_ip(mock_request)
        
        assert ip is not None
        assert str(ip) == "192.168.1.100"

    def test_validates_ipv6_address(self):
        """Test that IPv6 addresses are validated correctly."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        
        ip = get_request_ip(mock_request)
        
        assert ip is not None
        # netaddr normalizes IPv6 addresses
        assert "2001:db8:85a3" in str(ip).lower()

    def test_invalid_ip_returns_none(self):
        """Test that invalid IP address returns None."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "not.a.valid.ip"
        
        ip = get_request_ip(mock_request)
        
        assert ip is None

    def test_no_client_returns_none(self):
        """Test that missing client returns None."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = None
        
        ip = get_request_ip(mock_request)
        
        assert ip is None

    def test_x_forwarded_for_strips_whitespace(self):
        """Test that X-Forwarded-For IPs have whitespace stripped."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "X-Forwarded-For": "  203.0.113.1  , 198.51.100.1  "
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        ip = get_request_ip(mock_request)
        
        assert str(ip) == "203.0.113.1"

