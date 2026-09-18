from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ClimateData, ClimateCache, utc_now
from app.services.nasa_power import nasa_power_service
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/locations")
async def get_available_locations():
    locations = {
        "leh": {"name": "Leh, Ladakh", "lat": 34.1526, "lon": 77.5770, "region": "Ladakh"},
        "kargil": {"name": "Kargil, Ladakh", "lat": 34.5551, "lon": 76.1286, "region": "Ladakh"},
        "srinagar": {"name": "Srinagar, Kashmir", "lat": 34.0837, "lon": 74.7973, "region": "Jammu & Kashmir"},
        "baramulla": {"name": "Baramulla, Kashmir", "lat": 34.2087, "lon": 74.3457, "region": "Jammu & Kashmir"},
        "jaisalmer": {"name": "Jaisalmer, Rajasthan", "lat": 26.9157, "lon": 70.9083, "region": "Rajasthan"},
        "bikaner": {"name": "Bikaner, Rajasthan", "lat": 28.0229, "lon": 73.3119, "region": "Rajasthan"},
        "manali": {"name": "Manali, Himachal", "lat": 32.2396, "lon": 77.1887, "region": "Himachal Pradesh"},
        "shimla": {"name": "Shimla, Himachal", "lat": 31.1048, "lon": 77.1734, "region": "Himachal Pradesh"},
    }
    return locations

@router.get("/data/{location_id}")
async def get_climate_data(location_id: str, db: Session = Depends(get_db)):
    loc_key = location_id.lower()
    
    # 1. Check if cached in DB
    cached = db.query(ClimateData).filter(ClimateData.location_name == loc_key).first()
    if cached:
        return {
            "location_name": cached.location_name,
            "latitude": cached.latitude,
            "longitude": cached.longitude,
            "temperature": cached.temperature,
            "solar_radiation": cached.solar_radiation,
            "wind_speed": cached.wind_speed,
            "humidity": cached.humidity,
            "timestamps": cached.timestamps,
            "daily_summary": cached.daily_summary,
        }

    # 2. Fetch from NASA POWER
    climate_data = nasa_power_service.get_location_climate(loc_key)
    if not climate_data:
        raise HTTPException(status_code=404, detail="Location not found")
    
    # 3. Store in ClimateData
    db_climate = ClimateData(
        location_name=loc_key,
        latitude=climate_data.get("latitude"),
        longitude=climate_data.get("longitude"),
        temperature=climate_data.get("temperature"),
        solar_radiation=climate_data.get("solar_radiation"),
        wind_speed=climate_data.get("wind_speed"),
        humidity=climate_data.get("humidity"),
        timestamps=climate_data.get("timestamps"),
        daily_summary=climate_data.get("daily_summary"),
        fetched_at=utc_now(),
    )
    db.add(db_climate)

    # 4. Cache sample rows in ClimateCache
    if climate_data.get("daily_summary"):
        summ = climate_data["daily_summary"]
        cache_row = ClimateCache(
            latitude=climate_data["latitude"],
            longitude=climate_data["longitude"],
            timestamp=utc_now(),
            ambient_temp=summ.get("avg_temp", 0.0),
            solar_irradiance=summ.get("avg_solar", 0.0),
            wind_speed=summ.get("avg_wind", 0.0),
        )
        db.add(cache_row)

    db.commit()
    return climate_data

@router.get("/custom")
async def get_custom_climate(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    
    climate_data = nasa_power_service.fetch_climate_data(lat, lon, start_date, end_date)
    climate_data["location_name"] = f"Custom ({lat:.4f}, {lon:.4f})"

    # Cache sample row in ClimateCache
    if climate_data.get("daily_summary"):
        summ = climate_data["daily_summary"]
        cache_row = ClimateCache(
            latitude=lat,
            longitude=lon,
            timestamp=utc_now(),
            ambient_temp=summ.get("avg_temp", 0.0),
            solar_irradiance=summ.get("avg_solar", 0.0),
            wind_speed=summ.get("avg_wind", 0.0),
        )
        db.add(cache_row)
        db.commit()

    return climate_data