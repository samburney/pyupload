## Authentication Implementation Plan

### Goal
Implement a session‑based authentication system using the legacy simplegallery users. The system should:
- Verify bcrypt passwords stored in the legacy database.
- Use file‑based session storage.
- Allow login, registration, and logout.
- Redirect newly registered users to the login page.
- Provide a clear set of acceptance criteria for each milestone.

---

## Milestones & Acceptance Criteria

1. **Create Branch**: COMPLETED
   - Command: `git checkout -b implement_auth main`
   - *AC*: Branch `implement_auth` exists and points to `main` commit.

2. **Add Auth Dependencies**: COMPLETED
   - Update `pyproject.toml` to add `passlib[bcrypt]`, `python-multipart`, and `starlette-sessions`.
   - *AC*: `pip list` (or `uv run python -m pip list`) shows the packages installed and `pyproject.toml` reflects the additions.

3. **Create Security Utilities** COMPLETED
   - File: `app/lib/security.py` with `hash_password` and `verify_password`.
   - *AC*: `verify_password('plain', <existing bcrypt hash>)` returns `True` for known user.

4. **Add Session Middleware** COMPLETED
   - In `app/main.py`, add `SessionMiddleware` from `starlette.middleware.sessions` with secret key and file path. DONE
   - *AC*: Starting the app (`uvicorn app.main:app --reload`) sets a session cookie on login.

5. **Update Config**: COMPLETED
   - Add `SESSION_SECRET_KEY`, `SESSION_MAX_AGE_DAYS`, and `SESSION_FILE_PATH` to `app/lib/config.py`.
   - *AC*: Reading the environment variables via dotenv in `app/lib/config.py` returns non‑empty values.

6. **Create Auth Router**
   - File: `app/api/auth.py` with endpoints: PARTIALLY IMPLEMENTED
        * `POST /api/auth/login`
        * `POST /api/auth/register` DONE
        * `POST /api/auth/logout`
        * Add success confirmation flash messages. DONE
   - *AC*: Login returns 200 and sets a cookie; registration redirects to `/login` and creates a new user; logout clears the cookie.

7. **Create User Helper Methods**
   - In `app/models/legacy.py`, add `async def find_by_username_or_email(cls, field)` and `async def find_by_remember_token(cls, token)`.
   - *AC*: Querying by username/email returns correct `User` instance.

8. **Add Current User Dependency**
   - File: `app/lib/auth.py` with `get_current_user(request)`.
   - *AC*: Calling the function with a request containing a valid session returns the corresponding `User` instance; an invalid session raises `HTTPException(401)`.

9. **Include Auth Router**
   - In `app/main.py`, `app.include_router(auth.router)`.
   - *AC*: Accessing `/api/auth/login` via FastAPI’s TestClient succeeds.

10. **Run Basic Tests**
    - Use FastAPI's `TestClient` to test login, register, logout.
    - *AC*: All tests pass and session cookie is persisted across requests.

---

## Acceptance Criteria Summary

- Branch creation verified.
- Dependencies installed and listed.
- Security utilities produce correct hash/verify results.
- Session middleware correctly sets and clears cookies.
- Config reads env variables.
- Auth endpoints perform expected actions and redirect appropriately.
- Helper methods locate users as intended.
- Current user dependency works with session cookie.
- Tests confirm login flow.

---

### Next Step
Implement the code according to the plan and commit changes to the `implement_auth` branch.
