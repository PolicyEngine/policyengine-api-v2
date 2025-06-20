from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, Field
from policyengine_api.fastapi.database import SessionGeneratorFactory


class HouseholdBase(SQLModel):
    pass


class Household(HouseholdBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class HouseholdCreate(HouseholdBase):
    pass


def create_router(session_dependency: SessionGeneratorFactory):
    router = APIRouter()

    @router.post("/household")
    async def create_houshold(
        item: HouseholdCreate,
        session: Annotated[Session, Depends(session_dependency)],
    ) -> Household:
        model = Household.model_validate(item)
        session.add(model)
        session.commit()
        session.refresh(model)

        return model

    def _get_household(id: int, session: Session) -> Household:
        model = session.get(Household, id)
        if not model:
            raise HTTPException(status_code=404, detail="Household not found")
        return model

    @router.get("/household/{id}")
    async def get_household(
        id: int, session: Annotated[Session, Depends(session_dependency)]
    ) -> Household:
        return _get_household(id, session)

    @router.delete("/household/{id}")
    async def delete_household(
        id: int, session: Annotated[Session, Depends(session_dependency)]
    ) -> None:
        model = _get_household(id, session)
        session.delete(model)
        session.commit()

    return router
