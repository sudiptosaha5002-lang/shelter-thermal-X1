import numpy as np
from scipy.integrate import solve_ivp
from dataclasses import dataclass
from typing import Dict, List, Optional
from pythermalcomfort.models import pmv_ppd_iso
from pythermalcomfort.utilities import v_relative

@dataclass
class MaterialProperties:
    name: str
    density: float
    specific_heat: float
    thermal_conductivity: float
    emissivity: float = 0.9
    solar_absorptance: float = 0.7
    thickness: float = 0.1

@dataclass
class ShelterGeometry:
    length: float
    width: float
    height: float
    wall_thickness: float
    roof_thickness: float
    floor_thickness: float
    window_area: float
    window_orientation: float
    orientation: float

@dataclass
class ClimateData:
    temperature: np.ndarray
    solar_radiation: np.ndarray
    wind_speed: np.ndarray
    humidity: np.ndarray
    timestamps: np.ndarray

class ThermalEngine:
    def __init__(self, time_step: int = 3600):
        self.time_step = time_step
        self.materials_db = self._load_materials_db()
    
    def _load_materials_db(self) -> Dict[str, MaterialProperties]:
        return {
            "concrete": MaterialProperties("Concrete", 2400, 880, 1.7, 0.9, 0.7, 0.2),
            "brick": MaterialProperties("Brick", 1800, 840, 0.7, 0.9, 0.7, 0.2),
            "stone": MaterialProperties("Stone", 2600, 790, 2.5, 0.9, 0.7, 0.3),
            "adobe": MaterialProperties("Adobe", 1600, 900, 0.5, 0.9, 0.6, 0.3),
            "wood": MaterialProperties("Wood", 600, 1500, 0.15, 0.9, 0.7, 0.15),
            "pcm": MaterialProperties("PCM", 1500, 2000, 0.2, 0.9, 0.5, 0.05),
            "insulation": MaterialProperties("Insulation", 30, 1400, 0.04, 0.9, 0.3, 0.1),
            "glass": MaterialProperties("Glass", 2500, 840, 1.0, 0.85, 0.85, 0.006),
            "eps insulation": MaterialProperties("EPS Insulation", 30, 1450, 0.035, 0.9, 0.3, 0.1),
            "plywood outer": MaterialProperties("Plywood Outer", 600, 1200, 0.13, 0.9, 0.7, 0.02),
            "adobe brick": MaterialProperties("Adobe Brick", 1700, 1000, 0.75, 0.9, 0.6, 0.3),
        }
    
    def calculate_thermal_mass(self, geometry: ShelterGeometry, material: MaterialProperties) -> float:
        wall_volume = 2 * (geometry.length + geometry.width) * geometry.height * geometry.wall_thickness
        roof_volume = geometry.length * geometry.width * geometry.roof_thickness
        floor_volume = geometry.length * geometry.width * geometry.floor_thickness
        total_volume = wall_volume + roof_volume + floor_volume
        return total_volume * material.density * material.specific_heat
    
    def calculate_u_value(self, material: MaterialProperties) -> float:
        return material.thermal_conductivity / material.thickness
    
    def solar_gain(self, climate: ClimateData, geometry: ShelterGeometry, 
                   material: MaterialProperties, hour: int) -> float:
        solar_rad = climate.solar_radiation[hour]
        window_gain = geometry.window_area * material.solar_absorptance * solar_rad * 0.8
        wall_area = 2 * (geometry.length + geometry.width) * geometry.height
        roof_area = geometry.length * geometry.width
        opaque_gain = (wall_area + roof_area) * material.solar_absorptance * solar_rad * 0.1
        return window_gain + opaque_gain
    
    def heat_loss(self, t_inside: float, t_outside: float, geometry: ShelterGeometry,
                  material: MaterialProperties, wind_speed: float) -> float:
        h_conv = 5.8 + 4.1 * wind_speed
        wall_area = 2 * (geometry.length + geometry.width) * geometry.height
        roof_area = geometry.length * geometry.width
        floor_area = geometry.length * geometry.width
        window_area = geometry.window_area
        
        u_wall = self.calculate_u_value(material)
        u_window = 2.8
        
        q_wall = u_wall * wall_area * (t_inside - t_outside)
        q_roof = u_wall * roof_area * (t_inside - t_outside)
        q_floor = u_wall * floor_area * (t_inside - t_outside) * 0.5
        q_window = u_window * window_area * (t_inside - t_outside)
        
        return q_wall + q_roof + q_floor + q_window
    
    def simulate(self, geometry: ShelterGeometry, material_name: str, 
                 climate: ClimateData, initial_temp: float = 20.0) -> Dict:
        mat_key = material_name.lower().strip()
        material = self.materials_db.get(mat_key, self.materials_db["concrete"])
        thermal_mass = self.calculate_thermal_mass(geometry, material)
        
        n_hours = len(climate.temperature)
        t_inside = np.zeros(n_hours)
        t_inside[0] = initial_temp
        heating_load = np.zeros(n_hours)
        
        for i in range(1, n_hours):
            q_solar = self.solar_gain(climate, geometry, material, i)
            q_loss = self.heat_loss(
                t_inside[i-1], climate.temperature[i], geometry, material, 
                climate.wind_speed[i]
            )
            q_net = q_solar - q_loss
            delta_t = q_net * self.time_step / thermal_mass
            t_inside[i] = t_inside[i-1] + delta_t
            
            if t_inside[i] < 18.0:
                heating_load[i] = (18.0 - t_inside[i]) * thermal_mass / self.time_step
                t_inside[i] = 18.0
        
        comfort_hours, pmv_index = self._calculate_comfort_metrics(t_inside, climate.humidity)
        avg_pmv = float(np.mean(pmv_index)) if pmv_index else 0.0
        
        return {
            "indoor_temperature": t_inside.tolist(),
            "heating_load": heating_load.tolist(),
            "heating_load_watt": heating_load.tolist(),
            "total_heating_energy": float(np.sum(heating_load) * self.time_step / 3.6e6),
            "comfort_hours": comfort_hours,
            "pmv_index": pmv_index,
            "average_pmv": avg_pmv,
            "min_temp": float(np.min(t_inside)),
            "max_temp": float(np.max(t_inside)),
            "avg_temp": float(np.mean(t_inside)),
        }
    
    def _calculate_comfort_metrics(self, t_inside: np.ndarray, humidity: np.ndarray) -> tuple:
        comfort_count = 0
        pmv_list = []
        for i, t in enumerate(t_inside):
            rh = float(humidity[i]) if i < len(humidity) else 50.0
            rh = max(0.0, min(100.0, rh))
            result = pmv_ppd_iso(tdb=t, tr=t, vr=0.1, rh=rh, met=1.2, clo=1.0, limit_inputs=False)
            pmv_val = round(float(result.pmv), 3)
            pmv_list.append(pmv_val)
            if -0.5 <= pmv_val <= 0.5:
                comfort_count += 1
        return comfort_count, pmv_list
    
    def optimize(self, base_geometry: ShelterGeometry, materials: List[str], 
                 climate: ClimateData) -> List[Dict]:
        results = []
        for mat in materials:
            result = self.simulate(base_geometry, mat, climate)
            result["material"] = mat
            results.append(result)
        
        results.sort(key=lambda x: x["total_heating_energy"])
        return results


thermal_engine = ThermalEngine()