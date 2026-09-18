"""
ML Prediction Module
====================
Loads trained models and provides prediction interface for the API.

Usage:
    from ml.predict import ThermalMLPredictor
    predictor = ThermalMLPredictor()
    result = predictor.predict(features)
"""

import os
import json
import numpy as np
import joblib
from typing import Dict, List, Optional

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_models")

REGRESSION_TARGETS = [
    "total_heating_energy_mwh",
    "heat_flux_w_m2",
    "mean_indoor_temp_c",
    "heating_degree_days",
    "peak_heating_w",
    "comfort_ratio",
]

FEATURE_COLS = [
    "density",
    "specific_heat",
    "thermal_conductivity",
    "emissivity",
    "solar_absorptance",
    "thickness",
    "u_value",
    "thermal_resistance",
    "volumetric_heat_capacity",
    "length",
    "width",
    "height",
    "window_area",
    "glazing_ratio",
    "wall_area",
    "roof_area",
    "total_envelope_area",
    "elevation_m",
    "mean_humidity",
    "mean_wind_speed",
    "mean_solar_radiation",
    "temp_range",
    "freeze_thaw_cycles",
    "snow_depth_max",
    "dust_storm_days",
]

CATEGORICAL_COLS = ["region_key", "material_key"]

REGION_ELEVATIONS = {
    "leh": 3524,
    "kargil": 2676,
    "srinagar": 1585,
    "baramulla": 1590,
    "jaisalmer": 171,
    "bikaner": 237,
}

REGION_CLIMATE_STATS = {
    "leh": {"humidity": 36, "wind": 4.5, "solar": 5.5, "temp_range": 68, "frost": 120, "snow": 65, "dust": 0},
    "kargil": {"humidity": 42, "wind": 3.8, "solar": 5.2, "temp_range": 63, "frost": 100, "snow": 45, "dust": 0},
    "srinagar": {"humidity": 62, "wind": 3.2, "solar": 4.8, "temp_range": 53, "frost": 85, "snow": 80, "dust": 0},
    "baramulla": {"humidity": 64, "wind": 3.0, "solar": 4.6, "temp_range": 53, "frost": 80, "snow": 85, "dust": 0},
    "jaisalmer": {"humidity": 28, "wind": 5.0, "solar": 6.2, "temp_range": 49, "frost": 0, "snow": 0, "dust": 25},
    "bikaner": {"humidity": 38, "wind": 4.5, "solar": 5.8, "temp_range": 46, "frost": 0, "snow": 0, "dust": 15},
}

MATERIAL_DB = {
    "concrete": {"density": 2400, "cp": 880, "k": 1.7, "eps": 0.9, "alpha": 0.7},
    "brick": {"density": 1800, "cp": 840, "k": 0.84, "eps": 0.9, "alpha": 0.7},
    "fly_ash_brick": {"density": 1600, "cp": 850, "k": 0.62, "eps": 0.9, "alpha": 0.7},
    "stone": {"density": 2200, "cp": 800, "k": 1.7, "eps": 0.9, "alpha": 0.7},
    "granite": {"density": 2650, "cp": 820, "k": 2.8, "eps": 0.9, "alpha": 0.7},
    "adobe": {"density": 1700, "cp": 880, "k": 0.68, "eps": 0.9, "alpha": 0.6},
    "rammed_earth": {"density": 1900, "cp": 840, "k": 0.80, "eps": 0.9, "alpha": 0.6},
    "wood": {"density": 550, "cp": 1200, "k": 0.12, "eps": 0.9, "alpha": 0.7},
    "hardwood": {"density": 720, "cp": 1210, "k": 0.16, "eps": 0.9, "alpha": 0.7},
    "bamboo": {"density": 700, "cp": 1580, "k": 0.16, "eps": 0.9, "alpha": 0.6},
    "eps": {"density": 25, "cp": 1450, "k": 0.035, "eps": 0.9, "alpha": 0.3},
    "xps": {"density": 35, "cp": 1400, "k": 0.030, "eps": 0.9, "alpha": 0.3},
    "puf": {"density": 32, "cp": 1500, "k": 0.022, "eps": 0.9, "alpha": 0.3},
    "glass_wool": {"density": 24, "cp": 840, "k": 0.040, "eps": 0.9, "alpha": 0.3},
    "rock_wool": {"density": 80, "cp": 840, "k": 0.038, "eps": 0.9, "alpha": 0.3},
    "aac_block": {"density": 600, "cp": 1000, "k": 0.16, "eps": 0.9, "alpha": 0.7},
    "cement_mortar": {"density": 1800, "cp": 840, "k": 0.72, "eps": 0.9, "alpha": 0.7},
    "lime_mortar": {"density": 1600, "cp": 840, "k": 0.69, "eps": 0.9, "alpha": 0.7},
    "steel": {"density": 7850, "cp": 480, "k": 50.0, "eps": 0.9, "alpha": 0.7},
    "aluminium": {"density": 2700, "cp": 920, "k": 205.0, "eps": 0.9, "alpha": 0.5},
    "glass": {"density": 2500, "cp": 750, "k": 1.0, "eps": 0.84, "alpha": 0.85},
    "clay_tile": {"density": 1900, "cp": 840, "k": 0.84, "eps": 0.9, "alpha": 0.7},
    "calcium_silicate": {"density": 870, "cp": 1000, "k": 0.17, "eps": 0.9, "alpha": 0.5},
    "gypsum_board": {"density": 800, "cp": 1000, "k": 0.16, "eps": 0.9, "alpha": 0.5},
    "plywood": {"density": 600, "cp": 1200, "k": 0.13, "eps": 0.9, "alpha": 0.7},
    "aerogel": {"density": 200, "cp": 1000, "k": 0.015, "eps": 0.9, "alpha": 0.3},
    "phenolic_foam": {"density": 40, "cp": 1400, "k": 0.022, "eps": 0.9, "alpha": 0.3},
    "expanded_clay": {"density": 1200, "cp": 880, "k": 0.45, "eps": 0.9, "alpha": 0.7},
    "cellular_concrete": {"density": 600, "cp": 1000, "k": 0.18, "eps": 0.9, "alpha": 0.7},
    "cseb": {"density": 1750, "cp": 880, "k": 0.72, "eps": 0.9, "alpha": 0.6},
}


class ThermalMLPredictor:
    """Load trained models and predict thermal performance."""

    def __init__(self, model_dir: str = MODEL_DIR):
        self.model_dir = model_dir
        self.models = {}
        self.scaler = None
        self.le_dict = {}
        self.feature_cols = []
        self.results = {}
        self._loaded = False

    def load(self):
        """Load all models and preprocessing artifacts."""
        if self._loaded:
            return

        scaler_path = os.path.join(self.model_dir, "scaler.joblib")
        le_path = os.path.join(self.model_dir, "label_encoders.joblib")
        feat_path = os.path.join(self.model_dir, "feature_columns.joblib")
        results_path = os.path.join(self.model_dir, "training_results.json")

        if not os.path.exists(scaler_path):
            raise FileNotFoundError(
                f"Models not found at {self.model_dir}. Run training first: python -m ml.train"
            )

        self.scaler = joblib.load(scaler_path)
        self.le_dict = joblib.load(le_path)
        self.feature_cols = joblib.load(feat_path)

        with open(results_path) as f:
            self.results = json.load(f)

        for fname in os.listdir(self.model_dir):
            if fname.startswith("model_") and fname.endswith(".joblib"):
                target_name = fname[6:-8]
                self.models[target_name] = joblib.load(
                    os.path.join(self.model_dir, fname)
                )

        self._loaded = True

    def _build_features(
        self,
        material_key: str,
        region_key: str,
        thickness: float,
        length: float,
        width: float,
        height: float,
        glazing_ratio: float = 0.10,
        window_area: float = None,
        custom_material_props: dict = None,
    ) -> np.ndarray:
        """Build feature vector from input parameters."""
        mat = MATERIAL_DB.get(material_key, MATERIAL_DB["concrete"])
        if custom_material_props:
            mat.update(custom_material_props)

        wall_area = 2 * (length + width) * height
        roof_area = length * width
        floor_area = length * width
        if window_area is None:
            window_area = glazing_ratio * wall_area
        total_area = wall_area + roof_area + floor_area + window_area

        u_value = mat["k"] / thickness if thickness > 0 else 999.0
        thermal_resistance = thickness / mat["k"] if mat["k"] > 0 else 0.0

        region_stats = REGION_CLIMATE_STATS.get(region_key, REGION_CLIMATE_STATS["leh"])
        elevation = REGION_ELEVATIONS.get(region_key, 1500)

        features = [
            mat["density"],
            mat["cp"],
            mat["k"],
            mat["eps"],
            mat["alpha"],
            thickness,
            u_value,
            thermal_resistance,
            mat["density"] * mat["cp"],
            length,
            width,
            height,
            window_area,
            glazing_ratio,
            wall_area,
            roof_area,
            total_area,
            elevation,
            region_stats["humidity"],
            region_stats["wind"],
            region_stats["solar"],
            region_stats["temp_range"],
            region_stats["frost"],
            region_stats["snow"],
            region_stats["dust"],
        ]

        X = np.array(features).reshape(1, -1)

        for col in CATEGORICAL_COLS:
            le = self.le_dict.get(col)
            if le is not None:
                val = region_key if col == "region_key" else material_key
                if val in le.classes_:
                    encoded = le.transform([val])[0]
                else:
                    encoded = 0
                X = np.hstack([X, [[encoded]]])

        return X

    def predict(
        self,
        material_key: str,
        region_key: str,
        thickness: float = 0.20,
        length: float = 5.0,
        width: float = 4.0,
        height: float = 3.0,
        glazing_ratio: float = 0.10,
        window_area: float = None,
        custom_material_props: dict = None,
    ) -> Dict:
        """
        Predict thermal performance for a shelter assembly.

        Returns dict with predictions for all targets plus compliance.
        """
        self.load()

        X = self._build_features(
            material_key, region_key, thickness,
            length, width, height, glazing_ratio,
            window_area, custom_material_props,
        )
        X_scaled = self.scaler.transform(X)

        predictions = {}
        for target_name in REGRESSION_TARGETS:
            if target_name in self.models:
                pred = self.models[target_name].predict(X_scaled)[0]
                predictions[target_name] = float(pred)

        if "compliance_label" in self.models:
            pred_clf = self.models["compliance_label"].predict(X_scaled)[0]
            proba = None
            if hasattr(self.models["compliance_label"], "predict_proba"):
                proba = self.models["compliance_label"].predict_proba(X_scaled)[0].tolist()
            predictions["compliance_label"] = bool(pred_clf)
            predictions["compliance_probability"] = proba

        predictions["input"] = {
            "material": material_key,
            "region": region_key,
            "thickness_m": thickness,
            "geometry": {"length": length, "width": width, "height": height},
            "glazing_ratio": glazing_ratio,
        }

        if material_key in MATERIAL_DB:
            mat = MATERIAL_DB[material_key]
            predictions["material_properties"] = {
                "density": mat["density"],
                "thermal_conductivity": mat["k"],
                "specific_heat": mat["cp"],
                "u_value": mat["k"] / thickness if thickness > 0 else None,
            }

        return predictions

    def batch_predict(self, params_list: List[Dict]) -> List[Dict]:
        """Predict for multiple assemblies."""
        self.load()
        results = []
        for params in params_list:
            try:
                result = self.predict(**params)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "input": params})
        return results

    def get_model_info(self) -> Dict:
        """Return model metadata and performance summary."""
        self.load()
        info = {}
        for target, res in self.results.items():
            if target == "cross_validation":
                info["cross_validation"] = res
                continue
            info[target] = {
                "model": res.get("model_name"),
                "test_r2": res.get("test_r2"),
                "test_mae": res.get("test_mae"),
                "test_rmse": res.get("test_rmse"),
                "test_accuracy": res.get("test_accuracy"),
                "test_f1": res.get("test_f1"),
            }
        return info


_predictor: Optional[ThermalMLPredictor] = None


def get_predictor() -> ThermalMLPredictor:
    """Singleton predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = ThermalMLPredictor()
    return _predictor


if __name__ == "__main__":
    predictor = ThermalMLPredictor()
    predictor.load()

    print("=" * 72)
    print("  ML Prediction Module — Demo")
    print("=" * 72)

    info = predictor.get_model_info()
    print("\n  Model Info:")
    for target, details in info.items():
        print(f"    {target}: {details}")

    test_cases = [
        {"material_key": "eps", "region_key": "leh", "thickness": 0.08, "length": 5.0, "width": 4.0, "height": 3.0},
        {"material_key": "brick", "region_key": "jaisalmer", "thickness": 0.23, "length": 6.0, "width": 5.0, "height": 3.0},
        {"material_key": "adobe", "region_key": "srinagar", "thickness": 0.30, "length": 4.0, "width": 3.5, "height": 2.8},
        {"material_key": "aerogel", "region_key": "leh", "thickness": 0.02, "length": 5.0, "width": 4.0, "height": 3.0},
    ]

    for case in test_cases:
        print(f"\n  Prediction: {case['material_key']} @ {case['region_key']}, "
              f"t={case['thickness']}m, {case['length']}x{case['width']}x{case['height']}m")
        result = predictor.predict(**case)
        for key, val in result.items():
            if key not in ("input", "material_properties", "compliance_probability"):
                if isinstance(val, float):
                    print(f"    {key}: {val:.4f}")
                else:
                    print(f"    {key}: {val}")
