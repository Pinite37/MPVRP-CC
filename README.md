# MPVRP-CC: Multi-Product Vehicle Routing Problem with Changeover Cost

A comprehensive platform for generating, verifying, and evaluating solutions to the **MPVRP-CC** problem (Multi-Product Vehicle Routing Problem with Changeover Cost).

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Problem Description](#problem-description)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
  - [Quick Start Script](#quick-start-script)
  - [API Endpoints](#api-endpoints)
  - [Web Interface](#web-interface)
- [Development](#development)
- [Testing](#testing)
- [License](#license)

---

## Overview

MPVRP-CC is a research platform designed to support the Multi-Product Vehicle Routing Problem with Changeover Cost. It provides:

- **Instance Generation**: Automatically generate MPVRP-CC instances with customizable parameters
- **Solution Verification**: Check the feasibility of proposed solutions
- **Scoring & Evaluation**: Evaluate solutions across 150 test instances with detailed metrics
- **Scoreboard & Leaderboard**: Track team performance and rankings
- **Web Interface**: User-friendly frontend for submissions and visualization

This project is built using **FastAPI** for the backend and provides both REST API and web-based interfaces.

---

## Features

✅ **Instance Generation**
- Generate random MPVRP-CC instances with configurable parameters
- Support for vehicles, depots, garages, stations, and products
- Customizable capacity, demand, and transition cost ranges

✅ **Solution Verification**
- Validate solution feasibility against instance constraints
- Detailed error reporting and metrics computation
- Support for multiple product deliveries and vehicle capacity constraints

✅ **Batch Evaluation**
- Score solutions against 150 standardized test instances
- Multi-category evaluation (small, medium, large instances)
- Detailed result reporting per instance

✅ **User Management & Authentication**
- Team registration and authentication
- Submission history tracking
- Secure API with JWT tokens

✅ **Visualization & Dashboard**
- Scoreboard with team rankings
- Submission history
- Solution visualization interface
- Real-time results updates

---

## Problem Description

The **Multi-Product Vehicle Routing Problem with Changeover Cost (MPVRP-CC)** is an extension of the Vehicle Routing Problem where:

1. **Multiple Products**: Vehicles must deliver multiple product types to stations
2. **Vehicle Capacities**: Each vehicle has a maximum capacity constraint
3. **Changeover Costs**: Switching between products in a vehicle's route incurs a cost
4. **Depots & Garages**: Vehicles start/end at garages and load/unload at depots
5. **Station Demands**: Each station has specific demand for each product

For detailed problem definition, refer to the documentation in the `docs/` folder.

---

## Project Structure

```
MPVRP-CC/
├── backup/                    # Main application source code
│   ├── app/                   # FastAPI application
│   │   ├── main.py           # Main application setup
│   │   ├── schemas.py        # Pydantic models
│   │   ├── utils.py          # Utility functions
│   │   └── routes/           # API endpoints
│   │       ├── generator.py  # Instance generation
│   │       ├── model.py      # Solution verification
│   │       ├── scoring.py    # Scoring & evaluation
│   │       ├── scoreboard.py # Leaderboard
│   │       └── auth.py       # Authentication
│   ├── core/                 # Core business logic
│   │   ├── generator/        # Instance generation logic
│   │   ├── model/            # Solution validation logic
│   │   ├── scoring/          # Scoring calculations
│   │   └── auth/             # Authentication utilities
│   └── database/             # Database models and setup
│       ├── db.py             # Database connection
│       └── models_db.py      # SQLAlchemy models
├── data/                      # Data and instances
│   ├── instances/            # Test instances (small, medium, large)
│   ├── solutions/            # Reference solutions
│   ├── test/                 # Test instances
│   └── zips/                 # Compressed instance collections
├── pages/                     # Web interface
│   ├── scoreboard.html       # Scoreboard page
│   ├── submission.html       # Submission page
│   ├── visualisation.html    # Solution visualization
│   └── static/               # CSS, JavaScript, images
├── docs/                      # Documentation
│   ├── problem_definition.pdf
│   ├── instance_description.pdf
│   └── solution_description.pdf
├── tests/                     # Test suite
│   ├── test_api.py
│   ├── test_feasibility.py
│   ├── test_instance_generator.py
│   ├── test_instance_verificator.py
│   ├── test_integration.py
│   ├── conftest.py
│   └── fixtures/             # Test data
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Project metadata
├── pytest.ini               # Pytest configuration
└── index.html               # Main entry point
```

---

## Installation

### Prerequisites

- Python 3.12+
- pip or uv package manager

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd MPVRP-CC
   ```

2. **Create a virtual environment**:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
   Or using uv:
   ```bash
   uv sync
   ```

4. **Set up environment variables** (if needed):
   Create a `.env` file in the root directory:
   ```bash
   # Example .env
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=sqlite:///./mpvrp_scoring.db
   ```

---

## Usage

### Quick Start Script

Use the helper script from the project root to launch the API with environment variables preconfigured:

```bash
./start.sh
```

What it does:

- Generates and exports `SECRET_KEY` using Python `secrets.token_urlsafe(32)`
- Exports `DATABASE_URL` (defaults to `sqlite:///./mpvrp_scoring.db` if not already set)
- Starts the server with `uvicorn backup.app.main:app --host 0.0.0.0 --port 8000 --reload`

After startup:

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### API Endpoints

#### 1. **Health Check**
```bash
GET /health
```
Returns the API health status.

#### 2. **Instance Generation**
```bash
POST /generator/generate
Content-Type: application/json

{
  "id_instance": "01",
  "nb_vehicules": 5,
  "nb_depots": 2,
  "nb_garages": 1,
  "nb_stations": 10,
  "nb_produits": 3,
  "max_coord": 100.0,
  "min_capacite": 10000,
  "max_capacite": 25000,
  "min_transition_cost": 10.0,
  "max_transition_cost": 80.0,
  "min_demand": 500,
  "max_demand": 5000,
  "seed": 42
}
```

**Response**:
```json
{
  "filename": "MPVRP_01_s10_d2_p3.dat",
  "content": "instance file content..."
}
```

#### 3. **Solution Verification**
```bash
POST /model/verify
Content-Type: application/json

{
  "instance": "instance content...",
  "solution": "solution content..."
}
```

**Response**:
```json
{
  "feasible": true,
  "errors": [],
  "metrics": {
    "total_cost": 5432.10,
    "vehicle_count": 5,
    "utilization": 0.85
  }
}
```

#### 4. **Submit Solutions for Scoring**
```bash
POST /scoring/submit/{user_id}
Content-Type: multipart/form-data

Files: 150 solution files
```

#### 5. **Get Scoring Results**
```bash
GET /scoring/result/{submission_id}
```

**Response**: Detailed scores and feasibility status for each instance.

#### 6. **Get Submission History**
```bash
GET /scoring/history/{user_id}
```

#### 7. **Get Scoreboard**
```bash
GET /scoreboard/
```

**Response**: Current rankings with best submissions per team.

#### 8. **Authentication**
- `POST /auth/register`: Register new team
- `POST /auth/login`: Login with credentials
- `POST /auth/logout`: Logout

For complete API documentation, visit `/docs` when the server is running.

### Web Interface

1. **Start the development server**:
   ```bash
   cd backup
   uvicorn app.main:app --reload
   ```
   
   The API will be available at `http://localhost:8000`
   - Interactive API docs: `http://localhost:8000/docs`
   - Web interface: Open `index.html` or navigate to the pages folder

2. **Access the Web Pages**:
   - **Scoreboard**: View team rankings and results
   - **Submission**: Upload solutions for evaluation
   - **Visualization**: Visualize instance and solution data

---

## Development

### Project Dependencies

Key dependencies include:

- **fastapi**: Web framework for building the API
- **uvicorn**: ASGI server
- **pydantic**: Data validation
- **sqlalchemy**: Database ORM
- **pulp**: Linear programming (optimization)
- **networkx**: Graph algorithms
- **numpy**: Numerical computing
- **pytest**: Testing framework
- **python-jose**: JWT authentication
- **passlib**: Password hashing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backup tests/

# Run specific test file
pytest tests/test_integration.py

# Run specific test
pytest tests/test_api.py::test_health_check
```

### Code Structure Guidelines

- **Core Logic**: `backup/core/` - Pure business logic without dependencies
- **API Layer**: `backup/app/routes/` - HTTP request handling
- **Database**: `backup/database/` - Data persistence
- **Tests**: `tests/` - Unit and integration tests

---

## Data Formats

### Instance Format

Instances follow the `.dat` format with the following structure:
```
Number of products, vehicles, depots, garages, stations
Coordinates and parameters for each node
Capacity constraints
Demand matrices
Transition costs between products
```

See `docs/instance_description.pdf` for detailed specification.

### Solution Format

Solutions must follow the naming convention:
```
Sol_MPVRP_{id_instance}_s{nb_stations}_d{nb_depots}_p{nb_produits}.dat
```

Structure:
```
Vehicle routes with:
- Garage → Depot [load] → Stations (deliver) → Depot [unload] → Garage
- Product changeover information
- Delivery quantities
```

See `data/solutions/README.md` for detailed solution format specification.

---

## Testing

The project includes comprehensive test coverage:

- **Unit Tests**: Core functionality and utilities
- **Integration Tests**: End-to-end workflows
- **API Tests**: HTTP endpoint validation
- **Feasibility Tests**: Solution validation logic
- **Instance Tests**: Instance generation and verification

Run tests with pytest:
```bash
pytest
```

Generate coverage report:
```bash
pytest --cov=backup --cov-report=html
```

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -am 'Add new feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Submit a pull request

---

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

---

## Contact & Support

For issues, questions, or contributions, please refer to the project documentation in the `docs/` folder or contact the development team.

---

## Changelog

### v0.1.0
- Initial release
- Instance generation
- Solution verification
- Scoring and leaderboard system
- Web interface for submissions
- REST API with comprehensive endpoints

