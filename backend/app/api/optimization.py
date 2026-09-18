"""
Multi-Objective Optimization API Endpoints
===========================================
FastAPI endpoints for shelter thermal optimization.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
import numpy as np
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import get_db
from app.db.models import Simulation, SimulationResult, OptimizationRun
from app.services.nasa_power import nasa_power_service

router = APIRouter(prefix="/optimization", tags=["Multi-Objective Optimization"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class WallLayerInput(BaseModel):
    material_key: str = Field(..., description="Material key (e.g. 'eps', 'brick', 'aerogel')")
    min_thickness: float = Field(0.01, ge=0.002, le=0.50, description="Minimum thickness (m)")
    max_thickness: float = Field(0.20, ge=0.005, le=0.50, description="Maximum thickness (m)")
    is_fixed: bool = Field(False, description="If True, thickness is fixed (not optimized)")
    fixed_thickness: float = Field(0.10, description="Fixed thickness when is_fixed=True")


class OptimizationRequest(BaseModel):
    latitude: float = Field(..., description="Site latitude")
    longitude: float = Field(..., description="Site longitude")
    wall_layers: List[WallLayerInput] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Wall layer assembly (inside to outside)",
    )
    length: float = Field(5.0, ge=2.0, le=20.0, description="Shelter length (m)")
    width: float = Field(4.0, ge=2.0, le=20.0, description="Shelter width (m)")
    height: float = Field(3.0, ge=2.0, le=6.0, description="Shelter height (m)")
    glazing_ratio_min: float = Field(0.05, ge=0.0, le=0.50)
    glazing_ratio_max: float = Field(0.30, ge=0.05, le=0.60)
    w_energy: float = Field(1.0, ge=0.0, le=10.0, description="Weight for heating energy")
    w_mass: float = Field(0.5, ge=0.0, le=10.0, description="Weight for transport mass")
    w_discomfort: float = Field(2.0, ge=0.0, le=10.0, description="Weight for discomfort hours")
    w_cost: float = Field(0.3, ge=0.0, le=5.0, description="Weight for cost")
    max_envelope_mass_kg: float = Field(5000.0, ge=100.0, le=50000.0, description="Max transport mass (kg)")
    max_u_value: float = Field(0.35, ge=0.05, le=2.0, description="Max wall U-value (W/m2.K)")
    solver: str = Field("SLSQP", description="Solver: SLSQP, L-BFGS-B, differential_evolution")
    max_iterations: int = Field(150, ge=20, le=500)
    initial_temp: float = Field(20.0, description="Initial indoor temperature (C)")
    project_name: Optional[str] = Field(None, description="Project name for DB record")


class ParetoRequest(BaseModel):
    latitude: float
    longitude: float
    wall_layers: List[WallLayerInput]
    length: float = 5.0
    width: float = 4.0
    height: float = 3.0
    glazing_ratio_min: float = 0.05
    glazing_ratio_max: float = 0.30
    max_envelope_mass_kg: float = 5000.0
    max_u_value: float = 0.35
    n_pareto_samples: int = Field(100, ge=20, le=500, description="Number of Pareto front samples")
    initial_temp: float = 20.0
    project_name: Optional[str] = None


class MaterialSensitivityRequest(BaseModel):
    latitude: float
    longitude: float
    material_key: str
    thickness_range: List[float] = Field(
        [0.02, 0.05, 0.08, 0.10, 0.15, 0.20],
        description="List of thicknesses to test",
    )
    length: float = 5.0
    width: float = 4.0
    height: float = 3.0
    glazing_ratio: float = 0.15


class OptimalDesignResponse(BaseModel):
    status: str
    solver: str
    solve_time_s: float
    layer_thicknesses: List[Dict]
    glazing_ratio: float
    total_heating_energy_mwh: float
    envelope_mass_kg: float
    discomfort_hours: float
    total_cost: float
    cost_per_m2: float
    u_value_wall: float
    compliance_status: bool
    fire_rating_hours: float
    total_objective: float
    comfort_hours: int
    average_pmv: float
    min_temp: float
    max_temp: float
    avg_temp: float
    material_summary: List[Dict]
    convergence_history: List[float]
    indoor_temperatures: Optional[List[float]] = None
    heating_loads: Optional[List[float]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/optimize", response_model=OptimalDesignResponse)
async def run_optimization(request: OptimizationRequest, db: Session = Depends(get_db)):
    """
    Run multi-objective optimization to find optimal shelter wall assembly.

    Minimizes: J(x) = w_E * E_heating + w_M * M_envelope + w_D * D_discomfort
    Subject to: mass, U-value, structural, and glazing constraints.
    """
    try:
        from app.core.optimizer import (
            OptimizationConfig,
            WallLayerConfig,
            ShelterOptimizer,
        )

        wall_layers = []
        for wl in request.wall_layers:
            wall_layers.append(WallLayerConfig(
                material_key=wl.material_key,
                min_thickness=wl.min_thickness,
                max_thickness=wl.max_thickness,
                is_fixed=wl.is_fixed,
                fixed_thickness=wl.fixed_thickness,
            ))

        config = OptimizationConfig(
            wall_layers=wall_layers,
            length=request.length,
            width=request.width,
            height=request.height,
            glazing_ratio_min=request.glazing_ratio_min,
            glazing_ratio_max=request.glazing_ratio_max,
            initial_temp=request.initial_temp,
            w_energy=request.w_energy,
            w_mass=request.w_mass,
            w_discomfort=request.w_discomfort,
            w_cost=request.w_cost,
            max_envelope_mass_kg=request.max_envelope_mass_kg,
            max_u_value=request.max_u_value,
            solver=request.solver,
            max_iterations=request.max_iterations,
        )

        end_date = __import__("datetime").datetime.now().strftime("%Y%m%d")
        start_date = (__import__("datetime").datetime.now().replace(year=__import__("datetime").datetime.now().year - 1)).strftime("%Y%m%d")
        climate_data = nasa_power_service.fetch_climate_data(
            request.latitude, request.longitude, start_date, end_date
        )

        from app.core.thermal_engine import ClimateData
        climate = ClimateData(
            temperature=np.array(climate_data["temperature"]),
            solar_radiation=np.array(climate_data["solar_radiation"]),
            wind_speed=np.array(climate_data["wind_speed"]),
            humidity=np.array(climate_data["humidity"]),
            timestamps=np.array(climate_data["timestamps"]),
        )

        optimizer = ShelterOptimizer(config, climate)
        result = optimizer.optimize()

        from app.core.optimizer import OPTIMIZER_MATERIALS

        layer_summary = []
        for i, wl in enumerate(wall_layers):
            mat = OPTIMIZER_MATERIALS.get(wl.material_key, {})
            layer_summary.append({
                "material_key": wl.material_key,
                "material_name": mat.get("name", wl.material_key),
                "thickness_m": result.layer_thicknesses[i],
                "density_kg_m3": mat.get("density", 0),
                "conductivity_w_mk": mat.get("k", 0),
                "r_value_m2k_w": result.layer_thicknesses[i] / mat.get("k", 1.0) if mat.get("k", 0) > 0 else 0,
                "cost_per_kg": mat.get("cost_per_kg", 0),
            })

        opt_run = OptimizationRun(
            region=f"{request.latitude:.2f}, {request.longitude:.2f}",
            objectives={
                "energy": "total_heating_energy_mwh",
                "mass": "envelope_mass_kg",
                "discomfort": "discomfort_hours",
                "cost": "total_cost",
            },
            constraints={
                "max_mass_kg": request.max_envelope_mass_kg,
                "max_u_value": request.max_u_value,
            },
            best_solution={
                "layer_thicknesses": result.layer_thicknesses,
                "glazing_ratio": result.glazing_ratio,
                "energy_mwh": result.total_heating_energy_mwh,
                "mass_kg": result.envelope_mass_kg,
                "discomfort_hours": result.discomfort_hours,
                "cost": result.total_cost,
            },
            source_materials=[wl.material_key for wl in wall_layers],
        )
        db.add(opt_run)
        db.commit()

        return OptimalDesignResponse(
            status="success",
            solver=result.solver_name,
            solve_time_s=round(result.solve_time_s, 3),
            layer_thicknesses=layer_summary,
            glazing_ratio=round(result.glazing_ratio, 4),
            total_heating_energy_mwh=round(result.total_heating_energy_mwh, 4),
            envelope_mass_kg=round(result.envelope_mass_kg, 2),
            discomfort_hours=round(result.discomfort_hours, 1),
            total_cost=round(result.total_cost, 2),
            cost_per_m2=round(result.cost_per_m2, 2),
            u_value_wall=round(result.u_value_wall, 4),
            compliance_status=result.compliance_status,
            fire_rating_hours=round(result.fire_rating_hours, 1),
            total_objective=round(result.total_objective, 6),
            comfort_hours=result.comfort_hours,
            average_pmv=round(result.average_pmv, 3),
            min_temp=round(result.min_temp, 2),
            max_temp=round(result.max_temp, 2),
            avg_temp=round(result.avg_temp, 2),
            material_summary=result.material_summary,
            convergence_history=result.convergence_history[-50:] if result.convergence_history else [],
            indoor_temperatures=result.indoor_temperatures[:168] if result.indoor_temperatures else None,
            heating_loads=result.heating_loads[:168] if result.heating_loads else None,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/pareto")
async def generate_pareto_front(request: ParetoRequest, db: Session = Depends(get_db)):
    """
    Generate Pareto front by varying objective weights.
    Returns non-dominated solutions across energy, mass, and comfort objectives.
    """
    try:
        from app.core.optimizer import (
            OptimizationConfig,
            WallLayerConfig,
            ShelterOptimizer,
        )

        wall_layers = []
        for wl in request.wall_layers:
            wall_layers.append(WallLayerConfig(
                material_key=wl.material_key,
                min_thickness=wl.min_thickness,
                max_thickness=wl.max_thickness,
                is_fixed=wl.is_fixed,
                fixed_thickness=wl.fixed_thickness,
            ))

        config = OptimizationConfig(
            wall_layers=wall_layers,
            length=request.length,
            width=request.width,
            height=request.height,
            glazing_ratio_min=request.glazing_ratio_min,
            glazing_ratio_max=request.glazing_ratio_max,
            initial_temp=request.initial_temp,
            max_envelope_mass_kg=request.max_envelope_mass_kg,
            max_u_value=request.max_u_value,
            solver="SLSQP",
            max_iterations=100,
            n_pareto_samples=request.n_pareto_samples,
        )

        end_date = __import__("datetime").datetime.now().strftime("%Y%m%d")
        start_date = (__import__("datetime").datetime.now().replace(year=__import__("datetime").datetime.now().year - 1)).strftime("%Y%m%d")
        climate_data = nasa_power_service.fetch_climate_data(
            request.latitude, request.longitude, start_date, end_date
        )

        from app.core.thermal_engine import ClimateData
        climate = ClimateData(
            temperature=np.array(climate_data["temperature"]),
            solar_radiation=np.array(climate_data["solar_radiation"]),
            wind_speed=np.array(climate_data["wind_speed"]),
            humidity=np.array(climate_data["humidity"]),
            timestamps=np.array(climate_data["timestamps"]),
        )

        optimizer = ShelterOptimizer(config, climate)
        pareto = optimizer.generate_pareto_front(request.n_pareto_samples)

        solutions = []
        for sol in pareto.solutions:
            solutions.append({
                "layer_thicknesses": sol.layer_thicknesses,
                "glazing_ratio": round(sol.glazing_ratio, 4),
                "energy_mwh": round(sol.total_heating_energy_mwh, 4),
                "mass_kg": round(sol.envelope_mass_kg, 2),
                "discomfort_hours": round(sol.discomfort_hours, 1),
                "cost": round(sol.total_cost, 2),
                "cost_per_m2": round(sol.cost_per_m2, 2),
                "u_value": round(sol.u_value_wall, 4),
                "compliant": sol.compliance_status,
                "objective": round(sol.total_objective, 6),
            })

        return {
            "status": "success",
            "n_solutions": len(solutions),
            "energy_range": pareto.energy_range,
            "mass_range": pareto.mass_range,
            "discomfort_range": pareto.discomfort_range,
            "solutions": solutions,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pareto generation failed: {str(e)}")


@router.post("/sensitivity")
async def material_sensitivity(request: MaterialSensitivityRequest):
    """
    Analyze sensitivity of a single material's thickness on thermal performance.
    Returns energy, mass, and comfort metrics for each thickness.
    """
    try:
        from app.core.optimizer import (
            OptimizationConfig,
            WallLayerConfig,
            ShelterOptimizer,
        )
        from app.core.thermal_engine import ClimateData

        results = []
        for thickness in request.thickness_range:
            config = OptimizationConfig(
                wall_layers=[
                    WallLayerConfig(request.material_key, thickness, thickness, is_fixed=True, fixed_thickness=thickness),
                ],
                length=request.length,
                width=request.width,
                height=request.height,
                glazing_ratio_min=request.glazing_ratio,
                glazing_ratio_max=request.glazing_ratio,
                initial_temp=20.0,
                w_energy=1.0,
                w_mass=0.0,
                w_discomfort=0.0,
                max_envelope_mass_kg=99999.0,
                max_u_value=2.0,
                solver="SLSQP",
                max_iterations=50,
            )

            end_date = __import__("datetime").datetime.now().strftime("%Y%m%d")
            start_date = (__import__("datetime").datetime.now().replace(year=__import__("datetime").datetime.now().year - 1)).strftime("%Y%m%d")
            climate_data = nasa_power_service.fetch_climate_data(
                request.latitude, request.longitude, start_date, end_date
            )

            climate = ClimateData(
                temperature=np.array(climate_data["temperature"]),
                solar_radiation=np.array(climate_data["solar_radiation"]),
                wind_speed=np.array(climate_data["wind_speed"]),
                humidity=np.array(climate_data["humidity"]),
                timestamps=np.array(climate_data["timestamps"]),
            )

            optimizer = ShelterOptimizer(config, climate)
            result = optimizer.optimize()

            results.append({
                "thickness_m": thickness,
                "energy_mwh": round(result.total_heating_energy_mwh, 4),
                "mass_kg": round(result.envelope_mass_kg, 2),
                "discomfort_hours": round(result.discomfort_hours, 1),
                "u_value": round(result.u_value_wall, 4),
                "cost": round(result.total_cost, 2),
            })

        return {
            "status": "success",
            "material": request.material_key,
            "results": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sensitivity analysis failed: {str(e)}")


@router.get("/presets")
async def get_optimization_presets():
    """
    Return predefined optimization configurations for common mission profiles.
    """
    return {
        "presets": {
            "leh_defense": {
                "name": "Leh Defense Shelter",
                "description": "High-altitude defense shelter for Ladakh region",
                "wall_layers": [
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                    {"material_key": "eps", "min_thickness": 0.03, "max_thickness": 0.15},
                    {"material_key": "brick", "min_thickness": 0.10, "max_thickness": 0.25},
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                ],
                "w_energy": 1.5,
                "w_mass": 1.0,
                "w_discomfort": 2.5,
                "max_envelope_mass_kg": 4000.0,
                "max_u_value": 0.30,
            },
            "rapid_airlift": {
                "name": "Rapid Airlift Deployment",
                "description": "Ultra-light shelter for helicopter/airlift deployment",
                "wall_layers": [
                    {"material_key": "aerogel", "min_thickness": 0.005, "max_thickness": 0.05},
                    {"material_key": "plywood", "min_thickness": 0.005, "max_thickness": 0.02},
                ],
                "w_energy": 1.0,
                "w_mass": 3.0,
                "w_discomfort": 1.5,
                "max_envelope_mass_kg": 800.0,
                "max_u_value": 0.25,
            },
            "permanent_base": {
                "name": "Permanent Base Construction",
                "description": "Standard permanent shelter with cost optimization",
                "wall_layers": [
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                    {"material_key": "xps", "min_thickness": 0.03, "max_thickness": 0.12},
                    {"material_key": "brick", "min_thickness": 0.10, "max_thickness": 0.30},
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                ],
                "w_energy": 1.5,
                "w_mass": 0.2,
                "w_discomfort": 3.0,
                "w_cost": 0.8,
                "max_envelope_mass_kg": 15000.0,
                "max_u_value": 0.30,
            },
            "jaisalmer_heat": {
                "name": "Jaisalmer Heat Shield",
                "description": "Heat-resistant shelter for extreme desert conditions",
                "wall_layers": [
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                    {"material_key": "rock_wool", "min_thickness": 0.03, "max_thickness": 0.12},
                    {"material_key": "brick", "min_thickness": 0.10, "max_thickness": 0.25},
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                ],
                "w_energy": 1.0,
                "w_mass": 0.5,
                "w_discomfort": 2.0,
                "max_envelope_mass_kg": 5000.0,
                "max_u_value": 0.40,
            },
            "armoured_shelter": {
                "name": "Armoured Defence Shelter",
                "description": "Protected shelter with fire-resistant and ballistic layers",
                "wall_layers": [
                    {"material_key": "steel", "min_thickness": 0.002, "max_thickness": 0.015},
                    {"material_key": "calcium_silicate", "min_thickness": 0.005, "max_thickness": 0.03},
                    {"material_key": "rock_wool", "min_thickness": 0.02, "max_thickness": 0.10},
                    {"material_key": "steel", "min_thickness": 0.002, "max_thickness": 0.015},
                ],
                "w_energy": 1.0,
                "w_mass": 1.5,
                "w_discomfort": 2.0,
                "max_envelope_mass_kg": 6000.0,
                "max_u_value": 0.30,
            },
            "kashmir_cold": {
                "name": "Kashmir Valley Cold Shelter",
                "description": "Shelter optimized for Kashmir's cold, humid winters",
                "wall_layers": [
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                    {"material_key": "puf", "min_thickness": 0.02, "max_thickness": 0.12},
                    {"material_key": "aac_block", "min_thickness": 0.10, "max_thickness": 0.25},
                    {"material_key": "cement_mortar", "min_thickness": 0.01, "max_thickness": 0.03},
                ],
                "w_energy": 1.5,
                "w_mass": 0.8,
                "w_discomfort": 2.5,
                "max_envelope_mass_kg": 3500.0,
                "max_u_value": 0.28,
            },
        }
    }


@router.get("/materials")
async def get_optimization_materials():
    """List all materials available for optimization with their properties."""
    from app.core.optimizer import OPTIMIZER_MATERIALS

    materials = []
    for key, props in OPTIMIZER_MATERIALS.items():
        materials.append({
            "key": key,
            "name": props["name"],
            "density": props["density"],
            "conductivity": props["k"],
            "specific_heat": props["cp"],
            "cost_per_kg": props["cost_per_kg"],
            "min_thickness": props["min_thickness"],
            "max_thickness": props["max_thickness"],
            "is_structural": props["is_structural"],
            "compressive_strength_mpa": props["compressive_strength_mpa"],
            "fire_rating_hours": props["fire_rating_hours"],
        })
    return {"materials": materials, "count": len(materials)}
