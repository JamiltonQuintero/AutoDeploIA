from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1.api import api_router_v1
from app.database.database import engine # Import engine
from app.database.models import Base # Import Base

# Lifespan context manager for startup/shutdown logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: 
    # The dedicated 'migrations' service in docker-compose.yml now handles migrations.
    # Programmatic migration runs from here have been removed to avoid redundancy and errors.
    print("Application startup: Database migrations are handled by the 'migrations' service.")

    yield
    # Shutdown logic: Clean up resources if needed
    print("Application shutdown.")

app = FastAPI(
    title="AutoDeploIA Agent API",
    version="0.1.0",
    lifespan=lifespan # Use the lifespan manager
)

# Include the API router
app.include_router(api_router_v1, prefix="/api/v1")

# Root endpoint for basic health check
@app.get("/", tags=["Health"])
async def read_root():
    return {"message": "Welcome to the AutoDeploIA Agent API"}


if __name__ == "__main__":
    import uvicorn
    # Ensure to run with reload for development if you change uvicorn call elsewhere
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
