import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import (
    Base,
    Material,
    Shelter,
    ShelterWallLayer,
    SimulationLog,
    FieldValidationData,
    ClimateCache,
    RegionalEconomics,
    ClimateData,
    Simulation,
    SimulationResult,
)

# Reads from docker-compose environment variables or default PostgreSQL credentials
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://thermal_admin:securepassword123@localhost:5432/shelter_db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
    # Check if database is reachable; if not, fallback to SQLite for local development
    with engine.connect():
        pass
except Exception:
    DATABASE_URL = "sqlite:///./shelter_optimizer.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
