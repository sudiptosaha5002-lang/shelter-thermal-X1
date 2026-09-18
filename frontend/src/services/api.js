import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export const apiService = {
  async getLocations() {
    const response = await api.get('/climate/locations');
    return response.data;
  },

  async getClimateData(locationId) {
    const response = await api.get(`/climate/data/${locationId}`);
    return response.data;
  },

  async getCustomClimate(lat, lon) {
    const response = await api.get('/climate/custom', { params: { lat, lon } });
    return response.data;
  },

  async getMaterials() {
    const response = await api.get('/materials/');
    return response.data;
  },

  async getDefaultMaterials() {
    const response = await api.get('/materials/defaults');
    return response.data;
  },

  async runSimulation(data) {
    const response = await api.post('/simulation/run', data);
    return response.data;
  },

  async optimizeMaterials(data) {
    const response = await api.post('/simulation/optimize', data);
    return response.data;
  },

  async getSimulationHistory() {
    const response = await api.get('/simulation/history');
    return response.data;
  },

  async getSimulation(id) {
    const response = await api.get(`/simulation/${id}`);
    return response.data;
  },

  async getShelters() {
    const response = await api.get('/shelters/');
    return response.data;
  },

  async getShelter(id) {
    const response = await api.get(`/shelters/${id}`);
    return response.data;
  },

  async getFieldValidation(shelterId) {
    const response = await api.get(`/shelters/${shelterId}/field-validation`);
    return response.data;
  },

  async postFieldValidation(shelterId, data) {
    const response = await api.post(`/shelters/${shelterId}/field-validation`, data);
    return response.data;
  },

  async getEconomicsBenchmarks() {
    const response = await api.get('/shelters/economics/benchmarks');
    return response.data;
  },

  async getShelterEconomics(shelterId) {
    const response = await api.get(`/shelters/${shelterId}/economics`);
    return response.data;
  },
};