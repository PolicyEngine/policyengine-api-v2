"""AI-powered report elements generation and processing."""

import json
import os
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from fastapi import HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from policyengine.database import AggregateTable, AggregateChangeTable, SimulationTable
from policyengine.models import Aggregate, AggregateChange

from policyengine_api_full.models import ReportElementTable
from policyengine_api_full.database import get_session, database

# Set up logging
logger = logging.getLogger(__name__)


def log_ai_debug(prompt: str, response: Dict[str, Any], endpoint: str = "ai"):
    """Log AI interactions to a markdown file for debugging."""
    if not os.getenv("DEBUG_AI", "").lower() in ("true", "1", "yes"):
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = Path("ai_debug_logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"{endpoint}_{timestamp}.md"

    with open(log_file, "w") as f:
        f.write(f"# AI Debug Log - {endpoint}\n\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write("## Prompt\n\n```\n")
        f.write(str(prompt))
        f.write("\n```\n\n")
        f.write("## Response\n\n```json\n")
        f.write(json.dumps(response, indent=2))
        f.write("\n```\n")

    logger.info(f"AI debug log written to {log_file}")


class AIReportElementRequest(BaseModel):
    """Request model for AI-generated report elements."""
    prompt: str
    report_id: str
    simulation_ids: List[str]


class AIReportElementResponse(BaseModel):
    """Response model for AI-generated report elements."""
    report_element: ReportElementTable
    aggregates: List[Dict[str, Any]]
    aggregate_changes: List[Dict[str, Any]]
    explanation: str


class AIProcessRequest(BaseModel):
    """Request model for AI processing of report element data."""
    prompt: str
    context: Dict[str, Any]
    element_id: str


class AIProcessResponse(BaseModel):
    """Response model for AI processing."""
    type: str  # "markdown" or "plotly"
    content: Any


def get_anthropic_client():
    """Get Anthropic client with API key from environment."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API key not configured. Please set ANTHROPIC_API_KEY environment variable."
        )
    return anthropic.Anthropic(api_key=api_key)


def parse_data_request(prompt: str, simulation_ids: List[str]) -> Dict[str, Any]:
    """Use Claude to parse a natural language prompt into data requests."""
    client = get_anthropic_client()

    system_prompt = """You are an expert at PolicyEngine's data model. You need to parse user requests into specific data aggregates.

CRITICAL: Return ONLY valid JSON. Do not wrap your response in markdown code blocks or any other formatting. Your entire response must be parseable as JSON.

PolicyEngine tracks economic simulations with these key variable categories:

INCOME VARIABLES:
- household_net_income: Total household income after taxes and benefits
- employment_income: Income from employment
- self_employment_income: Income from self-employment
- pension_income: Pension income
- investment_income: Investment income
- rental_income: Rental income
- total_income: Total income before taxes

TAX VARIABLES:
- income_tax: Income tax liability
- national_insurance: National Insurance contributions (UK)
- council_tax: Council tax (UK)
- payroll_tax: Payroll tax (US)
- state_income_tax: State income tax (US)
- federal_income_tax: Federal income tax (US)
- gov_tax: Total government tax revenue (UK)

BENEFIT VARIABLES:
- gov_balance: Government defifcit/surplus (UK)
- gov_spending: Total government spending (UK)
- universal_credit: Universal Credit (UK)
- child_benefit: Child benefit (UK)
- housing_benefit: Housing benefit (UK)
- pension_credit: Pension credit (UK)
- snap: Food stamps (US)
- tanf: Temporary assistance (US)
- eitc: Earned income tax credit (US)
- ctc: Child tax credit (US)s

HOUSEHOLD CHARACTERISTICS:
- age: Person's age

AGGREGATE FUNCTIONS:
- sum: Total across population (use for revenue, spending, total income/benefits)
- mean: Average per household/person (use for typical amounts, average income)
- count: Number of households/people (use for counting beneficiaries, taxpayers)

ENTITIES (when to use each):
- null/omit: Let the system infer from the variable name (preferred in most cases)
- "household": Force household-level aggregation (for household_net_income, household_weight)
- "person": Force person-level aggregation (for age, employment_status, individual benefits)

FILTER FIELDS (all optional - use to subset data):
- filter_variable_name: Variable to filter on (REQUIRED if using any filter)
- filter_variable_value: Exact value match
- filter_variable_geq: Greater than or equal to this value (use for numeric ranges)
- filter_variable_leq: Less than or equal to this value (use for numeric ranges)
- filter_variable_quantile_leq: Less than or equal to this quantile (fraction)
- filter_variable_quantile_geq: Greater than or equal to this quantile (fraction)

IMPORTANT FILTER RULES:
- Use filter_variable_value for exact matches
- Use filter_variable_geq/leq for numeric ranges
- When asked for decile or other related analysis, remember you can use the quantile leq and geq fields to make the rows
- You can combine geq AND leq for bounded ranges (e.g., age 18-65)
- Do NOT use filter_variable_value with geq/leq on the same variable

IMPORTANT RULES:
- For "count" function, variable_name should typically be a weight variable (household_weight, person_weight)
- For income/tax/benefit totals, use "sum" with the appropriate variable
- For average amounts per household/person, use "mean"
- Filters can be combined (all conditions must be true)
- Entity can usually be left null - the system will infer it correctly

When users ask for comparisons between simulations, create aggregate_changes.
When users ask for metrics from individual simulations, create aggregates.

Your response must be valid JSON starting with { and ending with }. Do not include any text before or after the JSON. Do not use markdown formatting.

Response format:
{
  "type": "aggregates" or "aggregate_changes",
  "data": [array of aggregate or aggregate_change objects],
  "title": "Short title (max 7 words)",
  "explanation": "Brief explanation of what will be calculated"
}

For aggregates, each object should have:
- entity: null (preferred) or "household"/"person" if you need to override
- variable_name: The variable to aggregate
- aggregate_function: "sum", "mean", or "count"
- simulation_id: The simulation ID (from the provided list)
- year: 2026 (default) or specific year if mentioned
- filter_variable_name: Optional - variable to filter on
- filter_variable_value: Optional - exact value to match
- filter_variable_geq: Optional - minimum value (inclusive)
- filter_variable_leq: Optional - maximum value (inclusive)
- filter_variable_quantile_geq: Optional - minimum quantile (fraction 0-1)
- filter_variable_quantile_leq: Optional - maximum quantile (fraction 0-1)

For aggregate_changes, same fields but with:
- baseline_simulation_id: First simulation ID (instead of simulation_id)
- comparison_simulation_id: Other simulation ID"""

    user_message = f"""Parse this request into data aggregates:

Request: "{prompt}"

Available simulations: {json.dumps(simulation_ids)}

If the request mentions comparing, differences, changes, or impacts between simulations, create aggregate_changes.
If the request asks for specific metrics from each simulation separately, create aggregates.
Include relevant variables based on the request - don't just include one variable if the user asks about a broad topic.

For the title field: Maximum 7 words in sentence case (e.g., "Tax impact by income decile").
For the explanation field: Clear description in sentence case of what will be calculated.

Return only the JSON object, starting with {{ and ending with }}."""

    try:
        response = client.beta.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            temperature=0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        # Get raw response text (prefilled with "{")
        raw_response = "{" + response.content[0].text
        logger.info(f"[PARSE_DATA] Raw LLM response: {raw_response[:500]}")

        # Parse the JSON response
        result = json.loads(raw_response)
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[PARSE_DATA] JSON parsing failed. Raw response: {raw_response if 'raw_response' in locals() else 'N/A'}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse LLM response as JSON: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PARSE_DATA] Unexpected error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate data request: {str(e)}"
        )


def create_ai_report_element(
    request: AIReportElementRequest,
    session: Session = Depends(get_session),
) -> AIReportElementResponse:
    """Create a report element using AI to generate data requests."""

    logger.info(f"[CREATE_AI] Starting AI report element creation")
    logger.info(f"[CREATE_AI] Request: prompt={request.prompt[:100]}..., report_id={request.report_id}, simulation_ids={request.simulation_ids}")

    try:
        # Parse the prompt to determine what data to create
        logger.info(f"[CREATE_AI] Calling AI to parse data request...")
        parsed = parse_data_request(request.prompt, request.simulation_ids)
        logger.info(f"[CREATE_AI] AI parsing successful: type={parsed.get('type')}, data_count={len(parsed.get('data', []))}")
    except Exception as e:
        logger.error(f"[CREATE_AI] FAILED during AI parsing: {type(e).__name__}: {str(e)}")
        raise

    # Log the parsed response with filter information
    log_ai_debug(
        prompt=request.prompt,
        response=parsed,
        endpoint="create_ai_report_element"
    )

    # Debug log filter usage
    logger.info(f"AI parsed {parsed['type']} with {len(parsed.get('data', []))} items")
    for idx, item in enumerate(parsed.get("data", [])):
        filter_fields = {k: v for k, v in item.items() if k.startswith("filter_")}
        if filter_fields:
            logger.info(f"Item {idx} has filters: {filter_fields}")

    # Check if any data was generated
    if not parsed.get("data") or len(parsed["data"]) == 0:
        logger.warning(f"[CREATE_AI] No data generated from AI parsing")
        raise HTTPException(
            status_code=400,
            detail="Could not generate any data from your request. Please be more specific about what metrics you want to analyse."
        )

    # Use title from AI response (AI should generate in sentence case)
    title = parsed.get("title", parsed["explanation"][:50])
    logger.info(f"[CREATE_AI] Creating report element with title: {title}")

    try:
        # Create the report element only after we know we have data
        report_element = ReportElementTable(
            label=title,
            type="data",
            report_id=request.report_id,
            data_table="aggregate_changes" if parsed["type"] == "aggregate_changes" else "aggregates",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(report_element)
        session.commit()
        session.refresh(report_element)
        logger.info(f"[CREATE_AI] Report element created with id: {report_element.id}")
    except Exception as e:
        logger.error(f"[CREATE_AI] FAILED creating report element: {type(e).__name__}: {str(e)}")
        raise

    aggregates = []
    aggregate_changes = []

    if parsed["type"] == "aggregate_changes":
        logger.info(f"[CREATE_AI] Processing {len(parsed['data'])} aggregate changes")
        # Process aggregate changes
        aggregate_change_models = []

        for idx, change_data in enumerate(parsed["data"]):
            try:
                logger.info(f"[CREATE_AI] Processing aggregate change {idx + 1}/{len(parsed['data'])}: variable={change_data.get('variable_name')}, baseline={change_data.get('baseline_simulation_id')}, comparison={change_data.get('comparison_simulation_id')}")

                # Fetch simulations
                baseline_sim = session.get(SimulationTable, change_data["baseline_simulation_id"])
                comparison_sim = session.get(SimulationTable, change_data["comparison_simulation_id"])

                if not baseline_sim:
                    logger.warning(f"[CREATE_AI] Baseline simulation not found: {change_data['baseline_simulation_id']}")
                    continue
                if not comparison_sim:
                    logger.warning(f"[CREATE_AI] Comparison simulation not found: {change_data['comparison_simulation_id']}")
                    continue

                logger.info(f"[CREATE_AI] Simulations fetched, converting to models...")

                # Convert to models
                db = database
                baseline_model = baseline_sim.convert_to_model(db)
                comparison_model = comparison_sim.convert_to_model(db)

                logger.info(f"[CREATE_AI] Creating AggregateChange model...")

                # Create AggregateChange model
                agg_change = AggregateChange(
                    baseline_simulation=baseline_model,
                    comparison_simulation=comparison_model,
                    entity=change_data.get("entity"),  # Let it be None to infer
                    variable_name=change_data["variable_name"],
                    aggregate_function=change_data["aggregate_function"],
                    year=change_data.get("year", 2026),
                    filter_variable_name=change_data.get("filter_variable_name"),
                    filter_variable_value=change_data.get("filter_variable_value"),
                    filter_variable_leq=change_data.get("filter_variable_leq"),
                    filter_variable_geq=change_data.get("filter_variable_geq"),
                    reportelement_id=report_element.id
                )
                aggregate_change_models.append(agg_change)
                logger.info(f"[CREATE_AI] AggregateChange model created successfully")

            except Exception as e:
                logger.error(f"[CREATE_AI] FAILED creating aggregate change {idx + 1}: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[CREATE_AI] Traceback: {traceback.format_exc()}")
                # Continue to next item instead of failing completely
                continue

        # Run computations
        if aggregate_change_models:
            try:
                logger.info(f"[CREATE_AI] Running computations for {len(aggregate_change_models)} aggregate change models...")
                computed_models = AggregateChange.run(aggregate_change_models)
                logger.info(f"[CREATE_AI] Computations completed, got {len(computed_models)} results")
            except Exception as e:
                logger.error(f"[CREATE_AI] FAILED during aggregate change computation: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[CREATE_AI] Traceback: {traceback.format_exc()}")
                raise

            # Save to database
            try:
                logger.info(f"[CREATE_AI] Saving {len(computed_models)} aggregate changes to database...")
                for idx, agg_model in enumerate(computed_models):
                    agg_table = AggregateChangeTable(
                        id=agg_model.id,
                        baseline_simulation_id=agg_model.baseline_simulation.id,
                        comparison_simulation_id=agg_model.comparison_simulation.id,
                        entity=agg_model.entity,
                        variable_name=agg_model.variable_name,
                        year=agg_model.year,
                        filter_variable_name=agg_model.filter_variable_name,
                        filter_variable_value=agg_model.filter_variable_value,
                        filter_variable_leq=agg_model.filter_variable_leq,
                        filter_variable_geq=agg_model.filter_variable_geq,
                        aggregate_function=agg_model.aggregate_function,
                        reportelement_id=report_element.id,
                        baseline_value=agg_model.baseline_value,
                        comparison_value=agg_model.comparison_value,
                        change=agg_model.change,
                        relative_change=agg_model.relative_change
                    )
                    session.add(agg_table)

                    aggregate_changes.append({
                        "baseline_simulation_id": agg_table.baseline_simulation_id,
                        "comparison_simulation_id": agg_table.comparison_simulation_id,
                        "variable_name": agg_table.variable_name,
                        "aggregate_function": agg_table.aggregate_function,
                        "baseline_value": agg_table.baseline_value,
                        "comparison_value": agg_table.comparison_value,
                        "change": agg_table.change,
                        "relative_change": agg_table.relative_change,
                    })
                logger.info(f"[CREATE_AI] Aggregate changes saved successfully")
            except Exception as e:
                logger.error(f"[CREATE_AI] FAILED saving aggregate changes to database: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[CREATE_AI] Traceback: {traceback.format_exc()}")
                raise

    else:
        logger.info(f"[CREATE_AI] Processing {len(parsed['data'])} aggregates")
        # Process regular aggregates
        aggregate_models = []

        for idx, agg_data in enumerate(parsed["data"]):
            try:
                logger.info(f"[CREATE_AI] Processing aggregate {idx + 1}/{len(parsed['data'])}: variable={agg_data.get('variable_name')}, simulation={agg_data.get('simulation_id')}")

                # Fetch simulation
                sim = session.get(SimulationTable, agg_data["simulation_id"])
                if not sim:
                    logger.warning(f"[CREATE_AI] Simulation not found: {agg_data['simulation_id']}")
                    continue

                logger.info(f"[CREATE_AI] Simulation fetched, converting to model...")

                # Convert to model
                db = database
                sim_model = sim.convert_to_model(db)

                logger.info(f"[CREATE_AI] Creating Aggregate model...")

                # Create Aggregate model
                agg = Aggregate(
                    simulation=sim_model,
                    entity=agg_data.get("entity"),  # Let it be None to infer
                    variable_name=agg_data["variable_name"],
                    aggregate_function=agg_data["aggregate_function"],
                    year=agg_data.get("year", 2026),
                    filter_variable_name=agg_data.get("filter_variable_name"),
                    filter_variable_value=agg_data.get("filter_variable_value"),
                    filter_variable_leq=agg_data.get("filter_variable_leq"),
                    filter_variable_geq=agg_data.get("filter_variable_geq"),
                    reportelement_id=report_element.id
                )
                aggregate_models.append(agg)
                logger.info(f"[CREATE_AI] Aggregate model created successfully")

            except Exception as e:
                logger.error(f"[CREATE_AI] FAILED creating aggregate {idx + 1}: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[CREATE_AI] Traceback: {traceback.format_exc()}")
                # Continue to next item instead of failing completely
                continue

        # Run computations
        if aggregate_models:
            try:
                logger.info(f"[CREATE_AI] Running computations for {len(aggregate_models)} aggregate models...")
                computed_models = Aggregate.run(aggregate_models)
                logger.info(f"[CREATE_AI] Computations completed, got {len(computed_models)} results")
            except Exception as e:
                logger.error(f"[CREATE_AI] FAILED during aggregate computation: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[CREATE_AI] Traceback: {traceback.format_exc()}")
                raise

            # Save to database
            try:
                logger.info(f"[CREATE_AI] Saving {len(computed_models)} aggregates to database...")
                for idx, agg_model in enumerate(computed_models):
                    agg_table = AggregateTable(
                        id=agg_model.id,
                        simulation_id=agg_model.simulation.id,
                        entity=agg_model.entity,
                        variable_name=agg_model.variable_name,
                        year=agg_model.year,
                        filter_variable_name=agg_model.filter_variable_name,
                        filter_variable_value=agg_model.filter_variable_value,
                        filter_variable_leq=agg_model.filter_variable_leq,
                        filter_variable_geq=agg_model.filter_variable_geq,
                        aggregate_function=agg_model.aggregate_function,
                        reportelement_id=report_element.id,
                        value=agg_model.value
                    )
                    session.add(agg_table)

                    aggregates.append({
                        "simulation_id": agg_table.simulation_id,
                        "variable_name": agg_table.variable_name,
                        "aggregate_function": agg_table.aggregate_function,
                        "value": agg_table.value,
                    })
                logger.info(f"[CREATE_AI] Aggregates saved successfully")
            except Exception as e:
                logger.error(f"[CREATE_AI] FAILED saving aggregates to database: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[CREATE_AI] Traceback: {traceback.format_exc()}")
                raise

    # Check if we actually generated any data before committing
    if len(aggregates) == 0 and len(aggregate_changes) == 0:
        logger.error(f"[CREATE_AI] No data computed - aggregates: {len(aggregates)}, aggregate_changes: {len(aggregate_changes)}")
        # Delete the report element we created
        session.delete(report_element)
        session.commit()
        raise HTTPException(
            status_code=500,
            detail="Failed to compute any data. This might be due to simulation errors or invalid variables."
        )

    try:
        logger.info(f"[CREATE_AI] Committing changes to database...")
        session.commit()
        logger.info(f"[CREATE_AI] Database commit successful")
    except Exception as e:
        logger.error(f"[CREATE_AI] FAILED during database commit: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"[CREATE_AI] Traceback: {traceback.format_exc()}")
        raise

    logger.info(f"[CREATE_AI] Successfully created AI report element with {len(aggregates)} aggregates and {len(aggregate_changes)} aggregate changes")

    return AIReportElementResponse(
        report_element=report_element,
        aggregates=aggregates,
        aggregate_changes=aggregate_changes,
        explanation=parsed["explanation"]
    )


def process_with_ai(
    request: AIProcessRequest,
    session: Session = Depends(get_session),
) -> AIProcessResponse:
    """Process report element data with AI to generate visualizations or insights."""

    # Get the report element
    report_element = session.get(ReportElementTable, request.element_id)
    if not report_element:
        raise HTTPException(status_code=404, detail="Report element not found")

    client = get_anthropic_client()

    # Prepare the data context
    context_str = json.dumps(request.context, indent=2)

    print(f"[AI PROCESS] Received context:")
    print(f"[AI PROCESS] - Simulations: {request.context.get('simulations', [])}")
    print(f"[AI PROCESS] - Aggregates count: {len(request.context.get('aggregates', []))}")
    print(f"[AI PROCESS] - Aggregate changes count: {len(request.context.get('aggregate_changes', []))}")

    # Extract theme if provided
    theme_colors = request.context.get('theme', {}).get('colors', {})
    theme_font = request.context.get('theme', {}).get('font', 'system-ui, -apple-system, sans-serif')

    system_prompt = """You are a data visualization and analysis expert for PolicyEngine.

CRITICAL: Return ONLY valid JSON. Do not wrap your response in markdown code blocks or any other formatting. Your entire response must be parseable as JSON.

When the user asks for a chart or visualization, respond with JSON in this format:
{
  "type": "plotly",
  "content": {
    "data": [Plotly data array],
    "layout": {Plotly layout object}
  }
}

When the user asks for a summary, table, or text analysis, respond with just the markdown content.

For Plotly charts, use these theme colors:
- Primary: #319795 (teal)
- Secondary: #6B7280 (gray)
- Grid: #E2E8F0
- Text: #1F2937
- Success/positive: #22C55E (green)
- Error/negative: #EF4444 (red)

Plotly chart guidelines:
- **IMPORTANT: Always set `plot_bgcolor: 'rgba(0,0,0,0)'` and `paper_bgcolor: 'rgba(0,0,0,0)'` for transparent background**
- **IMPORTANT: Always set title alignment to left with `title: { text: '...', x: 0, xanchor: 'left' }`**
- Use clean, minimal design
- Set gridcolor to #E2E8F0 for subtle grid lines
- Use the primary teal color (#319795) for main data series
- Use red/green for negative/positive values
- Set font family to match the app's design system
- Include clear titles and axis labels with sentence case
- Format currency values properly (use $, £, €)
- Make all charts responsive with autosize: true

For markdown:
- Use proper markdown formatting (headers, lists, bold, italic)
- **IMPORTANT: Use HTML table syntax (`<table>`, `<tr>`, `<td>`, `<th>`), NOT markdown pipe tables (`|---|`)**
- HTML tables render correctly while pipe tables do not
- Focus on insights and key findings
- Format numbers with appropriate units and precision
- Be concise and professional
- Do not include meta-commentary about the analysis"""

    # Add theme to user message if available
    theme_info = ""
    if theme_colors:
        theme_info = f"""
Use these specific theme colors for the chart:
- Primary: {theme_colors.get('primary', '#319795')}
- Grid lines: {theme_colors.get('grid', '#E2E8F0')}
- Text: {theme_colors.get('text', '#1F2937')}
- Background: {theme_colors.get('background', 'rgba(0,0,0,0)')} (use for plot_bgcolor and paper_bgcolor)
Font family: {theme_font}
"""

    user_message = f"""Analyze this data and create what the user requested:

User request: "{request.prompt}"

Available data context:
{context_str}

Context structure notes:
- `simulations`: Array of simulation objects with:
  - `id`: Simulation ID
  - `name`/`label`: Display name (custom name or default)
  - `policy_name`: Name of the policy used
  - `dataset_name`: Name of the dataset used
  - `dynamic_name`: Name of the dynamic if applicable
  - Use these names when creating labels, titles, and explanations
- `aggregates`: Array of aggregate calculations with variable values for each simulation
- `aggregate_changes`: Array showing differences between baseline and comparison simulations
- When creating visualizations, use policy names, dataset names, and custom names for clarity

{theme_info}

Create an appropriate visualization or analysis based on the request. Be direct and focus on the data insights.
Always use sentence case for all text output (titles, labels, descriptions).
When creating charts, use the simulation names from the context for legend labels and titles."""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        # Parse the JSON response from Claude (prefilled with "{")
        raw_response = "{" + response.content[0].text
        print(f"[AI PROCESS] Raw Claude response: {raw_response[:500]}")

        result = json.loads(raw_response)
        content_type = result["type"]
        content_data = result["content"]

        print(f"[AI PROCESS] Parsed type: {content_type}")
        print(f"[AI PROCESS] Parsed content TYPE: {type(content_data)}")
        print(f"[AI PROCESS] Parsed content preview: {str(content_data)[:200]}")

        # Store ONLY the content string in the database
        report_element.processed_output_type = content_type

        if content_type == 'markdown':
            # For markdown, content should be a string - store it directly
            if not isinstance(content_data, str):
                raise ValueError(f"Expected string for markdown content, got {type(content_data)}")
            report_element.processed_output = content_data
            print(f"[AI PROCESS] Storing markdown STRING: {content_data[:200]}")
        elif content_type == 'plotly':
            # For plotly, content is a dict - stringify it
            if not isinstance(content_data, dict):
                raise ValueError(f"Expected dict for plotly content, got {type(content_data)}")
            report_element.processed_output = json.dumps(content_data)
            print(f"[AI PROCESS] Storing plotly JSON: {report_element.processed_output[:200]}")

        # Create response object for return
        ai_response = AIProcessResponse(
            type=content_type,
            content=content_data
        )

        report_element.updated_at = datetime.now(timezone.utc)

        print(f"[AI PROCESS] BEFORE COMMIT - processed_output_type: {report_element.processed_output_type}")
        print(f"[AI PROCESS] BEFORE COMMIT - processed_output: {report_element.processed_output[:200] if report_element.processed_output else 'None'}")

        session.add(report_element)
        session.commit()
        session.refresh(report_element)

        print(f"[AI PROCESS] AFTER COMMIT - processed_output_type: {report_element.processed_output_type}")
        print(f"[AI PROCESS] AFTER COMMIT - processed_output: {report_element.processed_output[:200] if report_element.processed_output else 'None'}")

        return ai_response

    except json.JSONDecodeError as e:
        # If JSON parsing fails, create a markdown response with the raw text
        ai_response = AIProcessResponse(
            type="markdown",
            content=response.content[0].text if response else "Failed to process request"
        )

        # Use the new fields
        report_element.processed_output_type = ai_response.type
        report_element.processed_output = ai_response.content
        report_element.updated_at = datetime.now(timezone.utc)
        session.add(report_element)
        session.commit()

        return ai_response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process with AI: {str(e)}"
        )