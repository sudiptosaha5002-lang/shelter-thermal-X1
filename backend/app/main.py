from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import simulation, climate, materials, shelters, ml_prediction, optimization
from app.core.config import settings
from app.db.session import init_db

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Shelter Thermal Optimizer API",
    description="API for passive shelter thermal simulation and optimization",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulation.router, prefix="/api/v1/simulation", tags=["simulation"])
app.include_router(climate.router, prefix="/api/v1/climate", tags=["climate"])
app.include_router(materials.router, prefix="/api/v1/materials", tags=["materials"])
app.include_router(shelters.router, prefix="/api/v1/shelters", tags=["shelters"])
app.include_router(ml_prediction.router, prefix="/api/v1", tags=["ML Prediction"])
app.include_router(optimization.router, prefix="/api/v1", tags=["Multi-Objective Optimization"])

from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import SimulationLog
from typing import Union
from app.api.simulation import run_simulation, SimulationRequest, EnhancedSimulationRequest

@app.post("/api/v1/simulate", tags=["simulation"])
async def run_thermal_simulation(req: Union[EnhancedSimulationRequest, SimulationRequest], db: Session = Depends(get_db)):
    """Run transient thermal simulation and record key metrics to SimulationLog."""
    return await run_simulation(req, db)

@app.get("/api/v1/history", tags=["simulation"])
def get_simulation_history(db: Session = Depends(get_db)):
    """Fetch previous optimization/simulation runs for the dashboard."""
    logs = db.query(SimulationLog).order_by(SimulationLog.simulation_date.desc()).limit(10).all()
    return logs

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "shelter-thermal-optimizer"}