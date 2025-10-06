"""Create a dev test user for local development."""
from policyengine_api_full.models import UserTable
from policyengine_api_full.database import get_session


def create_dev_user():
    """Create a dev test user if it doesn't exist."""
    with next(get_session()) as db:
        # Check if dev user already exists
        from sqlmodel import select

        existing = db.exec(
            select(UserTable).where(UserTable.username == "dev_test")
        ).first()

        if existing:
            print(f"Dev user already exists: {existing.id}")
        else:
            # Create new dev user
            dev_user = UserTable(
                username="dev_test",
                first_name="Dev",
                last_name="User",
                email="dev@policyengine.org",
            )

            db.add(dev_user)
            db.commit()
            db.refresh(dev_user)

            print(f"Created dev user: {dev_user.id}")

        # Check if anonymous user exists
        existing_anon = db.exec(
            select(UserTable).where(UserTable.id == "anonymous")
        ).first()

        if existing_anon:
            print(f"Anonymous user already exists: {existing_anon.id}")
        else:
            # Create anonymous user
            anon_user = UserTable(
                id="anonymous",
                username="anonymous",
                first_name="Anonymous",
                last_name="User",
                email="anonymous@policyengine.org",
            )

            db.add(anon_user)
            db.commit()
            db.refresh(anon_user)

            print(f"Created anonymous user: {anon_user.id}")


if __name__ == "__main__":
    create_dev_user()