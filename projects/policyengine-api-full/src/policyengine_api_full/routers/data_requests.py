"""
Data request parsing endpoint using LLM
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import anthropic
import json
import os
from policyengine_api_full.database import get_session
from policyengine.database import BaselineVariableTable, SimulationTable, PolicyTable, DatasetTable

router = APIRouter(prefix="/data-requests", tags=["data requests"])


class DataRequest(BaseModel):
    description: str
    report_id: str
    simulation_ids: Optional[List[str]] = None
    is_comparison: Optional[bool] = False


class ParsedAggregate(BaseModel):
    simulation_id: Optional[str] = None
    baseline_simulation_id: Optional[str] = None
    comparison_simulation_id: Optional[str] = None
    entity: str
    variable_name: str
    aggregate_function: str
    year: Optional[int] = None
    filter_variable_name: Optional[str] = None
    filter_variable_value: Optional[str] = None
    filter_variable_leq: Optional[float] = None
    filter_variable_geq: Optional[float] = None
    filter_variable_quantile_leq: Optional[float] = None
    filter_variable_quantile_geq: Optional[float] = None
    filter_variable_quantile_value: Optional[str] = None


class DataRequestResponse(BaseModel):
    aggregates: List[ParsedAggregate]
    chart_type: str
    x_axis_variable: Optional[str] = None
    y_axis_variable: Optional[str] = None
    explanation: str


@router.post("/parse", response_model=DataRequestResponse)
async def parse_data_request(
    request: DataRequest,
    db: Session = Depends(get_session)
):
    """Parse a natural language data request into aggregates configuration"""

    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    # Fetch context data
    variables = db.exec(select(BaselineVariableTable).limit(1000)).all()
    simulations = db.exec(select(SimulationTable).limit(100)).all()
    policies = db.exec(select(PolicyTable).limit(100)).all()
    datasets = db.exec(select(DatasetTable).limit(100)).all()

    # Create lookup maps
    policy_map = {p.id: p for p in policies}
    dataset_map = {d.id: d for d in datasets}

    # Build context for LLM
    variables_context = [
        {
            "name": v.id,
            "label": v.label,
            "entity": v.entity,
            "description": v.description
        }
        for v in variables[:100]  # Limit to avoid token limits
    ]

    simulations_context = [
        {
            "id": s.id,
            "policy_label": policy_map.get(s.policy_id).name if s.policy_id and s.policy_id in policy_map else "Baseline",
            "dataset_label": dataset_map.get(s.dataset_id).name if s.dataset_id and s.dataset_id in dataset_map else "Default"
        }
        for s in simulations
    ]

    # Create prompt for Claude
    system_prompt = """You are a JSON API that converts natural language requests into structured aggregate queries.

CRITICAL RULES:
1. Return ONLY raw JSON - no markdown, no code blocks, no explanations outside the JSON
2. The JSON must be valid and parseable by Python's json.loads()
3. Never use trailing commas in JSON
4. All string values must use double quotes
5. null values must be lowercase "null"
6. Boolean values must be lowercase "true" or "false"

You have access to:
- Variables (metrics that can be aggregated)
- Simulations (different policy scenarios to compare)
- Aggregation functions: mean, sum, median, count

QUANTILE FILTERING RULES:
When users ask for deciles, quintiles, vigintiles, or percentiles:

1. DECILES (10 groups): Create 10 separate aggregates with quantile filters
   - 1st decile: filter_variable_quantile_geq: 0.0, filter_variable_quantile_leq: 0.1
   - 2nd decile: filter_variable_quantile_geq: 0.1, filter_variable_quantile_leq: 0.2
   - 3rd decile: filter_variable_quantile_geq: 0.2, filter_variable_quantile_leq: 0.3
   - ... and so on up to 10th decile: filter_variable_quantile_geq: 0.9, filter_variable_quantile_leq: 1.0

2. QUINTILES (5 groups): Create 5 separate aggregates
   - 1st quintile: filter_variable_quantile_geq: 0.0, filter_variable_quantile_leq: 0.2
   - 2nd quintile: filter_variable_quantile_geq: 0.2, filter_variable_quantile_leq: 0.4
   - 3rd quintile: filter_variable_quantile_geq: 0.4, filter_variable_quantile_leq: 0.6
   - 4th quintile: filter_variable_quantile_geq: 0.6, filter_variable_quantile_leq: 0.8
   - 5th quintile: filter_variable_quantile_geq: 0.8, filter_variable_quantile_leq: 1.0

3. VIGINTILES (20 groups): Create 20 separate aggregates
   - 1st vigintile: filter_variable_quantile_geq: 0.00, filter_variable_quantile_leq: 0.05
   - 2nd vigintile: filter_variable_quantile_geq: 0.05, filter_variable_quantile_leq: 0.10
   - ... and so on with 0.05 increments

4. TOP/BOTTOM percentages: Use filter_variable_quantile_value
   - "top 10%": filter_variable_quantile_value: "top_10%"
   - "bottom 20%": filter_variable_quantile_value: "bottom_20%"

IMPORTANT: When creating quantile groups, you must:
- Set filter_variable_name to the variable you want to group by (usually income)
- Create multiple aggregate objects, one for each quantile group
- Use the quantile filter fields (filter_variable_quantile_leq, filter_variable_quantile_geq)

Create ONE aggregate object for EACH combination of simulation, variable, and quantile group.
Example: 2 simulations × 1 variable × 10 deciles = 20 aggregate objects.

Required JSON structure (return EXACTLY this format):
{
    "aggregates": [
        {
            "entity": "string",
            "variable_name": "string",
            "aggregate_function": "string",
            "year": null,
            "filter_variable_name": null,
            "filter_variable_value": null,
            "filter_variable_leq": null,
            "filter_variable_geq": null,
            "filter_variable_quantile_leq": null,
            "filter_variable_quantile_geq": null,
            "filter_variable_quantile_value": null
        }
    ],
    "chart_type": "table",
    "x_axis_variable": null,
    "y_axis_variable": null,
    "explanation": "string"
}

Note: Do NOT include simulation_id in the aggregates - simulations are handled separately.

Remember: Return ONLY the JSON object. No text before or after."""

    # Customize prompt based on whether simulations are provided
    if request.simulation_ids:
        sim_context = f"Using simulation IDs: {request.simulation_ids}"
        if request.is_comparison and len(request.simulation_ids) == 2:
            sim_context = f"Comparing baseline simulation {request.simulation_ids[0]} with reform simulation {request.simulation_ids[1]}"
    else:
        sim_context = f"Available simulations:\n{json.dumps(simulations_context, indent=2)}"

    user_prompt = f"""User request: {request.description}

Available variables (first 100):
{json.dumps(variables_context, indent=2)}

{sim_context}

Parse this request into aggregate queries. {"The simulations have already been selected, so just focus on parsing what variables and aggregations are needed." if request.simulation_ids else "If the user mentions comparing policies or simulations, include multiple simulation_ids."}

If they mention:
- Income bands or ranges: use filter_variable_leq and filter_variable_geq
- Deciles: create 10 aggregates with filter_variable_quantile_leq and filter_variable_quantile_geq (0.0-0.1, 0.1-0.2, etc)
- Quintiles: create 5 aggregates with quantile filters (0.0-0.2, 0.2-0.4, etc)
- Vigintiles: create 20 aggregates with quantile filters (0.0-0.05, 0.05-0.10, etc)
- Top/bottom X%: use filter_variable_quantile_value (e.g., "top_10%" or "bottom_20%")

REMINDER: Return ONLY valid JSON. No text before or after. Ensure all JSON syntax is correct:
- No trailing commas
- All strings in double quotes
- Proper null values (not None or undefined)
- Valid array/object structure"""

    # Call Claude
    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            temperature=0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        # Parse the response - should be pure JSON
        response_text = message.content[0].text.strip()
        print(f"LLM Response: {response_text[:1000]}...")  # Debug logging

        try:
            # Clean up common issues before parsing
            # Remove any potential Unicode BOM
            if response_text.startswith('\ufeff'):
                response_text = response_text[1:]

            # Remove any leading/trailing whitespace
            response_text = response_text.strip()

            # Try to parse as pure JSON
            parsed_response = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Failed text: {response_text[:500]}")

            # Try to extract JSON from the response
            import re
            # Look for JSON object pattern
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    parsed_response = json.loads(json_match.group())
                except json.JSONDecodeError as e2:
                    print(f"Failed to parse extracted JSON: {e2}")
                    raise ValueError(f"Failed to parse LLM response: {str(e)}")
            else:
                raise ValueError(f"Failed to parse LLM response: {str(e)}")

        print(f"Parsed JSON: {json.dumps(parsed_response, indent=2)[:500]}...")  # Debug logging

        # Convert to response model - validate each aggregate
        aggregates = []

        # If this is a comparison and we have simulation_ids from the request, use them
        is_comparison = request.is_comparison and request.simulation_ids and len(request.simulation_ids) == 2

        for agg_data in parsed_response.get("aggregates", []):
            var_names = agg_data.get("variable_name", [])
            if not isinstance(var_names, list):
                var_names = [var_names]

            # Create one aggregate for each variable
            for var_name in var_names:
                agg_copy = agg_data.copy()
                agg_copy["variable_name"] = var_name

                # If it's a comparison, set baseline and comparison IDs
                if is_comparison:
                    # Use the provided simulation_ids for comparison
                    agg_copy["baseline_simulation_id"] = request.simulation_ids[0]
                    agg_copy["comparison_simulation_id"] = request.simulation_ids[1]
                    # Don't set simulation_id for comparisons
                    agg_copy.pop("simulation_id", None)
                else:
                    # For single simulation, use the first simulation_id
                    if request.simulation_ids and len(request.simulation_ids) > 0:
                        agg_copy["simulation_id"] = request.simulation_ids[0]
                    else:
                        # Fallback if no simulation_ids provided (shouldn't happen in new flow)
                        agg_copy["simulation_id"] = agg_data.get("simulation_id", "default")

                # Ensure entity has a default
                if not agg_copy.get("entity"):
                    agg_copy["entity"] = "person"
                # Ensure aggregate_function has a default
                if not agg_copy.get("aggregate_function"):
                    agg_copy["aggregate_function"] = "mean"
                aggregates.append(ParsedAggregate(**agg_copy))

        return DataRequestResponse(
            aggregates=aggregates,
            chart_type=parsed_response.get("chart_type", "table"),
            x_axis_variable=parsed_response.get("x_axis_variable"),
            y_axis_variable=parsed_response.get("y_axis_variable"),
            explanation=parsed_response.get("explanation", "Data visualization based on your request")
        )

    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"Anthropic API error: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")