from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.db.session import get_db
from app.db.models import Shelter, ShelterWallLayer, SimulationLog, Material, FieldValidationData, RegionalEconomics, utc_now

router = APIRouter()

# Pydantic schemas
class WallLayerCreate(BaseModel):
    material_id: int
    thickness: float # in meters
    layer_order: int # 1 = innermost, 2 = next, etc.

class WallLayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shelter_id: int
    material_id: int
    thickness: float
    layer_order: int
    material_name: Optional[str] = None
    conductivity: Optional[float] = None
    r_value: Optional[float] = None

class ShelterCreate(BaseModel):
    project_name: str
    climate_zone: Optional[str] = "Extreme cold (Ladakh)"
    shape_type: Optional[str] = "Rectangular"
    azimuth_angle: Optional[float] = 0.0
    latitude: float
    longitude: float
    length: float
    width: float
    height: float
    glazing_ratio: float
    wall_layers: Optional[List[WallLayerCreate]] = None

class SimulationLogCreate(BaseModel):
    peak_heating_kw: float
    average_pmv: float
    optimal_insulation_m: Optional[float] = None

class SimulationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shelter_id: int
    simulation_date: Optional[datetime] = None
    peak_heating_kw: float
    average_pmv: float
    optimal_insulation_m: Optional[float] = None

class FieldValidationCreate(BaseModel):
    recorded_at: Optional[datetime] = None
    actual_indoor_temp: float
    actual_humidity: Optional[float] = None
    predicted_indoor_temp: Optional[float] = None
    error_margin: Optional[float] = None

class FieldValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shelter_id: int
    recorded_at: datetime
    actual_indoor_temp: float
    actual_humidity: Optional[float] = None
    predicted_indoor_temp: Optional[float] = None
    error_margin: Optional[float] = None

class ShelterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_name: str
    climate_zone: str
    shape_type: str
    azimuth_angle: float
    latitude: float
    longitude: float
    length: float
    width: float
    height: float
    glazing_ratio: float
    created_at: datetime
    composite_u_value: Optional[float] = None
    total_wall_thickness: Optional[float] = None
    wall_layers: List[WallLayerResponse] = []
    simulation_logs: List[SimulationLogResponse] = []
    field_validations: List[FieldValidationResponse] = []

def calculate_composite_u_value(layers: List[ShelterWallLayer], db: Session) -> dict:
    """
    Calculates composite U-value (W/m2-K) for multi-layered wall:
    R_total = R_si + sum(thickness_i / conductivity_i) + R_se
    U = 1 / R_total
    R_si = 0.13 (internal surface resistance), R_se = 0.04 (external surface resistance)
    """
    r_si = 0.13
    r_se = 0.04
    r_layers = 0.0
    total_thickness = 0.0
    layer_details = []

    for l in sorted(layers, key=lambda x: x.layer_order):
        mat = db.query(Material).filter(Material.id == l.material_id).first()
        k = mat.conductivity if mat else 0.5
        r_layer = l.thickness / k if k > 0 else 0
        r_layers += r_layer
        total_thickness += l.thickness
        layer_details.append({
            "id": l.id,
            "shelter_id": l.shelter_id,
            "material_id": l.material_id,
            "thickness": l.thickness,
            "layer_order": l.layer_order,
            "material_name": mat.name if mat else "Unknown",
            "conductivity": k,
            "r_value": round(r_layer, 4),
        })

    r_total = r_si + r_layers + r_se
    u_value = 1.0 / r_total if r_total > 0 else 0.0

    return {
        "composite_u_value": round(u_value, 4),
        "total_wall_thickness": round(total_thickness, 4),
        "layers": layer_details,
    }

@router.post("/", response_model=ShelterResponse)
async def create_shelter(shelter_in: ShelterCreate, db: Session = Depends(get_db)):
    shelter = Shelter(
        project_name=shelter_in.project_name,
        climate_zone=shelter_in.climate_zone or "Extreme cold (Ladakh)",
        shape_type=shelter_in.shape_type or "Rectangular",
        azimuth_angle=shelter_in.azimuth_angle if shelter_in.azimuth_angle is not None else 0.0,
        latitude=shelter_in.latitude,
        longitude=shelter_in.longitude,
        length=shelter_in.length,
        width=shelter_in.width,
        height=shelter_in.height,
        glazing_ratio=shelter_in.glazing_ratio,
    )
    db.add(shelter)
    db.flush()

    if shelter_in.wall_layers:
        for l_in in shelter_in.wall_layers:
            layer = ShelterWallLayer(
                shelter_id=shelter.id,
                material_id=l_in.material_id,
                thickness=l_in.thickness,
                layer_order=l_in.layer_order,
            )
            db.add(layer)

    db.commit()
    db.refresh(shelter)

    u_info = calculate_composite_u_value(shelter.wall_layers, db)
    return {
        "id": shelter.id,
        "project_name": shelter.project_name,
        "climate_zone": shelter.climate_zone,
        "shape_type": shelter.shape_type,
        "azimuth_angle": shelter.azimuth_angle,
        "latitude": shelter.latitude,
        "longitude": shelter.longitude,
        "length": shelter.length,
        "width": shelter.width,
        "height": shelter.height,
        "glazing_ratio": shelter.glazing_ratio,
        "created_at": shelter.created_at,
        "composite_u_value": u_info["composite_u_value"],
        "total_wall_thickness": u_info["total_wall_thickness"],
        "wall_layers": u_info["layers"],
        "simulation_logs": [],
    }

@router.get("/", response_model=List[ShelterResponse])
async def list_shelters(db: Session = Depends(get_db)):
    shelters = db.query(Shelter).order_by(Shelter.created_at.desc()).all()
    out = []
    for s in shelters:
        u_info = calculate_composite_u_value(s.wall_layers, db)
        out.append({
            "id": s.id,
            "project_name": s.project_name,
            "climate_zone": s.climate_zone,
            "shape_type": s.shape_type,
            "azimuth_angle": s.azimuth_angle,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "length": s.length,
            "width": s.width,
            "height": s.height,
            "glazing_ratio": s.glazing_ratio,
            "created_at": s.created_at,
            "composite_u_value": u_info["composite_u_value"],
            "total_wall_thickness": u_info["total_wall_thickness"],
            "wall_layers": u_info["layers"],
            "simulation_logs": s.simulation_logs,
            "field_validations": s.field_validations,
        })
    return out

@router.get("/{shelter_id}", response_model=ShelterResponse)
async def get_shelter(shelter_id: int, db: Session = Depends(get_db)):
    s = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    u_info = calculate_composite_u_value(s.wall_layers, db)
    return {
        "id": s.id,
        "project_name": s.project_name,
        "climate_zone": s.climate_zone,
        "shape_type": s.shape_type,
        "azimuth_angle": s.azimuth_angle,
        "latitude": s.latitude,
        "longitude": s.longitude,
        "length": s.length,
        "width": s.width,
        "height": s.height,
        "glazing_ratio": s.glazing_ratio,
        "created_at": s.created_at,
        "composite_u_value": u_info["composite_u_value"],
        "total_wall_thickness": u_info["total_wall_thickness"],
        "wall_layers": u_info["layers"],
        "simulation_logs": s.simulation_logs,
        "field_validations": s.field_validations,
    }

@router.post("/{shelter_id}/layers", response_model=ShelterResponse)
async def add_wall_layer(shelter_id: int, layer_in: WallLayerCreate, db: Session = Depends(get_db)):
    s = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    mat = db.query(Material).filter(Material.id == layer_in.material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    layer = ShelterWallLayer(
        shelter_id=shelter_id,
        material_id=layer_in.material_id,
        thickness=layer_in.thickness,
        layer_order=layer_in.layer_order,
    )
    db.add(layer)
    db.commit()
    db.refresh(s)

    u_info = calculate_composite_u_value(s.wall_layers, db)
    return {
        "id": s.id,
        "project_name": s.project_name,
        "climate_zone": s.climate_zone,
        "shape_type": s.shape_type,
        "azimuth_angle": s.azimuth_angle,
        "latitude": s.latitude,
        "longitude": s.longitude,
        "length": s.length,
        "width": s.width,
        "height": s.height,
        "glazing_ratio": s.glazing_ratio,
        "created_at": s.created_at,
        "composite_u_value": u_info["composite_u_value"],
        "total_wall_thickness": u_info["total_wall_thickness"],
        "wall_layers": u_info["layers"],
        "simulation_logs": s.simulation_logs,
        "field_validations": s.field_validations,
    }

@router.post("/{shelter_id}/simulation-logs", response_model=SimulationLogResponse)
async def log_simulation(shelter_id: int, log_in: SimulationLogCreate, db: Session = Depends(get_db)):
    s = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    log = SimulationLog(
        shelter_id=shelter_id,
        peak_heating_kw=log_in.peak_heating_kw,
        average_pmv=log_in.average_pmv,
        optimal_insulation_m=log_in.optimal_insulation_m,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

@router.post("/{shelter_id}/field-validation", response_model=FieldValidationResponse)
async def add_field_validation(shelter_id: int, val_in: FieldValidationCreate, db: Session = Depends(get_db)):
    s = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    # Calculate error margin if not explicitly given
    err = val_in.error_margin
    if err is None and val_in.predicted_indoor_temp is not None:
        err = round(abs(val_in.actual_indoor_temp - val_in.predicted_indoor_temp), 2)
    
    record = FieldValidationData(
        shelter_id=shelter_id,
        recorded_at=val_in.recorded_at or utc_now(),
        actual_indoor_temp=val_in.actual_indoor_temp,
        actual_humidity=val_in.actual_humidity,
        predicted_indoor_temp=val_in.predicted_indoor_temp,
        error_margin=err,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@router.get("/{shelter_id}/field-validation")
async def get_field_validation_summary(shelter_id: int, db: Session = Depends(get_db)):
    s = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    records = db.query(FieldValidationData).filter(FieldValidationData.shelter_id == shelter_id).order_by(FieldValidationData.recorded_at.desc()).all()
    
    errors = [r.error_margin for r in records if r.error_margin is not None]
    mae = round(sum(errors) / len(errors), 2) if errors else 0.0
    max_err = max(errors) if errors else 0.0
    
    return {
        "shelter_id": shelter_id,
        "project_name": s.project_name,
        "sample_count": len(records),
        "mean_absolute_error_celsius": mae,
        "max_deviation_celsius": max_err,
        "validation_records": [
            {
                "id": r.id,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "actual_indoor_temp": r.actual_indoor_temp,
                "actual_humidity": r.actual_humidity,
                "predicted_indoor_temp": r.predicted_indoor_temp,
                "error_margin": r.error_margin,
            }
            for r in records
        ],
    }

@router.get("/economics/benchmarks")
async def get_regional_economics_benchmarks(db: Session = Depends(get_db)):
    """Fetch baseline fuel costs (₹/kWh) and carbon emission factors (kg CO2/kWh) by climate zone."""
    ecos = db.query(RegionalEconomics).all()
    return [
        {
            "id": e.id,
            "climate_zone": e.climate_zone,
            "fuel_cost_per_kwh": e.fuel_cost_per_kwh,
            "carbon_emission_factor": e.carbon_emission_factor,
        }
        for e in ecos
    ]

@router.get("/{shelter_id}/economics")
async def calculate_shelter_roi(shelter_id: int, db: Session = Depends(get_db)):
    """
    Computes Capital Investment, Annual Fuel Savings, Payback Period (ROI), and Carbon Offset.
    Payback Period = Capital Investment (₹) / Annual Savings (₹/year)
    """
    s = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shelter not found")

    # 1. Fetch matching regional economics or fallback
    eco = db.query(RegionalEconomics).filter(RegionalEconomics.climate_zone == s.climate_zone).first()
    fuel_cost_per_kwh = eco.fuel_cost_per_kwh if eco else 24.50
    carbon_factor = eco.carbon_emission_factor if eco else 0.27

    # 2. Estimate shelter envelope surface area (m²)
    # 4 walls + roof
    wall_area = 2 * (s.length * s.height + s.width * s.height)
    roof_area = s.length * s.width
    total_envelope_area = wall_area + roof_area

    # 3. Compute material capital investment for multi-layer envelope
    capital_cost_inr = 0.0
    material_breakdown = []

    for l in s.wall_layers:
        mat = db.query(Material).filter(Material.id == l.material_id).first()
        if mat:
            vol_m3 = wall_area * l.thickness
            mass_kg = vol_m3 * mat.density
            unit_cost = mat.cost_per_kg if mat.cost_per_kg and mat.cost_per_kg > 0 else 120.0
            layer_cost = round(mass_kg * unit_cost, 2)
            capital_cost_inr += layer_cost
            material_breakdown.append({
                "material_name": mat.name,
                "thickness_m": l.thickness,
                "mass_kg": round(mass_kg, 1),
                "cost_per_kg": unit_cost,
                "layer_cost_inr": layer_cost,
                "is_pcm": bool(mat.latent_heat and mat.latent_heat > 0),
                "latent_heat_j_kg": mat.latent_heat,
            })

    # If no custom layers yet, estimate baseline insulation cost
    if capital_cost_inr == 0:
        capital_cost_inr = round(total_envelope_area * 0.10 * 30.0 * 180.0, 2) # ~0.1m EPS equivalent

    # 4. Determine energy savings from simulation log vs uninsulated baseline
    latest_log = db.query(SimulationLog).filter(SimulationLog.shelter_id == shelter_id).order_by(SimulationLog.simulation_date.desc()).first()
    
    # Baseline heating energy demand for extreme climate post (~18,500 kWh/yr)
    baseline_annual_kwh = 18500.0
    if latest_log and latest_log.peak_heating_kw:
        # Optimized annual demand scaled from peak heating ratio
        optimized_annual_kwh = max(3500.0, min(14000.0, latest_log.peak_heating_kw * 1800.0))
    else:
        optimized_annual_kwh = 5200.0

    annual_kwh_saved = max(1000.0, baseline_annual_kwh - optimized_annual_kwh)
    annual_cost_savings_inr = round(annual_kwh_saved * fuel_cost_per_kwh, 2)
    carbon_reduction_kg = round(annual_kwh_saved * carbon_factor, 2)

    # 5. Calculate simple payback period (ROI)
    payback_years = round(capital_cost_inr / annual_cost_savings_inr, 2) if annual_cost_savings_inr > 0 else 0.0

    return {
        "shelter_id": shelter_id,
        "project_name": s.project_name,
        "climate_zone": s.climate_zone,
        "fuel_cost_per_kwh": fuel_cost_per_kwh,
        "carbon_emission_factor": carbon_factor,
        "capital_investment_inr": round(capital_cost_inr, 2),
        "baseline_heating_kwh_per_year": baseline_annual_kwh,
        "optimized_heating_kwh_per_year": round(optimized_annual_kwh, 2),
        "annual_energy_saved_kwh": round(annual_kwh_saved, 2),
        "annual_fuel_savings_inr": annual_cost_savings_inr,
        "payback_period_years": payback_years,
        "carbon_emissions_avoided_kg_per_year": carbon_reduction_kg,
        "material_breakdown": material_breakdown,
    }


