import importlib
import json
from policyengine_core.taxbenefitsystems import TaxBenefitSystem
from policyengine_core.variables import Variable as CoreVariable
from policyengine_api.api.utils.constants import COUNTRY_PACKAGE_VERSIONS, CURRENT_LAW_IDS
from policyengine_api.api.utils.json import get_safe_json
from policyengine_api.api.utils.metadata import (
    parse_enum_possible_values,
    parse_default_value,
)
from policyengine_api.api.models.metadata.variable import (
    Variable,
    VariableModule,
)
from policyengine_api.api.models.metadata.entity import Entity
from policyengine_api.api.models.metadata.economy_options import (
    Region,
    TimePeriod,
    EconomyOptions,
)
from policyengine_api.api.models.metadata.parameter import (
    ParameterScaleItem,
    ParameterNode,
    Parameter,
)
from policyengine_api.api.models.metadata.metadata_module import MetadataModule
from typing import Union, Any

# from policyengine_api.utils import (
#     get_safe_json,
# )
from policyengine_core.entities import Entity as CoreEntity
from policyengine_core.parameters import (
    ParameterNode as CoreParameterNode,
    Parameter as CoreParameter,
    ParameterScale as CoreParameterScale,
    ParameterScaleBracket as CoreParameterScaleBracket,
)
from typing import Annotated
from policyengine_core.parameters import get_parameter
import pkg_resources
from policyengine_core.model_api import Reform, Enum
from policyengine_core.periods import instant
import dpath
from pathlib import Path
import math
from uuid import UUID, uuid4
import policyengine_uk
import policyengine_us
import policyengine_canada
import policyengine_ng
import policyengine_il


class PolicyEngineCountry:
    def __init__(self, country_package_name: str, country_id: str):
        self.country_package_name = country_package_name
        self.country_id = country_id
        self.country_package = importlib.import_module(country_package_name)
        self.tax_benefit_system: TaxBenefitSystem = (
            self.country_package.CountryTaxBenefitSystem()
        )
        self.build_metadata()

    # In progress
    def build_metadata(self):
        self.metadata: MetadataModule = MetadataModule(
            variables=self.build_variables(),
            parameters=self.build_parameters(),
            entities=self.build_entities(),
            variableModules=self.build_variable_modules(),
            economy_options=self.build_economy_options(),
            current_law_id=CURRENT_LAW_IDS[self.country_id],
            basicInputs=self.tax_benefit_system.basic_inputs,
        )

        # self.metadata = dict(
        #     status="ok",
        #     message=None,
        #     result=dict(
        #         variables=self.build_variables(), # Done
        #         parameters=self.build_parameters(), # Done
        #         entities=self.build_entities(), # Done
        #         variableModules=self.tax_benefit_system.variable_module_metadata, # Done
        #         economy_options=self.build_microsimulation_options(),
        #         current_law_id={
        #             "uk": 1,
        #             "us": 2,
        #             "ca": 3,
        #             "ng": 4,
        #             "il": 5,
        #         }[self.country_id],
        #         basicInputs=self.tax_benefit_system.basic_inputs,
        #         modelled_policies=self.tax_benefit_system.modelled_policies,
        #         version=pkg_resources.get_distribution(
        #             self.country_package_name
        #         ).version,
        #     ),
        # )

    def build_economy_options(self) -> EconomyOptions:
        regions: list[Region] = self.build_regions(self.country_id)
        time_periods: list[TimePeriod] = self.build_time_periods(
            self.country_id
        )
        return EconomyOptions(region=regions, time_period=time_periods)

    def build_variables(self) -> dict[str, Variable]:
        variables: dict[str, CoreVariable] = self.tax_benefit_system.variables
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

    def build_parameters(
        self,
    ) -> dict[str, ParameterScaleItem | ParameterNode | Parameter]:
        APPROVED_TOP_LEVEL_FOLDERS = ["gov"]

        parameters: list[
            CoreParameter
            | CoreParameterNode
            | CoreParameterScaleBracket
            | CoreParameterScale
        ] = self.tax_benefit_system.parameters
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
                    parameter_data[parameter.name] = (
                        self.build_parameter_scale(parameter)
                    )
                case p if isinstance(parameter, CoreParameterScaleBracket):
                    parameter_data[parameter.name] = (
                        self.build_parameter_scale_bracket(parameter)
                    )
                case p if isinstance(parameter, CoreParameter):
                    parameter_data[parameter.name] = self.build_parameter(
                        parameter
                    )
                case p if isinstance(parameter, CoreParameterNode):
                    parameter_data[parameter.name] = self.build_parameter_node(
                        parameter
                    )
                case p:
                    continue

        return parameter_data

    def build_entities(self) -> dict[str, Entity]:
        entities: list[CoreEntity] = self.tax_benefit_system.entities
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

    def build_variable_modules(self) -> dict[str, VariableModule]:
        variable_modules: dict[str, dict[str, Any]] = (
            self.tax_benefit_system.variable_module_metadata
        )
        modules = {}
        for module_path, module in variable_modules.items():
            modules[module_path] = VariableModule(
                label=module.get("label", None),
                description=module.get("description", None),
                index=module.get("index", None),
            )
        return modules

    def build_parameter_scale(
        self, parameter: CoreParameterScale
    ) -> ParameterScaleItem:
        end_name = parameter.name.split(".")[-1]
        return ParameterScaleItem(
            type="parameterNode",
            parameter=parameter.name,
            description=parameter.description,
            label=parameter.metadata.get("label", end_name.replace("_", " ")),
        )

    def build_parameter_scale_bracket(
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

    def build_parameter(self, parameter: CoreParameter) -> Parameter:
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

    def build_parameter_node(
        self, parameter: CoreParameterNode
    ) -> ParameterNode:
        end_name = parameter.name.split(".")[-1]
        return ParameterNode(
            type="parameterNode",
            parameter=parameter.name,
            description=parameter.description,
            label=parameter.metadata.get("label", end_name.replace("_", " ")),
            economy=parameter.metadata.get("economy", True),
            household=parameter.metadata.get("household", True),
        )

    def build_regions(self, country_id) -> list[Region]:
        cwd = Path(__file__).parent
        region_file_path = cwd.joinpath(
            f"data/regions/{country_id}_regions.json"
        )
        with open(region_file_path, "r") as region_file:
            regions = json.load(region_file)
        return [Region(**region) for region in regions]

    def build_time_periods(self, country_id) -> list[TimePeriod]:
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

    # Not done
    def calculate(
        self,
        household: dict,
        reform: Union[dict, None] = None,
        enable_ai_explainer: bool = False,
    ):
        if reform is not None and len(reform.keys()) > 0:
            system = self.tax_benefit_system.clone()
            for parameter_name in reform:
                for time_period, value in reform[parameter_name].items():
                    start_instant, end_instant = time_period.split(".")
                    parameter = get_parameter(
                        system.parameters, parameter_name
                    )
                    node_type = type(parameter.values_list[-1].value)
                    if node_type == int:
                        node_type = float
                    try:
                        value = float(value)
                    except:
                        pass
                    parameter.update(
                        start=instant(start_instant),
                        stop=instant(end_instant),
                        value=node_type(value),
                    )
        else:
            system = self.tax_benefit_system

        simulation = self.country_package.Simulation(
            tax_benefit_system=system,
            situation=household,
        )

        household = json.loads(json.dumps(household))

        # Run tracer on household
        simulation.trace = True
        requested_computations = get_requested_computations(household)

        for (
            entity_plural,
            entity_id,
            variable_name,
            period,
        ) in requested_computations:
            try:
                variable = system.get_variable(variable_name)
                result = simulation.calculate(variable_name, period)
                population = simulation.get_population(entity_plural)
                if "axes" in household:
                    count_entities = len(household[entity_plural])
                    entity_index = 0
                    for _entity_id in household[entity_plural].keys():
                        if _entity_id == entity_id:
                            break
                        entity_index += 1
                    result = (
                        result.astype(float)
                        .reshape((-1, count_entities))
                        .T[entity_index]
                        .tolist()
                    )
                    # If the result contains infinities, throw an error
                    if any([math.isinf(value) for value in result]):
                        raise ValueError("Infinite value")
                    else:
                        household[entity_plural][entity_id][variable_name][
                            period
                        ] = result
                else:
                    entity_index = population.get_index(entity_id)
                    if variable.value_type == Enum:
                        entity_result = result.decode()[entity_index].name
                    elif variable.value_type == float:
                        entity_result = float(str(result[entity_index]))
                        # Convert infinities to JSON infinities
                        if entity_result == float("inf"):
                            entity_result = "Infinity"
                        elif entity_result == float("-inf"):
                            entity_result = "-Infinity"
                    elif variable.value_type == str:
                        entity_result = str(result[entity_index])
                    else:
                        entity_result = result.tolist()[entity_index]

                    household[entity_plural][entity_id][variable_name][
                        period
                    ] = entity_result
            except Exception as e:
                if "axes" in household:
                    pass
                else:
                    household[entity_plural][entity_id][variable_name][
                        period
                    ] = None
                    print(
                        f"Error computing {variable_name} for {entity_id}: {e}"
                    )


# Not done
def create_policy_reform(policy_data: dict) -> dict:
    """
    Create a policy reform.

    Args:
        policy_data (dict): The policy data.

    Returns:
        dict: The reform.
    """

    def modify_parameters(parameters: ParameterNode) -> ParameterNode:
        for path, values in policy_data.items():
            node = parameters
            for step in path.split("."):
                if "[" in step:
                    step, index = step.split("[")
                    index = int(index[:-1])
                    node = node.children[step].brackets[index]
                else:
                    node = node.children[step]
            for period, value in values.items():
                start, end = period.split(".")
                node_type = type(node.values_list[-1].value)
                if node_type == int:
                    node_type = float  # '0' is of type int by default, but usually we want to cast to float.
                node.update(
                    start=instant(start),
                    stop=instant(end),
                    value=node_type(value),
                )

        return parameters

    class reform(Reform):
        def apply(self):
            self.modify_parameters(modify_parameters)

    return reform


# Not done
def get_requested_computations(household: dict):
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


# Not done
COUNTRIES = {
    "uk": PolicyEngineCountry("policyengine_uk", "uk"),
    "us": PolicyEngineCountry("policyengine_us", "us"),
    "ca": PolicyEngineCountry("policyengine_canada", "ca"),
    "ng": PolicyEngineCountry("policyengine_ng", "ng"),
    "il": PolicyEngineCountry("policyengine_il", "il"),
}


# Not done
def validate_country(country_id: str) -> Union[None, str]:
    """Validate that a country ID is valid. If not, return a 404 response.

    Args:
        country_id (str): The country ID to validate.

    Returns:

    """
    if country_id not in COUNTRIES:
        body = dict(
            status="error",
            message=f"Country {country_id} not found. Available countries are: {', '.join(COUNTRIES.keys())}",
        )
        # return Response(json.dumps(body), status=404)
    return None
