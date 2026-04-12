import streamlit as st
from streamlit_folium import st_folium
import folium
import numpy as np
from global_land_mask import globe
from scipy.spatial import KDTree
import heapq

# --- 1. CONFIG ---
st.set_page_config(page_title="Maritime DSS", layout="wide")
st.title("🚢 Indian Ocean Strategic Ship Routing System")
st.caption("Industrial Decision Support System | Group 13")

# --- 2. GRID ENGINE ---
@st.cache_resource
def build_maritime_grid():
    nodes = []
    for lat in np.arange(-30, 25, 2.5): 
        for lon in np.arange(30, 110, 2.5):
            if not globe.is_land(lat, lon):
                nodes.append([lat, lon])
    nodes = np.array(nodes)
    tree = KDTree(nodes)
    graph = {i: tree.query_ball_point(p, r=3.8) for i, p in enumerate(nodes)}
    return nodes, tree, graph

nodes, tree, graph = build_maritime_grid()

def haversine_nm(p1, p2):
    lat1, lon1, lat2, lon2 = map(np.radians, [p1[0], p1[1], p2[0], p2[1]])
    d = 2 * 3440 * np.arcsin(np.sqrt(np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2))
    return d

def get_risk(lat, lon):
    if -5 <= lat <= 10 and 65 <= lon <= 85: return 20.0
    if 5 <= lat <= 15 and 45 <= lon <= 55: return 12.0
    return 1.0

# --- 3. SIDEBAR ---
st.sidebar.header("🚢 Voyage Parameters")
vessel = st.sidebar.selectbox("Vessel Type", ["Container Carrier", "Oil Tanker", "Bulk Carrier"])
start_port = st.sidebar.text_input("Departure (Mumbai)", "18.9, 72.8")
end_port = st.sidebar.text_input("Arrival (Mauritius)", "-20.1, 57.5")
strategy = st.sidebar.select_slider("Strategy", options=["Economy", "Standard", "Safe", "Storm Avoidance"])

# --- 4. SESSION STATE (The Fix) ---
# Isse data screen par bacha rahega
if 'routing_result' not in st.session_state:
    st.session_state.routing_result = None

# --- 5. LOGIC ---
if st.sidebar.button("⚙️ Execute Optimization"):
    try:
        s_coords = [float(x.strip()) for x in start_port.split(',')]
        e_coords = [float(x.strip()) for x in end_port.split(',')]
        s_idx, e_idx = tree.query(s_coords)[1], tree.query(e_coords)[1]

        pq = [(0, s_idx, [])]
        visited = set()
        risk_map = {"Economy": 1, "Standard": 10, "Safe": 40, "Storm Avoidance": 180}
        
        with st.spinner("Calculating Optimal Route..."):
            while pq:
                (cost, curr, path) = heapq.heappop(pq)
                if curr in visited: continue
                visited.add(curr)
                path = path + [curr]
                if curr == e_idx:
                    # Save results to session state
                    dist_nm = sum(haversine_nm(nodes[path[i]], nodes[path[i+1]]) for i in range(len(path)-1))
                    burn = {"Container Carrier": 90, "Oil Tanker": 45, "Bulk Carrier": 30}[vessel]
                    st.session_state.routing_result = {
                        "path": path,
                        "distance": dist_nm,
                        "fuel": (dist_nm / 16 / 24) * burn,
                        "days": (dist_nm / 16 / 24)
                    }
                    break
                for n in graph[curr]:
                    if n not in visited:
                        dist = haversine_nm(nodes[curr], nodes[n])
                        penalty = 1 + (get_risk(nodes[n][0], nodes[n][1]) * risk_map[strategy] / 20)
                        heapq.heappush(pq, (cost + (dist * penalty) + haversine_nm(nodes[n], nodes[e_idx]), n, path))
    except Exception as e:
        st.error(f"Error: {e}")

# --- 6. DISPLAY RESULTS (Persistent) ---
if st.session_state.routing_result:
    res = st.session_state.routing_result
    
    # Show Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Distance", f"{res['distance']:,.1f} NM")
    c2.metric("Fuel Consumption", f"{res['fuel']:.1f} MT")
    c3.metric("Voyage Time", f"{res['days']:.1f} Days")

    st.markdown("---")
    
    # Create and Display Map
    m = folium.Map(location=[10, 75], zoom_start=4, tiles="CartoDB positron")
    folium.Rectangle(bounds=[[-5, 65], [10, 85]], color="orange", fill=True, opacity=0.1).add_to(m)
    folium.Rectangle(bounds=[[5, 45], [15, 55]], color="red", fill=True, opacity=0.1).add_to(m)
    
    route_pts = [nodes[i].tolist() for i in res['path']]
    folium.PolyLine(route_pts, color="#1a5276", weight=6).add_to(m)
    folium.Marker(route_pts[0], icon=folium.Icon(color='green')).add_to(m)
    folium.Marker(route_pts[-1], icon=folium.Icon(color='red')).add_to(m)
    
    st_folium(m, width=1300, height=500, key="main_map")
    st.success("Analysis verified. Optimized route is displayed.")
else:
    st.info("System Ready. Click 'Execute Optimization' to generate the route.")