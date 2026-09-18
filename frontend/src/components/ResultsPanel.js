import React from 'react';
import { Thermometer, Flame, CheckCircle, Clock, TrendingDown, AlertTriangle } from 'lucide-react';

export function ResultsPanel({ simulationResult, optimizationResults, activeTab }) {
  const result = simulationResult?.result;
  const optResults = optimizationResults?.results;

  if (!result && !optResults) {
    return null;
  }

  if (optResults && activeTab === 'optimization') {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-600" />
          Optimization Results
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="pb-3 font-medium text-gray-500">Rank</th>
                <th className="pb-3 font-medium text-gray-500">Material</th>
                <th className="pb-3 font-medium text-gray-500">Heating Energy (kWh)</th>
                <th className="pb-3 font-medium text-gray-500">Comfort Hours</th>
                <th className="pb-3 font-medium text-gray-500">Min Temp (°C)</th>
                <th className="pb-3 font-medium text-gray-500">Max Temp (°C)</th>
                <th className="pb-3 font-medium text-gray-500">Avg Temp (°C)</th>
              </tr>
            </thead>
            <tbody>
              {optResults.map((res, idx) => (
                <tr key={res.material} className={`border-b border-gray-100 ${idx === 0 ? 'bg-green-50' : ''}`}>
                  <td className="py-3 font-bold">{idx + 1}</td>
                  <td className="py-3 font-medium">{res.material}</td>
                  <td className="py-3">{res.total_heating_energy.toFixed(1)}</td>
                  <td className="py-3">{res.comfort_hours} / 8760</td>
                  <td className="py-3">{res.min_temp.toFixed(1)}</td>
                  <td className="py-3">{res.max_temp.toFixed(1)}</td>
                  <td className="py-3">{res.avg_temp.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {optResults.length > 0 && (
          <div className="mt-4 p-4 bg-green-50 rounded-lg border border-green-200">
            <p className="font-medium text-green-800">Recommended: <span className="font-bold">{optResults[0].material}</span></p>
            <p className="text-green-700 text-sm mt-1">
              Lowest heating energy demand: {optResults[0].total_heating_energy.toFixed(1)} kWh/year
              ({(100 - optResults[0].total_heating_energy / optResults[optResults.length - 1].total_heating_energy * 100).toFixed(1)}% savings vs worst)
            </p>
          </div>
        )}
      </div>
    );
  }

  if (result) {
    const comfortPercentage = (result.comfort_hours / 8760 * 100).toFixed(1);
    const heatingKWh = result.total_heating_energy;
    
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Thermometer className="w-5 h-5 text-blue-600" />
          Simulation Results
        </h3>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
            <div className="flex items-center gap-2 mb-1">
              <Thermometer className="w-5 h-5 text-blue-600" />
              <span className="text-sm text-gray-500">Avg Indoor Temp</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{result.avg_temp.toFixed(1)}°C</p>
          </div>
          <div className="p-4 bg-orange-50 rounded-lg border border-orange-100">
            <div className="flex items-center gap-2 mb-1">
              <Flame className="w-5 h-5 text-orange-600" />
              <span className="text-sm text-gray-500">Annual Heating</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{heatingKWh.toFixed(1)} kWh</p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg border border-green-100">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="w-5 h-5 text-green-600" />
              <span className="text-sm text-gray-500">Comfort Hours</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{result.comfort_hours} hrs</p>
            <p className="text-sm text-gray-500">({comfortPercentage}% of year)</p>
          </div>
          <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
            <div className="flex items-center gap-2 mb-1">
              <TrendingDown className="w-5 h-5 text-purple-600" />
              <span className="text-sm text-gray-500">Temp Range</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">
              {result.min_temp.toFixed(1)} - {result.max_temp.toFixed(1)}°C
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-700 mb-2">Temperature Statistics</h4>
            <ul className="space-y-1 text-sm">
              <li className="flex justify-between"><span>Minimum</span><span className="font-medium">{result.min_temp.toFixed(1)}°C</span></li>
              <li className="flex justify-between"><span>Maximum</span><span className="font-medium">{result.max_temp.toFixed(1)}°C</span></li>
              <li className="flex justify-between"><span>Average</span><span className="font-medium">{result.avg_temp.toFixed(1)}°C</span></li>
              <li className="flex justify-between"><span>Comfort Range</span><span className="font-medium">18-24°C</span></li>
            </ul>
          </div>
          
          <div className="p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-700 mb-2">Energy Performance</h4>
            <ul className="space-y-1 text-sm">
              <li className="flex justify-between"><span>Total Heating Energy</span><span className="font-medium">{heatingKWh.toFixed(1)} kWh</span></li>
              <li className="flex justify-between"><span>Peak Heating Load</span><span className="font-medium">{Math.max(...result.heating_load).toFixed(2)} kW</span></li>
              <li className="flex justify-between"><span>Heating Degree Hours</span><span className="font-medium">{(result.heating_load.filter(h => h > 0).length).toLocaleString()}</span></li>
            </ul>
          </div>

          <div className="p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-700 mb-2">Comfort Assessment</h4>
            <ul className="space-y-1 text-sm">
              <li className="flex justify-between"><span>Hours in Comfort</span><span className="font-medium">{result.comfort_hours.toLocaleString()}</span></li>
              <li className="flex justify-between"><span>Hours Below 18°C</span><span className="font-medium">{result.heating_load.filter(h => h > 0).length.toLocaleString()}</span></li>
              <li className="flex justify-between"><span>Hours Above 24°C</span><span className="font-medium">{(8760 - result.comfort_hours - result.heating_load.filter(h => h > 0).length).toLocaleString()}</span></li>
              <li className="flex justify-between">
                <span>Status</span>
                <span className={`font-medium ${comfortPercentage > 80 ? 'text-green-600' : comfortPercentage > 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {comfortPercentage > 80 ? 'Excellent' : comfortPercentage > 50 ? 'Good' : 'Needs Improvement'}
                </span>
              </li>
            </ul>
          </div>
        </div>

        {heatingKWh > 5000 && (
          <div className="mt-4 p-4 bg-yellow-50 rounded-lg border border-yellow-200 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
            <div>
              <p className="font-medium text-yellow-800">High Heating Demand</p>
              <p className="text-yellow-700 text-sm mt-1">
                This shelter requires {heatingKWh.toFixed(0)} kWh/year for heating. Consider adding insulation, 
                increasing thermal mass, or optimizing orientation to reduce energy demand.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
}