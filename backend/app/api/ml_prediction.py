"""
ML Prediction API Endpoints
============================
FastAPI endpoints for ML-based thermal performance prediction.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/ml", tags=["ML Prediction"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class PredictionRequest(BaseModel):
    material_key: str = Field(..., description="Material key (e.g. 'brick', 'eps', 'adobe')")
    region_key: str = Field(..., description="Region key (e.g. 'leh', 'jaisalmer', 'srinagar')")
    thickness: float = Field(0.20, description="Wall thickness in meters")
    length: float = Field(5.0, description="Shelter length in meters")
    width: float = Field(4.0, description="Shelter width in meters")
    height: float = Field(3.0, description="Shelter height in meters")
    glazing_ratio: float = Field(0.10, description="Window-to-wall ratio (0-1)")
    window_area: Optional[float] = Field(None, description="Window area in m2 (overrides glazing_ratio)")
    custom_material_props: Optional[Dict] = Field(None, description="Override material properties")


class BatchPredictionRequest(BaseModel):
    predictions: List[PredictionRequest]


class PredictionResponse(BaseModel):
    total_heating_energy_mwh: Optional[float] = None
    heat_flux_w_m2: Optional[float] = None
    mean_indoor_temp_c: Optional[float] = None
    heating_degree_days: Optional[float] = None
    peak_heating_w: Optional[float] = None
    comfort_ratio: Optional[float] = None
    compliance_label: Optional[bool] = None
    compliance_probability: Optional[List[float]] = None
    input: Optional[Dict] = None
    material_properties: Optional[Dict] = None


class ModelInfoResponse(BaseModel):
    target: str
    model: Optional[str] = None
    test_r2: Optional[float] = None
    test_mae: Optional[float] = None
    test_rmse: Optional[float] = None
    test_accuracy: Optional[float] = None
    test_f1: Optional[float] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/predict", response_model=PredictionResponse)
async def predict_thermal_performance(request: PredictionRequest):
    """
    Predict thermal performance of a shelter assembly using trained ML models.

    Returns predicted heating energy, heat flux, indoor temperature,
    compliance status, and more.
    """
    try:
        from ml.predict import get_predictor
        predictor = get_predictor()

        result = predictor.predict(
            material_key=request.material_key,
            region_key=request.region_key,
            thickness=request.thickness,
            length=request.length,
            width=request.width,
            height=request.height,
            glazing_ratio=request.glazing_ratio,
            window_area=request.window_area,
            custom_material_props=request.custom_material_props,
        )
        return PredictionResponse(**result)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="ML models not found. Run training first: python -m ml.train",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/batch")
async def predict_batch(request: BatchPredictionRequest):
    """
    Batch prediction for multiple shelter assemblies.
    """
    try:
        from ml.predict import get_predictor
        predictor = get_predictor()

        params_list = [p.model_dump() for p in request.predictions]
        results = predictor.batch_predict(params_list)
        return {"predictions": results, "count": len(results)}
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="ML models not found. Run training first: python -m ml.train",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/info")
async def get_model_info():
    """
    Get metadata and performance summary for all trained models.
    """
    try:
        from ml.predict import get_predictor
        predictor = get_predictor()
        info = predictor.get_model_info()
        return info
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="ML models not found. Run training first: python -m ml.train",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/materials")
async def get_available_materials():
    """
    List all available material keys for prediction.
    """
    from ml.predict import MATERIAL_DB
    materials = []
    for key, props in MATERIAL_DB.items():
        materials.append({
            "key": key,
            "density": props["density"],
            "thermal_conductivity": props["k"],
            "specific_heat": props["cp"],
        })
    return {"materials": materials, "count": len(materials)}


@router.get("/regions")
async def get_available_regions():
    """
    List all available region keys for prediction.
    """
    from ml.predict import REGION_CLIMATE_STATS, REGION_ELEVATIONS
    regions = []
    for key, stats in REGION_CLIMATE_STATS.items():
        regions.append({
            "key": key,
            "elevation_m": REGION_ELEVATIONS.get(key),
            **stats,
        })
    return {"regions": regions, "count": len(regions)}


@router.get("/compare")
async def compare_materials(
    region_key: str = Query(..., description="Region key"),
    thickness: float = Query(0.20, description="Wall thickness in meters"),
    length: float = Query(5.0),
    width: float = Query(4.0),
    height: float = Query(3.0),
    glazing_ratio: float = Query(0.10),
):
    """
    Compare all materials for a given region and geometry.
    Returns ranked predictions by heating energy.
    """
    try:
        from ml.predict import get_predictor, MATERIAL_DB
        predictor = get_predictor()

        results = []
        for mat_key in MATERIAL_DB:
            try:
                pred = predictor.predict(
                    material_key=mat_key,
                    region_key=region_key,
                    thickness=thickness,
                    length=length,
                    width=width,
                    height=height,
                    glazing_ratio=glazing_ratio,
                )
                results.append({
                    "material": mat_key,
                    "energy_mwh": pred.get("total_heating_energy_mwh"),
                    "heat_flux": pred.get("heat_flux_w_m2"),
                    "indoor_temp": pred.get("mean_indoor_temp_c"),
                    "compliant": pred.get("compliance_label"),
                })
            except Exception:
                continue

        results.sort(key=lambda x: x.get("energy_mwh") or float("inf"))
        return {
            "region": region_key,
            "thickness": thickness,
            "rankings": results,
            "best": results[0] if results else None,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="ML models not found. Run training first: python -m ml.train",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
