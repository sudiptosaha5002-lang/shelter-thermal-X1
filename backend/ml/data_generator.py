"""
Training Data Generator
=======================
Generates synthetic training data by running the thermal engine across
different material, climate, and geometry combinations.

Uses the lumped-capacitance transient thermal model to produce
heat flux, energy demand, surface temperature, and compliance labels.
"""

import numpy as np
import pandas as pd
from itertools import product
from typing import List, Dict, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.thermal_engine import (
    ThermalEngine,
    MaterialProperties,
    ShelterGeometry,
    ClimateData,
)


# ---------------------------------------------------------------------------
# Material library — from BEE ECBC / BMTPC / seed_materials.py
# ---------------------------------------------------------------------------
MATERIAL_LIBRARY: Dict[str, MaterialProperties] = {
    "concrete": MaterialProperties("Concrete", 2400, 880, 1.7, 0.9, 0.7, 0.2),
    "brick": MaterialProperties("Brick (Clay)", 1800, 840, 0.84, 0.9, 0.7, 0.2),
    "fly_ash_brick": MaterialProperties("Fly-Ash Brick", 1600, 850, 0.62, 0.9, 0.7, 0.2),
    "stone": MaterialProperties("Sandstone", 2200, 800, 1.7, 0.9, 0.7, 0.3),
    "granite": MaterialProperties("Granite", 2650, 820, 2.8, 0.9, 0.7, 0.3),
    "adobe": MaterialProperties("Adobe", 1700, 880, 0.68, 0.9, 0.6, 0.3),
    "rammed_earth": MaterialProperties("Rammed Earth", 1900, 840, 0.80, 0.9, 0.6, 0.3),
    "wood": MaterialProperties("Timber (Softwood)", 550, 1200, 0.12, 0.9, 0.7, 0.15),
    "hardwood": MaterialProperties("Timber (Hardwood)", 720, 1210, 0.16, 0.9, 0.7, 0.15),
    "bamboo": MaterialProperties("Bamboo", 700, 1580, 0.16, 0.9, 0.6, 0.15),
    "eps": MaterialProperties("EPS Insulation", 25, 1450, 0.035, 0.9, 0.3, 0.1),
    "xps": MaterialProperties("XPS Insulation", 35, 1400, 0.030, 0.9, 0.3, 0.1),
    "puf": MaterialProperties("PUF Insulation", 32, 1500, 0.022, 0.9, 0.3, 0.1),
    "glass_wool": MaterialProperties("Glass Wool", 24, 840, 0.040, 0.9, 0.3, 0.1),
    "rock_wool": MaterialProperties("Rock Wool", 80, 840, 0.038, 0.9, 0.3, 0.1),
    "aac_block": MaterialProperties("AAC Block", 600, 1000, 0.16, 0.9, 0.7, 0.2),
    "cement_mortar": MaterialProperties("Cement Mortar", 1800, 840, 0.72, 0.9, 0.7, 0.05),
    "lime_mortar": MaterialProperties("Lime Mortar", 1600, 840, 0.69, 0.9, 0.7, 0.05),
    "steel": MaterialProperties("Structural Steel", 7850, 480, 50.0, 0.9, 0.7, 0.01),
    "aluminium": MaterialProperties("Aluminium", 2700, 920, 205.0, 0.9, 0.5, 0.01),
    "glass": MaterialProperties("Float Glass", 2500, 750, 1.0, 0.84, 0.85, 0.006),
    "clay_tile": MaterialProperties("Clay Roofing Tile", 1900, 840, 0.84, 0.9, 0.7, 0.02),
    "calcium_silicate": MaterialProperties("Calcium Silicate Board", 870, 1000, 0.17, 0.9, 0.5, 0.015),
    "gypsum_board": MaterialProperties("Gypsum Board", 800, 1000, 0.16, 0.9, 0.5, 0.015),
    "plywood": MaterialProperties("Plywood", 600, 1200, 0.13, 0.9, 0.7, 0.02),
    "aerogel": MaterialProperties("Aerogel Blanket", 200, 1000, 0.015, 0.9, 0.3, 0.02),
    "phenolic_foam": MaterialProperties("Phenolic Foam", 40, 1400, 0.022, 0.9, 0.3, 0.02),
    "expanded_clay": MaterialProperties("Expanded Clay Concrete", 1200, 880, 0.45, 0.9, 0.7, 0.2),
    "cellular_concrete": MaterialProperties("Cellular Lightweight Concrete", 600, 1000, 0.18, 0.9, 0.7, 0.2),
    "cseb": MaterialProperties("Stabilised CSEB", 1750, 880, 0.72, 0.9, 0.6, 0.2),
}


# ---------------------------------------------------------------------------
# Climate profiles — from IMD design values
# ---------------------------------------------------------------------------
def generate_climate_profile(
    region: str,
    base_temp_min: float,
    base_temp_max: float,
    humidity_mean: float,
    humidity_range: float,
    wind_mean: float,
    wind_range: float,
    solar_peak: float,
    precip_mm_year: float,
    elevation_m: float,
    snow_depth_max: float = 0.0,
    freeze_thaw_cycles: int = 0,
    dust_storm_days: int = 0,
) -> dict:
    """Return a climate parameter dict for a region."""
    return {
        "region": region,
        "base_temp_min": base_temp_min,
        "base_temp_max": base_temp_max,
        "humidity_mean": humidity_mean,
        "humidity_range": humidity_range,
        "wind_mean": wind_mean,
        "wind_range": wind_range,
        "solar_peak": solar_peak,
        "precip_mm_year": precip_mm_year,
        "elevation_m": elevation_m,
        "snow_depth_max": snow_depth_max,
        "freeze_thaw_cycles": freeze_thaw_cycles,
        "dust_storm_days": dust_storm_days,
    }


REGION_CLIMATES = {
    "leh": generate_climate_profile(
        "Leh, Ladakh", -33.0, 35.0, 36.0, 25.0, 4.5, 3.0, 5.5, 102, 3524, 65, 120, 0,
    ),
    "kargil": generate_climate_profile(
        "Kargil, Ladakh", -25.0, 38.0, 42.0, 30.0, 3.8, 2.5, 5.2, 150, 2676, 45, 100, 0,
    ),
    "srinagar": generate_climate_profile(
        "Srinagar, Kashmir", -16.0, 37.0, 62.0, 40.0, 3.2, 2.5, 4.8, 720, 1585, 80, 85, 0,
    ),
    "baramulla": generate_climate_profile(
        "Baramulla, Kashmir", -15.0, 38.0, 64.0, 42.0, 3.0, 2.5, 4.6, 780, 1590, 85, 80, 0,
    ),
    "jaisalmer": generate_climate_profile(
        "Jaisalmer, Rajasthan", 2.0, 51.0, 28.0, 30.0, 5.0, 4.0, 6.2, 170, 171, 0, 0, 25,
    ),
    "bikaner": generate_climate_profile(
        "Bikaner, Rajasthan", 1.0, 47.0, 38.0, 28.0, 4.5, 3.5, 5.8, 280, 237, 0, 0, 15,
    ),
}


# ---------------------------------------------------------------------------
# Synthetic hourly climate data generator (8760 hours)
# ---------------------------------------------------------------------------
def generate_hourly_climate(profile: dict, n_hours: int = 8760) -> ClimateData:
    """
    Generate synthetic hourly climate data from regional design values.
    Uses sinusoidal diurnal + seasonal patterns with noise.
    """
    rng = np.random.default_rng(42)
    hours = np.arange(n_hours)
    day_of_year = (hours // 24) % 365
    hour_of_day = hours % 24

    t_min = profile["base_temp_min"]
    t_max = profile["base_temp_max"]
    t_mid = (t_min + t_max) / 2
    t_amp = (t_max - t_min) / 2

    seasonal = t_mid + t_amp * np.sin(2 * np.pi * (day_of_year - 80) / 365)
    diurnal = t_amp * 0.3 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    temp = seasonal + diurnal + rng.normal(0, 1.5, n_hours)
    temp = np.clip(temp, t_min - 2, t_max + 2)

    solar_base = profile["solar_peak"] * 1000 / 24
    solar = np.zeros(n_hours)
    for h in range(n_hours):
        hod = hour_of_day[h]
        if 6 <= hod <= 18:
            solar[h] = solar_base * np.sin(np.pi * (hod - 6) / 12)
        solar[h] *= max(0.3, 1.0 + 0.3 * np.sin(2 * np.pi * day_of_year[h] / 365))
        solar[h] += rng.normal(0, solar_base * 0.05)
    solar = np.maximum(solar, 0)

    rh_mean = profile["humidity_mean"]
    rh_range = profile["humidity_range"]
    humidity = rh_mean + rh_range * 0.3 * np.sin(2 * np.pi * (day_of_year - 170) / 365)
    humidity += rh_range * 0.2 * np.sin(2 * np.pi * (hour_of_day - 3) / 24)
    humidity += rng.normal(0, 3, n_hours)
    humidity = np.clip(humidity, 5, 98)

    wind_mean = profile["wind_mean"]
    wind_range = profile["wind_range"]
    wind = wind_mean + wind_range * 0.3 * np.sin(2 * np.pi * day_of_year / 365)
    wind += rng.normal(0, 0.8, n_hours)
    wind = np.maximum(wind, 0.1)

    timestamps = pd.date_range("2024-01-01", periods=n_hours, freq="h")

    return ClimateData(
        temperature=temp,
        solar_radiation=solar,
        wind_speed=wind,
        humidity=humidity,
        timestamps=timestamps,
    )


# ---------------------------------------------------------------------------
# Geometry variations
# ---------------------------------------------------------------------------
def generate_geometries() -> List[ShelterGeometry]:
    """Generate a set of shelter geometries covering typical military shelters."""
    lengths = [3.0, 4.0, 5.0, 6.0]
    widths = [3.0, 4.0, 5.0]
    heights = [2.5, 3.0]
    glazings = [0.05, 0.10, 0.15, 0.20]
    orientations = [0.0, 90.0, 180.0, 270.0]

    geometries = []
    for l, w, h, g, o in product(lengths, widths, heights, glazings, orientations):
        if l < w:
            continue
        win_area = g * l * h
        geometries.append(
            ShelterGeometry(
                length=l,
                width=w,
                height=h,
                wall_thickness=0.2,
                roof_thickness=0.2,
                floor_thickness=0.15,
                window_area=win_area,
                window_orientation=o,
                orientation=o,
            )
        )
    return geometries


# ---------------------------------------------------------------------------
# Material thickness variations
# ---------------------------------------------------------------------------
THICKNESS_RANGES = {
    "concrete": [0.10, 0.15, 0.20, 0.25, 0.30],
    "brick": [0.10, 0.15, 0.20, 0.23, 0.30],
    "fly_ash_brick": [0.10, 0.15, 0.20, 0.23],
    "stone": [0.15, 0.20, 0.25, 0.30],
    "granite": [0.15, 0.20, 0.25, 0.30],
    "adobe": [0.15, 0.20, 0.25, 0.30],
    "rammed_earth": [0.15, 0.20, 0.25, 0.30],
    "wood": [0.05, 0.10, 0.15, 0.20],
    "hardwood": [0.05, 0.10, 0.15, 0.20],
    "bamboo": [0.05, 0.10, 0.15],
    "eps": [0.03, 0.05, 0.08, 0.10, 0.12],
    "xps": [0.03, 0.05, 0.08, 0.10],
    "puf": [0.03, 0.05, 0.08, 0.10],
    "glass_wool": [0.05, 0.08, 0.10, 0.12],
    "rock_wool": [0.05, 0.08, 0.10, 0.12],
    "aac_block": [0.10, 0.15, 0.20, 0.25],
    "cement_mortar": [0.02, 0.03, 0.05],
    "lime_mortar": [0.02, 0.03, 0.05],
    "steel": [0.005, 0.01, 0.02],
    "aluminium": [0.005, 0.01, 0.02],
    "clay_tile": [0.015, 0.02, 0.03],
    "calcium_silicate": [0.01, 0.015, 0.025],
    "gypsum_board": [0.01, 0.015, 0.02],
    "plywood": [0.01, 0.015, 0.02],
    "aerogel": [0.01, 0.02, 0.03],
    "phenolic_foam": [0.01, 0.02, 0.03],
    "expanded_clay": [0.10, 0.15, 0.20],
    "cellular_concrete": [0.10, 0.15, 0.20],
    "cseb": [0.10, 0.15, 0.20, 0.25],
}


# ---------------------------------------------------------------------------
# Compliance threshold (BEE ECBC U-value for walls)
# ---------------------------------------------------------------------------
def check_compliance(material: MaterialProperties, thickness: float, climate_zone: str) -> bool:
    """
    Check if material assembly meets BEE ECBC / Eco-Niwas compliance.
    U-value <= threshold for given climate zone.
    """
    u_value = material.thermal_conductivity / thickness
    thresholds = {
        "leh": 0.35,
        "kargil": 0.35,
        "srinagar": 0.35,
        "baramulla": 0.35,
        "jaisalmer": 0.40,
        "bikaner": 0.40,
    }
    threshold = thresholds.get(climate_zone, 0.40)
    return u_value <= threshold


# ---------------------------------------------------------------------------
# Main training data generator
# ---------------------------------------------------------------------------
def generate_training_data(
    max_samples_per_region: int = 5000,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Generate the full ML training dataset.

    For each region × material × thickness × geometry combination,
    run the thermal engine and record features + targets.

    Returns a DataFrame with columns matching MLDatasetRecord schema.
    """
    engine = ThermalEngine()
    geometries = generate_geometries()
    rng = np.random.default_rng(random_seed)

    all_rows = []

    total_combos = (
        len(REGION_CLIMATES)
        * len(MATERIAL_LIBRARY)
        * sum(len(v) for v in THICKNESS_RANGES.values())
        * len(geometries)
    )
    print(f"  Total possible combinations: {total_combos:,}")

    for region_key, climate_profile in REGION_CLIMATES.items():
        print(f"\n  Generating data for: {climate_profile['region']}")
        climate = generate_hourly_climate(climate_profile)
        region_count = 0

        material_names = list(MATERIAL_LIBRARY.keys())
        rng.shuffle(material_names)

        for mat_key in material_names:
            if region_count >= max_samples_per_region:
                break
            mat = MATERIAL_LIBRARY[mat_key]
            thicknesses = THICKNESS_RANGES.get(mat_key, [0.15])
            rng.shuffle(thicknesses)

            for thickness in thicknesses:
                if region_count >= max_samples_per_region:
                    break

                mat_copy = MaterialProperties(
                    name=mat.name,
                    density=mat.density,
                    specific_heat=mat.specific_heat,
                    thermal_conductivity=mat.thermal_conductivity,
                    emissivity=mat.emissivity,
                    solar_absorptance=mat.solar_absorptance,
                    thickness=thickness,
                )

                selected_geos = geometries[: min(8, len(geometries))]
                for geo in selected_geos:
                    if region_count >= max_samples_per_region:
                        break

                    try:
                        result = engine.simulate(geo, mat_key, climate, initial_temp=20.0)
                    except Exception:
                        continue

                    heating_energy = result["total_heating_energy"]
                    avg_temp = result["avg_temp"]
                    min_temp = result["min_temp"]
                    max_temp = result["max_temp"]
                    comfort_hours = result["comfort_hours"]
                    avg_pmv = result["average_pmv"]

                    heating_arr = np.array(result["heating_load"])
                    peak_heating = float(np.max(heating_arr)) if len(heating_arr) > 0 else 0.0

                    hourly_temps = np.array(result["indoor_temperature"])
                    mean_indoor = float(np.mean(hourly_temps))

                    h_degree_days = float(np.sum(np.maximum(18.0 - hourly_temps, 0)))

                    mean_humidity = float(np.mean(climate.humidity))
                    mean_wind = float(np.mean(climate.wind_speed))
                    mean_solar = float(np.mean(climate.solar_radiation))

                    wall_area = 2 * (geo.length + geo.width) * geo.height
                    roof_area = geo.length * geo.width
                    floor_area = geo.length * geo.width
                    total_envelope_area = wall_area + roof_area + floor_area + geo.window_area

                    heat_flux = peak_heating / total_envelope_area if total_envelope_area > 0 else 0.0

                    u_value = mat.thermal_conductivity / thickness
                    thermal_resistance = thickness / mat.thermal_conductivity

                    compliance = check_compliance(mat_copy, thickness, region_key)

                    row = {
                        # Material features
                        "material_name": mat.name,
                        "material_key": mat_key,
                        "density": mat_copy.density,
                        "specific_heat": mat_copy.specific_heat,
                        "thermal_conductivity": mat_copy.thermal_conductivity,
                        "emissivity": mat_copy.emissivity,
                        "solar_absorptance": mat_copy.solar_absorptance,
                        "thickness": thickness,
                        "u_value": u_value,
                        "thermal_resistance": thermal_resistance,
                        "volumetric_heat_capacity": mat_copy.density * mat_copy.specific_heat,
                        # Geometry features
                        "length": geo.length,
                        "width": geo.width,
                        "height": geo.height,
                        "window_area": geo.window_area,
                        "glazing_ratio": geo.window_area / (wall_area + 1e-6),
                        "wall_area": wall_area,
                        "roof_area": roof_area,
                        "total_envelope_area": total_envelope_area,
                        # Climate features
                        "region": climate_profile["region"],
                        "region_key": region_key,
                        "elevation_m": climate_profile["elevation_m"],
                        "mean_temperature": mean_humidity,
                        "mean_humidity": mean_humidity,
                        "mean_wind_speed": mean_wind,
                        "mean_solar_radiation": mean_solar,
                        "temp_range": climate_profile["base_temp_max"] - climate_profile["base_temp_min"],
                        "freeze_thaw_cycles": climate_profile["freeze_thaw_cycles"],
                        "snow_depth_max": climate_profile["snow_depth_max"],
                        "dust_storm_days": climate_profile["dust_storm_days"],
                        # Targets
                        "total_heating_energy_mwh": heating_energy,
                        "peak_heating_w": peak_heating,
                        "heat_flux_w_m2": heat_flux,
                        "mean_indoor_temp_c": mean_indoor,
                        "min_indoor_temp_c": min_temp,
                        "max_indoor_temp_c": max_temp,
                        "comfort_hours": comfort_hours,
                        "comfort_ratio": comfort_hours / 8760,
                        "average_pmv": avg_pmv,
                        "heating_degree_days": h_degree_days,
                        "compliance_label": int(compliance),
                        # Split
                        "split": "train",
                    }
                    all_rows.append(row)
                    region_count += 1

        print(f"    -> {region_count:,} samples generated for {climate_profile['region']}")

    df = pd.DataFrame(all_rows)

    n_regions = df["region_key"].nunique()
    n_materials = df["material_key"].nunique()
    df["split"] = "train"
    n_total = len(df)

    test_ratio = 0.15
    val_ratio = 0.10
    n_test = int(n_total * test_ratio)
    n_val = int(n_total * val_ratio)

    region_test_keys = list(REGION_CLIMATES.keys())[-2:]
    region_val_keys = list(REGION_CLIMATES.keys())[-4:-2]

    test_mask = df["region_key"].isin(region_test_keys)
    val_mask = df["region_key"].isin(region_val_keys) & ~test_mask
    train_mask = ~test_mask & ~val_mask

    df.loc[test_mask, "split"] = "test"
    df.loc[val_mask, "split"] = "validation"
    df.loc[train_mask, "split"] = "train"

    print(f"\n  Dataset summary:")
    print(f"    Total samples:  {n_total:,}")
    print(f"    Regions:        {n_regions}")
    print(f"    Materials:      {n_materials}")
    print(f"    Train:          {(df['split'] == 'train').sum():,}")
    print(f"    Validation:     {(df['split'] == 'validation').sum():,}")
    print(f"    Test:           {(df['split'] == 'test').sum():,}")

    return df


def save_dataset(df: pd.DataFrame, output_dir: str = None):
    """Save the dataset to CSV and parquet."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "training_dataset.csv")
    parquet_path = os.path.join(output_dir, "training_dataset.parquet")

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)

    print(f"  Saved: {csv_path}")
    print(f"  Saved: {parquet_path}")
    return csv_path, parquet_path


if __name__ == "__main__":
    print("=" * 72)
    print("  ML Training Data Generator")
    print("  Thermal Engine × Material Library × Regional Climates")
    print("=" * 72)

    df = generate_training_data(max_samples_per_region=3000)
    save_dataset(df)
    print("\n  Done.")
