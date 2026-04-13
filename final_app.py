"""
final_app.py - Dynamic Multi-Objective Ship Routing System
============================================================
Upgrades from previous version:
1. Weather loads INSTANTLY (< 1 second vs 30+ seconds before)
2. Route analytics: fuel estimate, weather index, days at sea
3. Weather heatmap overlay on map
4. Better replan log with timestamps
5. Fuel level warning integrated into routing
"""

import streamlit as st
from streamlit_folium import st_folium
import folium
import numpy as np
from datetime import datetime
from routing_engine import (
    build_grid, dynamic_astar, replan_around_obstacle,
    haversine_nm, analyze_route,
    PROTECTED_ZONES, PIRACY_ZONES
)
from weather_service import (
    preload_weather_grid, get_live_weather_penalty,
    get_weather_description, _weather_cache
)

# ---- PAGE CONFIG ----
st.set_page_config(
    page_title="Dynamic Maritime DSS",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---- CUSTOM CSS ----
st.markdown("""
<style>
    .stMetric { background: #0a1628; border-radius: 8px; padding: 12px; border: 1px solid #1e3a5f; }
    .route-info { background: #0d2137; border-left: 4px solid #00FFCC; padding: 12px; border-radius: 4px; margin: 8px 0; }
    .warning-box { background: #2d1810; border-left: 4px solid #FF6B35; padding: 12px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("🚢 Dynamic Multi-Objective Ship Routing System")
st.caption("Indian Ocean — Real-time Obstacle Avoidance | Multi-Objective A* Pathfinding")

# ---- SESSION STATE ----
defaults = {
    'route': None, 'active': False, 'nodes': None,
    'tree': None, 'graph': None, 'weather_loaded': False,
    'replan_log': [], 'stats': {}, 'current_mode': 'safety'
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---- PORT DATA ----
PORT_DATA = {
    "Mumbai, India":          [18.93, 72.83],
    "Colombo, Sri Lanka":     [6.92,  79.86],
    "Singapore Port":         [1.26,  103.83],
    "Aden, Yemen":            [12.78, 45.01],
    "Mauritius (Port Louis)": [-20.1, 57.5],
    "Chennai, India":         [13.08, 80.28],
    "Mombasa, Kenya":         [-4.05, 39.67],
    "Karachi, Pakistan":      [24.86, 67.01],
    "Colombo → Mauritius":    [-10.0, 70.0],   # Mid-ocean waypoint
}

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Navigation Parameters")

    # Routing objective
    mode = st.selectbox(
        "Routing Objective",
        ["safety", "fuel", "speed"],
        format_func=lambda x: {
            "safety": "🛡️ Safety First — Avoid storms & pirates",
            "fuel":   "⛽ Fuel Efficient — Use currents, save fuel",
            "speed":  "⚡ Maximum Speed — Shortest path"
        }[x],
        help="Each mode changes how the A* algorithm weights different costs"
    )
    st.session_state.current_mode = mode

    # Port selection
    ports = list(PORT_DATA.keys())
    col1, col2 = st.columns(2)
    with col1:
        start_p = st.selectbox("🟢 Origin", ports, index=0)
    with col2:
        end_p = st.selectbox("🔴 Destination", ports, index=4)

    if start_p == end_p:
        st.error("Origin and destination must be different!")

    st.divider()

    # Fuel level — affects routing when low
    fuel_pct = st.slider("⛽ Fuel Level (%)", 10, 100, 80, 5)
    if fuel_pct < 25:
        st.error(f"⚠️ Critical fuel ({fuel_pct}%)! Route will be highly conservative.")
    elif fuel_pct < 50:
        st.warning(f"⚠️ Low fuel ({fuel_pct}%). Route avoids long detours.")
    else:
        st.success(f"✅ Fuel OK ({fuel_pct}%)")

    # Mode explanation
    mode_explain = {
        "safety": "**Safety mode**: Weather penalty amplified (^1.3). Piracy zones: 15x cost. Marine zones protected. Best for passenger vessels.",
        "fuel":   "**Fuel mode**: Ocean currents give discount (0.85–0.92x). Westward movement against monsoon: 2x cost when fuel < 40%. Best for cargo ships.",
        "speed":  "**Speed mode**: Weather penalty reduced (0.4x). Direct great-circle preferred. Best for time-critical cargo."
    }
    st.info(mode_explain[mode])

    st.divider()

    # Real-time obstacle simulation
    st.subheader("🌊 Simulate Real-time Events")
    obstacle_active = st.checkbox("Activate Storm / Obstacle")

    obs_lat, obs_lon, obs_radius = 5.0, 75.0, 200
    if obstacle_active:
        obs_lat    = st.slider("Obstacle Latitude",  -25.0, 20.0, 5.0, 0.5)
        obs_lon    = st.slider("Obstacle Longitude",  35.0, 105.0, 75.0, 0.5)
        obs_radius = st.slider("Radius (NM)", 50, 600, 200, 50)
        st.warning(f"Storm at ({obs_lat}°N, {obs_lon}°E) — {obs_radius}NM radius")

    st.divider()

    # Calculate button
    calc_disabled = (start_p == end_p)
    run = st.button("🗺️ Calculate Optimal Route", type="primary",
                    disabled=calc_disabled, use_container_width=True)

    if st.button("🗑️ Clear Route", use_container_width=True):
        st.session_state.route = None
        st.session_state.active = False
        st.session_state.stats = {}
        st.rerun()


# ============================================================
# ONE-TIME INITIALIZATION
# ============================================================

# Build grid (once)
if st.session_state.nodes is None:
    with st.spinner("🗺️ Building Indian Ocean navigation grid..."):
        nodes, tree, graph = build_grid(step=2.5)
        st.session_state.nodes = nodes
        st.session_state.tree  = tree
        st.session_state.graph = graph
        st.success(f"✅ Grid ready: {len(nodes)} navigation nodes")

nodes = st.session_state.nodes
tree  = st.session_state.tree
graph = st.session_state.graph

# Pre-load weather (INSTANT now — physics simulation, no API!)
if not st.session_state.weather_loaded:
    with st.spinner("🌤️ Computing weather simulation..."):
        preload_weather_grid()
        st.session_state.weather_loaded = True
        st.success("✅ Weather data ready! (Instant — physics simulation)")


# ============================================================
# ROUTE CALCULATION
# ============================================================

if run and start_p != end_p:
    s_coords = PORT_DATA[start_p]
    e_coords = PORT_DATA[end_p]
    s_idx = tree.query(s_coords)[1]
    e_idx = tree.query(e_coords)[1]

    # Build blocked set from obstacle
    blocked = set()
    if obstacle_active:
        for i, node in enumerate(nodes):
            if haversine_nm(node, [obs_lat, obs_lon]) < obs_radius:
                blocked.add(i)

    with st.status("🧭 Calculating optimal route...", expanded=True) as status:
        st.write(f"**Mode:** {mode.upper()} | **Fuel:** {fuel_pct}% | "
                 f"**Blocked nodes:** {len(blocked)}")

        route, total_cost = dynamic_astar(
            s_idx, e_idx, nodes, graph,
            mode=mode,
            fuel_level_pct=fuel_pct,
            blocked_nodes=blocked
        )

        if route:
            st.session_state.route  = [nodes[i].tolist() for i in route]
            st.session_state.stats  = analyze_route(route, nodes, mode)
            st.session_state.active = True

            if obstacle_active:
                ts = datetime.now().strftime("%H:%M:%S")
                st.session_state.replan_log.append(
                    f"[{ts}] Storm at ({obs_lat}°, {obs_lon}°), "
                    f"radius {obs_radius}NM — {len(blocked)} nodes blocked"
                )

            status.update(label="✅ Route calculated!", state="complete")
        else:
            status.update(label="❌ No viable route found. Try reducing obstacle radius.", state="error")


# ============================================================
# MAIN DISPLAY
# ============================================================

if st.session_state.active and st.session_state.route:
    stats = st.session_state.stats

    # ---- METRICS ROW ----
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("📍 Distance",      f"{stats.get('distance_nm', 0):.0f} NM")
    c2.metric("⏱️ Est. Time",     f"{stats.get('est_hours', 0):.0f} hrs")
    c3.metric("🗓️ Days at Sea",   f"{stats.get('est_days', 0):.1f}")
    c4.metric("⚡ Speed",         f"{stats.get('speed_knots', 0)} kts")
    c5.metric("⛽ Fuel Est.",     f"{stats.get('est_fuel_tons', 0):.0f} t")
    c6.metric("🌊 Weather Idx",   f"{stats.get('avg_weather_index', 0):.1f}")

    # ---- MAP ----
    m = folium.Map(location=[5, 70], zoom_start=4, tiles="CartoDB dark_matter")

    # Route line
    mode_colors = {"safety": "#00FF88", "fuel": "#FFB347", "speed": "#00BFFF"}
    route_color = mode_colors.get(st.session_state.current_mode, "#00FFCC")
    folium.PolyLine(
        st.session_state.route,
        color=route_color,
        weight=4, opacity=0.9,
        tooltip=f"Route ({st.session_state.current_mode.upper()} mode)"
    ).add_to(m)

    # Waypoint dots (every 5th point to avoid clutter)
    for i, coord in enumerate(st.session_state.route[1:-1:5]):
        folium.CircleMarker(
            location=coord, radius=3,
            color=route_color, fill=True, fill_opacity=0.7
        ).add_to(m)

    # Port markers
    folium.Marker(
        PORT_DATA[start_p],
        popup=f"🟢 ORIGIN: {start_p}",
        icon=folium.Icon(color='green', icon='anchor', prefix='fa')
    ).add_to(m)
    folium.Marker(
        PORT_DATA[end_p],
        popup=f"🔴 DESTINATION: {end_p}",
        icon=folium.Icon(color='red', icon='flag', prefix='fa')
    ).add_to(m)

    # Marine protected zones
    for zone in PROTECTED_ZONES:
        folium.Circle(
            location=[zone["lat"], zone["lon"]],
            radius=zone["radius_nm"] * 1852,
            color='#00AA44', fill=True, fill_opacity=0.12,
            tooltip=f"🌿 {zone['name']}"
        ).add_to(m)

    # Piracy zones
    for zone in PIRACY_ZONES:
        folium.Circle(
            location=[zone["lat"], zone["lon"]],
            radius=zone["radius_nm"] * 1852,
            color='#FF4444', fill=True, fill_opacity=0.12,
            tooltip="⚠️ High Piracy Risk Zone"
        ).add_to(m)

    # Active storm/obstacle
    if obstacle_active:
        folium.Circle(
            location=[obs_lat, obs_lon],
            radius=obs_radius * 1852,
            color='#FF8800', fill=True, fill_opacity=0.35,
            tooltip=f"🌀 Storm/Obstacle — {obs_radius}NM radius"
        ).add_to(m)
        # Show blocked zone boundary
        folium.Circle(
            location=[obs_lat, obs_lon],
            radius=obs_radius * 1852 * 1.1,
            color='#FF8800', fill=False, weight=2,
            dash_array='10',
            tooltip="Route avoidance boundary"
        ).add_to(m)

    # Weather heatmap (sample points)
    weather_fg = folium.FeatureGroup(name="Weather Overlay", show=False)
    sample_lats = np.arange(-25, 22, 8)
    sample_lons = np.arange(35, 108, 8)
    for slat in sample_lats:
        for slon in sample_lons:
            if not __import__('global_land_mask').globe.is_land(slat, slon):
                wp = get_live_weather_penalty(slat, slon)
                if wp > 3.0:  # Only show notable weather
                    color = '#FF0000' if wp > 10 else '#FF8800' if wp > 5 else '#FFFF00'
                    folium.CircleMarker(
                        location=[slat, slon],
                        radius=max(4, min(15, wp * 1.5)),
                        color=color, fill=True, fill_opacity=0.3,
                        tooltip=f"Weather: {get_weather_description(slat, slon)} ({wp:.1f}x)"
                    ).add_to(weather_fg)
    weather_fg.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width=None, height=540, returned_objects=[])

    # ---- ROUTE DETAILS ----
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📊 Route Analysis")
        max_wi = stats.get('max_weather_index', 0)
        if max_wi > 10:
            st.error(f"⚠️ High weather risk on route! Max index: {max_wi:.1f}")
        elif max_wi > 5:
            st.warning(f"⚠️ Moderate weather risk. Max index: {max_wi:.1f}")
        else:
            st.success(f"✅ Route clear. Max weather index: {max_wi:.1f}")

        st.markdown(f"""
        | Parameter | Value |
        |-----------|-------|
        | Total Distance | {stats.get('distance_nm', 0):.0f} NM |
        | Estimated Duration | {stats.get('est_hours', 0):.0f} hrs ({stats.get('est_days', 0):.1f} days) |
        | Cruise Speed | {stats.get('speed_knots', 0)} knots |
        | Fuel Estimate | {stats.get('est_fuel_tons', 0):.1f} tons |
        | Waypoints | {stats.get('waypoints', 0)} |
        | Avg Weather Index | {stats.get('avg_weather_index', 0):.2f} |
        | Max Weather Index | {stats.get('max_weather_index', 0):.2f} |
        | Route Mode | {st.session_state.current_mode.upper()} |
        """)

    with col_b:
        st.subheader("🔍 Cost Function Details")
        st.markdown(f"""
        **Active constraints for `{mode}` mode:**
        
        {'• Weather penalty amplified (^1.3x) for extra storm avoidance' if mode == 'safety' else ''}
        {'• Piracy zones: **15x cost** penalty' if mode == 'safety' else '• Piracy zones: **8x cost** penalty'}
        {'• Marine zones: up to 5x penalty' if mode in ['safety', 'fuel'] else '• Marine zones: up to 5x penalty'}
        {'• Ocean current bonus: 0.85–0.92x fuel discount' if mode == 'fuel' else ''}
        {'• Westward (anti-current) movement: **2x** when fuel < 40%' if mode == 'fuel' and fuel_pct < 40 else ''}
        {'• Weather reduced to 0.4x — accepting more risk for speed' if mode == 'speed' else ''}
        {'• Direct great-circle path prioritized' if mode == 'speed' else ''}
        
        **Fuel level impact:**
        {'🔴 Critical: Route highly conservative, max efficiency' if fuel_pct < 25
         else '🟡 Low: Avoiding unnecessary detours' if fuel_pct < 50
         else '🟢 Normal: Standard routing active'}
        """)

    # ---- REPLAN LOG ----
    if st.session_state.replan_log:
        st.subheader("📋 Real-time Replanning Log")
        for i, event in enumerate(reversed(st.session_state.replan_log[-5:]), 1):
            st.info(f"Event {i}: {event}")

# ---- EMPTY STATE ----
else:
    st.info("👈 Configure parameters in the sidebar and click **Calculate Optimal Route** to begin.")

    # Quick guide
    with st.expander("📖 How to use this system"):
        st.markdown("""
        ### Quick Start Guide
        
        1. **Choose Routing Objective** — Safety avoids storms, Fuel uses ocean currents, Speed takes shortest path
        2. **Select Ports** — Choose origin and destination from Indian Ocean major ports
        3. **Set Fuel Level** — Low fuel triggers conservative routing automatically
        4. **Optional: Simulate Storm** — Check the obstacle box to test real-time replanning
        5. **Calculate Route** — The Dynamic A* algorithm will find the optimal path
        
        ### Zone Legend
        - 🟢 **Green circles** — Marine Protected Zones (avoid for environmental reasons)
        - 🔴 **Red circles** — High Piracy Risk Zones (Gulf of Aden, Somali coast)
        - 🟠 **Orange circle** — Active storm/obstacle (if enabled)
        
        ### Why is it fast now?
        Previous version called OpenWeatherMap API ~200 times (30+ seconds).
        Now uses **physics-based simulation** of Indian Ocean weather patterns:
        - Cyclone zones (Bay of Bengal, Arabian Sea)
        - Seasonal monsoon patterns
        - Agulhas current turbulence
        - Latitude-based roughness
        
        Result: **< 1 second** load time with same realistic behavior!
        """)
