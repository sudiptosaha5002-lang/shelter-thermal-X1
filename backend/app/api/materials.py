from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.db.session import get_db
from app.db.models import Material
from app.core.thermal_engine import thermal_engine

router = APIRouter()

class MaterialCreate(BaseModel):
    name: str
    density: float
    specific_heat: float
    conductivity: Optional[float] = None
    thermal_conductivity: Optional[float] = None
    latent_heat: float = 0.0 # J/kg
    melting_temp: Optional[float] = None # °C
    cost_per_kg: float = 0.0 # Currency/kg
    display_name: Optional[str] = None
    emissivity: float = 0.9
    solar_absorptance: float = 0.7
    thickness: float = 0.1
    description: str = ""

class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    density: float
    specific_heat: float
    conductivity: float
    thermal_conductivity: float
    latent_heat: Optional[float] = 0.0
    melting_temp: Optional[float] = None
    cost_per_kg: Optional[float] = 0.0
    display_name: Optional[str] = None
    emissivity: Optional[float] = 0.9
    solar_absorptance: Optional[float] = 0.7
    thickness: Optional[float] = 0.1
    description: Optional[str] = ""

@router.get("/", response_model=List[MaterialResponse])
async def get_materials(db: Session = Depends(get_db)):
    materials = db.query(Material).all()
    if not materials:
        return _get_default_materials()
    return materials

@router.get("/defaults")
async def get_default_materials():
    return _get_default_materials()

def _get_default_materials():
    return [
        {
            "id": 1,
            "name": "EPS Insulation",
            "display_name": "EPS Insulation",
            "density": 30.0,
            "specific_heat": 1450.0,
            "conductivity": 0.035,
            "thermal_conductivity": 0.035,
            "emissivity": 0.9,
            "solar_absorptance": 0.3,
            "thickness": 0.1,
            "description": "Expanded Polystyrene Insulation (High R-value)",
        },
        {
            "id": 2,
            "name": "Plywood Outer",
            "display_name": "Plywood Outer",
            "density": 600.0,
            "specific_heat": 1200.0,
            "conductivity": 0.13,
            "thermal_conductivity": 0.13,
            "emissivity": 0.9,
            "solar_absorptance": 0.7,
            "thickness": 0.02,
            "description": "Engineered wood structural sheathing",
        },
        {
            "id": 3,
            "name": "Adobe Brick",
            "display_name": "Adobe Brick",
            "density": 1700.0,
            "specific_heat": 1000.0,
            "conductivity": 0.75,
            "thermal_conductivity": 0.75,
            "emissivity": 0.9,
            "solar_absorptance": 0.6,
            "thickness": 0.3,
            "description": "High thermal mass sun-dried earth brick",
        },
        {
            "id": 4,
            "name": "concrete",
            "display_name": "Concrete",
            "density": 2400.0,
            "specific_heat": 880.0,
            "conductivity": 1.7,
            "thermal_conductivity": 1.7,
            "emissivity": 0.9,
            "solar_absorptance": 0.7,
            "thickness": 0.2,
            "description": "Standard reinforced concrete",
        },
        {
            "id": 5,
            "name": "brick",
            "display_name": "Brick",
            "density": 1800.0,
            "specific_heat": 840.0,
            "conductivity": 0.7,
            "thermal_conductivity": 0.7,
            "emissivity": 0.9,
            "solar_absorptance": 0.7,
            "thickness": 0.2,
            "description": "Traditional clay brick",
        },
        {
            "id": 6,
            "name": "stone",
            "display_name": "Stone",
            "density": 2600.0,
            "specific_heat": 790.0,
            "conductivity": 2.5,
            "thermal_conductivity": 2.5,
            "emissivity": 0.9,
            "solar_absorptance": 0.7,
            "thickness": 0.3,
            "description": "Natural stone masonry",
        },
        {
            "id": 7,
            "name": "wood",
            "display_name": "Wood",
            "density": 600.0,
            "specific_heat": 1500.0,
            "conductivity": 0.15,
            "thermal_conductivity": 0.15,
            "emissivity": 0.9,
            "solar_absorptance": 0.7,
            "thickness": 0.15,
            "description": "Timber construction",
        },
        {
            "id": 8,
            "name": "pcm",
            "display_name": "Phase Change Material",
            "density": 1500.0,
            "specific_heat": 2000.0,
            "conductivity": 0.2,
            "thermal_conductivity": 0.2,
            "emissivity": 0.9,
            "solar_absorptance": 0.5,
            "thickness": 0.05,
            "description": "PCM-enhanced wallboard for thermal storage",
        },
    ]

@router.post("/", response_model=MaterialResponse)
async def create_material(material: MaterialCreate, db: Session = Depends(get_db)):
    existing = db.query(Material).filter(Material.name == material.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Material already exists")
    
    cond = material.conductivity if material.conductivity is not None else material.thermal_conductivity
    if cond is None:
        raise HTTPException(status_code=400, detail="Either conductivity or thermal_conductivity is required")
        
    db_material = Material(
        name=material.name,
        conductivity=cond,
        density=material.density,
        specific_heat=material.specific_heat,
        latent_heat=material.latent_heat,
        melting_temp=material.melting_temp,
        cost_per_kg=material.cost_per_kg,
        display_name=material.display_name or material.name,
        emissivity=material.emissivity,
        solar_absorptance=material.solar_absorptance,
        thickness=material.thickness,
        description=material.description,
    )
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    return db_material

@router.get("/{material_name}/properties")
async def get_material_properties(material_name: str):
    material = thermal_engine.materials_db.get(material_name)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return {
        "name": material.name,
        "density": material.density,
        "specific_heat": material.specific_heat,
        "thermal_conductivity": material.thermal_conductivity,
        "emissivity": material.emissivity,
        "solar_absorptance": material.solar_absorptance,
        "thickness": material.thickness,
        "u_value": material.thermal_conductivity / material.thickness,
    }