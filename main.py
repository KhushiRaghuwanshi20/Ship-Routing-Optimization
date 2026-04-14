<<<<<<< Updated upstream
import folium
import numpy as np
from global_land_mask import globe
from scipy.spatial import KDTree
import heapq

# 1. Generate Navigation Nodes (The Digital Ocean)
nodes = []
for lat in np.arange(-30, 25, 2.5):
    for lon in np.arange(30, 110, 2.5):
        if not globe.is_land(lat, lon):
            nodes.append([lat, lon])
nodes = np.array(nodes)
tree = KDTree(nodes)

# 2. Build the Network Connections (Graph)
graph = {}
for i, point in enumerate(nodes):
    neighbor_indices = tree.query_ball_point(point, r=3.6)
    neighbor_indices.remove(i)
    graph[i] = neighbor_indices

# 3. Helper: Straight Line Distance
def get_dist(p1, p2):
    return np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# --- NEW: ADVANCED COST ENGINE ---
def calculate_step_cost(idx1, idx2):
    p1, p2 = nodes[idx1], nodes[idx2]
    lat2, lon2 = p2[0], p2[1]
    
    # Base Cost is physical distance
    distance = get_dist(p1, p2)
    
    # HURDLE 1: Storm Penalty (Safety)
    weather_multiplier = 1.0
    if -5 <= lat2 <= 5 and 60 <= lon2 <= 80: # Storm Zone
        weather_multiplier = 20.0 
        
    # HURDLE 2: Piracy Risk (Security)
    piracy_multiplier = 1.0
    if 0 <= lat2 <= 12 and 40 <= lon2 <= 55: # Near Gulf of Aden
        piracy_multiplier = 10.0
        
    # HURDLE 3: Fuel Optimization (Against the Wind/Current)
    # Assume wind is blowing from the West. Going West costs more fuel.
    fuel_multiplier = 1.0
    if lon2 < p1[1]: # Moving Westward
        fuel_multiplier = 1.8 

    # Total Cost = distance weighted by all hurdles
    return distance * weather_multiplier * piracy_multiplier * fuel_multiplier

# 4. Advanced A* Pathfinder
def a_star_advanced(start_idx, end_idx):
    queue = [(0, start_idx, [])]
    visited = set()
    while queue:
        (cost, current, path) = heapq.heappop(queue)
        if current in visited: continue
        visited.add(current)
        path = path + [current]
        
        if current == end_idx: return path
        
        for neighbor in graph[current]:
            if neighbor not in visited:
                # Use our new cost engine here
                g_n = cost + calculate_step_cost(current, neighbor)
                h_n = get_dist(nodes[neighbor], nodes[end_idx])
                heapq.heappush(queue, (g_n + h_n, neighbor, path))
    return None

# 5. Define Start and End
mumbai_idx = tree.query([18.9, 72.8])[1]
mauritius_idx = tree.query([-20.1, 57.5])[1]

# 6. Run the Algorithm
route_indices = a_star_advanced(mumbai_idx, mauritius_idx)
route_coords = [nodes[i].tolist() for i in route_indices]

# 7. VISUALIZATION
my_map = folium.Map(location=[10, 70], zoom_start=4, tiles='CartoDB positron')

# Visualize Hurdles (Orange = Storm, Red = Piracy)
folium.Rectangle(bounds=[[-5, 60], [5, 80]], color="orange", fill=True, fill_opacity=0.2, popup="Storm").add_to(my_map)
folium.Rectangle(bounds=[[0, 40], [12, 55]], color="red", fill=True, fill_opacity=0.2, popup="Piracy Zone").add_to(my_map)

# Draw Final Optimal Route
folium.PolyLine(route_coords, color="green", weight=6, opacity=0.9, popup="Optimized Route").add_to(my_map)

# Markers
folium.Marker(route_coords[0], popup="Mumbai", icon=folium.Icon(color='green')).add_to(my_map)
folium.Marker(route_coords[-1], popup="Mauritius", icon=folium.Icon(color='red', icon='anchor', prefix='fa')).add_to(my_map)

my_map.save("advanced_route.html")
print("Advanced Diverse Routing Complete! Open 'advanced_route.html'.")
=======
import folium
import numpy as np
from global_land_mask import globe
from scipy.spatial import KDTree
import heapq
# 1. Weather Service ko import karein
from weather_service import get_live_weather_penalty

# 2. Generate Navigation Nodes (The Digital Ocean)
nodes = []
for lat in np.arange(-30, 25, 2.5):
    for lon in np.arange(30, 110, 2.5):
        if not globe.is_land(lat, lon):
            nodes.append([lat, lon])
nodes = np.array(nodes)
tree = KDTree(nodes)

# 3. Build the Network Connections (Graph)
graph = {}
for i, point in enumerate(nodes):
    neighbor_indices = tree.query_ball_point(point, r=3.6)
    neighbor_indices.remove(i)
    graph[i] = neighbor_indices

# Helper: Straight Line Distance
def get_dist(p1, p2):
    return np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# --- UPDATED: ADVANCED COST ENGINE ---
def calculate_step_cost(idx1, idx2):
    p1, p2 = nodes[idx1], nodes[idx2]
    lat2, lon2 = p2[0], p2[1]
    
    # Base Cost is physical distance
    distance = get_dist(p1, p2)
    
    # HURDLE 1: Dynamic Weather Penalty (Real API Data)
    weather_multiplier = get_live_weather_penalty(lat2, lon2)
    
    # Optional: Agar aapko lagta hai ki API data ke sath sath 
    # specific area ko extra risky rakhna hai, toh ye rakhein:
    if -5 <= lat2 <= 5 and 60 <= lon2 <= 80:
        weather_multiplier *= 2.0 # API factor ke upar extra risk
        
    # HURDLE 2: Piracy Risk (Security)
    piracy_multiplier = 1.0
    if 0 <= lat2 <= 12 and 40 <= lon2 <= 55: # Near Gulf of Aden
        piracy_multiplier = 10.0
        
    # HURDLE 3: Fuel Optimization
    fuel_multiplier = 1.0
    if lon2 < p1[1]: # Moving Westward
        fuel_multiplier = 1.5 

    # Total Weighted Cost
    return distance * weather_multiplier * piracy_multiplier * fuel_multiplier

# 4. Advanced A* Pathfinder
def a_star_advanced(start_idx, end_idx):
    queue = [(0, start_idx, [])]
    visited = set()
    while queue:
        (cost, current, path) = heapq.heappop(queue)
        if current in visited: continue
        visited.add(current)
        path = path + [current]
        
        if current == end_idx: return path
        
        for neighbor in graph[current]:
            if neighbor not in visited:
                g_n = cost + calculate_step_cost(current, neighbor)
                h_n = get_dist(nodes[neighbor], nodes[end_idx])
                heapq.heappush(queue, (g_n + h_n, neighbor, path))
    return None

# 5. Define Start and End
mumbai_idx = tree.query([18.9, 72.8])[1]
mauritius_idx = tree.query([-20.1, 57.5])[1]

# 6. Run the Algorithm
print("Route calculation start ho rahi hai (API calling in progress)...")
route_indices = a_star_advanced(mumbai_idx, mauritius_idx)
route_coords = [nodes[i].tolist() for i in route_indices]

# 7. VISUALIZATION
my_map = folium.Map(location=[10, 70], zoom_start=4, tiles='CartoDB positron')

# Draw Final Optimal Route
folium.PolyLine(route_coords, color="green", weight=6, opacity=0.9, popup="Optimized Route").add_to(my_map)

# Markers
folium.Marker(route_coords[0], popup="Mumbai", icon=folium.Icon(color='green')).add_to(my_map)
folium.Marker(route_coords[-1], popup="Mauritius", icon=folium.Icon(color='red', icon='anchor', prefix='fa')).add_to(my_map)

my_map.save("advanced_route.html")
print("Routing Complete! 'advanced_route.html' file check karein.")
>>>>>>> Stashed changes
