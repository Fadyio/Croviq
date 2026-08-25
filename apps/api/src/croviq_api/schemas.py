from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health status")
    service: str = Field(default="croviq-api", description="Service identifier")
    git_sha: str = Field(description="Current git commit SHA or environment identifier")


class DemoAccessRestrictedResponse(BaseModel):
    error_code: str = Field(default="demo_access_restricted", description="Error code identifier")
    message: str = Field(
        default="This Croviq demo is restricted to an approved account.",
        description="User-facing error explanation",
    )
