import importlib
import json
import logging
from policyengine_core.taxbenefitsystems import TaxBenefitSystem
from policyengine_core.variables import Variable as CoreVariable
from policyengine_core.simulations import Simulation
from policyengine_core.populations import Population
from policyengine_api_full.api.utils.constants import CURRENT_LAW_IDS
from policyengine_api_full.api.utils.json import get_safe_json
from policyengine_api_full.api.utils.metadata import (
    parse_enum_possible_values,
    parse_default_value,
)
from policyengine_api_full.api.models.household import (
    HouseholdUS,
    HouseholdUK,
    HouseholdGeneric,
)
from policyengine_api_full.api.models.metadata.variable import (
    Variable,
    VariableModule,
)
from policyengine_api_full.api.models.metadata.entity import Entity
from policyengine_api_full.api.models.metadata.modeled_policies import (
    ModeledPolicies,
)
from policyengine_api_full.api.models.metadata.economy_options import (
    Region,
    TimePeriod,
    EconomyOptions,
)
from policyengine_api_full.api.models.metadata.parameter import (
    ParameterScaleItem,
    ParameterNode,
    Parameter,
)
from policyengine_api_full.api.models.metadata.metadata_module import MetadataModule
from policyengine_api_full.api.models.periods import ISO8601Date
from typing import Union, Any
from numpy.typing import ArrayLike

from policyengine_core.entities import Entity as CoreEntity
from policyengine_core.parameters import (
    ParameterNode as CoreParameterNode,
    Parameter as CoreParameter,
    ParameterScale as CoreParameterScale,
    ParameterScaleBracket as CoreParameterScaleBracket,
)
from policyengine_core.parameters import get_parameter
import pkg_resources
from copy import deepcopy
from policyengine_core.model_api import Enum
from policyengine_core.periods import instant
import dpath
from pathlib import Path
import math

import logging

logger = logging.getLogger(__name__)


class PolicyEngineCountry:
    def __init__(self, country_package_name: str, country_id: str):
        self.country_package_name = country_package_name
        self.country_id = country_id
        self.country_package = importlib.import_module(country_package_name)
        self.tax_benefit_system: TaxBenefitSystem = (
            self.country_package.CountryTaxBenefitSystem()
        )
        self.metadata: MetadataModule = self._build_metadata(
            country_id=self.country_id,
            system=self.tax_benefit_system,
            country_package_name=self.country_package_name,
        )

    def _build_metadata(
        self,
        country_id: str,
        system: TaxBenefitSystem,
        country_package_name: str,
    ) -> MetadataModule:
        return MetadataModule(
            variables=self._build_variables(system=system),
            parameters=self._build_parameters(system=system),
            entities=self._build_entities(system=system),
            variableModules=self._build_variable_modules(system=system),
            economy_options=self._build_economy_options(country_id=country_id),
            current_law_id=CURRENT_LAW_IDS[country_id],
            basicInputs=system.basic_inputs,
            modeled_policies=self._build_modeled_policies(system=system),
            version=pkg_resources.get_distribution(country_package_name).version,
        )

    def _build_economy_options(self, country_id: str) -> EconomyOptions:
        regions: list[Region] = self._build_regions(country_id=country_id)
        time_periods: list[TimePeriod] = self._build_time_periods(country_id=country_id)
        return EconomyOptions(region=regions, time_period=time_periods)

    def _build_variables(self, system: TaxBenefitSystem) -> dict[str, Variable]:
        variables: dict[str, CoreVariable] = system.variables
        variable_data = {}
        for variable_name, variable in variables.items():
            variable_data[variable_name] = Variable(
                documentation=variable.documentation,
                entity=variable.entity.key,
                valueType=variable.value_type.__name__,
                definitionPeriod=variable.definition_period,
                name=variable_name,
                label=variable.label,
                category=variable.category,
                unit=variable.unit,
                moduleName=variable.module_name,
                indexInModule=variable.index_in_module,
                isInputVariable=variable.is_input_variable(),
                defaultValue=parse_default_value(variable),
                adds=variable.adds,
                subtracts=variable.subtracts,
                hidden_input=variable.hidden_input,
                possibleValues=parse_enum_possible_values(variable),
            )
        return variable_data

    def _build_parameters(
        self, system: TaxBenefitSystem
    ) -> dict[str, ParameterScaleItem | ParameterNode | Parameter]:
        APPROVED_TOP_LEVEL_FOLDERS = ["gov"]

        parameters: list[
            CoreParameter
            | CoreParameterNode
            | CoreParameterScaleBracket
            | CoreParameterScale
        ] = system.parameters
        parameter_data = {}
        for parameter in parameters.get_descendants():
            # Only include parameters from approved folders
            if not any(
                parameter.name.startswith(folder)
                for folder in APPROVED_TOP_LEVEL_FOLDERS
            ):
                continue

            match parameter:
                case p if isinstance(parameter, CoreParameterScale):
                    parameter_data[parameter.name] = self._build_parameter_scale(
                        parameter
                    )
                case p if isinstance(parameter, CoreParameterScaleBracket):
                    parameter_data[parameter.name] = (
                        self._build_parameter_scale_bracket(parameter)
                    )
                case p if isinstance(parameter, CoreParameter):
                    parameter_data[parameter.name] = self._build_parameter(parameter)
                case p if isinstance(parameter, CoreParameterNode):
                    parameter_data[parameter.name] = self._build_parameter_node(
                        parameter
                    )
                case p:
                    continue

        return parameter_data

    def _build_entities(self, system: TaxBenefitSystem) -> dict[str, Entity]:
        entities: list[CoreEntity] = system.entities
        data = {}

        for entity in entities:
            roles = {}
            if hasattr(entity, "roles"):
                roles = {
                    role.key: {
                        "plural": role.plural,
                        "label": role.label,
                        "doc": role.doc,
                    }
                    for role in entity.roles
                }

            data[entity.key] = Entity(
                plural=entity.plural,
                label=entity.label,
                doc=entity.doc,
                is_person=entity.is_person,
                key=entity.key,
                roles=roles,
            )

        return data

    def _build_variable_modules(
        self, system: TaxBenefitSystem
    ) -> dict[str, VariableModule]:
        variable_modules: dict[str, dict[str, Any]] = system.variable_module_metadata
        modules = {}
        for module_path, module in variable_modules.items():
            modules[module_path] = VariableModule(
                label=module.get("label", None),
                description=module.get("description", None),
                index=module.get("index", None),
            )
        return modules

    def _build_modeled_policies(
        self, system: TaxBenefitSystem
    ) -> ModeledPolicies | None:
        if system.modelled_policies:
            return ModeledPolicies(**system.modelled_policies)
        return None

    def _build_parameter_scale(
        self, parameter: CoreParameterScale
    ) -> ParameterScaleItem:
        end_name = parameter.name.split(".")[-1]
        return ParameterScaleItem(
            type="parameterNode",
            parameter=parameter.name,
            description=parameter.description,
            label=parameter.metadata.get("label", end_name.replace("_", " ")),
        )

    def _build_parameter_scale_bracket(
        self, parameter: CoreParameterScaleBracket
    ) -> ParameterScaleItem:
        # Set the label to 'bracket 1' for the first bracket, 'bracket 2' for the second, etc.
        bracket_index = int(parameter.name[parameter.name.index("[") + 1 : -1])
        bracket_label = f"bracket {bracket_index + 1}"
        return ParameterScaleItem(
            type="parameterNode",
            parameter=parameter.name,
            description=parameter.description,
            label=parameter.metadata.get("label", bracket_label),
        )

    def _build_parameter(self, parameter: CoreParameter) -> Parameter:
        end_name = parameter.name.split(".")[-1]
        values_list = {
            value_at_instant.instant_str: get_safe_json(value_at_instant.value)
            for value_at_instant in parameter.values_list
        }

        return Parameter(
            type="parameter",
            parameter=parameter.name,
            description=parameter.description,
            label=parameter.metadata.get("label", end_name.replace("_", " ")),
            unit=parameter.metadata.get("unit"),
            period=parameter.metadata.get("period"),
            values=values_list,
            economy=parameter.metadata.get("economy", True),
            household=parameter.metadata.get("household", True),
        )

    def _build_parameter_node(self, parameter: CoreParameterNode) -> ParameterNode:
        end_name = parameter.name.split(".")[-1]
        return ParameterNode(
            type="parameterNode",
            parameter=parameter.name,
            description=parameter.description,
            label=parameter.metadata.get("label", end_name.replace("_", " ")),
            economy=parameter.metadata.get("economy", True),
            household=parameter.metadata.get("household", True),
        )

    def _build_regions(self, country_id: str) -> list[Region]:
        cwd = Path(__file__).parent
        region_file_path = cwd.joinpath(f"data/regions/{country_id}_regions.json")
        with open(region_file_path, "r") as region_file:
            regions = json.load(region_file)
        return [Region(**region) for region in regions]

    def _build_time_periods(self, country_id: str) -> list[TimePeriod]:
        cwd = Path(__file__).parent
        country_time_period_path = cwd.joinpath(
            f"data/time_periods/{country_id}_time_periods.json"
        )
        if country_time_period_path.exists():
            with open(country_time_period_path, "r") as time_period_file:
                time_periods = json.load(time_period_file)
        else:
            time_period_path = cwd.joinpath(
                "data/time_periods/default_time_periods.json"
            )
            with open(time_period_path, "r") as time_period_file:
                time_periods = json.load(time_period_file)
        return [TimePeriod(**time_period) for time_period in time_periods]

    def calculate(
        self,
        household: HouseholdUS | HouseholdUK | HouseholdGeneric,
        reform: Union[dict, None] = None,
    ) -> HouseholdGeneric | HouseholdUK | HouseholdUS:
        system: TaxBenefitSystem = self._prepare_tax_benefit_system(reform)
        household_raw: dict[str, Any] = household.model_dump()

        simulation: Simulation = self.country_package.Simulation(
            tax_benefit_system=system,
            situation=household_raw,
        )

        household_result: dict[str, Any] = deepcopy(household_raw)
        requested_computations: list[tuple[str, str, str, str]] = (
            get_requested_computations(household_raw)
        )

        for computation in requested_computations:
            self._process_computation(simulation, system, household_result, computation)

        if self.country_id == "us":
            return HouseholdUS.model_validate(household_result)
        if self.country_id == "uk":
            return HouseholdUK.model_validate(household_result)
        return HouseholdGeneric.model_validate(household_result)

    def _prepare_tax_benefit_system(
        self, reform: Union[dict, None] = None
    ) -> TaxBenefitSystem:
        """Prepare the tax benefit system with optional reforms applied."""
        if not reform:
            return self.tax_benefit_system

        system: TaxBenefitSystem = self.tax_benefit_system.clone()

        for parameter_name, periods in reform.items():
            for time_period, value in periods.items():
                self._update_parameter(system, parameter_name, time_period, value)

        return system

    def _update_parameter(
        self,
        system: TaxBenefitSystem,
        parameter_name: str,
        time_period: str,
        value: Any,
    ) -> None:
        """Update a specific parameter in the tax benefit system."""
        start_instant: ISO8601Date
        end_instant: ISO8601Date
        start_instant, end_instant = time_period.split(".")
        parameter: CoreParameter = get_parameter(system.parameters, parameter_name)

        # Determine the appropriate type for the value
        node_type = type(parameter.values_list[-1].value)

        # Cast int to float to harmonize numeric handling
        # Int-float casting copied/pasted from the original household API at
        # https://github.com/PolicyEngine/policyengine-household-api/blob/96ebe4440f9cba81b09f64d53aa4f7e6e7003d77/policyengine_household_api/country.py#L319
        if node_type == int:
            node_type = float

        # Convert value to float if possible
        try:
            value = float(value)
        except (ValueError, TypeError):
            pass

        parameter.update(
            start=instant(start_instant),
            stop=instant(end_instant),
            value=node_type(value),
        )

    def _process_computation(
        self,
        simulation: Simulation,
        system: TaxBenefitSystem,
        household: dict[str, Any],
        computation,
    ):
        """Process a single computation request and update the household result."""
        entity_plural, entity_id, variable_name, period = computation

        try:
            variable: Variable = system.get_variable(variable_name)
            result: ArrayLike = simulation.calculate(variable_name, period)

            if getattr(household, "axes", None):
                self._handle_axes_computation(
                    household,
                    entity_plural,
                    entity_id,
                    variable_name,
                    period,
                    result,
                )
            else:
                self._handle_single_computation(
                    simulation,
                    household,
                    entity_plural,
                    entity_id,
                    variable_name,
                    period,
                    result,
                    variable,
                )
        except Exception as e:
            self._handle_computation_error(
                household, entity_plural, entity_id, variable_name, period, e
            )

    def _handle_axes_computation(
        self,
        household: dict[str, Any],
        entity_plural: str,
        entity_id,
        variable_name: str,
        period,
        result,
    ) -> None:
        """Handle computation for households with axes."""
        count_entities: int = len(household[entity_plural])
        entity_index: int = self._find_entity_index(household, entity_plural, entity_id)

        # Reshape result and get values for the specific entity
        result_values: list[float] = (
            result.astype(float).reshape((-1, count_entities)).T[entity_index].tolist()
        )

        # Check for infinite values
        if any(math.isinf(value) for value in result_values):
            raise ValueError("Infinite value")

        # Update household with results
        household[entity_plural][entity_id][variable_name][period] = result_values

    def _find_entity_index(
        self, household: dict[str, Any], entity_plural: str, entity_id
    ):
        """Find the index of an entity within its plural group."""
        entity_index = 0

        _entity_id: str
        for _entity_id in household[entity_plural].keys():
            if _entity_id == entity_id:
                break
            entity_index += 1
        return entity_index

    def _handle_single_computation(
        self,
        simulation: Simulation,
        household: dict[str, Any],
        entity_plural: str,
        entity_id,
        variable_name: str,
        period,
        result: ArrayLike,
        variable: Variable,
    ):
        """Handle computation for a single entity."""
        population: Population = simulation.get_population(entity_plural)
        entity_index: int = population.get_index(entity_id)

        # Format the result based on variable type
        entity_result = self._format_result(result, entity_index, variable)

        # Update household with result
        household[entity_plural][entity_id][variable_name][period] = entity_result

    def _format_result(
        self, result: ArrayLike, entity_index, variable: Variable
    ) -> Any:
        """Format calculation result based on variable type."""
        if variable.value_type == Enum:
            return result.decode()[entity_index].name
        if variable.value_type == float:
            value = float(str(result[entity_index]))
            # Convert infinities to JSON-compatible strings
            if value == float("inf"):
                return "Infinity"
            if value == float("-inf"):
                return "-Infinity"
            return value
        if variable.value_type == str:
            return str(result[entity_index])
        return result.tolist()[entity_index]

    def _handle_computation_error(
        self,
        household: dict[str, Any],
        entity_plural: str,
        entity_id: str,
        variable_name: str,
        period,
        error,
    ):
        """Handle errors during computation."""

        # Original code passes if "axes" in household - why?
        if "axes" not in household:
            household[entity_plural][entity_id][variable_name][period] = None
            print(f"Error computing {variable_name} for {entity_id}: {error}")


def get_requested_computations(household: dict[str, Any]):
    requested_computations = dpath.util.search(
        household,
        "*/*/*/*",
        afilter=lambda t: t is None,
        yielded=True,
    )
    requested_computation_data = []

    for computation in requested_computations:
        path = computation[0]
        entity_plural, entity_id, variable_name, period = path.split("/")
        requested_computation_data.append(
            (entity_plural, entity_id, variable_name, period)
        )

    return requested_computation_data


COUNTRIES = {
    "uk": PolicyEngineCountry("policyengine_uk", "uk"),
    "us": PolicyEngineCountry("policyengine_us", "us"),
    "ca": PolicyEngineCountry("policyengine_canada", "ca"),
    "ng": PolicyEngineCountry("policyengine_ng", "ng"),
    "il": PolicyEngineCountry("policyengine_il", "il"),
}
