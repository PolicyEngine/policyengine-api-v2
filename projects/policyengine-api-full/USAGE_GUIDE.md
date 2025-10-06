# Usage guide: Database initialization

## TL;DR

```bash
# From policyengine-api-v2 directory
make init-db
```

This replaces your old initialization script and does everything automatically.

## What changed

### Old way ❌
```python
from policyengine.database import Database
from policyengine.models.policyengine_uk import policyengine_uk_latest_version
from policyengine.utils.datasets import create_uk_dataset

uk_dataset = create_uk_dataset()
database = Database("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
database.reset()
database.register_model_version(policyengine_uk_latest_version)
```

### New way ✅
```bash
make init-db
```

## Why the change?

The API now has its own tables (users, reports) that need to be created alongside the core `policyengine.py` tables. The new command handles everything:

1. Drops any existing API tables (to avoid conflicts)
2. Resets core tables using `policyengine.py`
3. Registers UK model version
4. Creates API-specific tables
5. Creates anonymous user

## Available commands

```bash
make init-db    # Full reset and initialization
make reset-db   # Alias for init-db
make help       # Show all commands
```

## For production/existing databases

If you have an existing database and **don't want to reset everything**, use the migration script:

```bash
cd projects/policyengine-api-full
python scripts/migrate_add_api_tables.py
```

This only adds the new API tables without touching existing data.

## Architecture

```
Database tables:

policyengine.py (core)
├── models, model_versions
├── policies, parameters, parameter_values
├── simulations, datasets, dynamics
└── aggregates, aggregate_changes

policyengine-api-v2 (API layer - added on top)
├── users, reports, report_elements
└── user_policies, user_simulations, user_datasets, user_dynamics, user_reports
    (association tables linking users to core entities)
```

**Key principle**: API tables are pure additions. Core tables have NO user fields.

## Documentation

- `DATABASE_SETUP.md` - Detailed setup guide
- `README_MIGRATION.md` - Migration guide and architecture
- `REFACTOR_SUMMARY.md` - Complete refactoring summary

## Tests

All functionality is tested:

```bash
cd projects/policyengine-api-full
python -m pytest tests/test_database_migration.py tests/test_api_backwards_compatibility.py -v
```

**Result**: ✅ 11/11 tests pass
- Migration works
- API tables created correctly
- Backwards compatible
- No breaking changes
