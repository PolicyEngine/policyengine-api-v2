from fastapi.responses import PlainTextResponse
from fastapi import APIRouter


router = APIRouter()


@router.get("/readiness-check", response_class=PlainTextResponse)
async def readiness_check():
    return "OK"
