"""
Test database migration and table creation.
"""

import pytest
from sqlmodel import Session, select, create_engine
from policyengine.database import Database
from policyengine_api_full.database import create_api_tables
from policyengine_api_full.models import (
    UserTable,
    ReportTable,
    ReportElementTable,
    UserPolicyTable,
    UserDatasetTable,
    UserSimulationTable,
    UserDynamicTable,
    UserReportTable,
)


@pytest.fixture
def test_database_url():
    """Use a test database URL."""
    return "sqlite:///:memory:"


@pytest.fixture
def database(test_database_url):
    """Create a test database instance."""
    db = Database(test_database_url)
    db.create_tables()  # Create core tables
    yield db
    db.drop_tables()


def test_create_api_tables(database):
    """Test that API tables can be created."""
    # Create API tables
    create_api_tables()

    # Verify tables exist by trying to query them
    with Session(database.engine) as session:
        # Should not raise an error
        session.exec(select(UserTable)).all()
        session.exec(select(ReportTable)).all()
        session.exec(select(ReportElementTable)).all()
        session.exec(select(UserPolicyTable)).all()
        session.exec(select(UserDatasetTable)).all()
        session.exec(select(UserSimulationTable)).all()
        session.exec(select(UserDynamicTable)).all()
        session.exec(select(UserReportTable)).all()


def test_create_user(database):
    """Test creating a user."""
    create_api_tables()

    with Session(database.engine) as session:
        user = UserTable(
            username="test_user",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            current_model_id="policyengine_uk"
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Verify user was created
        assert user.id is not None
        assert user.username == "test_user"


def test_create_report(database):
    """Test creating a report."""
    create_api_tables()

    with Session(database.engine) as session:
        report = ReportTable(
            label="Test Report"
        )
        session.add(report)
        session.commit()
        session.refresh(report)

        # Verify report was created
        assert report.id is not None
        assert report.label == "Test Report"


def test_user_policy_association(database):
    """Test user-policy association table."""
    from policyengine.database import PolicyTable
    create_api_tables()

    with Session(database.engine) as session:
        # Create a user
        user = UserTable(
            username="test_user",
            current_model_id="policyengine_uk"
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create a policy
        policy = PolicyTable(
            name="Test Policy",
            description="Test"
        )
        session.add(policy)
        session.commit()
        session.refresh(policy)

        # Create association
        user_policy = UserPolicyTable(
            user_id=user.id,
            policy_id=policy.id,
            custom_name="My Custom Policy"
        )
        session.add(user_policy)
        session.commit()
        session.refresh(user_policy)

        # Verify association
        assert user_policy.id is not None
        assert user_policy.user_id == user.id
        assert user_policy.policy_id == policy.id
        assert user_policy.custom_name == "My Custom Policy"


def test_migration_idempotent(database):
    """Test that running migration multiple times is safe."""
    # Run migration twice
    create_api_tables()
    create_api_tables()

    # Should not raise an error
    with Session(database.engine) as session:
        session.exec(select(UserTable)).all()


def test_anonymous_user_creation(database):
    """Test anonymous user creation."""
    create_api_tables()

    with Session(database.engine) as session:
        # Check if anonymous user exists
        stmt = select(UserTable).where(UserTable.id == "anonymous")
        existing = session.exec(stmt).first()

        if not existing:
            # Create anonymous user
            anonymous_user = UserTable(
                id="anonymous",
                username="anonymous",
                first_name="Anonymous",
                last_name="User",
                email=None,
                current_model_id="policyengine_uk",
            )
            session.add(anonymous_user)
            session.commit()

        # Verify anonymous user exists
        stmt = select(UserTable).where(UserTable.id == "anonymous")
        user = session.exec(stmt).first()
        assert user is not None
        assert user.username == "anonymous"
