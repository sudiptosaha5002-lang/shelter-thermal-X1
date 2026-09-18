# 🏔️ Shelter Thermal Optimizer

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![React Version](https://img.shields.io/badge/react-18-61DAFB.svg?logo=react)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> A full-stack monorepo for passive shelter thermal simulation and optimization, specifically designed for extreme high-altitude climates like Ladakh, Rajasthan, and Himachal Pradesh.

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Getting Started](#-getting-started)
  - [Docker Setup (Recommended)](#docker-setup-recommended)
  - [Manual Local Setup](#manual-local-setup)
- [Project Structure](#-project-structure)
- [API Documentation](#-api-documentation)
- [Pre-configured Locations](#-pre-configured-locations)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

The **Shelter Thermal Optimizer** is an advanced tool that allows engineers, architects, and researchers to simulate and optimize the thermal performance of shelters in extreme climates. By leveraging NASA's POWER API for precise climate data and running transient heat flow analysis using finite difference methods, this application helps determine the most energy-efficient materials and structural designs for minimal heating loads.

---

## ✨ Key Features

- 🌡️ **Thermal Simulation**: Transient heat flow analysis utilizing the finite difference method.
- 🌍 **Real-time Climate Data**: Direct integration with the NASA POWER API for highly accurate global environmental data.
- 🏗️ **Material Optimization**: Automated comparison of various structural materials to find the configuration that minimizes heating energy requirements.
- 🧊 **3D Visualization**: Interactive, browser-based 3D previews of the shelter structures using Three.js.
- 📊 **Data Visualization**: Rich, dynamic charts for temperature profiles, heating loads, and material comparisons.
- 👤 **Comfort Analysis**: Built-in PMV/PPD (Predicted Mean Vote / Predicted Percentage of Dissatisfied) thermal comfort assessment.

---

## 🏗 System Architecture

The project follows a decoupled client-server architecture:

- **Frontend (React)**: Handles the UI, 3D rendering (React Three Fiber), and chart visualizations. Communicates with the backend via RESTful APIs.
- **Backend (FastAPI)**: Serves as the computational engine. Handles the thermal simulation math (NumPy/SciPy), database interactions, and external API requests (NASA POWER).

---

## 💻 Tech Stack

### Frontend
* **Core**: React 18, TypeScript/JavaScript
* **Styling**: Tailwind CSS
* **3D Rendering**: Three.js, `@react-three/fiber`, `@react-three/drei`
* **Charts**: Chart.js, `react-chartjs-2`

### Backend
* **Core**: Python 3.10+, FastAPI, Uvicorn
* **Scientific Computing**: NumPy, SciPy, Pandas, `pythermalcomfort`
* **Database**: PostgreSQL (`psycopg2-binary`)
* **HTTP & Validation**: Requests, Pydantic

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed:
- **Node.js** (v16.0 or higher) & **npm**
- **Python** (v3.10 or higher)
- **Docker & Docker Compose** (Optional, but recommended)

---

## 🚀 Getting Started

### Docker Setup (Recommended)

The easiest way to run the entire stack (Frontend, Backend, and Database) is via Docker Compose.

1. Clone the repository and navigate to the project root.
2. Run the following command:
```bash
docker compose up --build -d
```
3. Access the services:
   - **Frontend App**: [http://localhost:3000](http://localhost:3000)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)
   - **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

To stop the containers, run: `docker compose down`

---

### Manual Local Setup

If you prefer to run the services natively on your machine, you will need two separate terminal windows.

#### 1. Backend Setup
```bash
cd backend
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\activate
# Activate virtual environment (Mac/Linux)
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```
*The backend will be running at `http://localhost:8000`*

#### 2. Frontend Setup
Open a new terminal window:
```bash
cd frontend
npm install
npm start
```
*The frontend will automatically open at `http://localhost:3000`*

---

## 📂 Project Structure

```text
shelter-thermal-optimizer/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route endpoints
│   │   ├── core/           # Mathematical thermal simulation engine
│   │   ├── db/             # PostgreSQL models & database connections
│   │   └── services/       # External service integrations (NASA POWER API)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # React components (UI Controls, 3D Canvas, Charts)
│   │   └── services/       # Axios/Fetch API clients
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml
```

---

## 📡 API Documentation

Once the backend is running, FastAPI automatically generates interactive API documentation. Visit `http://localhost:8000/docs` to view and test all endpoints.

### Core Endpoints:
- `GET /api/v1/climate/locations` - Fetch available pre-configured climate locations.
- `GET /api/v1/climate/data/{location_id}` - Fetch NASA POWER climate data for a specific location.
- `GET /api/v1/materials/` - Retrieve available building materials and their thermal properties.
- `POST /api/v1/simulation/run` - Execute a custom thermal simulation.
- `POST /api/v1/simulation/optimize` - Run the optimization engine across materials.
- `GET /api/v1/simulation/history` - Fetch previous simulation runs.

---

## 📍 Pre-configured Locations

The system comes pre-loaded with critical extreme-weather locations for immediate testing:
- **Leh, Ladakh** (34.15°N, 77.58°E)
- **Kargil, Ladakh** (34.56°N, 76.13°E)
- **Jaisalmer, Rajasthan** (26.92°N, 70.91°E)
- **Bikaner, Rajasthan** (28.02°N, 73.31°E)
- **Srinagar, J&K** (34.08°N, 74.80°E)
- **Manali, Himachal** (32.24°N, 77.19°E)
- **Shimla, Himachal** (31.10°N, 77.17°E)

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.