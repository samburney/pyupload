from fastapi import Request

from app.lib.security import authenticated_user_id
from app.models.users import User, UserPydantic

class SessionAuthHandler:
    def __init__(self, secret_key: str = ""):
        """Initialize the session authentication handler."""
        self.request: None | Request = None # Placeholder for Request object
        self.secret_key = secret_key
        self.user_id = None

    async def get_current_user(self, request: Request) -> None | UserPydantic:
        """Dependency to get the current authenticated user from the session."""
        self.request = request

        # Validate user session
        if "user" in self.request.session:
            session_encoded = self.request.session["user"]
            user_id = authenticated_user_id(
                session_value=session_encoded,
                secret_key=self.secret_key,
            )

            # User logged in
            if user_id is not None:
                user = await User.get_or_none(id=user_id)
                if user:
                    return await UserPydantic.from_orm(user)
                
            # Anonymous user
            else:
                return UserPydantic.anonymous_user()
