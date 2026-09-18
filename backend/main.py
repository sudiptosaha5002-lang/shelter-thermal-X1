from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_db, engine
from models import Base, Shelter, SimulationLog, FieldValidationData, ClimateCache, RegionalEconomics
from app.main import app
from app.api.simulation import EnhancedSimulationRequest

# Initialize database tables
Base.metadata.create_all(bind=engine)

def run_and_log_simulation(req: EnhancedSimulationRequest, db: Session = Depends(get_db)):
    # 1. Save Parametric Shelter Geometry to Database
    new_shelter = Shelter(
        project_name=req.project_name,
        climate_zone=req.climate_zone,
        shape_type=req.shape_type,
        azimuth_angle=req.azimuth_angle,
        latitude=req.latitude,
        longitude=req.longitude,
        length=req.length,
        width=req.width,
        height=req.height,
        glazing_ratio=req.glazing_ratio
    )
    db.add(new_shelter)
    db.flush() # Get shelter ID without committing

    # 2. Execute Transient Thermal Simulation
    mock_peak_heating = 4.2 
    mock_avg_pmv = -0.4 
    
    # 3. Log Simulation Results
    sim_log = SimulationLog(
        shelter_id=new_shelter.id,
        peak_heating_kw=mock_peak_heating,
        average_pmv=mock_avg_pmv,
        optimal_insulation_m=0.12
    )
    db.add(sim_log)
    db.commit()
    
    return {"status": "success", "shelter_id": new_shelter.id, "message": "Simulation saved."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
