import React, { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { Sun, Thermometer, Flame, CheckCircle } from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export function Charts({ simulationResult, optimizationResults, climateData, activeTab }) {
  const tempChartData = useMemo(() => {
    if (!simulationResult?.result?.indoor_temperature) return null;
    
    const indoor = simulationResult.result.indoor_temperature;
    const outdoor = climateData?.temperature || [];
    const labels = Array.from({ length: indoor.length }, (_, i) => {
      const date = new Date(climateData?.timestamps?.[i] || Date.now() + i * 3600000);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + date.getHours() + ':00';
    });

    return {
      labels: labels.filter((_, i) => i % 24 === 0),
      datasets: [
        {
          label: 'Indoor Temperature',
          data: indoor.filter((_, i) => i % 24 === 0),
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
        },
        {
          label: 'Outdoor Temperature',
          data: outdoor.filter((_, i) => i % 24 === 0),
          borderColor: 'rgb(239, 68, 68)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderDash: [5, 5],
        },
        {
          label: 'Comfort Range (18-24°C)',
          data: indoor.filter((_, i) => i % 24 === 0).map(() => 21),
          borderColor: 'rgb(34, 197, 94)',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          fill: '-1',
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 0,
        },
      ],
    };
  }, [simulationResult, climateData]);

  const heatingChartData = useMemo(() => {
    if (!simulationResult?.result?.heating_load) return null;
    
    const heating = simulationResult.result.heating_load;
    const labels = Array.from({ length: heating.length }, (_, i) => {
      const date = new Date(climateData?.timestamps?.[i] || Date.now() + i * 3600000);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    return {
      labels: labels.filter((_, i) => i % 24 === 0),
      datasets: [
        {
          label: 'Daily Heating Load (kWh)',
          data: heating.filter((_, i) => i % 24 === 0).map(v => v * 24 / 1000),
          borderColor: 'rgb(249, 115, 22)',
          backgroundColor: 'rgba(249, 115, 22, 0.2)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    };
  }, [simulationResult, climateData]);

  const optimizationChartData = useMemo(() => {
    if (!optimizationResults?.results?.length) return null;
    
    const results = optimizationResults.results;
    return {
      labels: results.map(r => r.material),
      datasets: [
        {
          label: 'Total Heating Energy (kWh)',
          data: results.map(r => r.total_heating_energy),
          backgroundColor: [
            'rgba(59, 130, 246, 0.8)',
            'rgba(239, 68, 68, 0.8)',
            'rgba(34, 197, 94, 0.8)',
            'rgba(249, 115, 22, 0.8)',
            'rgba(168, 85, 247, 0.8)',
            'rgba(236, 72, 153, 0.8)',
            'rgba(20, 184, 166, 0.8)',
          ],
          borderWidth: 0,
          borderRadius: 8,
        },
      ],
    };
  }, [optimizationResults]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: { usePointStyle: true, padding: 20 },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { maxTicksLimit: 12 },
      },
      y: {
        grid: { color: 'rgba(0,0,0,0.05)' },
      },
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false,
    },
  };

  if (!simulationResult && !optimizationResults) {
    return (
      <div className="card mb-8">
        <div className="flex items-center justify-center h-64 text-gray-400">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
              <Thermometer className="w-8 h-8" />
            </div>
            <p className="text-lg">Run a simulation to see charts</p>
            <p className="text-sm mt-1">Temperature profiles, heating loads, and material comparisons will appear here</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      {tempChartData && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Thermometer className="w-5 h-5 text-blue-600" />
              Temperature Profile
            </h3>
            <span className="text-sm text-gray-500">Hourly (daily markers)</span>
          </div>
          <div style={{ height: '300px' }}>
            <Line data={tempChartData} options={chartOptions} />
          </div>
        </div>
      )}

      {heatingChartData && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Flame className="w-5 h-5 text-orange-600" />
              Heating Load
            </h3>
            <span className="text-sm text-gray-500">Daily accumulation</span>
          </div>
          <div style={{ height: '300px' }}>
            <Line data={heatingChartData} options={chartOptions} />
          </div>
        </div>
      )}

      {optimizationChartData && (
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-600" />
              Material Optimization Comparison
            </h3>
            <span className="text-sm text-gray-500">Lower is better</span>
          </div>
          <div style={{ height: '300px' }}>
            <Line
              data={optimizationChartData}
              options={{
                ...chartOptions,
                indexAxis: 'y',
                scales: {
                  x: { grid: { color: 'rgba(0,0,0,0.05)' }, title: { display: true, text: 'Heating Energy (kWh)' } },
                  y: { grid: { display: false } },
                },
              }}
            />
          </div>
        </div>
      )}

      {climateData && !optimizationChartData && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Sun className="w-5 h-5 text-yellow-600" />
              Solar Radiation (Climate)
            </h3>
          </div>
          <div style={{ height: '300px' }}>
            <Line
              data={{
                labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
                datasets: [{
                  label: 'Avg Daily Solar (W/m²)',
                  data: Array.from({ length: 24 }, (_, h) => {
                    const dailyAvg = climateData.daily_summary?.avg_solar || 0;
                    return h >= 6 && h <= 18 ? dailyAvg * Math.sin(Math.PI * (h - 6) / 12) : 0;
                  }),
                  borderColor: 'rgb(234, 179, 8)',
                  backgroundColor: 'rgba(234, 179, 8, 0.1)',
                  fill: true,
                  tension: 0.3,
                  pointRadius: 0,
                }],
              }}
              options={chartOptions}
            />
          </div>
        </div>
      )}
    </div>
  );
}