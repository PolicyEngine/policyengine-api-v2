from fastapi.responses import PlainTextResponse
from fastapi import APIRouter
import sys


router = APIRouter()


@router.get("/liveness-check", response_class=PlainTextResponse)
async def liveness_check():
    print("liveness check", file=sys.stderr)
    return "OK"
