# Implementation Plan: JWT Refresh Tokens

## Overview

Implement JWT refresh token functionality to enable long-lived sessions while maintaining security through short-lived access tokens and automatic token rotation.

**Current State**: Access tokens expire after 30 minutes, requiring re-login. No session persistence mechanism.

**Target State**: Users receive refresh tokens (7 days) that automatically renew access tokens, providing seamless experience while maintaining security.

---

## Step 1: Add Refresh Token Configuration

**Files**: `app/lib/config.py`, `.env.example`

**Tasks**:
1. Add `AUTH_REFRESH_TOKEN_AGE_DAYS` config variable with default value of 7
2. Update `.env.example` with refresh token configuration
3. Validate refresh token age is positive integer

**Acceptance Criteria**:
- [ ] Config loads `AUTH_REFRESH_TOKEN_AGE_DAYS` from environment
- [ ] Default value is 7 days if not specified
- [ ] Config raises error if value is not positive integer
- [ ] `.env.example` documents the new variable with example value

**Estimated Effort**: 15 minutes

---

## Step 2: Create Database Model for Refresh Tokens

**Files**: `app/models/users.py`

**Tasks**:
1. Create `RefreshToken` Tortoise model class
2. Add fields: `id` (PK), `user_id` (FK to users), `token_hash` (SHA256 hash), `expires_at`, `created_at`, `revoked` (boolean default False)
3. Add index on `token_hash` for fast lookups
4. Add foreign key relationship from `RefreshToken` to `User`
5. Add reverse relationship on `User` model (refresh_tokens)

**Acceptance Criteria**:
- [ ] `RefreshToken` model defined with all required fields
- [ ] `token_hash` field is indexed
- [ ] Foreign key relationship to `User` model exists
- [ ] `User.refresh_tokens` reverse relationship available
- [ ] Model passes basic Tortoise ORM validation
- [ ] Table name is `refresh_tokens`

**Estimated Effort**: 30 minutes

---

## Step 3: Generate Database Migration

**Files**: `app/models/migrations/`

**Tasks**:
1. Run `aerich migrate` to generate migration file
2. Review generated migration SQL
3. Run `aerich upgrade` to apply migration to development database
4. Verify `refresh_tokens` table created with correct schema

**Acceptance Criteria**:
- [ ] Migration file generated in `app/models/migrations/models/`
- [ ] Migration creates `refresh_tokens` table
- [ ] Table has all required columns with correct types
- [ ] Foreign key constraint to `users` table exists
- [ ] Index on `token_hash` column exists
- [ ] Migration applies successfully without errors

**Estimated Effort**: 15 minutes

---

## Step 4: Implement Refresh Token Creation

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create `create_refresh_token(user: User) -> str` function
2. Generate JWT with `sub` claim containing user ID
3. Set expiration to configured days from now
4. Sign with same secret key and algorithm as access tokens
5. Return the JWT string

**Acceptance Criteria**:
- [ ] Function accepts `User` model instance
- [ ] Returns valid JWT string
- [ ] Token contains `sub` claim with user ID
- [ ] Token has `exp` claim set to configured days in future
- [ ] Token signed with configured secret and algorithm
- [ ] Function has proper type hints and docstring

**Estimated Effort**: 20 minutes

---

## Step 5: Implement Refresh Token Storage

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create `store_refresh_token(user: User, token: str) -> RefreshToken` async function
2. Hash token with SHA256 before storage
3. Calculate expiration datetime from token's `exp` claim
4. Create `RefreshToken` database record with hashed token
5. Return created `RefreshToken` instance

**Acceptance Criteria**:
- [ ] Function accepts `User` instance and JWT token string
- [ ] Token is hashed with SHA256 before storage
- [ ] Expiration datetime extracted from JWT correctly
- [ ] Database record created with all required fields
- [ ] Function returns created `RefreshToken` instance
- [ ] Handles database errors gracefully

**Estimated Effort**: 25 minutes

---

## Step 6: Implement Refresh Token Validation

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create `validate_refresh_token(token: str) -> RefreshToken | None` async function
2. Decode JWT to extract claims
3. Hash provided token with SHA256
4. Query database for matching token hash
5. Check if token is revoked or expired
6. Return `RefreshToken` instance if valid, `None` otherwise

**Acceptance Criteria**:
- [ ] Function accepts JWT token string
- [ ] Decodes JWT and validates signature
- [ ] Queries database by hashed token
- [ ] Returns `None` if token not found
- [ ] Returns `None` if token is revoked
- [ ] Returns `None` if token is expired
- [ ] Returns `RefreshToken` instance if valid
- [ ] Handles JWT decode errors gracefully (returns `None`)

**Estimated Effort**: 30 minutes

---

## Step 7: Implement Token Revocation Functions

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create `revoke_refresh_token(token_hash: str) -> bool` async function
2. Update database record to set `revoked = True`
3. Create `revoke_user_refresh_tokens(user_id: int) -> int` async function
4. Revoke all non-revoked tokens for a user
5. Return count of revoked tokens

**Acceptance Criteria**:
- [ ] `revoke_refresh_token()` marks single token as revoked
- [ ] Returns `True` if token found and revoked, `False` otherwise
- [ ] `revoke_user_refresh_tokens()` revokes all user tokens
- [ ] Returns count of tokens actually revoked
- [ ] Both functions handle database errors gracefully
- [ ] Revoking already-revoked token is idempotent (no error)

**Estimated Effort**: 25 minutes

---

## Step 8: Update Login to Issue Refresh Tokens

**Files**: `app/ui/auth.py`

**Tasks**:
1. Update `login_for_access_token()` endpoint
2. After successful authentication, create refresh token
3. Store refresh token in database
4. Create refresh token cookie with proper settings
5. Set both access and refresh token cookies on response

**Acceptance Criteria**:
- [ ] Refresh token created after successful login
- [ ] Refresh token stored in database linked to user
- [ ] `refresh_token` cookie set with 7-day max age
- [ ] Refresh cookie has httponly, secure, and samesite=strict flags
- [ ] Access token functionality unchanged (backward compatible)
- [ ] Login still works if refresh token creation fails (graceful degradation)

**Estimated Effort**: 30 minutes

---

## Step 9: Implement Token Refresh Endpoint

**Files**: `app/ui/auth.py`

**Tasks**:
1. Create `POST /refresh` endpoint
2. Read `refresh_token` from request cookies
3. Validate refresh token using `validate_refresh_token()`
4. If valid, create new access token for the user
5. Return response with new access token cookie
6. Return 401 error if refresh token invalid/expired

**Acceptance Criteria**:
- [ ] `POST /refresh` endpoint exists and is routable
- [ ] Reads `refresh_token` from cookies
- [ ] Returns 401 if no refresh token provided
- [ ] Returns 401 if refresh token invalid
- [ ] Returns 401 if refresh token expired
- [ ] Returns 401 if refresh token revoked
- [ ] Issues new access token for valid refresh token
- [ ] New access token cookie set on response (200 status)
- [ ] Endpoint does not require existing valid access token

**Estimated Effort**: 35 minutes

---

## Step 10: Implement Refresh Token Rotation

**Files**: `app/ui/auth.py`, `app/lib/auth.py`

**Tasks**:
1. Update `/refresh` endpoint to revoke old refresh token
2. Generate new refresh token after validation
3. Store new refresh token in database
4. Return both new access and refresh token cookies
5. Ensure atomic operation (both succeed or both fail)

**Acceptance Criteria**:
- [ ] Old refresh token revoked immediately after validation
- [ ] New refresh token generated with fresh expiration
- [ ] New refresh token stored in database
- [ ] Both `access_token` and `refresh_token` cookies updated
- [ ] If any step fails, no tokens are revoked (rollback)
- [ ] Token rotation is transparent to client

**Estimated Effort**: 30 minutes

---

## Step 11: Update Logout to Revoke Refresh Tokens

**Files**: `app/ui/auth.py`

**Tasks**:
1. Update `logout()` endpoint to extract refresh token from cookies
2. Revoke the refresh token in database if present
3. Delete both access and refresh token cookies
4. Handle case where no refresh token exists (backward compatible)

**Acceptance Criteria**:
- [ ] Logout reads `refresh_token` from cookies
- [ ] Refresh token revoked in database if present
- [ ] Both `access_token` and `refresh_token` cookies deleted
- [ ] Logout succeeds even if no refresh token cookie
- [ ] Logout succeeds even if refresh token already revoked
- [ ] Flash message and redirect still work

**Estimated Effort**: 20 minutes

---

## Step 12: Add Logout All Devices Endpoint

**Files**: `app/ui/auth.py`

**Tasks**:
1. Create `POST /logout-all` endpoint
2. Require valid access token (authenticated user)
3. Revoke all refresh tokens for current user
4. Delete current device cookies
5. Return success response with redirect

**Acceptance Criteria**:
- [ ] `POST /logout-all` endpoint exists
- [ ] Requires authenticated user (uses `get_current_user` dependency)
- [ ] Revokes all user's refresh tokens in database
- [ ] Deletes access and refresh token cookies
- [ ] Returns success message
- [ ] Returns 401 if user not authenticated

**Estimated Effort**: 25 minutes

---

## Step 13: Implement Token Cleanup Scheduled Task

**Files**: `app/lib/scheduler.py` (new), `app/main.py`

**Tasks**:
1. Create scheduler module if not exists
2. Add `cleanup_expired_tokens()` async function
3. Delete refresh tokens where `expires_at < now()` OR `revoked = True` AND `created_at < now() - 30 days`
4. Schedule task to run daily at 2 AM
5. Integrate scheduler startup in `app/main.py` lifespan

**Acceptance Criteria**:
- [ ] Scheduler module created with proper initialization
- [ ] Cleanup function deletes expired tokens
- [ ] Cleanup function deletes old revoked tokens (30+ days old)
- [ ] Function logs count of deleted tokens
- [ ] Scheduled to run daily at 2 AM UTC
- [ ] Scheduler starts with application
- [ ] Scheduler stops gracefully on shutdown
- [ ] Cleanup can be run manually for testing

**Estimated Effort**: 45 minutes

---

## Step 14: Add Refresh Token Cookie Helper

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create `create_refresh_token_cookie(token: str) -> dict` function
2. Set appropriate cookie settings (7 days, httponly, secure, samesite=strict)
3. Return cookie configuration dictionary
4. Ensure consistent with existing `create_token_cookie()`

**Acceptance Criteria**:
- [ ] Function returns cookie configuration dict
- [ ] Cookie key is `refresh_token`
- [ ] Max age set to configured refresh token days (in seconds)
- [ ] `httponly=True` for security
- [ ] `secure=True` for HTTPS only
- [ ] `samesite="strict"` for CSRF protection
- [ ] Signature matches `create_token_cookie()` pattern

**Estimated Effort**: 15 minutes

---

## Step 15: Create Tests for Refresh Token Model

**Files**: `tests/test_models_refresh_token.py` (new)

**Tasks**:
1. Create test file for RefreshToken model
2. Test model creation with all fields
3. Test foreign key relationship to User
4. Test token expiration validation
5. Test revoked flag behavior

**Acceptance Criteria**:
- [ ] Test creates RefreshToken instance successfully
- [ ] Test verifies foreign key to User works
- [ ] Test verifies token_hash is stored correctly
- [ ] Test verifies expires_at datetime handling
- [ ] Test verifies revoked flag defaults to False
- [ ] Test verifies database constraints
- [ ] All tests pass

**Estimated Effort**: 30 minutes

---

## Step 16: Create Tests for Refresh Token Functions

**Files**: `tests/test_auth_refresh.py` (new)

**Tasks**:
1. Create test file for refresh token auth functions
2. Test `create_refresh_token()` creates valid JWT
3. Test `store_refresh_token()` stores in database
4. Test `validate_refresh_token()` with valid token
5. Test `validate_refresh_token()` with expired token
6. Test `validate_refresh_token()` with revoked token
7. Test `revoke_refresh_token()` marks as revoked
8. Test `revoke_user_refresh_tokens()` revokes all user tokens

**Acceptance Criteria**:
- [ ] All function tests use mocked database
- [ ] Test refresh token JWT structure and claims
- [ ] Test token validation success case
- [ ] Test token validation failure cases (expired, revoked, not found)
- [ ] Test revocation functions work correctly
- [ ] Test multi-user token isolation
- [ ] All tests pass independently

**Estimated Effort**: 60 minutes

---

## Step 17: Create Tests for Refresh Endpoint

**Files**: `tests/test_auth_jwt.py` (extend existing)

**Tasks**:
1. Add test class for refresh endpoint
2. Test `/refresh` with valid refresh token
3. Test `/refresh` with expired refresh token
4. Test `/refresh` with revoked refresh token
5. Test `/refresh` with no refresh token
6. Test `/refresh` with invalid refresh token
7. Test token rotation during refresh

**Acceptance Criteria**:
- [ ] Test valid refresh returns new access token
- [ ] Test expired refresh returns 401
- [ ] Test revoked refresh returns 401
- [ ] Test missing refresh returns 401
- [ ] Test invalid refresh returns 401
- [ ] Test new access token is valid and works
- [ ] Test old refresh token is revoked after rotation
- [ ] Test new refresh token is issued and works
- [ ] All tests pass

**Estimated Effort**: 45 minutes

---

## Step 18: Create Tests for Updated Login/Logout

**Files**: `tests/test_auth_jwt.py` (extend existing)

**Tasks**:
1. Update login tests to verify refresh token cookie
2. Test refresh token stored in database on login
3. Update logout tests to verify refresh token revoked
4. Test logout-all endpoint functionality
5. Test logout-all revokes all user tokens

**Acceptance Criteria**:
- [ ] Login test verifies both access and refresh cookies set
- [ ] Login test verifies refresh token in database
- [ ] Logout test verifies refresh token revoked in database
- [ ] Logout test verifies both cookies deleted
- [ ] Logout-all test requires authentication
- [ ] Logout-all test revokes all user's tokens
- [ ] All existing tests still pass (backward compatibility)

**Estimated Effort**: 40 minutes

---

## Step 19: Create Tests for Cleanup Task

**Files**: `tests/test_lib_scheduler.py` (new)

**Tasks**:
1. Create test file for scheduler module
2. Test cleanup function deletes expired tokens
3. Test cleanup function deletes old revoked tokens
4. Test cleanup function preserves valid tokens
5. Test cleanup function preserves recently revoked tokens
6. Test cleanup returns correct count

**Acceptance Criteria**:
- [ ] Test with expired tokens - deleted
- [ ] Test with revoked tokens older than 30 days - deleted
- [ ] Test with revoked tokens newer than 30 days - kept
- [ ] Test with valid tokens - kept
- [ ] Test mixed scenario with all token types
- [ ] Test returns count of deleted tokens
- [ ] All tests pass

**Estimated Effort**: 35 minutes

---

## Step 20: Update Documentation

**Files**: `README.md`, `docs/overview.md`

**Tasks**:
1. Document refresh token authentication flow
2. Document `/refresh` endpoint usage
3. Document logout-all functionality
4. Update environment variable documentation
5. Document token expiration and rotation strategy
6. Add security considerations for refresh tokens

**Acceptance Criteria**:
- [ ] README explains refresh token functionality
- [ ] Authentication flow diagram/description updated
- [ ] API endpoints documented with examples
- [ ] Environment variables documented
- [ ] Security best practices included
- [ ] Migration instructions for existing deployments

**Estimated Effort**: 30 minutes

---

## Step 21: Manual Testing and Validation

**Tasks**:
1. Test complete login flow in browser
2. Verify both cookies are set correctly
3. Test access token auto-refresh before expiration
4. Test logout revokes refresh token
5. Test logout-all from multiple devices
6. Test token rotation security
7. Verify cleanup task runs correctly

**Acceptance Criteria**:
- [ ] Login creates both access and refresh tokens
- [ ] Access token auto-refreshes seamlessly
- [ ] Logout from one device doesn't affect others
- [ ] Logout-all revokes all sessions
- [ ] Expired tokens handled gracefully
- [ ] Cleanup task removes old tokens
- [ ] No security vulnerabilities identified

**Estimated Effort**: 60 minutes

---

## Total Estimated Effort: ~12 hours

## Security Considerations

1. **Token Storage**: Refresh tokens stored as SHA256 hashes, never plaintext
2. **Token Rotation**: Refresh tokens rotated on each use to prevent replay attacks
3. **Revocation**: Server-side revocation prevents stolen token reuse
4. **Cleanup**: Automated removal of old tokens reduces attack surface
5. **Cookie Security**: Strict SameSite, HttpOnly, and Secure flags prevent XSS/CSRF
6. **Short Access Tokens**: 30-minute access tokens limit exposure window

## Rollback Plan

If issues arise, rollback steps:
1. Revert database migration (aerich downgrade)
2. Revert code changes to auth endpoints
3. Remove refresh token configuration
4. Existing access-only tokens continue working
5. Users re-login with existing flow (no data loss)

## Success Metrics

- [ ] All automated tests pass (target: 100% pass rate)
- [ ] Access tokens auto-refresh without user intervention
- [ ] User sessions persist for configured refresh token lifetime
- [ ] Logout successfully revokes tokens
- [ ] No increase in authentication-related errors
- [ ] Cleanup task runs successfully and reduces database size
