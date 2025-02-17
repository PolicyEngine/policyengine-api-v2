from fastapi.responses import PlainTextResponse
from fastapi import APIRouter


def create_router():
    router = APIRouter()

    @router.get("/readiness_check", response_class=PlainTextResponse)
    async def readiness_check():
        return "OK"

    return router
