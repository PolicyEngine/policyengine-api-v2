from typing import Any
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.testclient import TestClient
import pytest
from sqlmodel import SQLModel
from ...common.fixtures import createApi, engine
from policyengine_api.api.household import create_user_router
from pydantic_core import from_json
from policyengine_api.fastapi.database import create_session_dep


def auth_override(
    creds: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
):
    """
    fake auth that fails if there is no token and succeeds otherwise
    """
    if creds is None:
        raise HTTPException(status_code=403)
    print(f"Credentials are: {creds.credentials}")
    return from_json(creds.credentials)


def optional_auth_override(
    creds: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
):
    """
    same but doesn't raise an HTTPException if there is no bearer
    """
    if creds is None:
        return None
    print(f"Credentials are: {creds.credentials}")
    return from_json(creds.credentials)


@pytest.fixture
def client() -> TestClient:
    SQLModel.metadata.drop_all(bind=engine)
    SQLModel.metadata.create_all(engine)
    router = create_user_router(
        session_dependency=create_session_dep(engine),
        optional_auth=optional_auth_override,
        auth=auth_override,
    )
    api = createApi(router)
    return TestClient(api)


@pytest.fixture
def createdUser(client: TestClient) -> Any:
    response = client.post(
        "/user",
        json={"auth0_sub": "github|whatever", "username": "test_username"},
        headers={"authorization": 'Bearer {"sub":"github|whatever"}'},
    )
    return response.json()


def test_create_user(client: TestClient):
    response = client.post(
        "/user",
        json={"auth0_sub": "github|whatever", "username": "test_username"},
        headers={"authorization": 'Bearer {"sub":"github|whatever"}'},
    )
    assert response.status_code == 200
    assert response.json() == {
        "auth0_sub": "github|whatever",
        "id": 1,
        "username": "test_username",
    }


def test_create_user_no_auth(client: TestClient):
    response = client.post(
        "/user",
        json={"auth0_sub": "github|whatever", "username": "test_username"},
        headers={},
    )

    assert response.status_code == 403


def test_create_user_wrote_sub(client: TestClient):
    response = client.post(
        "/user",
        json={"auth0_sub": "github|whatever", "username": "test_username"},
        headers={"authorization": 'Bearer {"sub":"some_other_id"}'},
    )

    assert response.status_code == 403


def test_get_user_no_auth(client: TestClient, createdUser):
    response = client.get(f"/user/{createdUser['id']}")

    assert response.status_code == 200
    assert response.json() == {
        "id": createdUser["id"],
        "username": createdUser["username"],
    }


def test_get_user_by_same_user(client: TestClient, createdUser):
    response = client.get(
        f"/user/{createdUser['id']}",
        headers={
            "authorization": f'Bearer {{"sub":"{createdUser["auth0_sub"]}"}}'
        },
    )

    assert response.status_code == 200
    assert response.json() == createdUser


def test_get_user_not_exist(client: TestClient):
    response = client.get("/user/1234")
    assert response.status_code == 404


def test_delete_user(client: TestClient, createdUser):
    response = client.delete(
        f"/user/{createdUser['id']}",
        headers={
            "authorization": f'Bearer {{"sub":"{createdUser["auth0_sub"]}"}}'
        },
    )

    assert response.status_code == 200


def test_delete_user_wrong_auth(client: TestClient, createdUser):
    response = client.delete(
        f"/user/{createdUser['id']}",
        headers={"authorization": f'Bearer {{"sub":"not_right"}}'},
    )

    assert response.status_code == 403


def test_delete_user_not_exist(client: TestClient):
    response = client.delete(f"/user/12222234")

    assert response.status_code == 404
