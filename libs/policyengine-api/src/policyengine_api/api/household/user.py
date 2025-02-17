from typing import Annotated, Any, Callable, Tuple
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session
from policyengine_api.fastapi.database import SessionGeneratorFactory
from policyengine_api.fastapi.auth import JWTDecoder
import logging

# Use standard python logging
LOG = logging.getLogger(__name__)

# https://fastapi.tiangolo.com/tutorial/sql-databases/#update-the-app-with-multiple-models
# Reduce duplication by defining request/reponse models in terms of database models.


# SQLModel models
class UserBase(SQLModel):
    username: str
    pass


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    auth0_sub: str


# Request/Response Models
class UserPublic(UserBase):
    id: int
    pass


class UserCreate(UserBase):
    auth0_sub: str
    pass


class UserPrivate(User):
    pass


class AuthorizedUser(BaseModel):
    user: User
    authorized: bool


AuthType = Callable[[HTTPAuthorizationCredentials | None], Any]


def _get_user(id: int, session: Session) -> User:
    user = session.get(User, id)
    if user == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return user


# If you don't want to hard code the implementation of all dependencies in the router
# (which means the app can't change them) the only way I found that works is this
# at least for the security dependencies if you use app.override_dependencies it
# looses the security annotation information and doesn't generate the client properly.
def create_router(
    session_dependency: SessionGeneratorFactory,
    optional_auth: AuthType,
    auth: AuthType,
) -> APIRouter:
    router = APIRouter()

    # Replace this with whatever authorization scheme you prefer
    # Currently verifies the bearer token is the same user as the
    # user row being accessed.
    class AuthUser:
        """
        Authenticate the currently logged in user's bearer token against
        the user row being accessed to determine if the bearer owns the row
        or not
        """

        def __init__(self, auto_error=True):
            self.auto_error = auto_error

        def _check(self, user: User, token: dict[str, str] | None):
            if token is None:
                LOG.info("No auth token provided")
                return False
            sub = token["sub"]
            if user.auth0_sub != sub:
                LOG.info(
                    f"auth sub {sub} cannot access user {user.id}, {user.auth0_sub}"
                )
                return False
            return True

        async def __call__(
            self,
            id: int,
            session: Annotated[Session, Depends(session_dependency)],
            token=Security(optional_auth),
        ) -> AuthorizedUser:
            user = _get_user(id, session)
            authorized = self._check(user, token)
            if not (authorized) and self.auto_error:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
            return AuthorizedUser(user=user, authorized=authorized)

    auth_user = AuthUser(auto_error=True)
    auth_user_optional = AuthUser(auto_error=False)

    @router.post("/user")
    def create_user(
        user_create: UserCreate,
        session: Annotated[Session, Depends(session_dependency)],
        token=Security(auth),
    ) -> UserPrivate:
        if user_create.auth0_sub != token["sub"]:
            LOG.info(
                f"User {token['sub']} attempted to create a record for {user_create.auth0_sub}. Rejecting."
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        user = User.model_validate(user_create)
        session.add(user)
        session.commit()
        session.refresh(user)
        return UserPrivate.model_validate(user)

    @router.get("/user/{id}")
    def get_user(
        authUser: Annotated[AuthorizedUser, Depends(auth_user_optional)]
    ) -> UserPublic | UserPrivate:
        # model_validate will automatically convert the data in the
        # database model for a full row into just the fields defined in the
        # target model.
        if authUser.authorized:
            return UserPrivate.model_validate(authUser.user)
        return UserPublic.model_validate(authUser.user)

    @router.delete("/user/{id}")
    def delete_user(
        session: Annotated[Session, Depends(session_dependency)],
        authUser: Annotated[AuthorizedUser, Depends(auth_user)],
    ) -> None:
        session.delete(authUser.user)
        session.commit()

    return router
