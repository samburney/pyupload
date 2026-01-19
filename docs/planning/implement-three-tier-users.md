# Implementation Plan: Three-Tier User System with Auto-Generated Accounts

## Overview

Implement a sophisticated user system with three tiers: (1) truly anonymous read-only browsers with no database record, (2) auto-generated JWT-authenticated accounts with Reddit-style usernames restricted to UI-only access, and (3) fully registered accounts with API access and lifted restrictions. Auto-generated accounts use strict server-side fingerprinting for automatic re-authentication, issue fresh tokens per session, and are marked abandoned after 90 days of inactivity with private uploads deleted and fingerprint cleared for reuse.

**Current State**: 
- Binary authentication: users are either fully authenticated (JWT token) or completely anonymous (no access)
- No session persistence for unauthenticated users
- No mechanism for low-friction account creation
- Upload functionality not yet implemented

**Target State**: 
- Three-tier user system with seamless progression from anonymous → auto-generated → registered
- Fingerprint-based automatic re-authentication for returning users
- Reddit-style auto-generated usernames for easy identification
- Tiered upload limits (size, count, types) based on registration status
- 90-day activity window for auto-generated accounts with graceful abandonment
- API access restricted to registered users only

---

## Step 1: Add User Tier and Tracking Fields to User Model

**Files**: `app/models/users.py`

**Tasks**:
1. Add `is_registered` BooleanField with default=False to User model
2. Add `is_abandoned` BooleanField with default=False to User model
3. Add `fingerprint_hash` CharField (max_length=64, nullable, indexed) for fingerprint lookups
4. Add `fingerprint_data` JSONField to store headers and IP for audit trail
5. Add `registration_ip` CharField (max_length=45) for IPv6 support
6. Add `last_login_ip` CharField (max_length=45) for session tracking
7. Add `last_seen_at` DatetimeField for activity tracking
8. Update UserPydantic to make `email: Optional[EmailStr]` for auto-generated users
9. Add async `get_upload_count()` method returning count of user's uploads

**Acceptance Criteria**:
- [ ] All new fields added to User model with correct types
- [ ] `fingerprint_hash` field has database index for fast lookups
- [ ] `fingerprint_data` JSONField can store dict with user_agent, accept_language, accept_encoding, client_ip
- [ ] IPv6 addresses fit in IP address fields (45 characters)
- [ ] UserPydantic allows null email for auto-generated users
- [ ] `get_upload_count()` returns accurate count via database query
- [ ] Model passes Tortoise ORM validation
- [ ] All existing User functionality remains intact

**Estimated Effort**: 45 minutes

---

## Step 2: Generate Database Migration

**Files**: `app/models/migrations/`

**Tasks**:
1. Run `aerich migrate --name "add_user_tier_fields"` to generate migration
2. Review generated migration SQL for correctness
3. Verify all new columns and indexes are included
4. Run `aerich upgrade` to apply migration to development database
5. Verify schema changes in database

**Acceptance Criteria**:
- [ ] Migration file generated in `app/models/migrations/models/`
- [ ] Migration adds all 7 new fields to users table
- [ ] Index on `fingerprint_hash` column created
- [ ] Migration applies successfully without errors
- [ ] Database schema matches model definition
- [ ] Existing user records not corrupted (new fields nullable/defaulted)

**Estimated Effort**: 20 minutes

---

## Step 3: Create Username and Fingerprint Generators

**Files**: `app/lib/security.py`

**Tasks**:
1. Create word lists: adjectives (50+) and animals (50+) for username generation
2. Implement `generate_unique_username()` async function with pattern: Adjective+Animal+4digits
3. Add database uniqueness check in loop (max 10 attempts)
4. Implement `generate_fingerprint_hash(user_agent, accept_language, accept_encoding)` using SHA256
5. Implement `extract_fingerprint_data(request)` parsing Request headers
6. Extract client IP from `X-Forwarded-For` (first IP) with fallback to `request.client.host`
7. Return dict with keys: user_agent, accept_language, accept_encoding, client_ip

**Acceptance Criteria**:
- [ ] Username generator produces readable names (e.g., "HappyPanda1234", "CuriousKoala5678")
- [ ] Generated usernames are unique in database (retry logic works)
- [ ] Function raises exception if uniqueness not achieved after 10 attempts
- [ ] Fingerprint hash is consistent for same input (deterministic SHA256)
- [ ] Fingerprint hash is 64 characters (SHA256 hex digest)
- [ ] `extract_fingerprint_data()` handles missing headers gracefully (empty string defaults)
- [ ] Client IP extraction prioritizes `X-Forwarded-For` for reverse proxy compatibility
- [ ] All functions have proper type hints and docstrings

**Estimated Effort**: 60 minutes

---

## Step 4: Implement Auto-Registration Logic

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create async `get_or_create_unregistered_user(request, response)` function
2. Extract fingerprint data from request using `extract_fingerprint_data()`
3. Generate fingerprint hash from extracted data
4. Query User where `fingerprint_hash` matches AND `is_registered=False` AND `is_abandoned=False`
5. If found: update `last_seen_at` and `last_login_ip`, issue fresh JWT tokens
6. If not found: create new User with generated username, null email/password, fingerprint data
7. Set `registration_ip` and `last_login_ip` for new users
8. Issue fresh JWT access and refresh tokens via existing `create_tokens()` function
9. Return User instance with tokens set on response

**Acceptance Criteria**:
- [ ] Function returns User instance or raises exception
- [ ] Fingerprint matching only finds unregistered, non-abandoned users
- [ ] Existing users get `last_seen_at` and `last_login_ip` updated
- [ ] New users created with all required fields populated
- [ ] New users have `is_registered=False` and `is_abandoned=False`
- [ ] Fresh JWT tokens issued on every call (new session per connection)
- [ ] Both access and refresh token cookies set on response
- [ ] Function handles database errors gracefully
- [ ] Function is properly async/await compatible

**Estimated Effort**: 50 minutes

---

## Step 5: Update Authentication Dependency

**Files**: `app/lib/auth.py`

**Tasks**:
1. Modify `get_current_user_from_request()` to accept optional Response parameter
2. First attempt: validate JWT access token from cookies
3. If valid JWT token and user exists and not abandoned: return User with `is_authenticated=True`
4. Second attempt: call `get_or_create_unregistered_user(request, response)` for fingerprint auto-login
5. Return User from fingerprint auto-login with `is_authenticated=True`
6. Third attempt: return `None` for truly anonymous read-only users
7. Update return type to `Optional[UserPydantic]`
8. Ensure `is_authenticated` flag set correctly based on presence of User object

**Acceptance Criteria**:
- [ ] JWT token validation remains first priority (existing auth flow unchanged)
- [ ] Abandoned users cannot authenticate even with valid tokens
- [ ] Fingerprint auto-login creates/updates user when no JWT token present
- [ ] Truly anonymous users (no token, new fingerprint) get `None`
- [ ] Return type properly typed as `Optional[UserPydantic]`
- [ ] `is_authenticated=True` set when User returned, regardless of tier
- [ ] Response parameter optional for backward compatibility
- [ ] Function works with FastAPI dependency injection
- [ ] All existing endpoints continue working

**Estimated Effort**: 40 minutes

---

## Step 6: Create Account Upgrade Endpoint

**Files**: `app/ui/auth.py`

**Tasks**:
1. Create `GET /upgrade` route for account upgrade page
2. Require authenticated user (unregistered) via dependency
3. Render template showing current auto-generated username and upgrade form
4. Create `POST /upgrade` endpoint accepting optional new_username, required email and password
5. Validate current user has `is_registered=False` (403 if already registered)
6. Call `validate_username_change()` for email-username constraint enforcement
7. Hash password using existing `hash_password()` function
8. Update User: set username (if changed), email, password, `is_registered=True`
9. Set `registration_ip` to current client IP
10. Clear `fingerprint_hash` and `fingerprint_data` (registered users don't need fingerprint)
11. Issue fresh JWT tokens with updated user state
12. Redirect to home page with success message

**Acceptance Criteria**:
- [ ] GET endpoint renders upgrade form with current username displayed
- [ ] GET endpoint requires authenticated user (redirects if None)
- [ ] POST endpoint validates user is unregistered (rejects registered users)
- [ ] Username change validated via `validate_username_change()`
- [ ] Email field required and validated as EmailStr
- [ ] Password field required and meets existing validation (8+ chars)
- [ ] Successful upgrade sets `is_registered=True`
- [ ] Fingerprint cleared on registration (no longer needed)
- [ ] Fresh tokens issued reflecting registered status
- [ ] Success message displayed to user
- [ ] Form validation errors displayed properly

**Estimated Effort**: 60 minutes

---

## Step 7: Add Tiered Configuration

**Files**: `app/lib/config.py`

**Tasks**:
1. Add `UNREGISTERED_MAX_FILE_SIZE_MB` config variable (IntField, default=10)
2. Add `UNREGISTERED_MAX_UPLOADS` config variable (IntField, default=20)
3. Add `UNREGISTERED_ALLOWED_TYPES` config variable (CharField, default="image/jpeg,image/png,image/gif")
4. Add `REGISTERED_MAX_FILE_SIZE_MB` config variable (IntField, default=100)
5. Add `REGISTERED_MAX_UPLOADS` config variable (IntField, default=-1 for unlimited)
6. Add `REGISTERED_ALLOWED_TYPES` config variable (CharField, default="*")
7. Add `ACCOUNT_ABANDONMENT_DAYS` config variable (IntField, default=90)
8. Add validation for positive integers on size/count limits
9. Update `.env.example` with all new configuration variables

**Acceptance Criteria**:
- [ ] All configuration variables load from environment
- [ ] Default values match specifications
- [ ] Integer validation prevents negative values (except -1 for unlimited)
- [ ] MIME type lists are comma-separated strings
- [ ] Wildcard "*" supported for allowing all types
- [ ] Configuration accessible via AppConfig instance
- [ ] `.env.example` documents all new variables with descriptions
- [ ] Existing configuration unchanged

**Estimated Effort**: 30 minutes

---

## Step 8: Create Authentication Dependencies

**Files**: `app/lib/permissions.py` (new)

**Tasks**:
1. Create new `permissions.py` module in `app/lib/`
2. Import `get_current_user_from_request` and `UserPydantic` from auth
3. Implement `require_registered_user()` dependency function
4. Accept `current_user: Optional[UserPydantic] = Depends(get_current_user_from_request)`
5. Raise HTTPException(403, "Registration required") if user is None
6. Raise HTTPException(403, "Registration required") if `user.is_registered=False`
7. Return user if registered
8. Implement `require_authenticated_user()` dependency function
9. Raise HTTPException(401, "Authentication required") if user is None
10. Return user if authenticated (registered or unregistered)
11. Add proper type hints and docstrings

**Acceptance Criteria**:
- [ ] `permissions.py` module created and importable
- [ ] `require_registered_user()` works as FastAPI dependency
- [ ] Registered users pass through without error
- [ ] Unregistered users receive 403 error
- [ ] Anonymous users (None) receive 403 error
- [ ] `require_authenticated_user()` accepts both registered and unregistered
- [ ] Anonymous users (None) receive 401 error
- [ ] Dependencies compatible with FastAPI Security/Depends patterns
- [ ] Type hints correct for IDE autocomplete
- [ ] Docstrings explain usage and error codes

**Estimated Effort**: 35 minutes

---

## Step 9: Implement Username Validation

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create `validate_username_change(user: User, new_username: str)` function
2. Check if new_username matches email format (contains @ and .)
3. If username is email format: verify it matches user's email field
4. If username is email format and doesn't match email: raise ValueError
5. If username is not email format: allow any valid username
6. Add minimum length validation (3 characters)
7. Add maximum length validation (64 characters, matching database field)
8. Validate username doesn't contain invalid characters (alphanumeric + underscore + hyphen)
9. Return True if validation passes

**Acceptance Criteria**:
- [ ] Email-format usernames must match user's email field
- [ ] Non-email usernames can be any valid format
- [ ] Minimum 3 characters enforced
- [ ] Maximum 64 characters enforced
- [ ] Alphanumeric, underscore, hyphen allowed
- [ ] Special characters (except @ in email) rejected
- [ ] Raises ValueError with clear message on validation failure
- [ ] Returns True on success
- [ ] Existing username validation logic compatible

**Estimated Effort**: 30 minutes

---

## Step 10: Implement Abandonment Cleanup Function

**Files**: `app/lib/auth.py`

**Tasks**:
1. Create async `mark_abandoned_accounts()` function
2. Calculate cutoff date: `datetime.now() - timedelta(days=ACCOUNT_ABANDONMENT_DAYS)`
3. Query unregistered users where `last_seen_at < cutoff` AND `is_abandoned=False`
4. For each user: query uploads where `user_id=user.id` AND `private!=0`
5. Delete private upload database records (file deletion not in scope)
6. Update user: set `is_abandoned=True`, clear `fingerprint_hash` and `fingerprint_data`
7. Return count of users marked as abandoned
8. Add proper error handling and logging
9. Make function idempotent (safe to run multiple times)

**Acceptance Criteria**:
- [ ] Function queries only unregistered, non-abandoned users
- [ ] Cutoff date calculated from configured abandonment days
- [ ] Private uploads deleted from database (private field !=0)
- [ ] Public/non-private uploads preserved
- [ ] User marked as abandoned (`is_abandoned=True`)
- [ ] Fingerprint cleared allowing future reuse
- [ ] Function returns accurate count of abandoned users
- [ ] Errors logged with proper context
- [ ] Function can be called multiple times safely
- [ ] No impact on registered users

**Estimated Effort**: 45 minutes

---

## Step 11: Schedule Abandonment Cleanup Task

**Files**: `app/lib/scheduler.py`

**Tasks**:
1. Import `mark_abandoned_accounts()` function from auth
2. Create wrapper function `cleanup_abandoned_accounts()` for scheduler
3. Call `mark_abandoned_accounts()` and log result count
4. Handle exceptions and log errors
5. Schedule task to run daily at 3:00 AM
6. Use cron-style scheduling: `cron(hour=3, minute=0)`
7. Add job to existing scheduler instance
8. Ensure scheduler starts with application lifespan

**Acceptance Criteria**:
- [ ] Wrapper function calls `mark_abandoned_accounts()` correctly
- [ ] Success count logged at INFO level
- [ ] Errors caught and logged at ERROR level
- [ ] Task scheduled to run daily at 3:00 AM
- [ ] Scheduler configuration visible in startup logs
- [ ] Task can be manually triggered for testing
- [ ] Scheduler shutdown gracefully on app shutdown
- [ ] No interference with existing scheduled tasks (token cleanup)

**Estimated Effort**: 25 minutes

---

## Step 12: Update User Registration to Clear Fingerprints

**Files**: `app/api/auth.py`, `app/ui/auth.py`

**Tasks**:
1. Update existing `POST /api/v1/register` endpoint (if it exists)
2. After successful registration, clear `fingerprint_hash` and `fingerprint_data`
3. Update existing `POST /ui/register` endpoint
4. After successful registration, clear fingerprint fields
5. Ensure registered users never have fingerprint data
6. Add comment explaining why fingerprints cleared

**Acceptance Criteria**:
- [ ] API registration endpoint clears fingerprint (if endpoint exists)
- [ ] UI registration endpoint clears fingerprint
- [ ] Both endpoints set `is_registered=True`
- [ ] Fingerprint data cleared prevents automatic re-login
- [ ] Registered users must use explicit login
- [ ] Existing registration flow unchanged otherwise
- [ ] Code comments explain fingerprint clearing

**Estimated Effort**: 20 minutes

---

## Step 13: Create Tests for User Model Additions

**Files**: `tests/test_models_users.py`

**Tasks**:
1. Add test for creating unregistered user with fingerprint
2. Add test for `get_upload_count()` method
3. Add test for user with null email/password (unregistered)
4. Add test for fingerprint hash uniqueness (no constraint, can duplicate)
5. Add test for abandoned user flag behavior
6. Add test for IP address fields (IPv4 and IPv6)
7. Add test for last_seen_at timestamp updates

**Acceptance Criteria**:
- [ ] Test creates unregistered user successfully
- [ ] Test verifies `get_upload_count()` returns correct count
- [ ] Test verifies null email allowed for unregistered users
- [ ] Test verifies fingerprint fields populated correctly
- [ ] Test verifies abandoned flag defaults to False
- [ ] Test verifies IPv6 addresses fit in IP fields
- [ ] Test verifies timestamp fields auto-update
- [ ] All tests pass independently and in suite

**Estimated Effort**: 45 minutes

---

## Step 14: Create Tests for Fingerprint Functions

**Files**: `tests/test_lib_security.py` (new or extend existing)

**Tasks**:
1. Add test for `generate_unique_username()` format
2. Add test for username uniqueness retry logic
3. Add test for `generate_fingerprint_hash()` consistency
4. Add test for `generate_fingerprint_hash()` uniqueness with different inputs
5. Add test for `extract_fingerprint_data()` with all headers present
6. Add test for `extract_fingerprint_data()` with missing headers
7. Add test for `extract_fingerprint_data()` with X-Forwarded-For parsing
8. Add test for client IP extraction fallback

**Acceptance Criteria**:
- [ ] Username format matches pattern (Adjective+Animal+4digits)
- [ ] Username uniqueness enforced via retry
- [ ] Fingerprint hash is deterministic (same input = same hash)
- [ ] Fingerprint hash differs for different inputs
- [ ] Fingerprint extraction handles all headers correctly
- [ ] Missing headers default to empty string
- [ ] X-Forwarded-For first IP extracted correctly
- [ ] Fallback to request.client.host works
- [ ] All tests pass

**Estimated Effort**: 60 minutes

---

## Step 15: Create Tests for Auto-Registration

**Files**: `tests/test_lib_auth.py`

**Tasks**:
1. Add test for `get_or_create_unregistered_user()` creating new user
2. Add test for returning existing user on fingerprint match
3. Add test for updating last_seen_at on existing user
4. Add test for skipping abandoned users (creates new instead)
5. Add test for JWT token issuance
6. Add test for fingerprint mismatch creating new user
7. Add test for concurrent requests with same fingerprint

**Acceptance Criteria**:
- [ ] New fingerprint creates new user
- [ ] Existing fingerprint returns same user
- [ ] Last_seen_at updated on existing user access
- [ ] Abandoned users skipped, new user created
- [ ] Fresh tokens issued every call
- [ ] Different fingerprints create different users
- [ ] Concurrent requests handled correctly
- [ ] All tests pass

**Estimated Effort**: 60 minutes

---

## Step 16: Create Tests for Authentication Dependency

**Files**: `tests/test_lib_auth.py`

**Tasks**:
1. Add test for `get_current_user_from_request()` with valid JWT token
2. Add test for `get_current_user_from_request()` with fingerprint auto-login
3. Add test for `get_current_user_from_request()` returning None (anonymous)
4. Add test for abandoned user rejection
5. Add test for priority (JWT before fingerprint)
6. Add test for is_authenticated flag setting

**Acceptance Criteria**:
- [ ] Valid JWT returns authenticated user
- [ ] No JWT triggers fingerprint auto-login
- [ ] New fingerprint without JWT returns None (changed behavior)
- [ ] Abandoned users cannot authenticate
- [ ] JWT token takes priority over fingerprint
- [ ] is_authenticated set correctly
- [ ] All tests pass

**Estimated Effort**: 40 minutes

---

## Step 17: Create Tests for Account Upgrade

**Files**: `tests/test_ui_auth.py`

**Tasks**:
1. Add test for GET /upgrade rendering page
2. Add test for POST /upgrade with unregistered user
3. Add test for POST /upgrade with username change
4. Add test for POST /upgrade with email-username mismatch (should fail)
5. Add test for POST /upgrade clearing fingerprint
6. Add test for POST /upgrade setting is_registered=True
7. Add test for POST /upgrade with already registered user (should fail)

**Acceptance Criteria**:
- [ ] GET endpoint requires authentication
- [ ] POST upgrade succeeds for unregistered users
- [ ] Username can be changed if valid
- [ ] Email-username validation enforced
- [ ] Fingerprint cleared on upgrade
- [ ] is_registered flag set to True
- [ ] Registered users rejected (403)
- [ ] All tests pass

**Estimated Effort**: 50 minutes

---

## Step 18: Create Tests for Permission Dependencies

**Files**: `tests/test_lib_permissions.py` (new)

**Tasks**:
1. Create test file for permissions module
2. Add test for `require_registered_user()` with registered user
3. Add test for `require_registered_user()` with unregistered user (403)
4. Add test for `require_registered_user()` with None (403)
5. Add test for `require_authenticated_user()` with registered user
6. Add test for `require_authenticated_user()` with unregistered user
7. Add test for `require_authenticated_user()` with None (401)

**Acceptance Criteria**:
- [ ] Registered user passes require_registered_user
- [ ] Unregistered user raises 403 from require_registered_user
- [ ] Anonymous (None) raises 403 from require_registered_user
- [ ] Both user types pass require_authenticated_user
- [ ] Anonymous (None) raises 401 from require_authenticated_user
- [ ] HTTPException status codes correct
- [ ] All tests pass

**Estimated Effort**: 35 minutes

---

## Step 19: Create Tests for Username Validation

**Files**: `tests/test_lib_auth.py`

**Tasks**:
1. Add test for `validate_username_change()` with matching email-username
2. Add test for `validate_username_change()` with mismatched email-username
3. Add test for `validate_username_change()` with non-email username
4. Add test for username length validation (min/max)
5. Add test for username character validation
6. Add test for special character rejection

**Acceptance Criteria**:
- [ ] Email-format username matching email passes
- [ ] Email-format username not matching email fails
- [ ] Non-email username passes regardless of email
- [ ] Too short username fails (< 3 chars)
- [ ] Too long username fails (> 64 chars)
- [ ] Valid characters accepted (alphanumeric, _, -)
- [ ] Invalid characters rejected
- [ ] All tests pass

**Estimated Effort**: 30 minutes

---

## Step 20: Create Tests for Abandonment Cleanup

**Files**: `tests/test_lib_auth.py`

**Tasks**:
1. Add test for `mark_abandoned_accounts()` with old unregistered user
2. Add test for preserving recent unregistered users
3. Add test for skipping registered users
4. Add test for skipping already abandoned users
5. Add test for deleting private uploads only
6. Add test for preserving public uploads
7. Add test for clearing fingerprint on abandonment
8. Add test for return count accuracy

**Acceptance Criteria**:
- [ ] Old unregistered users marked as abandoned
- [ ] Recent users preserved
- [ ] Registered users never affected
- [ ] Already abandoned users skipped (idempotent)
- [ ] Private uploads deleted
- [ ] Public uploads preserved
- [ ] Fingerprint cleared
- [ ] Accurate count returned
- [ ] All tests pass

**Estimated Effort**: 60 minutes

---

## Step 21: Update Documentation

**Files**: `README.md`, `docs/overview.md`

**Tasks**:
1. Document three-tier user system architecture
2. Document auto-generated account flow
3. Document fingerprint-based auto-login
4. Document account upgrade process
5. Document tiered upload limits
6. Document abandonment policy
7. Update environment variables documentation
8. Add security considerations for fingerprinting

**Acceptance Criteria**:
- [ ] README explains three-tier system clearly
- [ ] User flow diagrams/descriptions added
- [ ] Fingerprint privacy implications documented
- [ ] Account upgrade process explained
- [ ] Upload limits documented by tier
- [ ] 90-day abandonment policy explained
- [ ] Environment variables documented
- [ ] Security best practices included

**Estimated Effort**: 60 minutes

---

## Step 22: Manual Testing and Validation

**Tasks**:
1. Test truly anonymous browsing (no database record)
2. Test auto-generated account creation on first action
3. Test fingerprint auto-login on return visit
4. Test account upgrade flow (unregistered → registered)
5. Test username change validation
6. Test tiered limits enforcement (when upload implemented)
7. Test abandonment cleanup (manually trigger)
8. Test fingerprint reuse after abandonment
9. Test browser update changes fingerprint

**Acceptance Criteria**:
- [ ] Anonymous users can browse without database record
- [ ] First action creates auto-generated account
- [ ] Return visits auto-login via fingerprint
- [ ] Account upgrade works smoothly
- [ ] Username validation enforced
- [ ] Abandonment cleanup runs successfully
- [ ] Abandoned fingerprints can be reused
- [ ] Browser changes create new accounts
- [ ] No security vulnerabilities identified

**Estimated Effort**: 90 minutes

---

## Total Estimated Effort: ~18 hours

## Security Considerations

1. **Fingerprint Privacy**: Store both hash (for matching) and raw data (for abuse investigation) with documented retention policy aligned with abandonment cleanup
2. **Fingerprint Stability**: Strict fingerprinting means browser updates create new accounts, encouraging registration for persistent access
3. **Abandoned Account Cleanup**: 90-day window balances usability with preventing database bloat
4. **Fingerprint Reuse**: Clearing fingerprint on abandonment allows same device to create new account
5. **API Access Control**: Unregistered users restricted to UI-only prevents API abuse
6. **Private Upload Deletion**: Abandoned accounts lose private uploads, public uploads preserved for community benefit
7. **Email Optional**: Unregistered users don't need email, reducing friction and privacy concerns
8. **Password Security**: Existing bcrypt hashing applies when upgrading to registered account
9. **Token Security**: Existing JWT token security applies to all authenticated users (registered and unregistered)
10. **Reverse Proxy Support**: X-Forwarded-For parsing essential for fingerprinting behind proxies

## Implementation Considerations

1. **Fingerprint Collision**: Same fingerprint auto-logins to same account - not a bug, it's the feature
2. **Session vs Persistent**: Unregistered accounts persist via refresh tokens (up to 7 days) not single session
3. **Upload Limits**: Enforcement happens in upload handlers (future implementation), not in auth system
4. **Email Constraint**: Email-username matching enforced at validation layer, not database constraint
5. **Abandonment Timing**: Scheduled at 3 AM daily for predictable maintenance window
6. **Fingerprint on Registration**: Cleared when upgrading to registered account - registered users use explicit login
7. **Database Transactions**: Per-user transactions in cleanup to prevent cascading failures
8. **Backwards Compatibility**: Existing fully authenticated users unaffected by new tiers

## Rollback Plan

If issues arise, rollback steps:
1. Disable scheduler task for abandonment cleanup
2. Revert authentication dependency to return None for unauthenticated
3. Revert database migration (aerich downgrade)
4. Remove fingerprint and tier configuration
5. Existing registered users continue working normally
6. Re-deploy previous version if necessary

## Success Metrics

- [ ] All automated tests pass (target: 100% of new tests)
- [ ] Anonymous users can browse without database records
- [ ] Auto-generated accounts created seamlessly on first action
- [ ] Fingerprint auto-login works reliably for returning users
- [ ] Account upgrade flow completes without errors
- [ ] Username validation prevents email-username mismatches
- [ ] Abandonment cleanup runs successfully and reduces database size
- [ ] No increase in authentication-related errors
- [ ] User experience is frictionless for new users
- [ ] Clear upgrade path from unregistered to registered

## Future Enhancements (Not in Scope)

1. Admin panel for managing abandoned accounts manually
2. Email verification for registered accounts
3. Fuzzy fingerprint matching for browser updates
4. User notification system for account status
5. Upload quota tracking and enforcement
6. User dashboard showing upload count and tier limits
7. Complete file deletion (filesystem) in abandonment cleanup
8. Permanent deletion of abandoned user records (beyond marking)
9. Analytics on user tier distribution and upgrade rates
10. OAuth/SSO integration for registered accounts
