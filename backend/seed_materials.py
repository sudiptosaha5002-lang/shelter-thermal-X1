"""
Regional Material & Microclimate Database Seeder
=================================================
Seeds PostgreSQL with thermal properties for military and local materials,
climate data for extreme regions (Leh-Ladakh, Jaisalmer), and data-source
provenance tracking.

Authoritative Sources:
  - BEE ECBC / Eco-Niwas Samhita (Ministry of Power, Government of India)
  - BMTPC (Department of Science & Technology, Government of India)
  - IMD-CLIMS (India Meteorological Department)
  - BIS (Bureau of Indian Standards)
  - DRDO (Defence Research & Development Organisation) — restricted data

Usage:
  cd backend
  python seed_materials.py

Requires: sqlalchemy, psycopg2-binary, python-dotenv (see requirements.txt)
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://thermal_admin:securepassword123@localhost:5432/shelter_db",
)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


# ===========================================================================
# ORM MODELS — New provenance-based tables
# ===========================================================================


class DataSource(Base):
    """Registry of every document, dataset, or measurement source."""

    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    organization = Column(String(255), nullable=False)
    document_type = Column(String(100), nullable=False)  # code, standard, lab_report, etc.
    document_id = Column(String(255))  # e.g. BEE ECBC-2017, IS 13355
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
    property_name = Column(String(100), nullable=False)  # density, conductivity, etc.
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)  # kg/m3, W/(m.K), J/(kg.K), etc.
    value_type = Column(
        String(50),
        nullable=False,
        default="government_default",
    )  # measured | government_default | manufacturer_declared | estimated | ml_predicted
    test_method = Column(String(255))  # BIS standard or lab method
    uncertainty = Column(Float)  # absolute or relative uncertainty
    temperature_range = Column(String(100))  # e.g. "20-30 C"
    moisture_condition = Column(String(100))  # e.g. "dry", "as-received"
    region = Column(String(100))  # if material is region-specific
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
    station_id = Column(String(50), unique=True, nullable=False)  # IMD station code
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
    quality_flag = Column(String(20), default="verified")  # verified | suspect | missing | estimated
    observation_period = Column(String(50))  # e.g. "1991-2020"
    missing_data_treatment = Column(Text)
    source_id = Column(Integer, ForeignKey("data_sources.id"))
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())

    station = relationship("ClimateStation", back_populates="observations")
    source = relationship("DataSource", back_populates="climate_observations")


class ClimateDesignValues(Base):
    """Computed design values from IMD observations (not raw measurements)."""

    __tablename__ = "climate_design_values"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(50), ForeignKey("climate_stations.station_id"), nullable=False)
    parameter_name = Column(String(100), nullable=False)
    percentile = Column(String(20))  # e.g. "99%", "1%", "50%"
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    calculation_period = Column(String(50))  # e.g. "1991-2020"
    method = Column(Text)  # how it was calculated
    source_id = Column(Integer, ForeignKey("data_sources.id"))
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("station_id", "parameter_name", "percentile", name="uq_design_value"),
    )


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
    split = Column(String(20), default="train")  # train | validation | test
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())


class OptimizationRun(Base):
    """Stores each multi-objective optimization run."""

    __tablename__ = "optimization_runs"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(100), nullable=False)
    objectives = Column(JSON)  # {f1: "heat_transfer", f2: "mass", ...}
    constraints = Column(JSON)
    pareto_front = Column(JSON)  # list of optimal solutions
    best_solution = Column(JSON)
    source_materials = Column(JSON)  # material IDs used
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())


# ===========================================================================
# SEED DATA
# ===========================================================================


def seed_data_sources(session) -> dict:
    """Register all authoritative data sources."""
    sources = [
        {
            "name": "BEE ECBC-2017",
            "organization": "Bureau of Energy Efficiency, Ministry of Power, Government of India",
            "document_type": "energy_code",
            "document_id": "ECBC-2017",
            "version": "2017",
            "year": 2017,
            "url": "https://beeindia.gov.in/app/uploads/2023/06/ECBC-2017-English.pdf",
            "access_restriction": "public",
            "access_notes": "Publicly available energy conservation building code. Free for non-commercial use.",
            "license_summary": "Government of India public document. Commercial redistribution requires permission.",
        },
        {
            "name": "BEE Eco-Niwas Samhita 2018",
            "organization": "Bureau of Energy Efficiency, Ministry of Power, Government of India",
            "document_type": "energy_code",
            "document_id": "ECBC-R-2018",
            "version": "2018",
            "year": 2018,
            "url": "https://beeindia.gov.in/app/uploads/2023/06/Eco-Niwas-Samhita-2018.pdf",
            "access_restriction": "public",
            "access_notes": "Residential building energy conservation code. Publicly available.",
            "license_summary": "Government of India public document.",
        },
        {
            "name": "BMTPC Thermal Properties Database",
            "organization": "Building Materials and Technology Promotion Council, Department of Science & Technology, Government of India",
            "document_type": "material_database",
            "document_id": "BMTPC-TP-2020",
            "version": "2020",
            "year": 2020,
            "url": "https://bmtpc.in/MaterialPropertiesThermal.aspx",
            "access_restriction": "public",
            "access_notes": "Generic construction material thermal properties under aegis of DST, GoI.",
            "license_summary": "Government of India. Free for research and non-commercial use.",
        },
        {
            "name": "IMD-CLIMS Portal",
            "organization": "India Meteorological Department, Ministry of Earth Sciences, Government of India",
            "document_type": "climate_data",
            "document_id": "IMD-CLIMS",
            "version": "latest",
            "year": 2024,
            "url": "https://imdpune.gov.in/IDY/district_good.html",
            "access_restriction": "restricted",
            "access_notes": "IMD climate services portal. Commercial reproduction requires written permission from IMD. Record access conditions here.",
            "license_summary": "Government of India. Data access governed by IMD terms. Request permission for commercial/redistributive use.",
        },
        {
            "name": "BIS IS 13355: Thermal Insulation for Buildings",
            "organization": "Bureau of Indian Standards, Government of India",
            "document_type": "standard",
            "document_id": "IS 13355",
            "version": "1992 (reaffirmed)",
            "year": 1992,
            "url": "https://www.bis.gov.in",
            "access_restriction": "restricted",
            "access_notes": "BIS standards require purchase. Test methods only — not a bulk material property database.",
            "license_summary": "BIS copyright. Available for purchase from BIS.",
        },
        {
            "name": "DRDO Defence Materials Handbook",
            "organization": "Defence Research & Development Organisation, Ministry of Defence, Government of India",
            "document_type": "technical_handbook",
            "document_id": "DRDO-DMH-2021",
            "version": "2021",
            "year": 2021,
            "url": None,
            "access_restriction": "classified",
            "access_notes": "Defence-specific material data. Detailed military material data is restricted. Use only authorized DRDO technical documents.",
            "license_summary": "Government of India (Defence). Restricted access. Do not represent generic values as DRDO-certified without authorization.",
        },
        {
            "name": "BMTPC Low Cost Building Materials and Construction Technologies",
            "organization": "Building Materials and Technology Promotion Council, Department of Science & Technology, Government of India",
            "document_type": "technical_report",
            "document_id": "BMTPC-LCBM-2019",
            "version": "2019",
            "year": 2019,
            "url": "https://bmtpc.in/",
            "access_restriction": "public",
            "access_notes": "Covers fired-clay bricks, fly-ash bricks, calcium-silicate bricks, expanded-clay bricks, bamboo, stone, insulation, boards.",
            "license_summary": "Government of India. Free for research and non-commercial use.",
        },
    ]

    source_map = {}
    for s in sources:
        existing = session.query(DataSource).filter(DataSource.name == s["name"]).first()
        if existing:
            source_map[s["name"]] = existing
        else:
            obj = DataSource(**s)
            session.add(obj)
            session.flush()
            source_map[s["name"]] = obj
    session.commit()
    return source_map


def seed_material_categories(session) -> dict:
    """Create material category hierarchy."""
    categories = [
        {"name": "Masonry & Bricks", "description": "Fired clay, fly-ash, and concrete masonry units", "is_structural": True},
        {"name": "Concrete", "description": "Plain and reinforced concrete mixes", "is_structural": True},
        {"name": "Stone", "description": "Natural stone — granite, sandstone, limestone, marble", "is_structural": True},
        {"name": "Earth & Adobe", "description": "Rammed earth, adobe, compressed earth blocks", "is_structural": True},
        {"name": "Timber & Bamboo", "description": "Natural wood, engineered timber, bamboo composites", "is_structural": True},
        {"name": "Metals", "description": "Steel, aluminium, copper, and alloys", "is_structural": True},
        {"name": "Glass", "description": "Float glass, tempered, insulated glazing units", "is_structural": False},
        {"name": "Insulation — Fibrous", "description": "Glass wool, rock wool, mineral wool, sheep wool", "is_insulation": True},
        {"name": "Insulation — Foam", "description": "EPS, XPS, PUF/PIR, phenolic foam, aerogel", "is_insulation": True},
        {"name": "Insulation — Reflective", "description": "Radiant barriers, multi-layer insulation", "is_insulation": True},
        {"name": "Plaster & Mortar", "description": "Cement plaster, lime plaster, gypsum plaster, mortar", "is_structural": False},
        {"name": "Roofing & Thatch", "description": "Tiles, sheets, thatch, grass roofing", "is_structural": False},
        {"name": "Composite Panels", "description": "Fibre-reinforced panels, sandwich panels, OSB", "is_structural": True},
        {"name": "Ceramics", "description": "Technical ceramics, ceramic tiles, armour ceramic", "is_structural": True, "is_defence_specific": False},
        {"name": "Phase Change Materials", "description": "PCM, paraffin, bio-based, inorganic salt hydrates", "is_insulation": True},
        {"name": "Defence Materials", "description": "Composite armour, ballistic ceramic, ARMOX steel — restricted data", "is_structural": True, "is_defence_specific": True},
    ]

    cat_map = {}
    for c in categories:
        existing = session.query(MaterialCategory).filter(MaterialCategory.name == c["name"]).first()
        if existing:
            cat_map[c["name"]] = existing
        else:
            obj = MaterialCategory(**c)
            session.add(obj)
            session.flush()
            cat_map[c["name"]] = obj
    session.commit()
    return cat_map


def seed_bee_ecbc_materials(session, source_map: dict, cat_map: dict):
    """
    Seed thermal properties from BEE ECBC-2017 and Eco-Niwas Samhita 2018.
    Values are government-code defaults, not site-specific laboratory measurements.
    Source: BEE ECBC-2017 Table 5.1 / Eco-Niwas Samhita Annexure.
    """

    def _add(mat_name, prop_name, value, unit, category_name, notes=""):
        src = source_map["BEE ECBC-2017"]
        cat_id = cat_map[category_name].id if category_name in cat_map else None
        existing = (
            session.query(MaterialThermalProperty)
            .filter(
                MaterialThermalProperty.material_name == mat_name,
                MaterialThermalProperty.property_name == prop_name,
                MaterialThermalProperty.source_id == src.id,
            )
            .first()
        )
        if not existing:
            session.add(
                MaterialThermalProperty(
                    material_name=mat_name,
                    category_id=cat_id,
                    property_name=prop_name,
                    value=value,
                    unit=unit,
                    value_type="government_default",
                    source_id=src.id,
                    notes=notes,
                )
            )

    # ---- Burnt Clay Brick ----
    _add("Clay Brick (Burnt)", "density", 1800, "kg/m3", "Masonry & Bricks", "BEE ECBC Table 5.1 — solid burnt-clay brick")
    _add("Clay Brick (Burnt)", "thermal_conductivity", 0.84, "W/(m.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")
    _add("Clay Brick (Burnt)", "specific_heat", 880, "J/(kg.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")

    # ---- Fly-Ash Brick ----
    _add("Fly-Ash Brick", "density", 1600, "kg/m3", "Masonry & Bricks", "BEE Eco-Niwas Samhita — fly-ash brick")
    _add("Fly-Ash Brick", "thermal_conductivity", 0.62, "W/(m.K)", "Masonry & Bricks", "BEE Eco-Niwas Samhita")
    _add("Fly-Ash Brick", "specific_heat", 850, "J/(kg.K)", "Masonry & Bricks", "BEE Eco-Niwas Samhita")

    # ---- Concrete Block (Hollow) ----
    _add("Concrete Block (Hollow)", "density", 1100, "kg/m3", "Masonry & Bricks", "BEE ECBC Table 5.1")
    _add("Concrete Block (Hollow)", "thermal_conductivity", 0.51, "W/(m.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")
    _add("Concrete Block (Hollow)", "specific_heat", 840, "J/(kg.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")

    # ---- Concrete Block (Solid) ----
    _add("Concrete Block (Solid)", "density", 2000, "kg/m3", "Masonry & Bricks", "BEE ECBC Table 5.1")
    _add("Concrete Block (Solid)", "thermal_conductivity", 1.40, "W/(m.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")
    _add("Concrete Block (Solid)", "specific_heat", 880, "J/(kg.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")

    # ---- Reinforced Concrete ----
    _add("Reinforced Concrete", "density", 2400, "kg/m3", "Concrete", "BEE ECBC Table 5.1 — 1:2:4 mix")
    _add("Reinforced Concrete", "thermal_conductivity", 1.75, "W/(m.K)", "Concrete", "BEE ECBC Table 5.1")
    _add("Reinforced Concrete", "specific_heat", 880, "J/(kg.K)", "Concrete", "BEE ECBC Table 5.1")

    # ---- Plain Cement Concrete ----
    _add("Plain Cement Concrete", "density", 2300, "kg/m3", "Concrete", "BEE ECBC Table 5.1")
    _add("Plain Cement Concrete", "thermal_conductivity", 1.40, "W/(m.K)", "Concrete", "BEE ECBC Table 5.1")
    _add("Plain Cement Concrete", "specific_heat", 880, "J/(kg.K)", "Concrete", "BEE ECBC Table 5.1")

    # ---- Cement Mortar ----
    _add("Cement Mortar (1:4)", "density", 1800, "kg/m3", "Plaster & Mortar", "BEE ECBC Table 5.1")
    _add("Cement Mortar (1:4)", "thermal_conductivity", 0.72, "W/(m.K)", "Plaster & Mortar", "BEE ECBC Table 5.1")
    _add("Cement Mortar (1:4)", "specific_heat", 840, "J/(kg.K)", "Plaster & Mortar", "BEE ECBC Table 5.1")

    # ---- Lime Mortar ----
    _add("Lime Mortar", "density", 1600, "kg/m3", "Plaster & Mortar", "BEE ECBC Table 5.1")
    _add("Lime Mortar", "thermal_conductivity", 0.69, "W/(m.K)", "Plaster & Mortar", "BEE ECBC Table 5.1")
    _add("Lime Mortar", "specific_heat", 840, "J/(kg.K)", "Plaster & Mortar", "BEE ECBC Table 5.1")

    # ---- Steel ----
    _add("Steel (Structural)", "density", 7850, "kg/m3", "Metals", "BEE ECBC Table 5.1")
    _add("Steel (Structural)", "thermal_conductivity", 50.0, "W/(m.K)", "Metals", "BEE ECBC Table 5.1")
    _add("Steel (Structural)", "specific_heat", 480, "J/(kg.K)", "Metals", "BEE ECBC Table 5.1")

    # ---- Aluminium ----
    _add("Aluminium", "density", 2700, "kg/m3", "Metals", "BEE ECBC Table 5.1")
    _add("Aluminium", "thermal_conductivity", 205.0, "W/(m.K)", "Metals", "BEE ECBC Table 5.1")
    _add("Aluminium", "specific_heat", 920, "J/(kg.K)", "Metals", "BEE ECBC Table 5.1")

    # ---- Glass (Float) ----
    _add("Glass (Float)", "density", 2500, "kg/m3", "Glass", "BEE ECBC Table 5.1")
    _add("Glass (Float)", "thermal_conductivity", 1.0, "W/(m.K)", "Glass", "BEE ECBC Table 5.1")
    _add("Glass (Float)", "specific_heat", 750, "J/(kg.K)", "Glass", "BEE ECBC Table 5.1")
    _add("Glass (Float)", "emissivity", 0.84, "unitless", "Glass", "BEE ECBC Table 5.1")

    # ---- Double Glazed Unit ----
    _add("Double Glazed Unit", "density", 2500, "kg/m3", "Glass", "BEE ECBC Table 5.1 — U-value based")
    _add("Double Glazed Unit", "thermal_conductivity", 1.0, "W/(m.K)", "Glass", "BEE ECBC Table 5.1 — effective k for air gap")
    _add("Double Glazed Unit", "u_value", 2.8, "W/(m2.K)", "Glass", "BEE ECBC Table 5.1 — clear DGU with 12mm air gap")

    # ---- EPS Insulation ----
    _add("EPS (Expanded Polystyrene)", "density", 25, "kg/m3", "Insulation — Foam", "BEE ECBC Table 5.1")
    _add("EPS (Expanded Polystyrene)", "thermal_conductivity", 0.035, "W/(m.K)", "Insulation — Foam", "BEE ECBC Table 5.1")
    _add("EPS (Expanded Polystyrene)", "specific_heat", 1450, "J/(kg.K)", "Insulation — Foam", "BEE ECBC Table 5.1")

    # ---- XPS Insulation ----
    _add("XPS (Extruded Polystyrene)", "density", 35, "kg/m3", "Insulation — Foam", "BEE ECBC Table 5.1")
    _add("XPS (Extruded Polystyrene)", "thermal_conductivity", 0.030, "W/(m.K)", "Insulation — Foam", "BEE ECBC Table 5.1")
    _add("XPS (Extruded Polystyrene)", "specific_heat", 1400, "J/(kg.K)", "Insulation — Foam", "BEE ECBC Table 5.1")

    # ---- PUF Insulation ----
    _add("PUF (Polyurethane Foam)", "density", 32, "kg/m3", "Insulation — Foam", "BEE ECBC Table 5.1")
    _add("PUF (Polyurethane Foam)", "thermal_conductivity", 0.022, "W/(m.K)", "Insulation — Foam", "BEE ECBC Table 5.1")
    _add("PUF (Polyurethane Foam)", "specific_heat", 1500, "J/(kg.K)", "Insulation — Foam", "BEE ECBC Table 5.1")

    # ---- Glass Wool ----
    _add("Glass Wool", "density", 24, "kg/m3", "Insulation — Fibrous", "BEE ECBC Table 5.1")
    _add("Glass Wool", "thermal_conductivity", 0.040, "W/(m.K)", "Insulation — Fibrous", "BEE ECBC Table 5.1")
    _add("Glass Wool", "specific_heat", 840, "J/(kg.K)", "Insulation — Fibrous", "BEE ECBC Table 5.1")

    # ---- Rock Wool ----
    _add("Rock Wool", "density", 80, "kg/m3", "Insulation — Fibrous", "BEE ECBC Table 5.1")
    _add("Rock Wool", "thermal_conductivity", 0.038, "W/(m.K)", "Insulation — Fibrous", "BEE ECBC Table 5.1")
    _add("Rock Wool", "specific_heat", 840, "J/(kg.K)", "Insulation — Fibrous", "BEE ECBC Table 5.1")

    # ---- Timber / Wood ----
    _add("Timber (Softwood)", "density", 550, "kg/m3", "Timber & Bamboo", "BEE ECBC Table 5.1")
    _add("Timber (Softwood)", "thermal_conductivity", 0.12, "W/(m.K)", "Timber & Bamboo", "BEE ECBC Table 5.1")
    _add("Timber (Softwood)", "specific_heat", 1200, "J/(kg.K)", "Timber & Bamboo", "BEE ECBC Table 5.1")

    _add("Timber (Hardwood)", "density", 720, "kg/m3", "Timber & Bamboo", "BEE ECBC Table 5.1")
    _add("Timber (Hardwood)", "thermal_conductivity", 0.16, "W/(m.K)", "Timber & Bamboo", "BEE ECBC Table 5.1")
    _add("Timber (Hardwood)", "specific_heat", 1210, "J/(kg.K)", "Timber & Bamboo", "BEE ECBC Table 5.1")

    # ---- Stone ----
    _add("Sandstone", "density", 2200, "kg/m3", "Stone", "BEE ECBC Table 5.1")
    _add("Sandstone", "thermal_conductivity", 1.70, "W/(m.K)", "Stone", "BEE ECBC Table 5.1")
    _add("Sandstone", "specific_heat", 800, "J/(kg.K)", "Stone", "BEE ECBC Table 5.1")

    _add("Granite", "density", 2650, "kg/m3", "Stone", "BEE ECBC Table 5.1")
    _add("Granite", "thermal_conductivity", 2.80, "W/(m.K)", "Stone", "BEE ECBC Table 5.1")
    _add("Granite", "specific_heat", 820, "J/(kg.K)", "Stone", "BEE ECBC Table 5.1")

    _add("Limestone", "density", 2200, "kg/m3", "Stone", "BEE ECBC Table 5.1")
    _add("Limestone", "thermal_conductivity", 1.33, "W/(m.K)", "Stone", "BEE ECBC Table 5.1")
    _add("Limestone", "specific_heat", 810, "J/(kg.K)", "Stone", "BEE ECBC Table 5.1")

    # ---- Earth / Adobe ----
    _add("Adobe (Earth Brick)", "density", 1700, "kg/m3", "Earth & Adobe", "BEE Eco-Niwas Samhita — traditional material")
    _add("Adobe (Earth Brick)", "thermal_conductivity", 0.68, "W/(m.K)", "Earth & Adobe", "BEE Eco-Niwas Samhita")
    _add("Adobe (Earth Brick)", "specific_heat", 880, "J/(kg.K)", "Earth & Adobe", "BEE Eco-Niwas Samhita")

    _add("Rammed Earth", "density", 1900, "kg/m3", "Earth & Adobe", "BEE Eco-Niwas Samhita")
    _add("Rammed Earth", "thermal_conductivity", 0.80, "W/(m.K)", "Earth & Adobe", "BEE Eco-Niwas Samhita")
    _add("Rammed Earth", "specific_heat", 840, "J/(kg.K)", "Earth & Adobe", "BEE Eco-Niwas Samhita")

    # ---- Bamboo ----
    _add("Bamboo", "density", 700, "kg/m3", "Timber & Bamboo", "BMTPC generic bamboo properties")
    _add("Bamboo", "thermal_conductivity", 0.16, "W/(m.K)", "Timber & Bamboo", "BMTPC generic bamboo properties")
    _add("Bamboo", "specific_heat", 1580, "J/(kg.K)", "Timber & Bamboo", "BMTPC generic bamboo properties")

    # ---- Roofing Tiles ----
    _add("Clay Roofing Tile", "density", 1900, "kg/m3", "Roofing & Thatch", "BEE ECBC Table 5.1")
    _add("Clay Roofing Tile", "thermal_conductivity", 0.84, "W/(m.K)", "Roofing & Thatch", "BEE ECBC Table 5.1")
    _add("Clay Roofing Tile", "specific_heat", 840, "J/(kg.K)", "Roofing & Thatch", "BEE ECBC Table 5.1")

    # ---- Corrugated Sheet ----
    _add("Corrugated Galvanised Iron", "density", 7850, "kg/m3", "Roofing & Thatch", "BEE ECBC Table 5.1")
    _add("Corrugated Galvanised Iron", "thermal_conductivity", 50.0, "W/(m.K)", "Roofing & Thatch", "BEE ECBC Table 5.1")
    _add("Corrugated Galvanised Iron", "specific_heat", 480, "J/(kg.K)", "Roofing & Thatch", "BEE ECBC Table 5.1")
    _add("Corrugated Galvanised Iron", "solar_absorptance", 0.70, "unitless", "Roofing & Thatch", "BEE ECBC Table 5.1")

    # ---- Thatch ----
    _add("Thatch (Grass/Dry Leaves)", "density", 120, "kg/m3", "Roofing & Thatch", "BMTPC traditional roofing")
    _add("Thatch (Grass/Dry Leaves)", "thermal_conductivity", 0.065, "W/(m.K)", "Roofing & Thatch", "BMTPC traditional roofing")
    _add("Thatch (Grass/Dry Leaves)", "specific_heat", 1500, "J/(kg.K)", "Roofing & Thatch", "BMTPC traditional roofing")

    # ---- Plywood ----
    _add("Plywood", "density", 600, "kg/m3", "Timber & Bamboo", "BEE ECBC Table 5.1")
    _add("Plywood", "thermal_conductivity", 0.13, "W/(m.K)", "Timber & Bamboo", "BEE ECBC Table 5.1")
    _add("Plywood", "specific_heat", 1200, "J/(kg.K)", "Timber & Bamboo", "BEE ECBC Table 5.1")

    # ---- Gypsum Board ----
    _add("Gypsum Board", "density", 800, "kg/m3", "Plaster & Mortar", "BEE ECBC Table 5.1")
    _add("Gypsum Board", "thermal_conductivity", 0.16, "W/(m.K)", "Plaster & Mortar", "BEE ECBC Table 5.1")
    _add("Gypsum Board", "specific_heat", 1000, "J/(kg.K)", "Plaster & Mortar", "BEE ECBC Table 5.1")

    # ---- AAC Block ----
    _add("AAC Block (Autoclaved Aerated Concrete)", "density", 600, "kg/m3", "Masonry & Bricks", "BEE ECBC Table 5.1")
    _add("AAC Block (Autoclaved Aerated Concrete)", "thermal_conductivity", 0.16, "W/(m.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")
    _add("AAC Block (Autoclaved Aerated Concrete)", "specific_heat", 1000, "J/(kg.K)", "Masonry & Bricks", "BEE ECBC Table 5.1")

    # ---- Calcium Silicate Board ----
    _add("Calcium Silicate Board", "density", 870, "kg/m3", "Plaster & Mortar", "BMTPC thermal properties database")
    _add("Calcium Silicate Board", "thermal_conductivity", 0.17, "W/(m.K)", "Plaster & Mortar", "BMTPC thermal properties database")
    _add("Calcium Silicate Board", "specific_heat", 1000, "J/(kg.K)", "Plaster & Mortar", "BMTPC thermal properties database")

    session.commit()
    print("  [+] BEE ECBC / Eco-Niwas thermal properties seeded.")


def seed_bmtpc_materials(session, source_map: dict, cat_map: dict):
    """
    Seed BMTPC-specific materials not already in BEE ECBC.
    Source: BMTPC Thermal Properties Database and Low-Cost Building Materials report.
    """

    def _add(mat_name, prop_name, value, unit, category_name, notes=""):
        src = source_map["BMTPC Thermal Properties Database"]
        cat_id = cat_map[category_name].id if category_name in cat_map else None
        existing = (
            session.query(MaterialThermalProperty)
            .filter(
                MaterialThermalProperty.material_name == mat_name,
                MaterialThermalProperty.property_name == prop_name,
                MaterialThermalProperty.source_id == src.id,
            )
            .first()
        )
        if not existing:
            session.add(
                MaterialThermalProperty(
                    material_name=mat_name,
                    category_id=cat_id,
                    property_name=prop_name,
                    value=value,
                    unit=unit,
                    value_type="government_default",
                    source_id=src.id,
                    notes=notes,
                )
            )

    # ---- Expanded Clay Aggregate ----
    _add("Expanded Clay Aggregate Concrete", "density", 1200, "kg/m3", "Concrete", "BMTPC — lightweight aggregate concrete")
    _add("Expanded Clay Aggregate Concrete", "thermal_conductivity", 0.45, "W/(m.K)", "Concrete", "BMTPC")
    _add("Expanded Clay Aggregate Concrete", "specific_heat", 880, "J/(kg.K)", "Concrete", "BMTPC")
    _add("Expanded Clay Aggregate Concrete", "volumetric_heat_capacity", 528000, "J/(m3.K)", "Concrete", "BMTPC — computed from density x specific_heat")

    # ---- Cellular Lightweight Concrete ----
    _add("Cellular Lightweight Concrete", "density", 600, "kg/m3", "Concrete", "BMTPC — thermal insulation concrete")
    _add("Cellular Lightweight Concrete", "thermal_conductivity", 0.18, "W/(m.K)", "Concrete", "BMTPC")
    _add("Cellular Lightweight Concrete", "specific_heat", 1000, "J/(kg.K)", "Concrete", "BMTPC")

    # ---- Stabilised Compressed Earth Block (CSEB) ----
    _add("Stabilised CSEB", "density", 1750, "kg/m3", "Earth & Adobe", "BMTPC — cement-stabilised earth block")
    _add("Stabilised CSEB", "thermal_conductivity", 0.72, "W/(m.K)", "Earth & Adobe", "BMTPC")
    _add("Stabilised CSEB", "specific_heat", 880, "J/(kg.K)", "Earth & Adobe", "BMTPC")

    # ---- Bamboo Composite Board ----
    _add("Bamboo Composite Board", "density", 800, "kg/m3", "Timber & Bamboo", "BMTPC — bamboo-based engineered panel")
    _add("Bamboo Composite Board", "thermal_conductivity", 0.15, "W/(m.K)", "Timber & Bamboo", "BMTPC")
    _add("Bamboo Composite Board", "specific_heat", 1500, "J/(kg.K)", "Timber & Bamboo", "BMTPC")

    # ---- Acrylic Board ----
    _add("Acrylic Sheet", "density", 1190, "kg/m3", "Glass", "BMTPC — PMMA sheet")
    _add("Acrylic Sheet", "thermal_conductivity", 0.19, "W/(m.K)", "Glass", "BMTPC")
    _add("Acrylic Sheet", "specific_heat", 1460, "J/(kg.K)", "Glass", "BMTPC")

    # ---- Aerogel Insulation ----
    _add("Aerogel Blanket", "density", 200, "kg/m3", "Insulation — Foam", "BMTPC / manufacturer data — super-insulation")
    _add("Aerogel Blanket", "thermal_conductivity", 0.015, "W/(m.K)", "Insulation — Foam", "BMTPC / manufacturer data")
    _add("Aerogel Blanket", "specific_heat", 1000, "J/(kg.K)", "Insulation — Foam", "BMTPC / manufacturer data")

    # ---- Phenolic Foam ----
    _add("Phenolic Foam", "density", 40, "kg/m3", "Insulation — Foam", "BMTPC / manufacturer data")
    _add("Phenolic Foam", "thermal_conductivity", 0.022, "W/(m.K)", "Insulation — Foam", "BMTPC / manufacturer data")
    _add("Phenolic Foam", "specific_heat", 1400, "J/(kg.K)", "Insulation — Foam", "BMTPC / manufacturer data")

    # ---- Sheep Wool Insulation ----
    _add("Sheep Wool Insulation", "density", 18, "kg/m3", "Insulation — Fibrous", "BMTPC — natural fibre insulation")
    _add("Sheep Wool Insulation", "thermal_conductivity", 0.038, "W/(m.K)", "Insulation — Fibrous", "BMTPC")
    _add("Sheep Wool Insulation", "specific_heat", 1380, "J/(kg.K)", "Insulation — Fibrous", "BMTPC")

    # ---- Jute Board ----
    _add("Jute Composite Board", "density", 250, "kg/m3", "Insulation — Fibrous", "BMTPC — natural fibre board")
    _add("Jute Composite Board", "thermal_conductivity", 0.055, "W/(m.K)", "Insulation — Fibrous", "BMTPC")
    _add("Jute Composite Board", "specific_heat", 1500, "J/(kg.K)", "Insulation — Fibrous", "BMTPC")

    # ---- Ferrock (iron-rich) ----
    _add("Ferrock", "density", 1800, "kg/m3", "Concrete", "BMTPC — iron-rich geopolymer concrete")
    _add("Ferrock", "thermal_conductivity", 0.95, "W/(m.K)", "Concrete", "BMTPC")
    _add("Ferrock", "specific_heat", 880, "J/(kg.K)", "Concrete", "BMTPC")

    # ---- Composite Panels ----
    _add("Fibre-Reinforced Polymer Panel", "density", 1800, "kg/m3", "Composite Panels", "BMTPC / manufacturer data")
    _add("Fibre-Reinforced Polymer Panel", "thermal_conductivity", 0.25, "W/(m.K)", "Composite Panels", "BMTPC / manufacturer data")
    _add("Fibre-Reinforced Polymer Panel", "specific_heat", 1000, "J/(kg.K)", "Composite Panels", "BMTPC / manufacturer data")

    # ---- OSB (Oriented Strand Board) ----
    _add("OSB (Oriented Strand Board)", "density", 650, "kg/m3", "Composite Panels", "BMTPC")
    _add("OSB (Oriented Strand Board)", "thermal_conductivity", 0.13, "W/(m.K)", "Composite Panels", "BMTPC")
    _add("OSB (Oriented Strand Board)", "specific_heat", 1200, "J/(kg.K)", "Composite Panels", "BMTPC")

    session.commit()
    print("  [+] BMTPC material properties seeded.")


def seed_defence_materials(session, source_map: dict, cat_map: dict):
    """
    Seed generic defence-related materials with CAUTION.
    These are engineering estimates — NOT DRDO-certified values unless explicitly authorized.
    """
    src = source_map["DRDO Defence Materials Handbook"]
    cat_id = cat_map["Defence Materials"].id if "Defence Materials" in cat_map else None
    ceramic_cat_id = cat_map["Ceramics"].id if "Ceramics" in cat_map else None

    def _add(mat_name, prop_name, value, unit, category_id, notes=""):
        existing = (
            session.query(MaterialThermalProperty)
            .filter(
                MaterialThermalProperty.material_name == mat_name,
                MaterialThermalProperty.property_name == prop_name,
                MaterialThermalProperty.source_id == src.id,
            )
            .first()
        )
        if not existing:
            session.add(
                MaterialThermalProperty(
                    material_name=mat_name,
                    category_id=category_id,
                    property_name=prop_name,
                    value=value,
                    unit=unit,
                    value_type="estimated",
                    source_id=src.id,
                    notes=notes,
                )
            )

    # ---- ARMOX Steel (Armour Steel) ----
    _add("ARMOX 500T Steel", "density", 7850, "kg/m3", cat_id,
         "CAUTION: Engineering estimate. DRDO-restricted for classified values. Use manufacturer datasheet with batch/grade.")
    _add("ARMOX 500T Steel", "thermal_conductivity", 42.0, "W/(m.K)", cat_id,
         "CAUTION: Engineering estimate — not DRDO-certified.")
    _add("ARMOX 500T Steel", "specific_heat", 480, "J/(kg.K)", cat_id, "CAUTION: Engineering estimate.")

    # ---- Boron Carbide Ceramic (Armour) ----
    _add("Boron Carbide Ceramic (B4C)", "density", 2520, "kg/m3", ceramic_cat_id,
         "CAUTION: Engineering estimate for armour-grade ceramic. DRDO data restricted.")
    _add("Boron Carbide Ceramic (B4C)", "thermal_conductivity", 30.0, "W/(m.K)", ceramic_cat_id,
         "CAUTION: Engineering estimate — varies with sintering process.")
    _add("Boron Carbide Ceramic (B4C)", "specific_heat", 950, "J/(kg.K)", ceramic_cat_id, "CAUTION: Engineering estimate.")

    # ---- Silicon Carbide Ceramic (Armour) ----
    _add("Silicon Carbide Ceramic (SiC)", "density", 3210, "kg/m3", ceramic_cat_id,
         "CAUTION: Engineering estimate for armour-grade SiC. Use manufacturer NABL-accredited test report.")
    _add("Silicon Carbide Ceramic (SiC)", "thermal_conductivity", 120.0, "W/(m.K)", ceramic_cat_id, "CAUTION: Engineering estimate.")
    _add("Silicon Carbide Ceramic (SiC)", "specific_heat", 750, "J/(kg.K)", ceramic_cat_id, "CAUTION: Engineering estimate.")

    # ---- Alumina Ceramic ----
    _add("Alumina Ceramic (Al2O3 99%)", "density", 3900, "kg/m3", ceramic_cat_id,
         "CAUTION: Engineering estimate. Grade-dependent — use BIS/ISO test method data.")
    _add("Alumina Ceramic (Al2O3 99%)", "thermal_conductivity", 30.0, "W/(m.K)", ceramic_cat_id, "CAUTION: Engineering estimate.")
    _add("Alumina Ceramic (Al2O3 99%)", "specific_heat", 880, "J/(kg.K)", ceramic_cat_id, "CAUTION: Engineering estimate.")

    # ---- UHMWPE (Ultra-High Molecular Weight Polyethylene) ----
    _add("UHMWPE (Dyneema/Spectra)", "density", 970, "kg/m3", cat_id,
         "CAUTION: Engineering estimate for ballistic-grade UHMWPE. Manufacturer certificate required.")
    _add("UHMWPE (Dyneema/Spectra)", "thermal_conductivity", 0.45, "W/(m.K)", cat_id, "CAUTION: Engineering estimate.")
    _add("UHMWPE (Dyneema/Spectra)", "specific_heat", 1800, "J/(kg.K)", cat_id, "CAUTION: Engineering estimate.")

    # ---- Fibre-Reinforced Composite (Glass/Carbon) ----
    _add("GFRP Composite (Glass Fibre Reinforced)", "density", 1800, "kg/m3", cat_map["Composite Panels"].id,
         "CAUTION: Engineering estimate. Use NABL test report for specific laminate.")
    _add("GFRP Composite (Glass Fibre Reinforced)", "thermal_conductivity", 0.35, "W/(m.K)", cat_map["Composite Panels"].id, "CAUTION: Engineering estimate.")
    _add("GFRP Composite (Glass Fibre Reinforced)", "specific_heat", 1050, "J/(kg.K)", cat_map["Composite Panels"].id, "CAUTION: Engineering estimate.")

    _add("CFRP Composite (Carbon Fibre Reinforced)", "density", 1550, "kg/m3", cat_map["Composite Panels"].id,
         "CAUTION: Engineering estimate. Use NABL test report for specific laminate.")
    _add("CFRP Composite (Carbon Fibre Reinforced)", "thermal_conductivity", 5.0, "W/(m.K)", cat_map["Composite Panels"].id,
         "CAUTION: Engineering estimate — highly anisotropic.")
    _add("CFRP Composite (Carbon Fibre Reinforced)", "specific_heat", 1000, "J/(kg.K)", cat_map["Composite Panels"].id, "CAUTION: Engineering estimate.")

    session.commit()
    print("  [+] Defence material estimates seeded (with CAUTION flags).")


def seed_climate_stations(session, source_map: dict) -> dict:
    """Seed IMD climate stations for Leh-Ladakh and Jaisalmer."""
    src = source_map["IMD-CLIMS Portal"]

    stations = [
        {
            "station_name": "Leh",
            "station_id": "IMD-LAD-001",
            "latitude": 34.1551,
            "longitude": 77.5751,
            "elevation_m": 3524,
            "state": "Ladakh",
            "district": "Leh",
            "climate_zone": "Extreme cold (Ladakh) — high-altitude cold desert",
            "is_military": True,
            "access_restriction": "restricted",
            "access_notes": "IMD data requires written permission for commercial use. Military installations may have additional restrictions. Record access conditions.",
        },
        {
            "station_name": "Kargil",
            "station_id": "IMD-LAD-002",
            "latitude": 34.5538,
            "longitude": 76.1344,
            "elevation_m": 2676,
            "state": "Ladakh",
            "district": "Kargil",
            "climate_zone": "Extreme cold (Ladakh) — high-altitude cold desert",
            "is_military": True,
            "access_restriction": "restricted",
            "access_notes": "IMD data. Kargil has military significance — access may require defence authorization.",
        },
        {
            "station_name": "Srinagar (Kashmir)",
            "station_id": "IMD-JK-001",
            "latitude": 34.0837,
            "longitude": 74.7973,
            "elevation_m": 1585,
            "state": "Jammu & Kashmir",
            "district": "Srinagar",
            "climate_zone": "Extreme cold (Kashmir) — high-altitude temperate valley",
            "is_military": True,
            "access_restriction": "restricted",
            "access_notes": "IMD data. Kashmir valley — military installations present. Active LoC proximity. Access may require defence authorization.",
        },
        {
            "station_name": "Baramulla (Kashmir)",
            "station_id": "IMD-JK-002",
            "latitude": 34.2087,
            "longitude": 74.3457,
            "elevation_m": 1590,
            "state": "Jammu & Kashmir",
            "district": "Baramulla",
            "climate_zone": "Extreme cold (Kashmir) — high-altitude temperate valley",
            "is_military": True,
            "access_restriction": "restricted",
            "access_notes": "IMD data. Near LoC — military area. Restricted access.",
        },
        {
            "station_name": "Jaisalmer",
            "station_id": "IMD-RJ-001",
            "latitude": 26.9157,
            "longitude": 70.9083,
            "elevation_m": 171,
            "state": "Rajasthan",
            "district": "Jaisalmer",
            "climate_zone": "Extreme heat (Rajasthan) — hot arid desert",
            "is_military": False,
            "access_restriction": "restricted",
            "access_notes": "IMD data. Pokhran test range nearby — military area restrictions may apply for certain coordinates.",
        },
        {
            "station_name": "Bikaner",
            "station_id": "IMD-RJ-002",
            "latitude": 28.0229,
            "longitude": 73.3132,
            "elevation_m": 237,
            "state": "Rajasthan",
            "district": "Bikaner",
            "climate_zone": "Extreme heat (Rajasthan) — hot arid desert",
            "is_military": False,
            "access_restriction": "restricted",
            "access_notes": "IMD data.",
        },
    ]

    station_map = {}
    for st in stations:
        existing = session.query(ClimateStation).filter(ClimateStation.station_id == st["station_id"]).first()
        if existing:
            station_map[st["station_id"]] = existing
        else:
            obj = ClimateStation(**st)
            session.add(obj)
            session.flush()
            station_map[st["station_id"]] = obj
    session.commit()
    print("  [+] IMD climate stations seeded.")
    return station_map


def seed_climate_design_values(session, source_map: dict, station_map: dict):
    """
    Seed design climate values computed from IMD observations.
    These are NOT raw measurements — they are derived design values.
    """
    src = source_map["IMD-CLIMS Portal"]

    design_values = [
        # ---- Leh (34.15°N, 77.58°E, 3524 m) ----
        {"station_id": "IMD-LAD-001", "parameter_name": "min_air_temperature", "percentile": "1%", "value": -33.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual minimum of daily minimum temperatures, 1st percentile over 30-year period"},
        {"station_id": "IMD-LAD-001", "parameter_name": "max_air_temperature", "percentile": "99%", "value": 35.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual maximum of daily maximum temperatures, 99th percentile over 30-year period"},
        {"station_id": "IMD-LAD-001", "parameter_name": "min_air_temperature", "percentile": "50%", "value": -14.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Median of annual minimum temperatures over 30-year period"},
        {"station_id": "IMD-LAD-001", "parameter_name": "max_air_temperature", "percentile": "50%", "value": 27.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Median of annual maximum temperatures over 30-year period"},
        {"station_id": "IMD-LAD-001", "parameter_name": "relative_humidity", "percentile": "50%", "value": 36.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Annual mean relative humidity over 30-year period"},
        {"station_id": "IMD-LAD-001", "parameter_name": "precipitation", "percentile": "50%", "value": 102.0, "unit": "mm/year",
         "calculation_period": "1991-2020", "method": "Annual total precipitation median over 30-year period"},
        {"station_id": "IMD-LAD-001", "parameter_name": "wind_speed", "percentile": "50%", "value": 4.5, "unit": "m/s",
         "calculation_period": "1991-2020", "method": "Mean daily wind speed at 10m height"},
        {"station_id": "IMD-LAD-001", "parameter_name": "atmospheric_pressure", "percentile": "50%", "value": 660.0, "unit": "hPa",
         "calculation_period": "1991-2020", "method": "Standard atmospheric pressure at 3524m elevation (barometric formula)"},
        {"station_id": "IMD-LAD-001", "parameter_name": "snow_depth", "percentile": "99%", "value": 65.0, "unit": "cm",
         "calculation_period": "1991-2020", "method": "Maximum snow depth recorded on ground"},
        {"station_id": "IMD-LAD-001", "parameter_name": "solar_radiation", "percentile": "50%", "value": 5.5, "unit": "kWh/m2/day",
         "calculation_period": "1991-2020", "method": "Mean daily global horizontal irradiance from IMD/NASA POWER cross-validation"},
        {"station_id": "IMD-LAD-001", "parameter_name": "freeze_thaw_cycles", "percentile": "50%", "value": 120, "unit": "cycles/year",
         "calculation_period": "2010-2020", "method": "Estimated from daily min/max temperature crossing 0°C"},

        # ---- Kargil (34.55°N, 76.13°E, 2676 m) ----
        {"station_id": "IMD-LAD-002", "parameter_name": "min_air_temperature", "percentile": "1%", "value": -25.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual minimum, 1st percentile"},
        {"station_id": "IMD-LAD-002", "parameter_name": "max_air_temperature", "percentile": "99%", "value": 38.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual maximum, 99th percentile"},
        {"station_id": "IMD-LAD-002", "parameter_name": "relative_humidity", "percentile": "50%", "value": 42.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Annual mean"},
        {"station_id": "IMD-LAD-002", "parameter_name": "precipitation", "percentile": "50%", "value": 150.0, "unit": "mm/year",
         "calculation_period": "1991-2020", "method": "Annual total median"},
        {"station_id": "IMD-LAD-002", "parameter_name": "wind_speed", "percentile": "50%", "value": 3.8, "unit": "m/s",
         "calculation_period": "1991-2020", "method": "Mean daily wind speed"},
        {"station_id": "IMD-LAD-002", "parameter_name": "atmospheric_pressure", "percentile": "50%", "value": 730.0, "unit": "hPa",
         "calculation_period": "1991-2020", "method": "Barometric formula at 2676m elevation"},
        {"station_id": "IMD-LAD-002", "parameter_name": "solar_radiation", "percentile": "50%", "value": 5.2, "unit": "kWh/m2/day",
         "calculation_period": "1991-2020", "method": "Mean GHI cross-validated"},

        # ---- Srinagar, Kashmir (34.08°N, 74.80°E, 1585 m) ----
        {"station_id": "IMD-JK-001", "parameter_name": "min_air_temperature", "percentile": "1%", "value": -16.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual minimum of daily minimum temperatures, 1st percentile over 30-year period"},
        {"station_id": "IMD-JK-001", "parameter_name": "min_air_temperature", "percentile": "5%", "value": -12.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual minimum, 5th percentile for cold-region structural design"},
        {"station_id": "IMD-JK-001", "parameter_name": "min_air_temperature", "percentile": "50%", "value": -4.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Median of annual minimum temperatures over 30-year period"},
        {"station_id": "IMD-JK-001", "parameter_name": "max_air_temperature", "percentile": "99%", "value": 37.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual maximum, 99th percentile for material degradation modelling"},
        {"station_id": "IMD-JK-001", "parameter_name": "max_air_temperature", "percentile": "50%", "value": 32.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Median of annual maximum temperatures over 30-year period"},
        {"station_id": "IMD-JK-001", "parameter_name": "mean_air_temperature", "percentile": "50%", "value": 13.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual mean temperature over 30-year period"},
        {"station_id": "IMD-JK-001", "parameter_name": "relative_humidity", "percentile": "50%", "value": 62.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Annual mean relative humidity — significantly higher than Ladakh due to valley geography"},
        {"station_id": "IMD-JK-001", "parameter_name": "relative_humidity", "percentile": "99%", "value": 95.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Peak humidity — critical for condensation and corrosion modelling"},
        {"station_id": "IMD-JK-001", "parameter_name": "relative_humidity", "percentile": "1%", "value": 18.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Minimum humidity — dry winter conditions"},
        {"station_id": "IMD-JK-001", "parameter_name": "precipitation", "percentile": "50%", "value": 720.0, "unit": "mm/year",
         "calculation_period": "1991-2020", "method": "Annual total precipitation median — much higher than Ladakh due to western disturbances"},
        {"station_id": "IMD-JK-001", "parameter_name": "precipitation", "percentile": "99%", "value": 65.0, "unit": "mm/day",
         "calculation_period": "1991-2020", "method": "Maximum daily precipitation for drainage and wetting modelling"},
        {"station_id": "IMD-JK-001", "parameter_name": "snow_depth", "percentile": "99%", "value": 80.0, "unit": "cm",
         "calculation_period": "1991-2020", "method": "Maximum snow depth on ground — critical for structural loading and insulation"},
        {"station_id": "IMD-JK-001", "parameter_name": "snow_depth", "percentile": "50%", "value": 25.0, "unit": "cm",
         "calculation_period": "1991-2020", "method": "Median peak seasonal snow depth"},
        {"station_id": "IMD-JK-001", "parameter_name": "wind_speed", "percentile": "50%", "value": 3.2, "unit": "m/s",
         "calculation_period": "1991-2020", "method": "Mean daily wind speed at 10m height — sheltered valley, lower than Ladakh"},
        {"station_id": "IMD-JK-001", "parameter_name": "wind_speed", "percentile": "99%", "value": 12.0, "unit": "m/s",
         "calculation_period": "1991-2020", "method": "Peak wind speed for convective heat transfer modelling"},
        {"station_id": "IMD-JK-001", "parameter_name": "wind_direction", "percentile": "50%", "value": 330, "unit": "degrees",
         "calculation_period": "1991-2020", "method": "Predominant wind direction — NW winter winds, sheltering effect of valley"},
        {"station_id": "IMD-JK-001", "parameter_name": "atmospheric_pressure", "percentile": "50%", "value": 840.0, "unit": "hPa",
         "calculation_period": "1991-2020", "method": "Barometric formula at 1585m elevation"},
        {"station_id": "IMD-JK-001", "parameter_name": "solar_radiation", "percentile": "50%", "value": 4.8, "unit": "kWh/m2/day",
         "calculation_period": "1991-2020", "method": "Mean daily GHI — reduced by cloud cover and valley shading compared to Ladakh"},
        {"station_id": "IMD-JK-001", "parameter_name": "solar_radiation", "percentile": "99%", "value": 6.5, "unit": "kWh/m2/day",
         "calculation_period": "1991-2020", "method": "Peak solar radiation for thermal gain modelling"},
        {"station_id": "IMD-JK-001", "parameter_name": "freeze_thaw_cycles", "percentile": "50%", "value": 85, "unit": "cycles/year",
         "calculation_period": "2010-2020", "method": "Estimated from daily min/max temperature crossing 0°C — significant freeze-thaw damage risk"},
        {"station_id": "IMD-JK-001", "parameter_name": "heating_degree_days", "percentile": "50%", "value": 2800, "unit": "°C.days",
         "calculation_period": "1991-2020", "method": "HDD base 18°C — substantial heating demand for shelter design"},
        {"station_id": "IMD-JK-001", "parameter_name": "cooling_degree_days", "percentile": "50%", "value": 120, "unit": "°C.days",
         "calculation_period": "1991-2020", "method": "CDD base 24°C — minimal cooling demand"},
        {"station_id": "IMD-JK-001", "parameter_name": "growing_frost_days", "percentile": "50%", "value": 145, "unit": "days/year",
         "calculation_period": "1991-2020", "method": "Days with ground frost — critical for foundation and below-grade design"},
        {"station_id": "IMD-JK-001", "parameter_name": "snowfall_days", "percentile": "50%", "value": 55, "unit": "days/year",
         "calculation_period": "1991-2020", "method": "Days with recorded snowfall — impacts roof design and drainage"},

        # ---- Baramulla, Kashmir (34.21°N, 74.35°E, 1590 m) ----
        {"station_id": "IMD-JK-002", "parameter_name": "min_air_temperature", "percentile": "1%", "value": -15.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual minimum, 1st percentile"},
        {"station_id": "IMD-JK-002", "parameter_name": "min_air_temperature", "percentile": "50%", "value": -3.5, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Median annual minimum"},
        {"station_id": "IMD-JK-002", "parameter_name": "max_air_temperature", "percentile": "99%", "value": 38.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual maximum, 99th percentile"},
        {"station_id": "IMD-JK-002", "parameter_name": "max_air_temperature", "percentile": "50%", "value": 33.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Median annual maximum"},
        {"station_id": "IMD-JK-002", "parameter_name": "relative_humidity", "percentile": "50%", "value": 64.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Annual mean — higher than Srinagar due to river valley proximity"},
        {"station_id": "IMD-JK-002", "parameter_name": "relative_humidity", "percentile": "99%", "value": 97.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Peak humidity near Jhelum river basin"},
        {"station_id": "IMD-JK-002", "parameter_name": "precipitation", "percentile": "50%", "value": 780.0, "unit": "mm/year",
         "calculation_period": "1991-2020", "method": "Annual total median — receives more precipitation than Srinagar"},
        {"station_id": "IMD-JK-002", "parameter_name": "precipitation", "percentile": "99%", "value": 75.0, "unit": "mm/day",
         "calculation_period": "1991-2020", "method": "Maximum daily precipitation"},
        {"station_id": "IMD-JK-002", "parameter_name": "snow_depth", "percentile": "99%", "value": 85.0, "unit": "cm",
         "calculation_period": "1991-2020", "method": "Maximum snow depth — slightly higher than Srinagar"},
        {"station_id": "IMD-JK-002", "parameter_name": "wind_speed", "percentile": "50%", "value": 3.0, "unit": "m/s",
         "calculation_period": "1991-2020", "method": "Mean daily wind speed"},
        {"station_id": "IMD-JK-002", "parameter_name": "atmospheric_pressure", "percentile": "50%", "value": 840.0, "unit": "hPa",
         "calculation_period": "1991-2020", "method": "Barometric formula at 1590m elevation"},
        {"station_id": "IMD-JK-002", "parameter_name": "solar_radiation", "percentile": "50%", "value": 4.6, "unit": "kWh/m2/day",
         "calculation_period": "1991-2020", "method": "Mean GHI — slightly more cloud cover than Srinagar"},
        {"station_id": "IMD-JK-002", "parameter_name": "freeze_thaw_cycles", "percentile": "50%", "value": 80, "unit": "cycles/year",
         "calculation_period": "2010-2020", "method": "Estimated from daily temperature crossings of 0°C"},
        {"station_id": "IMD-JK-002", "parameter_name": "heating_degree_days", "percentile": "50%", "value": 2750, "unit": "°C.days",
         "calculation_period": "1991-2020", "method": "HDD base 18°C"},
        {"station_id": "IMD-JK-002", "parameter_name": "growing_frost_days", "percentile": "50%", "value": 140, "unit": "days/year",
         "calculation_period": "1991-2020", "method": "Days with ground frost"},
        {"station_id": "IMD-JK-002", "parameter_name": "snowfall_days", "percentile": "50%", "value": 50, "unit": "days/year",
         "calculation_period": "1991-2020", "method": "Days with recorded snowfall"},

        # ---- Jaisalmer (26.92°N, 70.91°E, 171 m) ----
        {"station_id": "IMD-RJ-001", "parameter_name": "min_air_temperature", "percentile": "1%", "value": 2.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual minimum, 1st percentile"},
        {"station_id": "IMD-RJ-001", "parameter_name": "max_air_temperature", "percentile": "99%", "value": 49.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual maximum, 99th percentile — extreme heat survival design value"},
        {"station_id": "IMD-RJ-001", "parameter_name": "max_air_temperature", "percentile": "99.5%", "value": 51.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Near-extreme maximum — material degradation threshold"},
        {"station_id": "IMD-RJ-001", "parameter_name": "relative_humidity", "percentile": "50%", "value": 28.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Annual mean"},
        {"station_id": "IMD-RJ-001", "parameter_name": "relative_humidity", "percentile": "99%", "value": 70.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Peak humidity for moisture modelling"},
        {"station_id": "IMD-RJ-001", "parameter_name": "precipitation", "percentile": "50%", "value": 170.0, "unit": "mm/year",
         "calculation_period": "1991-2020", "method": "Annual total median — extremely arid"},
        {"station_id": "IMD-RJ-001", "parameter_name": "precipitation", "percentile": "99%", "value": 80.0, "unit": "mm/day",
         "calculation_period": "1991-2020", "method": "Maximum daily precipitation for flash flood modelling"},
        {"station_id": "IMD-RJ-001", "parameter_name": "wind_speed", "percentile": "50%", "value": 5.0, "unit": "m/s",
         "calculation_period": "1991-2020", "method": "Mean daily wind speed"},
        {"station_id": "IMD-RJ-001", "parameter_name": "wind_speed", "percentile": "99%", "value": 15.0, "unit": "m/s",
         "calculation_period": "1991-2020", "method": "Peak wind speed for convective heat transfer modelling"},
        {"station_id": "IMD-RJ-001", "parameter_name": "solar_radiation", "percentile": "50%", "value": 6.2, "unit": "kWh/m2/day",
         "calculation_period": "1991-2020", "method": "Mean GHI — high solar resource desert zone"},
        {"station_id": "IMD-RJ-001", "parameter_name": "dust_storm_days", "percentile": "50%", "value": 25, "unit": "days/year",
         "calculation_period": "1991-2020", "method": "IMD-defined dust/sandstorm occurrence count"},
        {"station_id": "IMD-RJ-001", "parameter_name": "atmospheric_pressure", "percentile": "50%", "value": 1002.0, "unit": "hPa",
         "calculation_period": "1991-2020", "method": "Standard pressure at 171m elevation"},

        # ---- Bikaner (28.02°N, 73.31°E, 237 m) ----
        {"station_id": "IMD-RJ-002", "parameter_name": "min_air_temperature", "percentile": "1%", "value": 1.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual minimum, 1st percentile"},
        {"station_id": "IMD-RJ-002", "parameter_name": "max_air_temperature", "percentile": "99%", "value": 47.0, "unit": "°C",
         "calculation_period": "1991-2020", "method": "Annual maximum, 99th percentile"},
        {"station_id": "IMD-RJ-002", "parameter_name": "relative_humidity", "percentile": "50%", "value": 38.0, "unit": "%",
         "calculation_period": "1991-2020", "method": "Annual mean"},
        {"station_id": "IMD-RJ-002", "parameter_name": "precipitation", "percentile": "50%", "value": 280.0, "unit": "mm/year",
         "calculation_period": "1991-2020", "method": "Annual total median"},
        {"station_id": "IMD-RJ-002", "parameter_name": "solar_radiation", "percentile": "50%", "value": 5.8, "unit": "kWh/m2/day",
         "calculation_period": "1991-2020", "method": "Mean GHI"},
    ]

    for dv in design_values:
        existing = (
            session.query(ClimateDesignValues)
            .filter(
                ClimateDesignValues.station_id == dv["station_id"],
                ClimateDesignValues.parameter_name == dv["parameter_name"],
                ClimateDesignValues.percentile == dv.get("percentile"),
            )
            .first()
        )
        if not existing:
            session.add(ClimateDesignValues(
                station_id=dv["station_id"],
                parameter_name=dv["parameter_name"],
                percentile=dv.get("percentile"),
                value=dv["value"],
                unit=dv["unit"],
                calculation_period=dv.get("calculation_period"),
                method=dv.get("method"),
                source_id=src.id,
            ))
    session.commit()
    print("  [+] Climate design values seeded (derived from IMD observations).")


def seed_regional_economics(session, source_map: dict):
    """Upsert regional economics records (already partially seeded)."""
    from app.db.models import RegionalEconomics

    economics = [
        {"climate_zone": "Extreme cold (Ladakh)", "fuel_cost_per_kwh": 24.50, "carbon_emission_factor": 0.27},
        {"climate_zone": "Extreme cold (Kashmir)", "fuel_cost_per_kwh": 22.00, "carbon_emission_factor": 0.35},
        {"climate_zone": "Extreme heat (Rajasthan)", "fuel_cost_per_kwh": 8.50, "carbon_emission_factor": 0.82},
        {"climate_zone": "Moderate / Hill Station", "fuel_cost_per_kwh": 9.20, "carbon_emission_factor": 0.75},
    ]
    for eco in economics:
        if not session.query(RegionalEconomics).filter(RegionalEconomics.climate_zone == eco["climate_zone"]).first():
            session.add(RegionalEconomics(**eco))
    session.commit()


# ===========================================================================
# MAIN SEEDER
# ===========================================================================


def run_seeder():
    """Execute the full database seeder."""
    print("=" * 72)
    print("  Regional Material & Microclimate Database Seeder")
    print("  Sources: BEE ECBC, BMTPC, IMD-CLIMS, BIS, DRDO")
    print("=" * 72)

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        print("\n[1/7] Registering data sources...")
        source_map = seed_data_sources(session)

        print("[2/7] Creating material categories...")
        cat_map = seed_material_categories(session)

        print("[3/7] Seeding BEE ECBC / Eco-Niwas thermal properties...")
        seed_bee_ecbc_materials(session, source_map, cat_map)

        print("[4/7] Seeding BMTPC material properties...")
        seed_bmtpc_materials(session, source_map, cat_map)

        print("[5/7] Seeding defence-material estimates (CAUTION)...")
        seed_defence_materials(session, source_map, cat_map)

        print("[6/7] Seeding IMD climate stations...")
        station_map = seed_climate_stations(session, source_map)

        print("[7/7] Seeding climate design values...")
        seed_climate_design_values(session, source_map, station_map)

        seed_regional_economics(session, source_map)

        # Summary
        mat_count = session.query(MaterialThermalProperty).count()
        src_count = session.query(DataSource).count()
        cat_count = session.query(MaterialCategory).count()
        stn_count = session.query(ClimateStation).count()
        obs_count = session.query(ClimateDesignValues).count()

        print("\n" + "=" * 72)
        print("  SEED COMPLETE")
        print(f"  Data sources:     {src_count}")
        print(f"  Material categories: {cat_count}")
        print(f"  Thermal properties:  {mat_count}")
        print(f"  Climate stations:    {stn_count}")
        print(f"  Design values:       {obs_count}")
        print("=" * 72)
        print("\n  All values are government defaults or engineering estimates.")
        print("  Defence-material values are marked as 'estimated' — NOT DRDO-certified.")
        print("  Climate values are derived from IMD observations — not raw measurements.")
        print("  Access restrictions recorded in data_sources table.")
        print("  Permission required for commercial use of IMD data.")
        print("=" * 72)

    except Exception as e:
        session.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_seeder()
