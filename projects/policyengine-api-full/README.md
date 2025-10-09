# policyengine-api-full

Full PolicyEngine API with all features.

## Setup

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

### Required Environment Variables

- `DATABASE_URL`: PostgreSQL connection string
- `ANTHROPIC_API_KEY`: Required for AI-powered report element features

### AI Features

The API includes AI-powered features for report elements:

1. **AI Report Element Creation** (`POST /report-elements/ai`):
   - Parses natural language prompts to create data aggregates
   - Automatically determines whether to create comparisons or individual metrics
   - Understands PolicyEngine variable names and creates appropriate queries

2. **AI Data Processing** (`POST /report-elements/ai/process`):
   - Processes report element data to generate visualisations or insights
   - Can create Plotly charts or markdown summaries based on prompts
   - Analyses data patterns and provides insights

### Running the API

```bash
# Install dependencies with uv
uv pip install -e .

# Run the API
uvicorn policyengine_api_full.main:app --reload
```

### Testing

```bash
pytest
```