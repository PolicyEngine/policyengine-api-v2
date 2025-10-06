# Database migration: API-specific tables

## Overview

User and report functionality has been moved from `policyengine.py` to the API layer (`policyengine-api-v2`). This makes `policyengine.py` lighter and focused purely on simulation/policy modelling.

## What changed

### Removed from `policyengine.py`:
- `User`, `Report`, `ReportElement` models
- `UserTable`, `ReportTable`, `ReportElementTable` database tables
- `UserPolicyTable`, `UserDatasetTable`, `UserSimulationTable`, `UserDynamicTable`, `UserReportTable` association tables

### Added to `policyengine-api-v2`:
- Local implementations of all user/report models and tables in `policyengine_api_full/models/`
- API-specific tables are now separate additions to the database schema

## Key principles

1. **No breaking changes**: Existing `policyengine.py` functionality is unchanged
2. **Additive only**: API tables are additions, not modifications to existing tables
3. **No user fields on core tables**: Core tables (policies, simulations, datasets) don't have direct user_id fields
4. **Association tables**: User relationships are managed through separate association tables (user_policies, user_simulations, etc.)

## Migration guide

### For existing databases

Run the migration script to add API-specific tables:

```bash
cd policyengine-api-v2/projects/policyengine-api-full
python scripts/migrate_add_api_tables.py
```

This will:
- Create user, report, and association tables
- Create an anonymous user (id: "anonymous")
- Not modify any existing tables or data

### For new databases

Use the standard initialization script:

```bash
cd policyengine-api-v2/projects/policyengine-api-full
python scripts/init_db_simple.py --reset  # WARNING: Drops all tables!
```

Or use the original policyengine.py initialization and then add API tables:

```python
from policyengine.database import Database
from policyengine.models.policyengine_uk import policyengine_uk_latest_version
from policyengine.utils.datasets import create_uk_dataset

# Create database
database = Database("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
database.reset()  # Drop and recreate all core tables
database.register_model_version(policyengine_uk_latest_version)

# Then add API tables
from policyengine_api_full.database import create_api_tables
create_api_tables()
```

## API startup behavior

The API automatically creates tables on startup:
1. Creates core tables (idempotent via SQLModel)
2. Creates API-specific tables (users, reports, associations)
3. Ensures anonymous user exists

No manual intervention needed when starting the API.

## Testing

Run the test suite to verify migration and backwards compatibility:

```bash
cd policyengine-api-v2/projects/policyengine-api-full
python -m pytest tests/test_database_migration.py tests/test_api_backwards_compatibility.py -v
```

Tests verify:
- API tables can be created
- User/report functionality works
- Association tables work correctly
- Migration is idempotent (safe to run multiple times)
- Core policyengine.py functionality unchanged
- No user fields on core tables
- Core models don't depend on User/Report

## Backwards compatibility

✅ **Guaranteed compatible:**
- All existing `policyengine.py` code continues to work
- `database.reset()` still works
- Core models (Policy, Simulation, Dataset, Aggregate) unchanged
- No dependencies on user/report models in core code

✅ **What's preserved:**
- All existing table schemas
- All existing model APIs
- All existing database operations

## Architecture

```
policyengine.py (core)
├── Models: Policy, Simulation, Dataset, Aggregate, etc.
└── Tables: policies, simulations, datasets, aggregates, etc.

policyengine-api-v2 (API layer)
├── Models: User, Report, ReportElement, UserPolicy*, etc.
└── Tables: users, reports, report_elements, user_policies*, etc.
    (* = association tables)
```

Association tables link users to core entities:
- `user_policies`: Links users to policies
- `user_simulations`: Links users to simulations
- `user_datasets`: Links users to datasets
- `user_dynamics`: Links users to dynamics
- `user_reports`: Links users to reports
