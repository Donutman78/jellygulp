from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    jellyfin_connected: bool
    database_connected: bool


class SeerrRequestPayload(BaseModel):
    media_type: Literal["movie", "tv"]
    tmdb_id: int
