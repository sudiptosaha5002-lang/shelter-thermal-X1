import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
    with engine.connect():
        pass
except Exception:
    DATABASE_URL = "sqlite:///./shelter_optimizer.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import text

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Ensure new columns exist on materials table in existing database
        for col, col_type in [("latent_heat", "FLOAT DEFAULT 0.0"), ("melting_temp", "FLOAT DEFAULT NULL"), ("cost_per_kg", "FLOAT DEFAULT 0.0")]:
            try:
                db.execute(text(f"ALTER TABLE materials ADD COLUMN {col} {col_type}"))
                db.commit()
            except Exception:
                db.rollback()

        from app.db.models import Material, RegionalEconomics
        default_materials = [
            {"name": "EPS Insulation", "conductivity": 0.035, "density": 30.0, "specific_heat": 1450.0, "latent_heat": 0.0, "melting_temp": None, "cost_per_kg": 180.0, "display_name": "EPS Insulation", "thickness": 0.1},
            {"name": "Plywood Outer", "conductivity": 0.13, "density": 600.0, "specific_heat": 1200.0, "latent_heat": 0.0, "melting_temp": None, "cost_per_kg": 95.0, "display_name": "Plywood Outer", "thickness": 0.02},
            {"name": "Adobe Brick", "conductivity": 0.75, "density": 1700.0, "specific_heat": 1000.0, "latent_heat": 0.0, "melting_temp": None, "cost_per_kg": 15.0, "display_name": "Adobe Brick", "thickness": 0.3},
            {"name": "Paraffin PCM Wallboard", "conductivity": 0.21, "density": 850.0, "specific_heat": 2200.0, "latent_heat": 190000.0, "melting_temp": 22.0, "cost_per_kg": 320.0, "display_name": "Paraffin PCM Wallboard", "thickness": 0.03},
            {"name": "Bio-based PCM Composite", "conductivity": 0.18, "density": 900.0, "specific_heat": 2400.0, "latent_heat": 210000.0, "melting_temp": 21.5, "cost_per_kg": 380.0, "display_name": "Bio-based PCM Composite", "thickness": 0.03},
        ]
        for m_data in default_materials:
            existing = db.query(Material).filter(Material.name == m_data["name"]).first()
            if not existing:
                db.add(Material(**m_data))
            else:
                for k, v in m_data.items():
                    if getattr(existing, k) is None and v is not None:
                        setattr(existing, k, v)
        db.commit()

        default_economics = [
            {"climate_zone": "Extreme cold (Ladakh)", "fuel_cost_per_kwh": 24.50, "carbon_emission_factor": 0.27},
            {"climate_zone": "Extreme heat (Rajasthan)", "fuel_cost_per_kwh": 8.50, "carbon_emission_factor": 0.82},
            {"climate_zone": "Moderate / Hill Station", "fuel_cost_per_kwh": 9.20, "carbon_emission_factor": 0.75},
        ]
        for eco in default_economics:
            if not db.query(RegionalEconomics).filter(RegionalEconomics.climate_zone == eco["climate_zone"]).first():
                db.add(RegionalEconomics(**eco))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()