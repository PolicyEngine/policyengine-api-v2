# Database setup

## Quick start

Reset and initialize the database (WARNING: Drops all tables!):

```bash
make init-db
```

Or use the alias:

```bash
make reset-db
```

## What it does

The `make init-db` command:

1. **Drops existing API tables** - Removes user/report tables if they exist (to avoid foreign key conflicts)
2. **Resets core tables** - Uses `policyengine.py` to drop and recreate all core tables
3. **Registers UK model** - Adds PolicyEngine UK model version and parameters
4. **Creates API tables** - Adds user, report, and association tables
5. **Creates anonymous user** - Ensures anonymous user exists for development

## What gets created

### Core tables (from `policyengine.py`):
- `models` - PolicyEngine model definitions
- `model_versions` - Model version tracking
- `policies` - Policy definitions
- `simulations` - Simulation data
- `datasets` - Dataset metadata
- `versioned_datasets` - Dataset versions
- `parameters` - Parameter definitions
- `parameter_values` - Parameter value overrides
- `baseline_parameter_values` - Baseline parameter values
- `baseline_variables` - Baseline variable values
- `dynamics` - Dynamic analysis metadata
- `aggregates` - Aggregate statistics
- `aggregate_changes` - Aggregate change comparisons

### API tables (from `policyengine-api-full`):
- `users` - User accounts
- `reports` - Report metadata
- `report_elements` - Report elements (charts, markdown)
- `user_policies` - User → Policy associations
- `user_simulations` - User → Simulation associations
- `user_datasets` - User → Dataset associations
- `user_dynamics` - User → Dynamic associations
- `user_reports` - User → Report associations

## For production/migration

If you have an existing database and just want to add the API tables (without resetting everything):

```bash
cd projects/policyengine-api-full
python scripts/migrate_add_api_tables.py
```

This will:
- Create API tables only
- Not modify existing data
- Be idempotent (safe to run multiple times)

## Manual setup

If you prefer to use the original policyengine.py initialization:

```python
from policyengine.database import Database
from policyengine.models.policyengine_uk import policyengine_uk_latest_version
from policyengine.utils.datasets import create_uk_dataset

# Load the dataset
uk_dataset = create_uk_dataset()

database = Database("postgresql://postgres:postgres@127.0.0.1:54322/postgres")

# Reset core tables
database.reset()

# Register model version
database.register_model_version(policyengine_uk_latest_version)

# Add API tables
from policyengine_api_full.database import create_api_tables
create_api_tables()
```

## Environment variables

The database URL can be customized via environment variable:

```bash
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
make init-db
```

Default: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`

## Troubleshooting

### Foreign key conflicts

If you get foreign key errors, it means API tables already exist. The init script handles this automatically by dropping them first.

### Tables already exist

The script is idempotent - it's safe to run multiple times. It will drop and recreate everything.

### Anonymous user already exists

This is expected and safe. The script checks before creating.
