from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

Base = declarative_base()

class Simulation(Base):
    __tablename__ = "simulations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    location_name = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    geometry_params = Column(JSON)
    material_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now)
    
    results = relationship("SimulationResult", back_populates="simulation", cascade="all, delete-orphan")

class SimulationResult(Base):
    __tablename__ = "simulation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, ForeignKey("simulations.id"), nullable=False)
    indoor_temperatures = Column(JSON)
    heating_loads = Column(JSON)
    total_heating_energy = Column(Float)
    comfort_hours = Column(Integer)
    min_temp = Column(Float)
    max_temp = Column(Float)
    avg_temp = Column(Float)
    created_at = Column(DateTime, default=utc_now)
    
    simulation = relationship("Simulation", back_populates="results")

class ClimateData(Base):
    __tablename__ = "climate_data"
    
    id = Column(Integer, primary_key=True, index=True)
    location_name = Column(String(255), unique=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    temperature = Column(JSON)
    solar_radiation = Column(JSON)
    wind_speed = Column(JSON)
    humidity = Column(JSON)
    timestamps = Column(JSON)
    daily_summary = Column(JSON)
    fetched_at = Column(DateTime, default=utc_now)

class Material(Base):
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    conductivity = Column(Float, nullable=False)
    density = Column(Float, nullable=False)
    specific_heat = Column(Float, nullable=False)
    latent_heat = Column(Float, default=0.0, nullable=False) # J/kg (Crucial for PCM heat storage)
    melting_temp = Column(Float, nullable=True) # °C (Phase change trigger point)
    cost_per_kg = Column(Float, default=0.0, nullable=False) # Local currency for capital investment
    display_name = Column(String(255), nullable=True)
    emissivity = Column(Float, default=0.9, nullable=True)
    solar_absorptance = Column(Float, default=0.7, nullable=True)
    thickness = Column(Float, default=0.1, nullable=True)
    description = Column(Text, nullable=True)

    @property
    def thermal_conductivity(self) -> float:
        return self.conductivity

    @thermal_conductivity.setter
    def thermal_conductivity(self, value: float):
        self.conductivity = value

class Shelter(Base):
    __tablename__ = "shelters"
    
    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(150), nullable=False)
    climate_zone = Column(String(50), nullable=False, default="Extreme cold (Ladakh)")
    shape_type = Column(String(50), nullable=False, default="Rectangular")
    azimuth_angle = Column(Float, nullable=False, default=0.0)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    length = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    glazing_ratio = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    
    wall_layers = relationship(
        "ShelterWallLayer",
        back_populates="shelter",
        cascade="all, delete-orphan",
        order_by="ShelterWallLayer.layer_order",
    )
    simulation_logs = relationship(
        "SimulationLog",
        back_populates="shelter",
        cascade="all, delete-orphan",
    )
    field_validations = relationship(
        "FieldValidationData",
        back_populates="shelter",
        cascade="all, delete-orphan",
    )

class ShelterWallLayer(Base):
    __tablename__ = "shelter_wall_layers"
    
    id = Column(Integer, primary_key=True, index=True)
    shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    thickness = Column(Float, nullable=False)
    layer_order = Column(Integer, nullable=False)
    
    shelter = relationship("Shelter", back_populates="wall_layers")
    material = relationship("Material")

class SimulationLog(Base):
    __tablename__ = "simulation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="CASCADE"), index=True, nullable=False)
    simulation_date = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    peak_heating_kw = Column(Float, nullable=False)
    average_pmv = Column(Float, nullable=False)
    optimal_insulation_m = Column(Float)
    
    shelter = relationship("Shelter", back_populates="simulation_logs")

class FieldValidationData(Base):
    """Stores real-world IoT sensor data from actual shelters for model comparison."""
    __tablename__ = "field_validation_data"
    
    id = Column(Integer, primary_key=True, index=True)
    shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="CASCADE"))
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    actual_indoor_temp = Column(Float, nullable=False)
    actual_humidity = Column(Float)
    predicted_indoor_temp = Column(Float) # Logged from the engine for direct comparison
    error_margin = Column(Float) # The "Error/deviation" metric

    shelter = relationship("Shelter", back_populates="field_validations")

class ClimateCache(Base):
    """Local storage for NASA POWER API historical weather data."""
    __tablename__ = "climate_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    ambient_temp = Column(Float, nullable=False)
    solar_irradiance = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)

class RegionalEconomics(Base):
    """Regional Economics for Payback Period (ROI) and Carbon Footprint Calculation."""
    __tablename__ = "regional_economics"
    
    id = Column(Integer, primary_key=True, index=True)
    climate_zone = Column(String(50), unique=True, nullable=False, index=True)
    fuel_cost_per_kwh = Column(Float, nullable=False) # Baseline cost of diesel/electricity in the region
    carbon_emission_factor = Column(Float, nullable=False) # kg CO2 per kWh to prove environmental impact


# ===========================================================================
# PROVENANCE-BASED MATERIAL & CLIMATE MODELS
# ===========================================================================


class DataSource(Base):
    """Registry of every document, dataset, or measurement source."""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    organization = Column(String(255), nullable=False)
    document_type = Column(String(100), nullable=False)
    document_id = Column(String(255))
    version = Column(String(50))
    year = Column(Integer)
    url = Column(Text)
    access_restriction = Column(String(100), default="public")
    access_notes = Column(Text)
    license_summary = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())

    thermal_properties = relationship("MaterialThermalProperty", back_populates="source")
    climate_observations = relationship("ClimateObservation", back_populates="source")


class MaterialCategory(Base):
    """Classification of materials for filtering and ML grouping."""
    __tablename__ = "material_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    parent_category_id = Column(Integer, ForeignKey("material_categories.id"))
    is_structural = Column(Boolean, default=False)
    is_insulation = Column(Boolean, default=False)
    is_defence_specific = Column(Boolean, default=False)

    parent = relationship("MaterialCategory", remote_side=[id])
    thermal_properties = relationship("MaterialThermalProperty", back_populates="category")


class MaterialThermalProperty(Base):
    """
    Individual thermal-property record with full provenance.
    Never mix measured, code-default, and ML-predicted values in one row.
    """
    __tablename__ = "material_thermal_properties"
    __table_args__ = (
        UniqueConstraint("material_name", "property_name", "source_id", name="uq_material_property_source"),
        Index("idx_mtp_category", "category_id"),
        Index("idx_mtp_value_type", "value_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    material_name = Column(String(150), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("material_categories.id"))
    property_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    value_type = Column(String(50), nullable=False, default="government_default")
    test_method = Column(String(255))
    uncertainty = Column(Float)
    temperature_range = Column(String(100))
    moisture_condition = Column(String(100))
    region = Column(String(100))
    notes = Column(Text)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now)

    category = relationship("MaterialCategory", back_populates="thermal_properties")
    source = relationship("DataSource", back_populates="thermal_properties")


class ClimateStation(Base):
    """IMD weather stations with metadata."""
    __tablename__ = "climate_stations"

    id = Column(Integer, primary_key=True, index=True)
    station_name = Column(String(255), nullable=False, index=True)
    station_id = Column(String(50), unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_m = Column(Float)
    state = Column(String(100))
    district = Column(String(100))
    climate_zone = Column(String(100))
    is_military = Column(Boolean, default=False)
    access_restriction = Column(String(100), default="restricted")
    access_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())

    observations = relationship("ClimateObservation", back_populates="station")


class ClimateObservation(Base):
    """Actual IMD climate observations — raw, not design values."""
    __tablename__ = "climate_observations"
    __table_args__ = (
        Index("idx_co_station_ts", "station_id", "observation_timestamp"),
        Index("idx_co_quality", "quality_flag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(50), ForeignKey("climate_stations.station_id"), nullable=False)
    observation_timestamp = Column(DateTime(timezone=True), nullable=False)
    min_air_temperature_c = Column(Float)
    max_air_temperature_c = Column(Float)
    mean_air_temperature_c = Column(Float)
    relative_humidity_percent = Column(Float)
    precipitation_mm = Column(Float)
    solar_radiation_w_m2 = Column(Float)
    wind_speed_m_s = Column(Float)
    wind_direction_deg = Column(Float)
    atmospheric_pressure_hpa = Column(Float)
    elevation_m = Column(Float)
    snow_depth_cm = Column(Float)
    quality_flag = Column(String(20), default="verified")
    observation_period = Column(String(50))
    missing_data_treatment = Column(Text)
    source_id = Column(Integer, ForeignKey("data_sources.id"))
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())

    station = relationship("ClimateStation", back_populates="observations")
    source = relationship("DataSource", back_populates="climate_observations")


class ClimateDesignValues(Base):
    """Computed design values from IMD observations (not raw measurements)."""
    __tablename__ = "climate_design_values"
    __table_args__ = (
        UniqueConstraint("station_id", "parameter_name", "percentile", name="uq_design_value"),
    )

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(50), ForeignKey("climate_stations.station_id"), nullable=False)
    parameter_name = Column(String(100), nullable=False)
    percentile = Column(String(20))
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    calculation_period = Column(String(50))
    method = Column(Text)
    source_id = Column(Integer, ForeignKey("data_sources.id"))
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())


class MLDatasetRecord(Base):
    """ML training dataset combining materials, climate, and targets."""
    __tablename__ = "ml_dataset_records"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("material_thermal_properties.id"))
    region = Column(String(100))
    timestamp = Column(DateTime(timezone=True))
    ambient_temperature_c = Column(Float)
    relative_humidity_percent = Column(Float)
    wind_speed_m_s = Column(Float)
    solar_radiation_w_m2 = Column(Float)
    material_thickness_m = Column(Float)
    moisture_condition = Column(String(100))
    surface_temperature_c = Column(Float)
    heat_flux_w_m2 = Column(Float)
    energy_demand_kwh = Column(Float)
    compliance_label = Column(Boolean)
    source_id = Column(Integer, ForeignKey("data_sources.id"))
    split = Column(String(20), default="train")
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())


class OptimizationRun(Base):
    """Stores each multi-objective optimization run."""
    __tablename__ = "optimization_runs"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(100), nullable=False)
    objectives = Column(JSON)
    constraints = Column(JSON)
    pareto_front = Column(JSON)
    best_solution = Column(JSON)
    source_materials = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())