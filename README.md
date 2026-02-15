 📌 Project Overview

The maritime industry is a major consumer of fossil fuels. This project focuses on developing a **Python-based optimization algorithm** to determine the most efficient sea route between ports in the Indian Ocean.

Unlike standard navigation tools, this algorithm is "Versatile and Fast," meaning it optimizes for multiple objectives: **Fuel Efficiency**, **Route Safety**, and **Travel Time**. It dynamically accounts for environmental "forcings" such as surface winds, ocean currents, and wave heights.

## 🎯 Key Objectives

* **Fuel Optimization:** Identify routes that minimize fuel consumption to reduce costs and  emissions.
* **Weather Safety:** Avoid storms and heavy seas using real-time weather data to protect the ship and crew.
* **Profit Speed Calculation:** Determine the optimal speed that balances time value against fuel costs.
* **Customizability:** Support varying ship dimensions and drift characteristics for different vessel types.

## 🛠️ Technical Stack

* **Language:** Python (Open-source implementation)
* **Algorithms:** A* (A-Star) Search modified for multi-objective maritime constraints
* **Visualization:** React.js & Leaflet.js for interactive map plotting
* **Project Management:** Jira (Agile Kanban Board)
* **Version Control:** Git & GitHub

---

## 📂 Project Directory Structure

```text
Optimal-Ship-Routing/
├── data/                   # Maritime datasets (Ports, Bathymetry)
│   ├── ports.json          # Coordinates for Indian Ocean ports
│   └── land_mask.geojson   # Coastal and island boundary data
├── docs/                   # Documentation and UML diagrams
│   ├── vision_doc.pdf      # Project Vision & Scope
│   └── use_case_diag.png   # Functional modeling diagrams
├── src/                    # Source code
│   ├── algorithms/         # Logic for A* and pathfinding
│   │   └── a_star.py
│   ├── models/             # Performance curves & fuel math
│   │   └── ship_model.py
│   ├── api/                # Weather API integration scripts
│   │   └── weather_svc.py
│   └── main.py             # Application entry point
├── frontend/               # React & Leaflet.js visualization
│   └── ...
├── tests/                  # Unit tests for algorithm accuracy
├── .gitignore              # Files to be ignored by Git
├── README.md               # Project overview and guide
└── requirements.txt        # Python dependencies



## 🏗️ System Architecture

1. **Data Layer:** Fetches weather forecasts and port coordinates.
2. **Logic Layer:** Processes ship performance curves and runs the A* optimization.
3. **Visualization Layer:** Renders the calculated optimal route on a Leaflet.js map.


## 📜 Development Roadmap

* **Phase 1:** Planning, Requirement Analysis, and Infrastructure Setup
* **Phase 2:** Functional Modeling (Use Case Diagrams) and System Design
* **Phase 3:** Backend Implementation (A* Logic & Data Integration)
* **Phase 4:** Frontend Integration and Final Testing

