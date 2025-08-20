from pydantic import BaseModel


class EntityRole(BaseModel):
    plural: str
    label: str
    doc: str


class Entity(BaseModel):
    plural: str
    label: str
    doc: str
    is_person: bool
    key: str  # Unsure if this is actually str or int; will check when validation errors occur
    roles: dict[str, EntityRole] = {}
