import React from 'react';
import { MapPin, Sun, Cloud, Wind, Droplets } from 'lucide-react';

export function Header({ location, setLocation, climateData }) {
  const locations = [
    { id: 'leh', name: 'Leh, Ladakh', region: 'High Altitude Desert' },
    { id: 'kargil', name: 'Kargil, Ladakh', region: 'High Altitude Desert' },
    { id: 'jaisalmer', name: 'Jaisalmer, Rajasthan', region: 'Hot Desert' },
    { id: 'bikaner', name: 'Bikaner, Rajasthan', region: 'Hot Desert' },
    { id: 'srinagar', name: 'Srinagar, J&K', region: 'Temperate Valley' },
    { id: 'manali', name: 'Manali, Himachal', region: 'Alpine' },
    { id: 'shimla', name: 'Shimla, Himachal', region: 'Subtropical Highland' },
  ];

  const currentLocation = locations.find(l => l.id === location) || locations[0];
  const summary = climateData?.daily_summary;

  return (
    <div className="mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Shelter Thermal Optimizer</h1>
          <p className="text-gray-600 mt-1">Passive shelter design for extreme climates &bull; <span className="text-blue-600 font-medium">{currentLocation.name} ({currentLocation.region})</span></p>
        </div>
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-blue-600" />
          <label className="text-sm font-medium text-gray-700">Location:</label>
          <select
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="input-field max-w-xs"
          >
            {locations.map(loc => (
              <option key={loc.id} value={loc.id}>
                {loc.name} ({loc.region})
              </option>
            ))}
          </select>
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Sun className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Avg Temperature</p>
                <p className="text-xl font-bold text-gray-900">{summary.avg_temp.toFixed(1)}°C</p>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <Cloud className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Solar Radiation</p>
                <p className="text-xl font-bold text-gray-900">{summary.avg_solar.toFixed(0)} W/m²</p>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Wind className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Wind Speed</p>
                <p className="text-xl font-bold text-gray-900">{summary.avg_wind.toFixed(1)} m/s</p>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Droplets className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Humidity</p>
                <p className="text-xl font-bold text-gray-900">{summary.avg_humidity.toFixed(0)}%</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}