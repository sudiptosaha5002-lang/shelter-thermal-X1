import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.core.config import settings

class NASAPowerService:
    def __init__(self):
        self.base_url = settings.NASA_POWER_API_URL
        self.parameters = [
            "T2M", "T2M_MAX", "T2M_MIN",
            "ALLSKY_SFC_SW_DWN", "WS2M", "RH2M",
            "PRECTOTCORR"
        ]
    
    def fetch_climate_data(self, latitude: float, longitude: float, 
                           start_date: str, end_date: str) -> Dict:
        params = {
            "parameters": ",".join(self.parameters),
            "community": "RE",
            "longitude": longitude,
            "latitude": latitude,
            "start": start_date.replace("-", ""),
            "end": end_date.replace("-", ""),
            "format": "JSON",
        }
        
        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        return self._process_nasa_data(data, latitude, longitude)
    
    @staticmethod
    def _sanitize(values: List[float], default: float = 0.0) -> List[float]:
        """Replace NASA POWER sentinel values (-999, -998, etc.) with defaults."""
        return [default if v is None or v < -900 else v for v in values]

    def _process_nasa_data(self, data: Dict, lat: float, lon: float) -> Dict:
        properties = data.get("properties", {})
        params = properties.get("parameter", {})

        timestamps = []
        temp = []
        temp_max = []
        temp_min = []
        solar = []
        wind = []
        humidity = []

        for date_str, value in params.get("T2M", {}).items():
            dt = datetime.strptime(date_str, "%Y%m%d")
            timestamps.append(dt)
            temp.append(value)

        for date_str, value in params.get("T2M_MAX", {}).items():
            temp_max.append(value)

        for date_str, value in params.get("T2M_MIN", {}).items():
            temp_min.append(value)

        for date_str, value in params.get("ALLSKY_SFC_SW_DWN", {}).items():
            solar.append(value * 1000 / 24)

        for date_str, value in params.get("WS2M", {}).items():
            wind.append(value)

        for date_str, value in params.get("RH2M", {}).items():
            humidity.append(value)

        temp = self._sanitize(temp, default=0.0)
        temp_max = self._sanitize(temp_max, default=max(temp) if temp else 20.0)
        temp_min = self._sanitize(temp_min, default=min(temp) if temp else 0.0)
        solar = self._sanitize(solar, default=200.0)
        wind = self._sanitize(wind, default=3.0)
        humidity = self._sanitize(humidity, default=50.0)

        n_hours = len(temp) * 24
        hourly_temp = np.zeros(n_hours)
        hourly_solar = np.zeros(n_hours)
        hourly_wind = np.zeros(n_hours)
        hourly_humidity = np.zeros(n_hours)
        hourly_timestamps = []

        for i in range(len(temp)):
            for h in range(24):
                idx = i * 24 + h
                hourly_timestamps.append(timestamps[i] + timedelta(hours=h))

                daily_range = temp_max[i] - temp_min[i]
                hourly_temp[idx] = temp_min[i] + daily_range * np.sin(np.pi * (h - 6) / 12)
                hourly_temp[idx] = np.clip(hourly_temp[idx], temp_min[i], temp_max[i])

                if 6 <= h <= 18:
                    hourly_solar[idx] = solar[i] * np.sin(np.pi * (h - 6) / 12)
                else:
                    hourly_solar[idx] = 0

                hourly_wind[idx] = wind[i]
                hourly_humidity[idx] = humidity[i]

        valid_temp_min = [v for v in temp_min if v > -900]
        valid_temp_max = [v for v in temp_max if v > -900]
        valid_solar = [v for v in solar if v > -900]
        valid_wind = [v for v in wind if v > -900]
        valid_humidity = [v for v in humidity if v > -900]

        return {
            "latitude": lat,
            "longitude": lon,
            "temperature": hourly_temp.tolist(),
            "solar_radiation": hourly_solar.tolist(),
            "wind_speed": hourly_wind.tolist(),
            "humidity": hourly_humidity.tolist(),
            "timestamps": [ts.isoformat() for ts in hourly_timestamps],
            "daily_summary": {
                "avg_temp": float(np.mean(temp)) if temp else 0.0,
                "min_temp": float(np.min(valid_temp_min)) if valid_temp_min else 0.0,
                "max_temp": float(np.max(valid_temp_max)) if valid_temp_max else 20.0,
                "avg_solar": float(np.mean(valid_solar)) if valid_solar else 200.0,
                "avg_wind": float(np.mean(valid_wind)) if valid_wind else 3.0,
                "avg_humidity": float(np.mean(valid_humidity)) if valid_humidity else 50.0,
            }
        }
    
    def get_location_climate(self, location_name: str) -> Optional[Dict]:
        locations = {
            "leh": {"lat": 34.1526, "lon": 77.5770, "name": "Leh, Ladakh"},
            "kargil": {"lat": 34.5551, "lon": 76.1286, "name": "Kargil, Ladakh"},
            "jaisalmer": {"lat": 26.9157, "lon": 70.9083, "name": "Jaisalmer, Rajasthan"},
            "bikaner": {"lat": 28.0229, "lon": 73.3119, "name": "Bikaner, Rajasthan"},
            "srinagar": {"lat": 34.0837, "lon": 74.7973, "name": "Srinagar, J&K"},
            "baramulla": {"lat": 34.2087, "lon": 74.3457, "name": "Baramulla, Kashmir"},
            "manali": {"lat": 32.2396, "lon": 77.1887, "name": "Manali, Himachal"},
            "shimla": {"lat": 31.1048, "lon": 77.1734, "name": "Shimla, Himachal"},
        }
        
        loc = locations.get(location_name.lower())
        if not loc:
            return None
        
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        
        climate_data = self.fetch_climate_data(loc["lat"], loc["lon"], start_date, end_date)
        climate_data["location_name"] = loc["name"]
        return climate_data


nasa_power_service = NASAPowerService()