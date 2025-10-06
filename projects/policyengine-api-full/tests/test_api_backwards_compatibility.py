"""
Test backwards compatibility - ensure existing policyengine.py functionality still works.
"""

import pytest
from policyengine.database import Database
from policyengine.models import Policy, Simulation, Dataset
from sqlmodel import Session, select


@pytest.fixture
def test_database_url():
    """Use a test database URL."""
    return "sqlite:///:memory:"


@pytest.fixture
def database(test_database_url):
    """Create a test database instance."""
    db = Database(test_database_url)
    db.create_tables()
    yield db
    db.drop_tables()


def test_core_database_still_works(database):
    """Test that core policyengine.py database functionality is unchanged."""
    # Should be able to create policies without user associations
    policy = Policy(
        name="Test Policy",
        description="A test policy",
        parameter_values=[]
    )

    database.set(policy)

    # Verify policy was saved
    with Session(database.engine) as session:
        from policyengine.database import PolicyTable
        stmt = select(PolicyTable).where(PolicyTable.id == policy.id)
        saved_policy = session.exec(stmt).first()
        assert saved_policy is not None
        assert saved_policy.name == "Test Policy"


def test_no_user_fields_on_core_tables(database):
    """Verify that core tables don't have user-specific fields."""
    from policyengine.database import PolicyTable, SimulationTable, DatasetTable

    # Check that core tables don't have user_id fields
    assert not hasattr(PolicyTable, 'user_id')
    assert not hasattr(SimulationTable, 'user_id')
    assert not hasattr(DatasetTable, 'user_id')


def test_api_imports_dont_break_core(database):
    """Test that importing API models doesn't break core functionality."""
    # Import API models
    from policyengine_api_full.models import UserTable, ReportTable

    # Core functionality should still work
    policy = Policy(
        name="Test Policy After Import",
        description="Test",
        parameter_values=[]
    )

    database.set(policy)

    # Verify
    with Session(database.engine) as session:
        from policyengine.database import PolicyTable
        stmt = select(PolicyTable).where(PolicyTable.id == policy.id)
        saved = session.exec(stmt).first()
        assert saved is not None


def test_database_reset_works(database):
    """Test that database.reset() still works correctly."""
    # Create some data
    policy = Policy(name="Test", description="Test", parameter_values=[])
    database.set(policy)

    # Reset database
    database.reset()

    # Verify tables are recreated (empty)
    with Session(database.engine) as session:
        from policyengine.database import PolicyTable
        policies = session.exec(select(PolicyTable)).all()
        assert len(policies) == 0


def test_core_models_no_user_dependencies(database):
    """Ensure core models don't depend on User or Report models."""
    from policyengine import models

    # Core models should not include User or Report
    assert not hasattr(models, 'User')
    assert not hasattr(models, 'Report')
    assert not hasattr(models, 'ReportElement')

    # But should have core models
    assert hasattr(models, 'Policy')
    assert hasattr(models, 'Simulation')
    assert hasattr(models, 'Dataset')
    assert hasattr(models, 'Aggregate')
    assert hasattr(models, 'AggregateChange')
