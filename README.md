# Dynamic Multi-Objective Ship Routing System (Indian Ocean)

## 1. Project Overview
This project aims to develop a **Versatile and Fast Algorithm for Optimal Ship Routing** using a robust Java-based architecture. Moving beyond traditional static routing, this system integrates real-time meteorological data and vessel-specific performance models to provide adaptive, safe, and fuel-efficient navigation paths specifically tailored for the **Indian Ocean** region.

### Core Vision
* **Real-Time Adaptation**: Continuous integration of weather and oceanographic data to evolve routes dynamically.
* **Multi-Objective Optimization**: Simultaneously balancing fuel consumption, travel time, passenger comfort, and safety.
* **Scalable Framework**: Developed using **Spring Boot** for a service-oriented backend and **React** for an interactive frontend.

---

## 2. Problem Statement
Traditional maritime routing systems often rely on fixed waypoints and shortest-distance paths, leading to:
* **Inefficiency**: High fuel consumption due to ignoring sea currents and wind resistance.
* **Safety Risks**: Lack of real-time adaptation to changing weather conditions and storms.
* **Sustainability Gaps**: Higher carbon emissions due to sub-optimal routing.

---

## 3. Technology Stack
* **Backend**: Java 17, Spring Boot, Hibernate, JGraphT (for Graph modeling).
* **Frontend**: React JS, Leaflet (Map visualization), Axios (API communication).
* **Optimization**: MOEA Framework / Custom NSGA-II Implementation.
* **Database**: MySQL / PostgreSQL.
* **Tooling**: Jira (Scrum/Kanban boards), Git (Version Control).

---

## 4. System Architecture
The system utilizes a layered service-oriented architecture:
1. **Data Collection Layer**: REST Clients to fetch real-time weather and ocean model data.
2. **Processing Layer**: Risk evaluation and data cleaning using Java Streams API.
3. **Routing Engine**: Modified A* algorithm running on a weighted coordinate-grid of the Indian Ocean.
4. **Presentation Layer**: React dashboard providing real-time route updates and performance indicators.



---

## 5. Development Roadmap (Week 1 Status)
We are currently in **Phase 1: Project Initiation**.
- [x] Formed teams and defined the Problem Statement.
- [x] Initialized Git Repository and established branching strategy.
- [x] Setup Jira Scrum Board and initialized Product Backlog.
- [ ] Initialize Spring Boot and React project structures (Planned for Week 2).

---

## 6. Initial Product Backlog (High Priority Tasks)
| ID | User Story | Priority | Java/Tech Component |
| :--- | :--- | :--- | :--- |
| **US01** | Backend Foundation | Setup Spring Boot with JPA, Lombok, and JGraphT. | High |
| **US02** | Ocean Grid Model | Map the Indian Ocean as a 2D weighted coordinate graph. | High |
| **US03** | Weather Integration | Develop a service to fetch/parse real-time wind/wave data. | Medium |
| **US04** | Modified A* Logic | Implement routing algorithm with weather-weighted costs. | High |
| **US05** | Map Visualization | Integrate Leaflet in React to display calculated routes. | Medium |

---

## 7. Installation & Setup
*(Documentation to be updated as Phase 2 development begins)*

---

### Team & Collaboration
* **Status**: Active - Week 1 Initiation Complete.
* **Focus Area**: Maritime Logistics & Sustainability.
