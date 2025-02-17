from fastapi.responses import PlainTextResponse
from fastapi import APIRouter


def create_router():
    router = APIRouter()

    @router.get("/liveness_check", response_class=PlainTextResponse)
    async def liveness_check():
        return "OK"

    return router
