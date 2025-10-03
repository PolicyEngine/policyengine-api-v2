from fastapi import APIRouter, HTTPException
from policyengine_core import reforms
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/variables", tags=["variables"])


class VariableResponse(BaseModel):
    """Response model for variable metadata."""
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    documentation: Optional[str] = None
    entity: Optional[str] = None
    value_type: Optional[str] = None
    unit: Optional[str] = None
    definition_period: Optional[str] = None
    default_value: Optional[str] = None


def get_model_system(model_id: str = "policyengine_uk"):
    """Get the tax-benefit system for a given model."""
    if model_id == "policyengine_uk":
        from policyengine_uk import CountryTaxBenefitSystem
        return CountryTaxBenefitSystem()
    elif model_id == "policyengine_us":
        from policyengine_us import CountryTaxBenefitSystem
        return CountryTaxBenefitSystem()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_id}")


@router.get("/{variable_name}", response_model=VariableResponse)
def get_variable(
    variable_name: str,
    model_id: str = "policyengine_uk",
):
    """Get metadata for a specific variable."""
    try:
        system = get_model_system(model_id)

        if variable_name not in system.variables:
            raise HTTPException(status_code=404, detail=f"Variable '{variable_name}' not found")

        variable = system.variables[variable_name]

        return VariableResponse(
            name=variable_name,
            label=getattr(variable, 'label', None) or variable_name.replace('_', ' ').title(),
            description=getattr(variable, 'description', None),
            documentation=getattr(variable, 'documentation', None),
            entity=getattr(variable, 'entity', None).key if hasattr(variable, 'entity') else None,
            value_type=getattr(variable, 'value_type', None).__name__ if hasattr(variable, 'value_type') else None,
            unit=getattr(variable, 'unit', None),
            definition_period=getattr(variable, 'definition_period', None),
            default_value=str(getattr(variable, 'default_value', None)) if hasattr(variable, 'default_value') else None,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
