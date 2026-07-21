from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    jellyfin_connected: bool
    database_connected: bool
