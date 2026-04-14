"""
routing_engine.py - Dynamic Multi-Objective A* Routing Engine
================================================================
Improvements over previous version:
1. Fixed marine penalty bug (was 1000x too aggressive)
2. Proper multi-objective cost functions
3. Better fuel efficiency modeling
4. Cleaner obstacle/replanning logic
"""

import numpy as np
from scipy.spatial import KDTree
from global_land_mask import globe
import heapq
from weather_service import get_live_weather_penalty

# ============================================
# GEOGRAPHIC ZONES
# ============================================

PROTECTED_ZONES = [
    {"lat": -6.0,  "lon": 71.5,  "radius_nm": 300, "name": "Chagos Marine Reserve"},
    {"lat": 8.5,   "lon": 73.0,  "radius_nm": 150, "name": "Lakshadweep Sanctuary"},
    {"lat": -20.0, "lon": 40.0,  "radius_nm": 200, "name": "Mozambique Channel Coral"},
    {"lat": -12.0, "lon": 48.0,  "radius_nm": 120, "name": "Madagascar Marine Park"},
]

PIRACY_ZONES = [
    {"lat": 12.0, "lon": 45.0, "radius_nm": 400},  # Gulf of Aden
    {"lat": 2.0,  "lon": 49.0, "radius_nm": 250},  # Somali coast
    {"lat": 4.0,  "lon": 43.0, "radius_nm": 180},  # Horn of Africa
]

# Favorable ocean currents (reduce fuel cost when used)
FAVORABLE_CURRENTS = [
    # Agulhas Current (southward along Africa east coast)
    {"lat_range": (-35, -15), "lon_range": (35, 45), "direction": "S", "strength": 0.85},
    # South Equatorial Current (westward, 5-20°S)
    {"lat_range": (-20, -5), "lon_range": (40, 100), "direction": "W", "strength": 0.90},
    # Indian Monsoon Current (varies by season)
    {"lat_range": (0, 15), "lon_range": (55, 90), "direction": "NE", "strength": 0.92},
]


# ============================================
# GRID SETUP
# ============================================

def build_grid(step=2.5):
    """
    Indian Ocean navigation grid banao.
    step=2.5° → ~800 water nodes, fast computation
    """
    nodes = []
    for lat in np.arange(-30, 25, step):
        for lon in np.arange(30, 110, step):
            if not globe.is_land(lat, lon):
                nodes.append([lat, lon])
    
    nodes = np.array(nodes)
    tree = KDTree(nodes)
    
    # Each node ke neighbors find karo (1.5x step radius)
    graph = {
        i: [n for n in tree.query_ball_point(p, r=step * 1.5) if n != i]
        for i, p in enumerate(nodes)
    }
    
    print(f"Grid built: {len(nodes)} navigation nodes")
    return nodes, tree, graph


# ============================================
# DISTANCE: Haversine (nautical miles)
# ============================================

def haversine_nm(p1, p2) -> float:
    """Accurate great-circle distance in nautical miles."""
    lat1, lon1 = np.radians(p1[0]), np.radians(p1[1])
    lat2, lon2 = np.radians(p2[0]), np.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 6371 * 2 * np.arcsin(np.sqrt(a)) * 0.539957


# ============================================
# CURRENT BONUS CALCULATOR
# ============================================

def get_current_bonus(p1, p2) -> float:
    """
    Ocean current ke saath travel karne par fuel discount.
    Returns multiplier: <1.0 = favorable, >1.0 = against current
    """
    lat, lon = p2[0], p2[1]
    direction = "E" if p2[1] > p1[1] else "W"
    ns_dir = "N" if p2[0] > p1[0] else "S"
    
    for current in FAVORABLE_CURRENTS:
        lat_ok = current["lat_range"][0] <= lat <= current["lat_range"][1]
        lon_ok = current["lon_range"][0] <= lon <= current["lon_range"][1]
        
        if lat_ok and lon_ok:
            curr_dir = current["direction"]
            # Check if moving WITH the current
            with_current = (
                (curr_dir == "W" and direction == "W") or
                (curr_dir == "E" and direction == "E") or
                (curr_dir == "S" and ns_dir == "S") or
                (curr_dir == "N" and ns_dir == "N") or
                (curr_dir == "NE" and direction == "E" and ns_dir == "N")
            )
            if with_current:
                return current["strength"]  # Discount!
    
    return 1.0  # No current effect


# ============================================
# MULTI-OBJECTIVE COST CALCULATOR
# ============================================

def calculate_cost(node_idx: int, neighbor_idx: int, 
                   nodes: np.ndarray, mode: str, 
                   fuel_level_pct: float) -> float:
    """
    Core cost function — har objective ke liye alag weights.
    
    MODE BEHAVIORS:
    - 'safety':  Weather avoid karo, piracy avoid karo, marine protect karo
    - 'fuel':    Currents use karo, fuel km hai to westward movement penalize
    - 'speed':   Shortest path, weather partially ignore karo
    
    Returns: weighted cost (higher = worse path)
    """
    p1 = nodes[node_idx]
    p2 = nodes[neighbor_idx]
    lat, lon = p2[0], p2[1]
    
    # ---- BASE: Physical distance ----
    dist_nm = haversine_nm(p1, p2)
    
    # ---- WEATHER PENALTY ----
    weather_raw = get_live_weather_penalty(lat, lon)
    
    # ---- MODE-BASED PROCESSING ----
    
    if mode == "fuel":
        # Fuel optimization: currents maximize karo, headwinds avoid karo
        current_bonus = get_current_bonus(p1, p2)
        
        # Low fuel = extra conservative (avoid long detours)
        fuel_multiplier = 1.0
        if fuel_level_pct < 40:
            # Westward against main monsoon current: expensive
            if lon < p1[1] - 1:
                fuel_multiplier = 2.0
            # Fuel-adjusted penalty: lower fuel = higher worry about efficiency
            fuel_multiplier *= (1.5 - fuel_level_pct / 100.0)
            fuel_multiplier = max(1.0, fuel_multiplier)
        
        weather_penalty = max(1.0, weather_raw * 0.8)  # Moderate weather tolerance
        mode_weight = 1.5 * fuel_multiplier * current_bonus
        
    elif mode == "speed":
        # Speed mode: distance minimize karo, weather partially ignore
        weather_penalty = max(1.0, weather_raw * 0.4)   # Much lower weather sensitivity
        mode_weight = 0.6  # Shorter paths preferred
        
    else:  # safety (default)
        # Safety mode: weather strongly avoid, careful routing
        weather_penalty = weather_raw ** 1.3  # Amplify danger zones
        mode_weight = 1.0
    
    # ---- MARINE PROTECTED ZONES ----
    # Fixed: was 1000x before, now reasonable 5x max penalty
    marine_penalty = 1.0
    for zone in PROTECTED_ZONES:
        d = haversine_nm([lat, lon], [zone["lat"], zone["lon"]])
        if d < zone["radius_nm"]:
            # Closer to center = higher penalty, max 5x
            proximity = 1.0 - (d / zone["radius_nm"])
            marine_penalty = max(marine_penalty, 1.0 + (4.0 * proximity))
    
    # ---- PIRACY ZONES ----
    piracy_penalty = 1.0
    for zone in PIRACY_ZONES:
        d = haversine_nm([lat, lon], [zone["lat"], zone["lon"]])
        if d < zone["radius_nm"]:
            # Safety mode: strongly avoid. Speed/fuel: still avoid but less so
            if mode == "safety":
                piracy_penalty = 15.0
            else:
                piracy_penalty = 8.0
    
    # ---- FINAL WEIGHTED COST ----
    total = dist_nm * weather_penalty * mode_weight * marine_penalty * piracy_penalty
    return total


# ============================================
# DYNAMIC A* WITH REAL-TIME REPLANNING
# ============================================

def dynamic_astar(start_idx: int, end_idx: int,
                  nodes: np.ndarray, graph: dict,
                  mode: str = "safety",
                  fuel_level_pct: float = 100,
                  blocked_nodes: set = None) -> tuple:
    """
    Multi-objective Dynamic A* pathfinder.
    
    Features:
    - Real-time obstacle avoidance (blocked_nodes)
    - Mode-aware cost function
    - Fuel-level aware routing
    - Heuristic: Haversine distance to goal
    
    Returns: (route_node_indices, total_cost)
    """
    if blocked_nodes is None:
        blocked_nodes = set()
    
    e_coords = nodes[end_idx]
    
    # Priority queue: (f_score, g_score, node_idx, path)
    pq = [(0.0, 0.0, start_idx, [start_idx])]
    
    # Best g-score seen for each node
    g_scores = {start_idx: 0.0}
    
    while pq:
        f, g, curr, path = heapq.heappop(pq)
        
        # Goal reached!
        if curr == end_idx:
            return path, g
        
        # Skip if we found a better path to curr already
        if g > g_scores.get(curr, float('inf')):
            continue
        
        for nbr in graph[curr]:
            # Skip blocked nodes (obstacles/storms)
            if nbr in blocked_nodes:
                continue
            
            step_cost = calculate_cost(curr, nbr, nodes, mode, fuel_level_pct)
            g_new = g + step_cost
            
            # Only explore if this path is better
            if g_new < g_scores.get(nbr, float('inf')):
                g_scores[nbr] = g_new
                h = haversine_nm(nodes[nbr], e_coords)
                f_new = g_new + h
                heapq.heappush(pq, (f_new, g_new, nbr, path + [nbr]))
    
    return None, float('inf')  # No route found


# ============================================
# REAL-TIME OBSTACLE HANDLER
# ============================================

def replan_around_obstacle(current_pos_idx: int, end_idx: int,
                            nodes: np.ndarray, tree: KDTree, graph: dict,
                            obstacle_center: list, obstacle_radius_nm: float,
                            mode: str, fuel_level_pct: float) -> tuple:
    """
    Real-time storm/obstacle detection par naya route calculate karo.
    
    Steps:
    1. Obstacle ke andar aane wale nodes find karo
    2. Blocked set banao
    3. Naya A* run karo
    
    Returns: (new_route, new_cost, blocked_node_set)
    """
    blocked = set()
    for i, node in enumerate(nodes):
        if haversine_nm(node, obstacle_center) < obstacle_radius_nm:
            blocked.add(i)
    
    print(f"Replanning: {len(blocked)} nodes blocked around obstacle at {obstacle_center}")
    
    new_route, new_cost = dynamic_astar(
        current_pos_idx, end_idx, nodes, graph,
        mode=mode,
        fuel_level_pct=fuel_level_pct,
        blocked_nodes=blocked
    )
    
    return new_route, new_cost, blocked


# ============================================
# ROUTE ANALYTICS
# ============================================

def analyze_route(route: list, nodes: np.ndarray, mode: str) -> dict:
    """Route ke baare mein detailed statistics calculate karo."""
    if not route or len(route) < 2:
        return {}
    
    total_dist = sum(
        haversine_nm(nodes[route[i]], nodes[route[i+1]])
        for i in range(len(route)-1)
    )
    
    # Average weather along route
    weather_values = [
        get_live_weather_penalty(nodes[idx][0], nodes[idx][1])
        for idx in route
    ]
    avg_weather = np.mean(weather_values)
    max_weather = np.max(weather_values)
    
    # Estimated speed by mode
    speed_knots = {"safety": 12, "fuel": 10, "speed": 18}.get(mode, 12)
    est_hours = total_dist / speed_knots
    
    # Fuel estimate (rough: 1 ton/100nm at cruise speed, mode adjusted)
    fuel_factor = {"safety": 1.0, "fuel": 0.75, "speed": 1.4}.get(mode, 1.0)
    est_fuel_tons = (total_dist / 100) * fuel_factor
    
    return {
        "distance_nm": round(total_dist, 1),
        "est_hours": round(est_hours, 1),
        "est_days": round(est_hours / 24, 1),
        "waypoints": len(route),
        "avg_weather_index": round(avg_weather, 2),
        "max_weather_index": round(max_weather, 2),
        "est_fuel_tons": round(est_fuel_tons, 1),
        "speed_knots": speed_knots,
    }
