import React from 'react';
import { Play, Zap, Loader2 } from 'lucide-react';

const geometryFields = [
  { key: 'length', label: 'Length (m)', min: 2, max: 20, step: 0.5 },
  { key: 'width', label: 'Width (m)', min: 2, max: 15, step: 0.5 },
  { key: 'height', label: 'Height (m)', min: 2, max: 5, step: 0.1 },
  { key: 'wall_thickness', label: 'Wall Thickness (m)', min: 0.1, max: 1, step: 0.05 },
  { key: 'roof_thickness', label: 'Roof Thickness (m)', min: 0.1, max: 1, step: 0.05 },
  { key: 'floor_thickness', label: 'Floor Thickness (m)', min: 0.1, max: 1, step: 0.05 },
  { key: 'window_area', label: 'Window Area (m²)', min: 0, max: 20, step: 0.5 },
  { key: 'window_orientation', label: 'Window Orientation (°)', min: 0, max: 360, step: 15 },
  { key: 'orientation', label: 'Building Orientation (°)', min: 0, max: 360, step: 15 },
];

export function Controls({
  geometry,
  setGeometry,
  material,
  setMaterial,
  materials,
  onSimulate,
  onOptimize,
  loading,
  activeTab,
  setActiveTab,
}) {
  const handleGeometryChange = (key, value) => {
    setGeometry(prev => ({ ...prev, [key]: parseFloat(value) || 0 }));
  };

  return (
    <div className="card mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Shelter Parameters</h2>
        <div className="flex gap-2">
          <button
            className={`btn-primary flex items-center gap-2 ${activeTab === 'simulate' ? 'bg-blue-700' : ''}`}
            onClick={() => setActiveTab('simulate')}
            disabled={loading}
          >
            <Play className="w-4 h-4" />
            Run Simulation
          </button>
          <button
            className={`btn-secondary flex items-center gap-2 ${activeTab === 'optimization' ? 'bg-gray-300' : ''}`}
            onClick={() => setActiveTab('optimization')}
            disabled={loading}
          >
            <Zap className="w-4 h-4" />
            Optimize Materials
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {geometryFields.map(field => (
          <div key={field.key} className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">{field.label}</label>
            <input
              type="number"
              min={field.min}
              max={field.max}
              step={field.step}
              value={geometry[field.key]}
              onChange={(e) => handleGeometryChange(field.key, e.target.value)}
              className="input-field"
            />
          </div>
        ))}
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 flex flex-col gap-1">
          <label className="text-sm font-medium text-gray-700">Wall Material</label>
          <select
            value={material}
            onChange={(e) => setMaterial(e.target.value)}
            className="input-field"
            disabled={loading}
          >
            {materials.map(mat => (
              <option key={mat.name} value={mat.name}>
                {mat.display_name} (k={mat.thermal_conductivity}, ρ={mat.density}, c={mat.specific_heat})
              </option>
            ))}
          </select>
        </div>
        
        {loading && (
          <div className="flex items-center gap-2 text-blue-600">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Running simulation...</span>
          </div>
        )}
      </div>
    </div>
  );
}