from fastapi import Header, HTTPException
from app.config import get_settings


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != get_settings().api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
