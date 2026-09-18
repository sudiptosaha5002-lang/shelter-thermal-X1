import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Layout, Header, Controls, Viewport3D, Charts, ResultsPanel } from './components';
import { apiService } from './services/api';

function App() {
  const [location, setLocation] = useState('leh');
  const [geometry, setGeometry] = useState({
    length: 6,
    width: 4,
    height: 2.5,
    wall_thickness: 0.2,
    roof_thickness: 0.2,
    floor_thickness: 0.2,
    window_area: 2,
    window_orientation: 180,
    orientation: 0,
  });
  const [material, setMaterial] = useState('');
  const [materials, setMaterials] = useState([]);
  const [climateData, setClimateData] = useState(null);
  const [simulationResult, setSimulationResult] = useState(null);
  const [optimizationResults, setOptimizationResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('simulate');
  const materialInitRef = useRef(false);

  const fetchMaterials = useCallback(async () => {
    try {
      const data = await apiService.getMaterials();
      setMaterials(data);
      if (data.length > 0 && !materialInitRef.current) {
        materialInitRef.current = true;
        setMaterial(data[0].name);
      }
    } catch (error) {
      console.error('Failed to fetch materials:', error);
    }
  }, []);

  const fetchClimateData = useCallback(async () => {
    try {
      const data = await apiService.getClimateData(location);
      setClimateData(data);
    } catch (error) {
      console.error('Failed to fetch climate data:', error);
    }
  }, [location]);

  useEffect(() => {
    fetchMaterials();
    fetchClimateData();
  }, [fetchMaterials, fetchClimateData]);

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const result = await apiService.runSimulation({
        name: `Simulation ${new Date().toLocaleString()}`,
        location_name: location,
        geometry,
        material,
      });
      setSimulationResult(result);
      setActiveTab('results');
    } catch (error) {
      console.error('Simulation failed:', error);
      alert('Simulation failed. Please check your inputs.');
    } finally {
      setLoading(false);
    }
  };

  const handleOptimize = async () => {
    setLoading(true);
    try {
      const materialNames = materials.map(m => m.name);
      const result = await apiService.optimizeMaterials({
        name: `Optimization ${new Date().toLocaleString()}`,
        location_name: location,
        geometry,
        materials: materialNames,
      });
      setOptimizationResults(result);
      setActiveTab('optimization');
    } catch (error) {
      console.error('Optimization failed:', error);
      alert('Optimization failed. Please check your inputs.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <Header 
        location={location} 
        setLocation={setLocation} 
        climateData={climateData}
      />
      <Controls
        geometry={geometry}
        setGeometry={setGeometry}
        material={material}
        setMaterial={setMaterial}
        materials={materials}
        onSimulate={handleSimulate}
        onOptimize={handleOptimize}
        loading={loading}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />
      <Viewport3D geometry={geometry} />
      <Charts 
        simulationResult={simulationResult} 
        optimizationResults={optimizationResults}
        climateData={climateData}
        activeTab={activeTab}
      />
      <ResultsPanel
        simulationResult={simulationResult}
        optimizationResults={optimizationResults}
        activeTab={activeTab}
      />
    </Layout>
  );
}

export default App;