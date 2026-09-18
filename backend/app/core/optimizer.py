"""
Multi-Objective Optimization Engine
====================================
Solves the constrained non-linear optimization problem for shelter design:

    minimize J(x) = w_E * E_heating(x) + w_M * M_envelope(x) + w_D * D_comfort(x)

    subject to:
        d_min_i <= d_i <= d_max_i     (layer thickness bounds)
        R_min <= R_glazing <= R_max    (glazing ratio bounds)
        M_envelope <= M_max            (transport weight limit)
        U_wall <= U_max                (thermal code compliance)
        structural_strength >= S_min   (minimum structural integrity)

Decision vector:
    x = [d_1, d_2, ..., d_n, R_glazing]

Solvers:
    - SLSQP (Sequential Least Squares Programming)
    - L-BFGS-B (Limited-memory BFGS with bounds)
    - Differential Evolution (global optimizer)
    - NSGA-II (Pareto front via pymoo or custom)
"""

import numpy as np
from scipy.optimize import minimize, differential_evolution
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
import warnings
import time

from app.core.thermal_engine import (
    ThermalEngine,
    MaterialProperties,
    ShelterGeometry,
    ClimateData,
)

warnings.filterwarnings("ignore")


# ===========================================================================
# Material Library for Optimization
# ===========================================================================
OPTIMIZER_MATERIALS: Dict[str, dict] = {
    "concrete": {
        "name": "Reinforced Concrete", "density": 2400, "cp": 880, "k": 1.7,
        "emissivity": 0.9, "solar_absorptance": 0.7, "cost_per_kg": 5.5,
        "min_thickness": 0.05, "max_thickness": 0.40, "is_structural": True,
        "compressive_strength_mpa": 25.0, "fire_rating_hours": 2.0,
    },
    "brick": {
        "name": "Clay Brick (Burnt)", "density": 1800, "cp": 880, "k": 0.84,
        "emissivity": 0.9, "solar_absorptance": 0.7, "cost_per_kg": 3.0,
        "min_thickness": 0.05, "max_thickness": 0.35, "is_structural": True,
        "compressive_strength_mpa": 10.0, "fire_rating_hours": 3.0,
    },
    "fly_ash_brick": {
        "name": "Fly-Ash Brick", "density": 1600, "cp": 850, "k": 0.62,
        "emissivity": 0.9, "solar_absorptance": 0.7, "cost_per_kg": 2.5,
        "min_thickness": 0.05, "max_thickness": 0.35, "is_structural": True,
        "compressive_strength_mpa": 7.5, "fire_rating_hours": 2.5,
    },
    "aac_block": {
        "name": "AAC Block", "density": 600, "cp": 1000, "k": 0.16,
        "emissivity": 0.9, "solar_absorptance": 0.7, "cost_per_kg": 4.0,
        "min_thickness": 0.05, "max_thickness": 0.30, "is_structural": True,
        "compressive_strength_mpa": 4.0, "fire_rating_hours": 4.0,
    },
    "adobe": {
        "name": "Adobe (Earth Brick)", "density": 1700, "cp": 880, "k": 0.68,
        "emissivity": 0.9, "solar_absorptance": 0.6, "cost_per_kg": 1.5,
        "min_thickness": 0.05, "max_thickness": 0.40, "is_structural": True,
        "compressive_strength_mpa": 2.0, "fire_rating_hours": 2.0,
    },
    "rammed_earth": {
        "name": "Rammed Earth", "density": 1900, "cp": 840, "k": 0.80,
        "emissivity": 0.9, "solar_absorptance": 0.6, "cost_per_kg": 1.2,
        "min_thickness": 0.05, "max_thickness": 0.45, "is_structural": True,
        "compressive_strength_mpa": 3.0, "fire_rating_hours": 3.0,
    },
    "eps": {
        "name": "EPS Insulation", "density": 25, "cp": 1450, "k": 0.035,
        "emissivity": 0.9, "solar_absorptance": 0.3, "cost_per_kg": 12.0,
        "min_thickness": 0.01, "max_thickness": 0.20, "is_structural": False,
        "compressive_strength_mpa": 0.1, "fire_rating_hours": 0.5,
    },
    "xps": {
        "name": "XPS Insulation", "density": 35, "cp": 1400, "k": 0.030,
        "emissivity": 0.9, "solar_absorptance": 0.3, "cost_per_kg": 15.0,
        "min_thickness": 0.01, "max_thickness": 0.20, "is_structural": False,
        "compressive_strength_mpa": 0.2, "fire_rating_hours": 0.5,
    },
    "puf": {
        "name": "PUF Insulation", "density": 32, "cp": 1500, "k": 0.022,
        "emissivity": 0.9, "solar_absorptance": 0.3, "cost_per_kg": 18.0,
        "min_thickness": 0.01, "max_thickness": 0.15, "is_structural": False,
        "compressive_strength_mpa": 0.15, "fire_rating_hours": 0.3,
    },
    "aerogel": {
        "name": "Aerogel Blanket", "density": 200, "cp": 1000, "k": 0.015,
        "emissivity": 0.9, "solar_absorptance": 0.3, "cost_per_kg": 150.0,
        "min_thickness": 0.005, "max_thickness": 0.05, "is_structural": False,
        "compressive_strength_mpa": 0.05, "fire_rating_hours": 1.0,
    },
    "rock_wool": {
        "name": "Rock Wool", "density": 80, "cp": 840, "k": 0.038,
        "emissivity": 0.9, "solar_absorptance": 0.3, "cost_per_kg": 10.0,
        "min_thickness": 0.01, "max_thickness": 0.15, "is_structural": False,
        "compressive_strength_mpa": 0.05, "fire_rating_hours": 3.0,
    },
    "glass_wool": {
        "name": "Glass Wool", "density": 24, "cp": 840, "k": 0.040,
        "emissivity": 0.9, "solar_absorptance": 0.3, "cost_per_kg": 8.0,
        "min_thickness": 0.01, "max_thickness": 0.15, "is_structural": False,
        "compressive_strength_mpa": 0.03, "fire_rating_hours": 2.5,
    },
    "phenolic_foam": {
        "name": "Phenolic Foam", "density": 40, "cp": 1400, "k": 0.022,
        "emissivity": 0.9, "solar_absorptance": 0.3, "cost_per_kg": 20.0,
        "min_thickness": 0.005, "max_thickness": 0.10, "is_structural": False,
        "compressive_strength_mpa": 0.1, "fire_rating_hours": 1.5,
    },
    "calcium_silicate": {
        "name": "Calcium Silicate Board", "density": 870, "cp": 1000, "k": 0.17,
        "emissivity": 0.9, "solar_absorptance": 0.5, "cost_per_kg": 8.0,
        "min_thickness": 0.005, "max_thickness": 0.05, "is_structural": False,
        "compressive_strength_mpa": 0.5, "fire_rating_hours": 3.0,
    },
    "gypsum_board": {
        "name": "Gypsum Board", "density": 800, "cp": 1000, "k": 0.16,
        "emissivity": 0.9, "solar_absorptance": 0.5, "cost_per_kg": 5.0,
        "min_thickness": 0.005, "max_thickness": 0.03, "is_structural": False,
        "compressive_strength_mpa": 0.3, "fire_rating_hours": 1.0,
    },
    "plywood": {
        "name": "Plywood", "density": 600, "cp": 1200, "k": 0.13,
        "emissivity": 0.9, "solar_absorptance": 0.7, "cost_per_kg": 6.0,
        "min_thickness": 0.005, "max_thickness": 0.03, "is_structural": False,
        "compressive_strength_mpa": 0.4, "fire_rating_hours": 0.3,
    },
    "cement_mortar": {
        "name": "Cement Mortar (1:4)", "density": 1800, "cp": 840, "k": 0.72,
        "emissivity": 0.9, "solar_absorptance": 0.7, "cost_per_kg": 3.5,
        "min_thickness": 0.01, "max_thickness": 0.05, "is_structural": False,
        "compressive_strength_mpa": 5.0, "fire_rating_hours": 2.0,
    },
    "steel": {
        "name": "Structural Steel", "density": 7850, "cp": 480, "k": 50.0,
        "emissivity": 0.9, "solar_absorptance": 0.7, "cost_per_kg": 45.0,
        "min_thickness": 0.002, "max_thickness": 0.02, "is_structural": True,
        "compressive_strength_mpa": 250.0, "fire_rating_hours": 0.5,
    },
}


# ===========================================================================
# Optimization Problem Definition
# ===========================================================================
@dataclass
class WallLayerConfig:
    """Configuration for a single wall layer in the optimization."""
    material_key: str
    min_thickness: float = 0.01
    max_thickness: float = 0.30
    is_fixed: bool = False
    fixed_thickness: float = 0.10


@dataclass
class OptimizationConfig:
    """Full optimization problem configuration."""
    wall_layers: List[WallLayerConfig]
    length: float = 5.0
    width: float = 4.0
    height: float = 3.0
    roof_thickness: float = 0.20
    floor_thickness: float = 0.15
    glazing_ratio_min: float = 0.05
    glazing_ratio_max: float = 0.40
    initial_temp: float = 20.0
    simulation_hours: int = 8760
    # Weights
    w_energy: float = 1.0
    w_mass: float = 0.5
    w_discomfort: float = 2.0
    w_cost: float = 0.3
    # Constraints
    max_envelope_mass_kg: float = 5000.0
    max_u_value: float = 0.35
    min_fire_rating_hours: float = 1.0
    max_cost_per_m2: float = 5000.0
    # Solver
    solver: str = "SLSQP"  # SLSQP, L-BFGS-B, differential_evolution
    max_iterations: int = 200
    tolerance: float = 1e-4
    n_population: int = 50  # for differential_evolution
    n_pareto_samples: int = 200  # for Pareto front generation


@dataclass
class OptimizationResult:
    """Result of a single optimization run."""
    decision_vector: List[float]
    layer_thicknesses: List[float]
    glazing_ratio: float
    total_heating_energy_mwh: float
    envelope_mass_kg: float
    discomfort_hours: float
    discomfort_penalty: float
    total_cost: float
    cost_per_m2: float
    u_value_wall: float
    compliance_status: bool
    fire_rating_hours: float
    total_objective: float
    indoor_temperatures: List[float]
    heating_loads: List[float]
    comfort_hours: int
    average_pmv: float
    min_temp: float
    max_temp: float
    avg_temp: float
    convergence_history: List[float] = field(default_factory=list)
    solver_name: str = ""
    solve_time_s: float = 0.0
    material_summary: List[dict] = field(default_factory=list)


@dataclass
class ParetoFront:
    """Collection of Pareto-optimal solutions."""
    solutions: List[OptimizationResult]
    energy_range: Tuple[float, float] = (0.0, 0.0)
    mass_range: Tuple[float, float] = (0.0, 0.0)
    discomfort_range: Tuple[float, float] = (0.0, 0.0)


# ===========================================================================
# Thermal Engine Wrapper for Optimizer
# ===========================================================================
class OptimizerThermalEngine:
    """
    Extended thermal engine that accepts variable layer thicknesses
    and glazing ratios from the optimizer decision vector.
    """

    def __init__(self):
        self.base_engine = ThermalEngine(time_step=3600)

    def build_multi_layer_assembly(
        self,
        layer_configs: List[WallLayerConfig],
        thicknesses: List[float],
    ) -> Tuple[MaterialProperties, float]:
        """
        Build an equivalent single-material wall assembly from multiple layers.
        Returns effective MaterialProperties and total thickness.
        """
        total_thickness = 0.0
        weighted_k = 0.0
        weighted_rho = 0.0
        weighted_cp = 0.0
        weighted_alpha = 0.0
        weighted_eps = 0.0

        for config, t in zip(layer_configs, thicknesses):
            mat = OPTIMIZER_MATERIALS.get(config.material_key)
            if mat is None:
                continue
            total_thickness += t
            weighted_k += mat["k"] * t
            weighted_rho += mat["density"] * t
            weighted_cp += mat["cp"] * t
            weighted_alpha += mat["solar_absorptance"] * t
            weighted_eps += mat["emissivity"] * t

        if total_thickness <= 0:
            total_thickness = 0.20
            weighted_k = 1.7
            weighted_rho = 2400
            weighted_cp = 880
            weighted_alpha = 0.7
            weighted_eps = 0.9

        effective = MaterialProperties(
            name="MultiLayerAssembly",
            density=weighted_rho / total_thickness,
            specific_heat=weighted_cp / total_thickness,
            thermal_conductivity=weighted_k / total_thickness,
            emissivity=weighted_eps / total_thickness,
            solar_absorptance=weighted_alpha / total_thickness,
            thickness=total_thickness,
        )
        return effective, total_thickness

    def simulate_with_vector(
        self,
        x: np.ndarray,
        config: OptimizationConfig,
        climate: ClimateData,
    ) -> Dict:
        """
        Run simulation for a given decision vector x.

        x = [d_1, d_2, ..., d_n, R_glazing]
        """
        n_layers = len(config.wall_layers)
        thicknesses = x[:n_layers]
        glazing_ratio = x[n_layers]

        glazing_ratio = np.clip(glazing_ratio, config.glazing_ratio_min, config.glazing_ratio_max)

        for i, layer in enumerate(config.wall_layers):
            thicknesses[i] = np.clip(thicknesses[i], layer.min_thickness, layer.max_thickness)

        effective_mat, total_thickness = self.build_multi_layer_assembly(
            config.wall_layers, thicknesses
        )

        wall_area = 2 * (config.length + config.width) * config.height
        window_area = glazing_ratio * wall_area

        geometry = ShelterGeometry(
            length=config.length,
            width=config.width,
            height=config.height,
            wall_thickness=total_thickness,
            roof_thickness=config.roof_thickness,
            floor_thickness=config.floor_thickness,
            window_area=window_area,
            window_orientation=180.0,
            orientation=0.0,
        )

        n_hours = min(config.simulation_hours, len(climate.temperature))
        climate_slice = ClimateData(
            temperature=climate.temperature[:n_hours],
            solar_radiation=climate.solar_radiation[:n_hours],
            wind_speed=climate.wind_speed[:n_hours],
            humidity=climate.humidity[:n_hours],
            timestamps=climate.timestamps[:n_hours] if hasattr(climate.timestamps, '__getitem__') else climate.timestamps,
        )

        result = self.base_engine.simulate(geometry, "concrete", climate_slice, config.initial_temp)

        original_materials_db = self.base_engine.materials_db
        self.base_engine.materials_db["concrete"] = effective_mat
        result = self.base_engine.simulate(geometry, "concrete", climate_slice, config.initial_temp)
        self.base_engine.materials_db = original_materials_db

        return result

    def compute_objectives(
        self,
        x: np.ndarray,
        config: OptimizationConfig,
        climate: ClimateData,
    ) -> Tuple[float, float, float, float, Dict]:
        """
        Compute all objective values for decision vector x.

        Returns: (J_total, E_heating, M_envelope, D_discomfort, details)
        """
        n_layers = len(config.wall_layers)
        thicknesses = list(x[:n_layers])
        glazing_ratio = float(x[n_layers])

        result = self.simulate_with_vector(x, config, climate)

        E_heating = result["total_heating_energy"]

        M_envelope = 0.0
        wall_area = 2 * (config.length + config.width) * config.height
        roof_area = config.length * config.width
        floor_area = config.length * config.width
        total_opaque_area = wall_area + roof_area + floor_area

        for layer_config, t in zip(config.wall_layers, thicknesses):
            mat = OPTIMIZER_MATERIALS.get(layer_config.material_key)
            if mat:
                M_envelope += mat["density"] * t * total_opaque_area

        hourly_temps = np.array(result["indoor_temperature"])
        discomfort_count = 0
        for temp in hourly_temps:
            if temp < 18.0:
                discomfort_count += 1
        D_discomfort = float(discomfort_count)

        total_cost = 0.0
        for layer_config, t in zip(config.wall_layers, thicknesses):
            mat = OPTIMIZER_MATERIALS.get(layer_config.material_key)
            if mat:
                total_cost += mat["density"] * t * total_opaque_area * mat["cost_per_kg"] / 1000.0

        floor_plan_area = config.length * config.width
        cost_per_m2 = total_cost / floor_plan_area if floor_plan_area > 0 else 0.0

        thermal_resistance = sum(
            thicknesses[i] / OPTIMIZER_MATERIALS[config.wall_layers[i].material_key]["k"]
            for i in range(n_layers)
            if config.wall_layers[i].material_key in OPTIMIZER_MATERIALS
        )
        total_t = sum(thicknesses)
        weighted_k = 0.0
        for i, lc in enumerate(config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(lc.material_key)
            if mat:
                weighted_k += mat["k"] * thicknesses[i]
        u_value = weighted_k / total_t if total_t > 0 else 999.0

        J = (
            config.w_energy * E_heating
            + config.w_mass * M_envelope / 1000.0
            + config.w_discomfort * D_discomfort / 8760.0
            + config.w_cost * cost_per_m2 / 1000.0
        )

        details = {
            "indoor_temperature": result["indoor_temperature"],
            "heating_load": result["heating_load"],
            "comfort_hours": result["comfort_hours"],
            "average_pmv": result["average_pmv"],
            "min_temp": result["min_temp"],
            "max_temp": result["max_temp"],
            "avg_temp": result["avg_temp"],
            "E_heating_mwh": E_heating,
            "M_envelope_kg": M_envelope,
            "D_discomfort_hours": D_discomfort,
            "total_cost": total_cost,
            "cost_per_m2": cost_per_m2,
            "u_value": u_value,
            "total_thickness": sum(thicknesses),
            "thermal_resistance": thermal_resistance,
        }

        return J, E_heating, M_envelope, D_discomfort, details


# ===========================================================================
# Constraint Functions
# ===========================================================================
def build_constraints(config: OptimizationConfig) -> List[dict]:
    """Build inequality and equality constraints for SLSQP."""
    constraints = []

    n_layers = len(config.wall_layers)

    def mass_constraint(x):
        total_thicknesses = list(x[:n_layers])
        wall_area = 2 * (config.length + config.width) * config.height
        roof_area = config.length * config.width
        floor_area = config.length * config.width
        total_opaque = wall_area + roof_area + floor_area
        mass = 0.0
        for i, lc in enumerate(config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(lc.material_key)
            if mat:
                mass += mat["density"] * total_thicknesses[i] * total_opaque
        return config.max_envelope_mass_kg - mass

    constraints.append({"type": "ineq", "fun": mass_constraint})

    def u_value_constraint(x):
        total_thicknesses = list(x[:n_layers])
        total_t = sum(total_thicknesses)
        if total_t <= 0:
            return -1.0
        weighted_k = 0.0
        for i, lc in enumerate(config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(lc.material_key)
            if mat:
                weighted_k += mat["k"] * total_thicknesses[i]
        u_value = weighted_k / total_t
        return config.max_u_value - u_value

    constraints.append({"type": "ineq", "fun": u_value_constraint})

    def structural_constraint(x):
        total_thicknesses = list(x[:n_layers])
        has_structural = False
        for i, lc in enumerate(config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(lc.material_key)
            if mat and mat["is_structural"] and total_thicknesses[i] > 0.02:
                has_structural = True
                break
        if not has_structural:
            for i, lc in enumerate(config.wall_layers):
                mat = OPTIMIZER_MATERIALS.get(lc.material_key)
                if mat and mat["is_structural"]:
                    return 0.02 - total_thicknesses[i]
        return 1.0

    constraints.append({"type": "ineq", "fun": structural_constraint})

    return constraints


def build_bounds(config: OptimizationConfig) -> List[tuple]:
    """Build variable bounds for the optimizer."""
    bounds = []
    for layer in config.wall_layers:
        bounds.append((layer.min_thickness, layer.max_thickness))
    bounds.append((config.glazing_ratio_min, config.glazing_ratio_max))
    return bounds


# ===========================================================================
# Solvers
# ===========================================================================
class ShelterOptimizer:
    """
    Multi-objective optimizer for shelter thermal design.

    Solves:
        minimize J(x) = w_E * E(x) + w_M * M(x) + w_D * D(x)
        subject to mass, U-value, structural, and glazing constraints.
    """

    def __init__(self, config: OptimizationConfig, climate: ClimateData):
        self.config = config
        self.climate = climate
        self.engine = OptimizerThermalEngine()
        self.convergence_history = []

    def _objective(self, x: np.ndarray) -> float:
        """Scalar objective function for minimization."""
        J, _, _, _, _ = self.engine.compute_objectives(x, self.config, self.climate)
        return J

    def _objective_with_callback(self, x: np.ndarray) -> float:
        """Objective with convergence tracking."""
        J = self._objective(x)
        self.convergence_history.append(J)
        return J

    def solve_slsqp(self) -> OptimizationResult:
        """Solve using Sequential Least Squares Programming."""
        n = len(self.config.wall_layers) + 1
        x0 = np.zeros(n)
        for i, layer in enumerate(self.config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(layer.material_key)
            if mat:
                x0[i] = (layer.min_thickness + layer.max_thickness) / 2.0
            else:
                x0[i] = layer.min_thickness + 0.05
        x0[-1] = (self.config.glazing_ratio_min + self.config.glazing_ratio_max) / 2.0

        bounds = build_bounds(self.config)
        constraints = build_constraints(self.config)

        self.convergence_history = []
        t0 = time.time()

        result = minimize(
            self._objective_with_callback,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={
                "maxiter": self.config.max_iterations,
                "ftol": self.config.tolerance,
                "disp": False,
            },
        )

        solve_time = time.time() - t0
        return self._build_result(result.x, "SLSQP", solve_time, result.success)

    def solve_lbfgsb(self) -> OptimizationResult:
        """Solve using L-BFGS-B with numerical gradients."""
        n = len(self.config.wall_layers) + 1
        x0 = np.zeros(n)
        for i, layer in enumerate(self.config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(layer.material_key)
            if mat:
                x0[i] = (layer.min_thickness + layer.max_thickness) / 2.0
            else:
                x0[i] = layer.min_thickness + 0.05
        x0[-1] = (self.config.glazing_ratio_min + self.config.glazing_ratio_max) / 2.0

        bounds = build_bounds(self.config)
        constraints = build_constraints(self.config)

        self.convergence_history = []
        t0 = time.time()

        result = minimize(
            self._objective_with_callback,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={
                "maxiter": self.config.max_iterations,
                "ftol": self.config.tolerance,
                "disp": False,
            },
        )

        solve_time = time.time() - t0
        return self._build_result(result.x, "L-BFGS-B", solve_time, result.success)

    def solve_differential_evolution(self) -> OptimizationResult:
        """Solve using Differential Evolution (global optimizer)."""
        bounds = build_bounds(self.config)

        self.convergence_history = []
        t0 = time.time()

        result = differential_evolution(
            self._objective,
            bounds,
            maxiter=self.config.max_iterations,
            popsize=self.config.n_population,
            tol=self.config.tolerance,
            seed=42,
            mutation=(0.5, 1.0),
            recombination=0.7,
            polish=True,
        )

        solve_time = time.time() - t0
        return self._build_result(result.x, "DifferentialEvolution", solve_time, result.success)

    def solve_random_search(self, n_samples: int = 500) -> OptimizationResult:
        """Random search fallback for robustness."""
        bounds = build_bounds(self.config)
        best_J = float("inf")
        best_x = None

        t0 = time.time()
        rng = np.random.default_rng(42)

        for _ in range(n_samples):
            x = np.array([
                rng.uniform(b[0], b[1]) for b in bounds
            ])
            J = self._objective(x)
            if J < best_J:
                best_J = J
                best_x = x.copy()

        solve_time = time.time() - t0
        return self._build_result(best_x, "RandomSearch", solve_time, True)

    def _build_result(self, x: np.ndarray, solver_name: str, solve_time: float, success: bool) -> OptimizationResult:
        """Build OptimizationResult from optimal decision vector."""
        n_layers = len(self.config.wall_layers)
        layer_thicknesses = [float(x[i]) for i in range(n_layers)]
        glazing_ratio = float(x[n_layers])

        J, E_heating, M_envelope, D_discomfort, details = self.engine.compute_objectives(
            x, self.config, self.climate
        )

        mat_summary = []
        for i, lc in enumerate(self.config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(lc.material_key, {})
            mat_summary.append({
                "material_key": lc.material_key,
                "material_name": mat.get("name", lc.material_key),
                "thickness_m": layer_thicknesses[i],
                "density": mat.get("density", 0),
                "k": mat.get("k", 0),
                "cost_per_kg": mat.get("cost_per_kg", 0),
                "is_structural": mat.get("is_structural", False),
            })

        fire_ratings = []
        for i, lc in enumerate(self.config.wall_layers):
            mat = OPTIMIZER_MATERIALS.get(lc.material_key)
            if mat and layer_thicknesses[i] > 0.01:
                fire_ratings.append(mat.get("fire_rating_hours", 0))
        min_fire = min(fire_ratings) if fire_ratings else 0

        return OptimizationResult(
            decision_vector=x.tolist(),
            layer_thicknesses=layer_thicknesses,
            glazing_ratio=glazing_ratio,
            total_heating_energy_mwh=details["E_heating_mwh"],
            envelope_mass_kg=details["M_envelope_kg"],
            discomfort_hours=details["D_discomfort_hours"],
            discomfort_penalty=D_discomfort / 8760.0,
            total_cost=details["total_cost"],
            cost_per_m2=details["cost_per_m2"],
            u_value_wall=details["u_value"],
            compliance_status=details["u_value"] <= self.config.max_u_value,
            fire_rating_hours=min_fire,
            total_objective=J,
            indoor_temperatures=details["indoor_temperature"],
            heating_loads=details["heating_load"],
            comfort_hours=details["comfort_hours"],
            average_pmv=details["average_pmv"],
            min_temp=details["min_temp"],
            max_temp=details["max_temp"],
            avg_temp=details["avg_temp"],
            convergence_history=self.convergence_history,
            solver_name=solver_name,
            solve_time_s=solve_time,
            material_summary=mat_summary,
        )

    def optimize(self) -> OptimizationResult:
        """Run the selected solver and return the best result."""
        solver = self.config.solver.upper()

        if solver == "SLSQP":
            return self.solve_slsqp()
        elif solver == "L-BFGS-B":
            return self.solve_lbfgsb()
        elif solver in ("DE", "DIFFERENTIAL_EVOLUTION", "DE"):
            return self.solve_differential_evolution()
        elif solver == "RANDOM":
            return self.solve_random_search()
        else:
            return self.solve_slsqp()

    def generate_pareto_front(
        self,
        n_samples: int = None,
    ) -> ParetoFront:
        """
        Generate Pareto front by varying weights and sampling.

        Returns a set of non-dominated solutions across the three objectives.
        """
        if n_samples is None:
            n_samples = self.config.n_pareto_samples

        weight_sets = []
        rng = np.random.default_rng(42)

        for _ in range(n_samples):
            w_e = rng.uniform(0.1, 2.0)
            w_m = rng.uniform(0.1, 2.0)
            w_d = rng.uniform(0.1, 3.0)
            weight_sets.append((w_e, w_m, w_d))

        solutions = []
        original_w_e = self.config.w_energy
        original_w_m = self.config.w_mass
        original_w_d = self.config.w_discomfort

        for w_e, w_m, w_d in weight_sets:
            self.config.w_energy = w_e
            self.config.w_mass = w_m
            self.config.w_discomfort = w_d

            try:
                result = self.optimize()
                solutions.append(result)
            except Exception:
                continue

        self.config.w_energy = original_w_e
        self.config.w_mass = original_w_m
        self.config.w_discomfort = original_w_d

        if not solutions:
            return ParetoFront(solutions=[])

        pareto = self._extract_pareto(solutions)

        energies = [s.total_heating_energy_mwh for s in pareto.solutions]
        masses = [s.envelope_mass_kg for s in pareto.solutions]
        discomforts = [s.discomfort_hours for s in pareto.solutions]

        pareto.energy_range = (min(energies), max(energies)) if energies else (0, 0)
        pareto.mass_range = (min(masses), max(masses)) if masses else (0, 0)
        pareto.discomfort_range = (min(discomforts), max(discomforts)) if discomforts else (0, 0)

        return pareto

    def _extract_pareto(self, solutions: List[OptimizationResult]) -> ParetoFront:
        """Extract non-dominated solutions (Pareto front)."""
        if not solutions:
            return ParetoFront(solutions=[])

        energies = np.array([s.total_heating_energy_mwh for s in solutions])
        masses = np.array([s.envelope_mass_kg for s in solutions])
        discomforts = np.array([s.discomfort_hours for s in solutions])

        e_norm = (energies - energies.min()) / (energies.max() - energies.min() + 1e-10)
        m_norm = (masses - masses.min()) / (masses.max() - masses.min() + 1e-10)
        d_norm = (discomforts - discomforts.min()) / (discomforts.max() - discomforts.min() + 1e-10)

        dominated = set()
        n = len(solutions)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if (e_norm[j] <= e_norm[i] and m_norm[j] <= m_norm[i] and d_norm[j] <= d_norm[i]):
                    if (e_norm[j] < e_norm[i] or m_norm[j] < m_norm[i] or d_norm[j] < d_norm[i]):
                        dominated.add(i)
                        break

        pareto_indices = [i for i in range(n) if i not in dominated]
        pareto_solutions = [solutions[i] for i in pareto_indices]
        pareto_solutions.sort(key=lambda s: s.total_heating_energy_mwh)

        return ParetoFront(solutions=pareto_solutions)


# ===========================================================================
# Convenience Functions
# ===========================================================================
def create_default_config() -> OptimizationConfig:
    """Create a default optimization configuration for Leh-Ladakh."""
    return OptimizationConfig(
        wall_layers=[
            WallLayerConfig("cement_mortar", 0.01, 0.03, is_fixed=True, fixed_thickness=0.02),
            WallLayerConfig("eps", 0.02, 0.20),
            WallLayerConfig("brick", 0.05, 0.25),
            WallLayerConfig("cement_mortar", 0.01, 0.03, is_fixed=True, fixed_thickness=0.02),
        ],
        length=5.0,
        width=4.0,
        height=3.0,
        glazing_ratio_min=0.05,
        glazing_ratio_max=0.30,
        w_energy=1.0,
        w_mass=0.5,
        w_discomfort=2.0,
        w_cost=0.3,
        max_envelope_mass_kg=4000.0,
        max_u_value=0.35,
        solver="SLSQP",
        max_iterations=150,
    )


def create_rapid_deploy_config() -> OptimizationConfig:
    """Config optimized for rapid airlift deployment (low weight priority)."""
    return OptimizationConfig(
        wall_layers=[
            WallLayerConfig("aerogel", 0.005, 0.05),
            WallLayerConfig("plywood", 0.005, 0.02),
        ],
        length=4.0,
        width=3.0,
        height=2.5,
        glazing_ratio_min=0.05,
        glazing_ratio_max=0.25,
        w_energy=1.0,
        w_mass=3.0,
        w_discomfort=1.5,
        w_cost=0.1,
        max_envelope_mass_kg=800.0,
        max_u_value=0.25,
        solver="SLSQP",
        max_iterations=150,
    )


def create_permanent_base_config() -> OptimizationConfig:
    """Config for permanent base (low cost, high comfort priority)."""
    return OptimizationConfig(
        wall_layers=[
            WallLayerConfig("cement_mortar", 0.01, 0.03, is_fixed=True, fixed_thickness=0.02),
            WallLayerConfig("xps", 0.03, 0.15),
            WallLayerConfig("brick", 0.10, 0.30),
            WallLayerConfig("cement_mortar", 0.01, 0.03, is_fixed=True, fixed_thickness=0.02),
        ],
        length=6.0,
        width=5.0,
        height=3.2,
        glazing_ratio_min=0.10,
        glazing_ratio_max=0.35,
        w_energy=1.5,
        w_mass=0.2,
        w_discomfort=3.0,
        w_cost=0.8,
        max_envelope_mass_kg=15000.0,
        max_u_value=0.30,
        solver="SLSQP",
        max_iterations=200,
    )


def create_composite_armour_config() -> OptimizationConfig:
    """Config for armoured shelter (defence materials, fire rating critical)."""
    return OptimizationConfig(
        wall_layers=[
            WallLayerConfig("steel", 0.002, 0.015),
            WallLayerConfig("calcium_silicate", 0.005, 0.03),
            WallLayerConfig("rock_wool", 0.02, 0.10),
            WallLayerConfig("steel", 0.002, 0.015),
        ],
        length=5.0,
        width=4.0,
        height=3.0,
        glazing_ratio_min=0.03,
        glazing_ratio_max=0.15,
        w_energy=1.0,
        w_mass=1.5,
        w_discomfort=2.0,
        w_cost=0.5,
        max_envelope_mass_kg=6000.0,
        max_u_value=0.30,
        min_fire_rating_hours=2.0,
        solver="SLSQP",
        max_iterations=150,
    )
