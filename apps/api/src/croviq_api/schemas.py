from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health status")
    service: str = Field(default="croviq-api", description="Service identifier")
    git_sha: str = Field(description="Current git commit SHA or environment identifier")
