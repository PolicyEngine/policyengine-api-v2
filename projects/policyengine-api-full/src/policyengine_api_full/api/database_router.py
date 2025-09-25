from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional, Any, Dict

# Import all the database tables and models from policyengine package
from policyengine.database import (
    UserTable,
    ModelTable,
    ModelVersionTable,
    DatasetTable,
    VersionedDatasetTable,
    PolicyTable,
    SimulationTable,
    ParameterTable,
    ParameterValueTable,
    BaselineParameterValueTable,
    BaselineVariableTable,
    DynamicTable,
)

from policyengine.models import (
    User,
    Model,
    ModelVersion,
    Dataset,
    VersionedDataset,
    Policy,
    Simulation,
    Parameter,
    ParameterValue,
    BaselineParameterValue,
    BaselineVariable,
    Dynamic,
)

from policyengine_api_full.database import get_session

def create_database_router() -> APIRouter:
    """Create a router with CRUD endpoints for all database tables."""
    router = APIRouter(prefix="/database", tags=["database"])

    # User endpoints
    @router.get("/users", response_model=List[User])
    def list_users(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all users with pagination."""
        statement = select(UserTable).offset(skip).limit(limit)
        users = session.exec(statement).all()
        return [User.model_validate(user.model_dump()) for user in users]

    @router.get("/users/{user_id}", response_model=User)
    def get_user(user_id: str, session: Session = Depends(get_session)):
        """Get a specific user by ID."""
        user = session.get(UserTable, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return User.model_validate(user.model_dump())

    @router.post("/users", response_model=User)
    def create_user(user: User, session: Session = Depends(get_session)):
        """Create a new user."""
        db_user = UserTable(**user.model_dump())
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return User.model_validate(db_user.model_dump())

    @router.put("/users/{user_id}", response_model=User)
    def update_user(user_id: str, user: User, session: Session = Depends(get_session)):
        """Update an existing user."""
        db_user = session.get(UserTable, user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = user.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            setattr(db_user, key, value)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return User.model_validate(db_user.model_dump())

    @router.delete("/users/{user_id}")
    def delete_user(user_id: str, session: Session = Depends(get_session)):
        """Delete a user."""
        user = session.get(UserTable, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(user)
        session.commit()
        return {"message": "User deleted successfully"}

    # Model endpoints
    @router.get("/models", response_model=List[Dict[str, Any]])
    def list_models(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all models with pagination."""
        statement = select(ModelTable).offset(skip).limit(limit)
        models = session.exec(statement).all()
        # Return as dict since Model has callable fields
        return [{"id": m.id, "name": m.name, "description": m.description} for m in models]

    @router.get("/models/{model_id}")
    def get_model(model_id: str, session: Session = Depends(get_session)):
        """Get a specific model by ID."""
        model = session.get(ModelTable, model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return {"id": model.id, "name": model.name, "description": model.description}

    # Model Version endpoints
    @router.get("/model-versions", response_model=List[ModelVersion])
    def list_model_versions(
        model_id: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all model versions with optional filtering by model_id."""
        statement = select(ModelVersionTable)
        if model_id:
            statement = statement.where(ModelVersionTable.model_id == model_id)
        statement = statement.offset(skip).limit(limit)
        versions = session.exec(statement).all()
        return [ModelVersion.model_validate(v.model_dump()) for v in versions]

    @router.post("/model-versions", response_model=ModelVersion)
    def create_model_version(version: ModelVersion, session: Session = Depends(get_session)):
        """Create a new model version."""
        db_version = ModelVersionTable(**version.model_dump())
        session.add(db_version)
        session.commit()
        session.refresh(db_version)
        return ModelVersion.model_validate(db_version.model_dump())

    # Dataset endpoints
    @router.get("/datasets", response_model=List[Dataset])
    def list_datasets(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all datasets with pagination."""
        statement = select(DatasetTable).offset(skip).limit(limit)
        datasets = session.exec(statement).all()
        return [Dataset.model_validate(d.model_dump()) for d in datasets]

    @router.get("/datasets/{dataset_id}", response_model=Dataset)
    def get_dataset(dataset_id: str, session: Session = Depends(get_session)):
        """Get a specific dataset by ID."""
        dataset = session.get(DatasetTable, dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return Dataset.model_validate(dataset.model_dump())

    @router.post("/datasets", response_model=Dataset)
    def create_dataset(dataset: Dataset, session: Session = Depends(get_session)):
        """Create a new dataset."""
        db_dataset = DatasetTable(**dataset.model_dump())
        session.add(db_dataset)
        session.commit()
        session.refresh(db_dataset)
        return Dataset.model_validate(db_dataset.model_dump())

    # Versioned Dataset endpoints
    @router.get("/versioned-datasets", response_model=List[VersionedDataset])
    def list_versioned_datasets(
        dataset_id: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all versioned datasets with optional filtering."""
        statement = select(VersionedDatasetTable)
        if dataset_id:
            statement = statement.where(VersionedDatasetTable.dataset_id == dataset_id)
        statement = statement.offset(skip).limit(limit)
        versioned = session.exec(statement).all()
        return [VersionedDataset.model_validate(v.model_dump()) for v in versioned]

    @router.post("/versioned-datasets", response_model=VersionedDataset)
    def create_versioned_dataset(versioned: VersionedDataset, session: Session = Depends(get_session)):
        """Create a new versioned dataset."""
        db_versioned = VersionedDatasetTable(**versioned.model_dump())
        session.add(db_versioned)
        session.commit()
        session.refresh(db_versioned)
        return VersionedDataset.model_validate(db_versioned.model_dump())

    # Policy endpoints
    @router.get("/policies", response_model=List[Policy])
    def list_policies(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all policies with pagination."""
        statement = select(PolicyTable).offset(skip).limit(limit)
        policies = session.exec(statement).all()
        return [Policy.model_validate(p.model_dump()) for p in policies]

    @router.get("/policies/{policy_id}", response_model=Policy)
    def get_policy(policy_id: str, session: Session = Depends(get_session)):
        """Get a specific policy by ID."""
        policy = session.get(PolicyTable, policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return Policy.model_validate(policy.model_dump())

    @router.post("/policies", response_model=Policy)
    def create_policy(policy: Policy, session: Session = Depends(get_session)):
        """Create a new policy."""
        db_policy = PolicyTable(**policy.model_dump())
        session.add(db_policy)
        session.commit()
        session.refresh(db_policy)
        return Policy.model_validate(db_policy.model_dump())

    @router.put("/policies/{policy_id}", response_model=Policy)
    def update_policy(policy_id: str, policy: Policy, session: Session = Depends(get_session)):
        """Update an existing policy."""
        db_policy = session.get(PolicyTable, policy_id)
        if not db_policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        policy_data = policy.model_dump(exclude_unset=True)
        for key, value in policy_data.items():
            setattr(db_policy, key, value)
        session.add(db_policy)
        session.commit()
        session.refresh(db_policy)
        return Policy.model_validate(db_policy.model_dump())

    @router.delete("/policies/{policy_id}")
    def delete_policy(policy_id: str, session: Session = Depends(get_session)):
        """Delete a policy."""
        policy = session.get(PolicyTable, policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        session.delete(policy)
        session.commit()
        return {"message": "Policy deleted successfully"}

    # Simulation endpoints
    @router.get("/simulations", response_model=List[Simulation])
    def list_simulations(
        policy_id: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all simulations with optional filtering."""
        statement = select(SimulationTable)
        if policy_id:
            statement = statement.where(SimulationTable.policy_id == policy_id)
        statement = statement.offset(skip).limit(limit)
        simulations = session.exec(statement).all()
        return [Simulation.model_validate(s.model_dump()) for s in simulations]

    @router.get("/simulations/{simulation_id}", response_model=Simulation)
    def get_simulation(simulation_id: str, session: Session = Depends(get_session)):
        """Get a specific simulation by ID."""
        simulation = session.get(SimulationTable, simulation_id)
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        return Simulation.model_validate(simulation.model_dump())

    @router.post("/simulations", response_model=Simulation)
    def create_simulation(simulation: Simulation, session: Session = Depends(get_session)):
        """Create a new simulation."""
        db_simulation = SimulationTable(**simulation.model_dump())
        session.add(db_simulation)
        session.commit()
        session.refresh(db_simulation)
        return Simulation.model_validate(db_simulation.model_dump())

    # Parameter endpoints
    @router.get("/parameters", response_model=List[Parameter])
    def list_parameters(
        model_id: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all parameters with optional filtering."""
        statement = select(ParameterTable)
        if model_id:
            statement = statement.where(ParameterTable.model_id == model_id)
        statement = statement.offset(skip).limit(limit)
        parameters = session.exec(statement).all()
        return [Parameter.model_validate(p.model_dump()) for p in parameters]

    @router.get("/parameters/{parameter_id}", response_model=Parameter)
    def get_parameter(parameter_id: str, session: Session = Depends(get_session)):
        """Get a specific parameter by ID."""
        parameter = session.get(ParameterTable, parameter_id)
        if not parameter:
            raise HTTPException(status_code=404, detail="Parameter not found")
        return Parameter.model_validate(parameter.model_dump())

    @router.post("/parameters", response_model=Parameter)
    def create_parameter(parameter: Parameter, session: Session = Depends(get_session)):
        """Create a new parameter."""
        db_parameter = ParameterTable(**parameter.model_dump())
        session.add(db_parameter)
        session.commit()
        session.refresh(db_parameter)
        return Parameter.model_validate(db_parameter.model_dump())

    # Parameter Value endpoints
    @router.get("/parameter-values", response_model=List[ParameterValue])
    def list_parameter_values(
        parameter_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all parameter values with optional filtering."""
        statement = select(ParameterValueTable)
        if parameter_id:
            statement = statement.where(ParameterValueTable.parameter_id == parameter_id)
        if policy_id:
            statement = statement.where(ParameterValueTable.policy_id == policy_id)
        statement = statement.offset(skip).limit(limit)
        values = session.exec(statement).all()
        return [ParameterValue.model_validate(v.model_dump()) for v in values]

    @router.post("/parameter-values", response_model=ParameterValue)
    def create_parameter_value(value: ParameterValue, session: Session = Depends(get_session)):
        """Create a new parameter value."""
        db_value = ParameterValueTable(**value.model_dump())
        session.add(db_value)
        session.commit()
        session.refresh(db_value)
        return ParameterValue.model_validate(db_value.model_dump())

    # Baseline Parameter Value endpoints
    @router.get("/baseline-parameter-values", response_model=List[BaselineParameterValue])
    def list_baseline_parameter_values(
        parameter_id: Optional[str] = None,
        model_version_id: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all baseline parameter values with optional filtering."""
        statement = select(BaselineParameterValueTable)
        if parameter_id:
            statement = statement.where(BaselineParameterValueTable.parameter_id == parameter_id)
        if model_version_id:
            statement = statement.where(BaselineParameterValueTable.model_version_id == model_version_id)
        statement = statement.offset(skip).limit(limit)
        values = session.exec(statement).all()
        return [BaselineParameterValue.model_validate(v.model_dump()) for v in values]

    @router.post("/baseline-parameter-values", response_model=BaselineParameterValue)
    def create_baseline_parameter_value(value: BaselineParameterValue, session: Session = Depends(get_session)):
        """Create a new baseline parameter value."""
        db_value = BaselineParameterValueTable(**value.model_dump())
        session.add(db_value)
        session.commit()
        session.refresh(db_value)
        return BaselineParameterValue.model_validate(db_value.model_dump())

    # Baseline Variable endpoints
    @router.get("/baseline-variables", response_model=List[BaselineVariable])
    def list_baseline_variables(
        model_version_id: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all baseline variables with optional filtering."""
        statement = select(BaselineVariableTable)
        if model_version_id:
            statement = statement.where(BaselineVariableTable.model_version_id == model_version_id)
        statement = statement.offset(skip).limit(limit)
        variables = session.exec(statement).all()
        return [BaselineVariable.model_validate(v.model_dump()) for v in variables]

    @router.post("/baseline-variables", response_model=BaselineVariable)
    def create_baseline_variable(variable: BaselineVariable, session: Session = Depends(get_session)):
        """Create a new baseline variable."""
        db_variable = BaselineVariableTable(**variable.model_dump())
        session.add(db_variable)
        session.commit()
        session.refresh(db_variable)
        return BaselineVariable.model_validate(db_variable.model_dump())

    # Dynamic endpoints
    @router.get("/dynamics", response_model=List[Dynamic])
    def list_dynamics(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: Session = Depends(get_session)
    ):
        """List all dynamics with pagination."""
        statement = select(DynamicTable).offset(skip).limit(limit)
        dynamics = session.exec(statement).all()
        return [Dynamic.model_validate(d.model_dump()) for d in dynamics]

    @router.get("/dynamics/{dynamic_id}", response_model=Dynamic)
    def get_dynamic(dynamic_id: str, session: Session = Depends(get_session)):
        """Get a specific dynamic by ID."""
        dynamic = session.get(DynamicTable, dynamic_id)
        if not dynamic:
            raise HTTPException(status_code=404, detail="Dynamic not found")
        return Dynamic.model_validate(dynamic.model_dump())

    @router.post("/dynamics", response_model=Dynamic)
    def create_dynamic(dynamic: Dynamic, session: Session = Depends(get_session)):
        """Create a new dynamic."""
        db_dynamic = DynamicTable(**dynamic.model_dump())
        session.add(db_dynamic)
        session.commit()
        session.refresh(db_dynamic)
        return Dynamic.model_validate(db_dynamic.model_dump())

    return router