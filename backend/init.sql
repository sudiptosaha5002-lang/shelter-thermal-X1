-- Standardized building materials library (with PCM and cost properties)
CREATE TABLE IF NOT EXISTS materials (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    conductivity FLOAT NOT NULL, -- W/m-K
    density FLOAT NOT NULL,      -- kg/m^3
    specific_heat FLOAT NOT NULL, -- J/kg-K
    latent_heat FLOAT DEFAULT 0.0,      -- J/kg (Crucial for PCM heat storage)
    melting_temp FLOAT DEFAULT NULL,    -- °C (Phase change trigger point)
    cost_per_kg FLOAT DEFAULT 0.0       -- Local currency for capital investment
);

-- Upgrade existing materials table for PCM and Capital Cost if upgrading schema
ALTER TABLE materials
ADD COLUMN IF NOT EXISTS latent_heat FLOAT DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS melting_temp FLOAT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS cost_per_kg FLOAT DEFAULT 0.0;

-- Regional Economics for Payback Period (ROI) and Carbon Impact Calculation
CREATE TABLE IF NOT EXISTS regional_economics (
    id SERIAL PRIMARY KEY,
    climate_zone VARCHAR(50) UNIQUE NOT NULL,
    fuel_cost_per_kwh FLOAT NOT NULL,      -- Baseline cost of diesel/electricity in the region
    carbon_emission_factor FLOAT NOT NULL  -- kg CO2 per kWh to prove environmental impact
);

-- User-defined parametric shelter geometries and regional data
CREATE TABLE IF NOT EXISTS shelters (
    id SERIAL PRIMARY KEY,
    project_name VARCHAR(150) NOT NULL,
    climate_zone VARCHAR(50) NOT NULL, -- e.g., 'Extreme cold (Ladakh)', 'Extreme heat (Rajasthan)'
    shape_type VARCHAR(50) NOT NULL DEFAULT 'Rectangular', -- Vaulted, Dome, Rectangular
    azimuth_angle FLOAT NOT NULL DEFAULT 0.0, -- Orientation relative to true South
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    length FLOAT NOT NULL,
    width FLOAT NOT NULL,
    height FLOAT NOT NULL,
    glazing_ratio FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Mapping materials to shelter walls (for composite U-value calculation)
CREATE TABLE IF NOT EXISTS shelter_wall_layers (
    id SERIAL PRIMARY KEY,
    shelter_id INTEGER REFERENCES shelters(id) ON DELETE CASCADE,
    material_id INTEGER REFERENCES materials(id),
    thickness FLOAT NOT NULL, -- meters
    layer_order INTEGER NOT NULL -- inside to outside (1, 2, 3...)
);

-- Historical simulation results
CREATE TABLE IF NOT EXISTS simulation_logs (
    id SERIAL PRIMARY KEY,
    shelter_id INTEGER REFERENCES shelters(id) ON DELETE CASCADE,
    simulation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    peak_heating_kw FLOAT NOT NULL,
    average_pmv FLOAT NOT NULL,
    optimal_insulation_m FLOAT
);

-- Real-world IoT sensor data from actual shelters for model comparison
CREATE TABLE IF NOT EXISTS field_validation_data (
    id SERIAL PRIMARY KEY,
    shelter_id INTEGER REFERENCES shelters(id) ON DELETE CASCADE,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_indoor_temp FLOAT NOT NULL,
    actual_humidity FLOAT,
    predicted_indoor_temp FLOAT, -- Logged from the engine for direct comparison
    error_margin FLOAT -- The "Error/deviation" metric
);

-- Local storage for NASA POWER API historical weather data
CREATE TABLE IF NOT EXISTS climate_cache (
    id SERIAL PRIMARY KEY,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    ambient_temp FLOAT NOT NULL,
    solar_irradiance FLOAT NOT NULL,
    wind_speed FLOAT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_climate_cache_lat_lon ON climate_cache (latitude, longitude);

-- ===========================================================================
-- PROVENANCE-BASED MATERIAL & CLIMATE TABLES
-- ===========================================================================

-- Data source registry — tracks every document, dataset, or measurement source
CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    organization VARCHAR(255) NOT NULL,
    document_type VARCHAR(100) NOT NULL,       -- energy_code, standard, lab_report, climate_data, etc.
    document_id VARCHAR(255),
    version VARCHAR(50),
    year INTEGER,
    url TEXT,
    access_restriction VARCHAR(100) DEFAULT 'public',  -- public | restricted | classified
    access_notes TEXT,
    license_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ds_name ON data_sources (name);

-- Material category hierarchy
CREATE TABLE IF NOT EXISTS material_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    parent_category_id INTEGER REFERENCES material_categories(id),
    is_structural BOOLEAN DEFAULT FALSE,
    is_insulation BOOLEAN DEFAULT FALSE,
    is_defence_specific BOOLEAN DEFAULT FALSE
);

-- Thermal properties with full provenance
CREATE TABLE IF NOT EXISTS material_thermal_properties (
    id SERIAL PRIMARY KEY,
    material_name VARCHAR(150) NOT NULL,
    category_id INTEGER REFERENCES material_categories(id),
    property_name VARCHAR(100) NOT NULL,       -- density, thermal_conductivity, specific_heat, etc.
    value FLOAT NOT NULL,
    unit VARCHAR(50) NOT NULL,                 -- kg/m3, W/(m.K), J/(kg.K), etc.
    value_type VARCHAR(50) NOT NULL DEFAULT 'government_default',
                                                -- measured | government_default | manufacturer_declared | estimated | ml_predicted
    test_method VARCHAR(255),                   -- BIS standard or lab method
    uncertainty FLOAT,
    temperature_range VARCHAR(100),
    moisture_condition VARCHAR(100),
    region VARCHAR(100),
    notes TEXT,
    source_id INTEGER REFERENCES data_sources(id) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (material_name, property_name, source_id)
);
CREATE INDEX IF NOT EXISTS idx_mtp_material ON material_thermal_properties (material_name);
CREATE INDEX IF NOT EXISTS idx_mtp_category ON material_thermal_properties (category_id);
CREATE INDEX IF NOT EXISTS idx_mtp_value_type ON material_thermal_properties (value_type);

-- IMD climate stations
CREATE TABLE IF NOT EXISTS climate_stations (
    id SERIAL PRIMARY KEY,
    station_name VARCHAR(255) NOT NULL,
    station_id VARCHAR(50) UNIQUE NOT NULL,    -- IMD station code
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    elevation_m FLOAT,
    state VARCHAR(100),
    district VARCHAR(100),
    climate_zone VARCHAR(100),
    is_military BOOLEAN DEFAULT FALSE,
    access_restriction VARCHAR(100) DEFAULT 'restricted',
    access_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Raw IMD climate observations
CREATE TABLE IF NOT EXISTS climate_observations (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(50) REFERENCES climate_stations(station_id) NOT NULL,
    observation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    min_air_temperature_c FLOAT,
    max_air_temperature_c FLOAT,
    mean_air_temperature_c FLOAT,
    relative_humidity_percent FLOAT,
    precipitation_mm FLOAT,
    solar_radiation_w_m2 FLOAT,
    wind_speed_m_s FLOAT,
    wind_direction_deg FLOAT,
    atmospheric_pressure_hpa FLOAT,
    elevation_m FLOAT,
    snow_depth_cm FLOAT,
    quality_flag VARCHAR(20) DEFAULT 'verified',  -- verified | suspect | missing | estimated
    observation_period VARCHAR(50),
    missing_data_treatment TEXT,
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_co_station_ts ON climate_observations (station_id, observation_timestamp);
CREATE INDEX IF NOT EXISTS idx_co_quality ON climate_observations (quality_flag);

-- Computed design values from IMD observations
CREATE TABLE IF NOT EXISTS climate_design_values (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(50) REFERENCES climate_stations(station_id) NOT NULL,
    parameter_name VARCHAR(100) NOT NULL,
    percentile VARCHAR(20),                    -- e.g. "99%", "1%", "50%"
    value FLOAT NOT NULL,
    unit VARCHAR(50) NOT NULL,
    calculation_period VARCHAR(50),            -- e.g. "1991-2020"
    method TEXT,
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (station_id, parameter_name, percentile)
);

-- ML training dataset
CREATE TABLE IF NOT EXISTS ml_dataset_records (
    id SERIAL PRIMARY KEY,
    material_id INTEGER REFERENCES material_thermal_properties(id),
    region VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE,
    ambient_temperature_c FLOAT,
    relative_humidity_percent FLOAT,
    wind_speed_m_s FLOAT,
    solar_radiation_w_m2 FLOAT,
    material_thickness_m FLOAT,
    moisture_condition VARCHAR(100),
    surface_temperature_c FLOAT,
    heat_flux_w_m2 FLOAT,
    energy_demand_kwh FLOAT,
    compliance_label BOOLEAN,
    source_id INTEGER REFERENCES data_sources(id),
    split VARCHAR(20) DEFAULT 'train',         -- train | validation | test
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Multi-objective optimization run storage
CREATE TABLE IF NOT EXISTS optimization_runs (
    id SERIAL PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    objectives JSON,
    constraints JSON,
    pareto_front JSON,
    best_solution JSON,
    source_materials JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default regional economics data
INSERT INTO regional_economics (climate_zone, fuel_cost_per_kwh, carbon_emission_factor) VALUES
('Extreme cold (Ladakh)', 24.50, 0.27),
('Extreme cold (Kashmir)', 22.00, 0.35),
('Extreme heat (Rajasthan)', 8.50, 0.82),
('Moderate / Hill Station', 9.20, 0.75)
ON CONFLICT (climate_zone) DO NOTHING;

-- Insert default materials (including phase change materials and insulation)
INSERT INTO materials (name, conductivity, density, specific_heat, latent_heat, melting_temp, cost_per_kg) VALUES 
('EPS Insulation', 0.035, 30, 1450, 0.0, NULL, 180.0),
('Plywood Outer', 0.13, 600, 1200, 0.0, NULL, 95.0),
('Adobe Brick', 0.75, 1700, 1000, 0.0, NULL, 15.0),
('Paraffin PCM Wallboard', 0.21, 850, 2200, 190000.0, 22.0, 320.0),
('Bio-based PCM Composite', 0.18, 900, 2400, 210000.0, 21.5, 380.0)
ON CONFLICT (name) DO NOTHING;
