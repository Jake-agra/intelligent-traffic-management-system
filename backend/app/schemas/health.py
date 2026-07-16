from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    service_name: str
    api_version: str
    environment: str
    api_status: str
    database_status: str

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "service_name": "Intelligent Traffic Management System API",
            "api_version": "0.1.0",
            "environment": "development",
            "api_status": "ok",
            "database_status": "ok",
        }
    })
