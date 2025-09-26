"""Pydantic schemas for API responses that handle binary data properly."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import base64


def encode_bytes(b: bytes | None) -> str | None:
    """Encode bytes to base64 string for JSON serialization."""
    if b is None:
        return None
    return base64.b64encode(b).decode('utf-8')


def decode_bytes(s: str | None) -> bytes | None:
    """Decode base64 string back to bytes."""
    if s is None:
        return None
    return base64.b64decode(s)


# Model schemas
class ModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    simulation_function: Optional[str] = Field(None, description="Base64 encoded simulation function")

    @staticmethod
    def from_orm(obj):
        return ModelResponse(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            simulation_function=encode_bytes(obj.simulation_function)
        )


class ModelCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    simulation_function: str  # Base64 encoded

    def to_orm_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "simulation_function": decode_bytes(self.simulation_function)
        }


class ModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    simulation_function: Optional[str] = None  # Base64 encoded


# Policy schemas
class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    simulation_modifier: Optional[str] = Field(None, description="Base64 encoded simulation modifier")
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_orm(obj):
        return PolicyResponse(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            simulation_modifier=encode_bytes(obj.simulation_modifier),
            created_at=obj.created_at,
            updated_at=obj.updated_at
        )


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    simulation_modifier: Optional[str] = None  # Base64 encoded

    def to_orm_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "simulation_modifier": decode_bytes(self.simulation_modifier) if self.simulation_modifier else None
        }


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    simulation_modifier: Optional[str] = None  # Base64 encoded


# Simulation schemas
class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    policy_id: Optional[str] = None
    dynamic_id: Optional[str] = None
    dataset_id: str
    model_id: str
    model_version_id: Optional[str] = None
    result: Optional[str] = Field(None, description="Base64 encoded result")

    @staticmethod
    def from_orm(obj):
        return SimulationResponse(
            id=obj.id,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            policy_id=obj.policy_id,
            dynamic_id=obj.dynamic_id,
            dataset_id=obj.dataset_id,
            model_id=obj.model_id,
            model_version_id=obj.model_version_id,
            result=encode_bytes(obj.result)
        )


class SimulationCreate(BaseModel):
    policy_id: Optional[str] = None
    dynamic_id: Optional[str] = None
    dataset_id: str
    model_id: str
    model_version_id: Optional[str] = None
    result: Optional[str] = None  # Base64 encoded

    def to_orm_dict(self):
        return {
            "policy_id": self.policy_id,
            "dynamic_id": self.dynamic_id,
            "dataset_id": self.dataset_id,
            "model_id": self.model_id,
            "model_version_id": self.model_version_id,
            "result": decode_bytes(self.result) if self.result else None
        }


# Dataset schemas
class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DatasetCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


# Versioned Dataset schemas
class VersionedDatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    version_name: str
    data: Optional[str] = Field(None, description="Base64 encoded data")

    @staticmethod
    def from_orm(obj):
        return VersionedDatasetResponse(
            id=obj.id,
            dataset_id=obj.dataset_id,
            version_name=obj.version_name,
            data=encode_bytes(obj.data)
        )


class VersionedDatasetCreate(BaseModel):
    dataset_id: str
    version_name: str
    data: Optional[str] = None  # Base64 encoded

    def to_orm_dict(self):
        return {
            "dataset_id": self.dataset_id,
            "version_name": self.version_name,
            "data": decode_bytes(self.data) if self.data else None
        }


# Parameter schemas
class ParameterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    model_id: str


class ParameterCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    model_id: str


# Parameter Value schemas
class ParameterValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    parameter_id: str
    policy_id: str
    value: Optional[str] = Field(None, description="Base64 encoded value")
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_orm(obj):
        return ParameterValueResponse(
            id=obj.id,
            parameter_id=obj.parameter_id,
            policy_id=obj.policy_id,
            value=encode_bytes(obj.value),
            created_at=obj.created_at,
            updated_at=obj.updated_at
        )


class ParameterValueCreate(BaseModel):
    parameter_id: str
    policy_id: str
    value: Optional[str] = None  # Base64 encoded

    def to_orm_dict(self):
        return {
            "parameter_id": self.parameter_id,
            "policy_id": self.policy_id,
            "value": decode_bytes(self.value) if self.value else None
        }


# Baseline Parameter Value schemas
class BaselineParameterValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    parameter_id: str
    model_id: str
    value: Optional[str] = Field(None, description="Base64 encoded value")

    @staticmethod
    def from_orm(obj):
        return BaselineParameterValueResponse(
            id=obj.id,
            parameter_id=obj.parameter_id,
            model_id=obj.model_id,
            value=encode_bytes(obj.value)
        )


class BaselineParameterValueCreate(BaseModel):
    parameter_id: str
    model_id: str
    value: Optional[str] = None  # Base64 encoded

    def to_orm_dict(self):
        return {
            "parameter_id": self.parameter_id,
            "model_id": self.model_id,
            "value": decode_bytes(self.value) if self.value else None
        }


# Baseline Variable schemas
class BaselineVariableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    variable_name: str
    model_id: str
    model_version_id: Optional[str] = None
    value: Optional[str] = Field(None, description="Base64 encoded value")

    @staticmethod
    def from_orm(obj):
        return BaselineVariableResponse(
            id=obj.id,
            variable_name=obj.variable_name,
            model_id=obj.model_id,
            model_version_id=obj.model_version_id,
            value=encode_bytes(obj.value)
        )


class BaselineVariableCreate(BaseModel):
    variable_name: str
    model_id: str
    model_version_id: Optional[str] = None
    value: Optional[str] = None  # Base64 encoded

    def to_orm_dict(self):
        return {
            "variable_name": self.variable_name,
            "model_id": self.model_id,
            "model_version_id": self.model_version_id,
            "value": decode_bytes(self.value) if self.value else None
        }


# Dynamic schemas
class DynamicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    years: list[int]


class DynamicCreate(BaseModel):
    name: str
    description: Optional[str] = None
    years: list[int]


# Model Version schemas
class ModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_id: str
    version_name: str


class ModelVersionCreate(BaseModel):
    model_id: str
    version_name: str