from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Shelter Thermal Optimizer"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str = "sqlite:///./shelter_optimizer.db"
    
    NASA_POWER_API_URL: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    NASA_POWER_API_KEY: str = ""
    
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://frontend:3000"]
    
    SIMULATION_TIME_STEP: int = 3600
    SIMULATION_DAYS: int = 365
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()