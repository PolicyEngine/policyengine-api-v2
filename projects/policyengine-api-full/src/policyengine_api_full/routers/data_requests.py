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
import time
from policyengine_api_full.database import get_session
from policyengine.database import BaselineVariableTable, SimulationTable, PolicyTable, DatasetTable

router = APIRouter(prefix="/data-requests", tags=["data requests"])


class SimulationInfo(BaseModel):
    id: str
    name: str


class DataRequest(BaseModel):
    description: str
    report_id: str
    simulation_ids: Optional[List[str]] = None
    simulations: Optional[List[SimulationInfo]] = None
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
    import time
    start_time = time.time()

    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    # Determine model_id from simulations to filter variables appropriately
    model_id = "policyengine_uk"  # Default
    simulations_context = []

    # Use provided simulations with names if available, otherwise fall back to simulation_ids
    if request.simulations and len(request.simulations) > 0:
        simulations_context = [{"id": s.id, "name": s.name} for s in request.simulations]
        # Get model_id from first simulation
        first_sim = db.get(SimulationTable, request.simulations[0].id)
        if first_sim and first_sim.model_id:
            model_id = first_sim.model_id
    elif request.simulation_ids and len(request.simulation_ids) > 0:
        # Fallback: just use IDs without names
        simulations_context = [{"id": sim_id, "name": f"Simulation {i+1}"}
                              for i, sim_id in enumerate(request.simulation_ids)]
        first_sim = db.get(SimulationTable, request.simulation_ids[0])
        if first_sim and first_sim.model_id:
            model_id = first_sim.model_id

    # Fetch common variables for the specific model
    if model_id == "policyengine_uk":
        common_variable_names = [
            "hbai_household_net_income", "equiv_hbai_household_net_income",
            "gov_tax", "gov_spending", "gov_balance",
            "income_tax", "vat", "ni_employee", "ni_employer", "universal_credit", "state_pension", "child_benefit", "housing_benefit", "pension_credit",
            "household_benefits", "household_tax", "employment_income", "self_employment_income", "pension_income", "state_pension", "property_income", "dividend_income", "savings_interest_income",
            "age",
            "in_poverty_bhc", "in_poverty_ahc", "in_relative_poverty_bhc", "in_relative_poverty_ahc"
        ]
    else:  # policyengine_us
        common_variable_names = [
            "household_net_income", "household_benefits", "household_tax",
            "employment_income", "person_weight", "spm_unit_net_income",
            "snap", "medicaid", "wic", "tanf"
        ]

    variables = db.exec(
        select(BaselineVariableTable)
        .where(BaselineVariableTable.id.in_(common_variable_names))
        .where(BaselineVariableTable.model_id == model_id)
    ).all()

    # Build minimal context
    variables_context = [{"name": v.id, "entity": v.entity} for v in variables]

    # Consolidated system prompt with examples
    model_context = f"PolicyEngine model: {model_id}\n"
    if model_id == "policyengine_uk":
        model_context += "- UK model: Use variables like hbai_household_net_income, in_poverty_bhc, in_poverty_ahc\n"
        model_context += "- Common filter variable: equiv_hbai_household_net_income\n"
    else:
        model_context += "- US model: Use variables like spm_unit_net_income, snap, medicaid\n"
        model_context += "- Common filter variable: spm_unit_net_income\n"

    system_prompt = f"""Convert natural language to JSON aggregate queries. Return ONLY valid JSON.

{model_context}

RULES:
- IMPORTANT: Only use variables available in {model_id} (see Variables list below)
- When user mentions simulation names, match them to the provided simulation IDs in the Simulations list
- For "by deciles": Create 10 aggregates with filter_variable_quantile_geq/leq from 0.0-0.1, 0.1-0.2, ... 0.9-1.0
- For "by quintiles": Create 5 aggregates with ranges 0.0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0
- entity is optional (auto-inferred from variable), default function: "mean"

JSON schema:
{{
  "aggregates": [{{
    "entity": null,
    "variable_name": "hbai_household_net_income",
    "aggregate_function": "mean",
    "year": null,
    "filter_variable_name": null,
    "filter_variable_value": null,
    "filter_variable_leq": null,
    "filter_variable_geq": null,
    "filter_variable_quantile_leq": null,
    "filter_variable_quantile_geq": null,
    "filter_variable_quantile_value": null,
    "simulation_id": "simulation-uuid-here"
  }}],
  "chart_type": "table",
  "x_axis_variable": null,
  "y_axis_variable": null,
  "explanation": "Brief description"
}}"""

    simulations_text = ""
    if simulations_context:
        simulations_text = f"\n\nSimulations: {json.dumps(simulations_context)}"

    user_prompt = f"""Request: {request.description}

Variables: {json.dumps(variables_context)}{simulations_text}

Return JSON:"""

    # Call Claude with Haiku for speed
    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            temperature=0,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        # Parse the response - should be pure JSON
        response_text = message.content[0].text.strip()
        print(f"LLM Response: {response_text[:1000]}...")  # Debug logging

        parse_start = time.time()
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

        # Check if quantile fields are present
        if parsed_response.get("aggregates"):
            first_agg = parsed_response["aggregates"][0]
            print(f"First aggregate quantile fields:")
            print(f"  filter_variable_quantile_leq: {first_agg.get('filter_variable_quantile_leq')}")
            print(f"  filter_variable_quantile_geq: {first_agg.get('filter_variable_quantile_geq')}")
            print(f"  filter_variable_name: {first_agg.get('filter_variable_name')}")
            print(f"  Total aggregates: {len(parsed_response['aggregates'])}")

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
                    # If the LLM provided a simulation_id, use it (for multi-simulation requests)
                    if agg_data.get("simulation_id"):
                        agg_copy["simulation_id"] = agg_data.get("simulation_id")
                    # Otherwise, use the first simulation_id from the request
                    elif request.simulation_ids and len(request.simulation_ids) > 0:
                        agg_copy["simulation_id"] = request.simulation_ids[0]
                    else:
                        # Fallback if no simulation_ids provided (shouldn't happen in new flow)
                        agg_copy["simulation_id"] = "default"

                # Ensure entity has a default
                if not agg_copy.get("entity"):
                    agg_copy["entity"] = "person"
                # Ensure aggregate_function has a default
                if not agg_copy.get("aggregate_function"):
                    agg_copy["aggregate_function"] = "mean"
                aggregates.append(ParsedAggregate(**agg_copy))

        parse_time = time.time()
        print(f"[PERFORMANCE] Response parsing took {parse_time - parse_start:.2f} seconds")
        total_time = time.time()
        print(f"[PERFORMANCE] Total data request parsing took {total_time - start_time:.2f} seconds")
        print(f"[PERFORMANCE] Generated {len(aggregates)} aggregates")

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