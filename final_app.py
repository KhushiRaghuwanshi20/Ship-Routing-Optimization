"""
final_app.py  –  Dynamic Multi-Objective Ship Routing System
=============================================================
UI upgrades:
  • Dark nautical theme with custom CSS
  • Visual mode-selection cards (Safety / Fuel / Speed)
  • Animated fuel bar with color feedback
  • Ship-type selector (affects cost function)
  • Route-comparison table (all 3 modes at once)
  • Tabbed bottom panel: Analysis | Constraints | Log | Export
  • One-click CSV waypoint download
  • Douglas-Peucker route smoothing
"""

import streamlit as st
from streamlit_folium import st_folium
import folium
import numpy as np
import pandas as pd
from datetime import datetime
from routing_engine import (
    build_grid, dynamic_astar,
    haversine_nm, analyze_route,
    PROTECTED_ZONES, PIRACY_ZONES,
)
from weather_service import (
    preload_weather_grid,
    get_live_weather_penalty,
    get_weather_description,
    _weather_cache,
)

# ── page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Maritime DSS",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── custom CSS  ──────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #060f1e; }
[data-testid="stSidebar"]          { background: #08152a; border-right: 1px solid #112240; }
[data-testid="stSidebar"] * { color: #c8d8f0 !important; }
h1 { color: #e2ecff !important; letter-spacing: -0.5px; }

.fuel-wrap {
    background: #0c1e38; border: 1px solid #1a3050;
    border-radius: 8px; padding: 10px 14px; margin: 6px 0;
}
.fuel-track { height:7px; border-radius:4px; background:#1a3050; overflow:hidden; margin-top:6px; }
.fuel-fill  { height:100%; border-radius:4px; transition:width .35s, background .35s; }

.m-card {
    background:#0a1a30; border:1px solid #1a3050;
    border-radius:10px; padding:12px 16px; text-align:center;
}
.m-label { font-size:11px; color:#5a7fa8; text-transform:uppercase; letter-spacing:.06em; }
.m-value { font-size:22px; font-weight:700; color:#e2ecff; line-height:1.2; }
.m-unit  { font-size:12px; color:#5a7fa8; }
.m-badge { display:inline-block; font-size:10px; font-weight:600; border-radius:6px; padding:2px 7px; margin-top:4px; }
.badge-ok   { background:#083d20; color:#34d399; }
.badge-warn { background:#3b2600; color:#fbbf24; }
.badge-bad  { background:#3b0f0f; color:#f87171; }
.badge-blue { background:#082040; color:#60a5fa; }

.chip { display:inline-block; font-size:11px; border-radius:6px; padding:3px 9px; margin:3px 3px 3px 0; }
.chip-teal  { background:#083d30; color:#34d399; border:1px solid #0f6a50; }
.chip-amber { background:#3b2600; color:#fbbf24; border:1px solid #7a5200; }
.chip-red   { background:#3b0f0f; color:#f87171; border:1px solid #7a1a1a; }
.chip-blue  { background:#082040; color:#60a5fa; border:1px solid #1a4a80; }

.log-row { border-bottom:1px solid #112240; padding:7px 0; display:flex; gap:10px; align-items:flex-start; }
.log-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; margin-top:4px; }
.log-time { font-size:10px; color:#3a6080; }
.log-text { font-size:12px; color:#a8c0d8; line-height:1.5; }

.cmp-table { width:100%; border-collapse:collapse; font-size:12px; color:#a8c0d8; }
.cmp-table th { background:#0c1e38; color:#5a7fa8; font-weight:600; text-transform:uppercase; letter-spacing:.05em; padding:8px 12px; border-bottom:1px solid #1a3050; }
.cmp-table td { padding:8px 12px; border-bottom:1px solid #112240; }
.cmp-table tr:hover td { background:#0a1a30; }
.best { color:#34d399; font-weight:600; }

.sec-header { font-size:11px; font-weight:700; color:#3a6080; text-transform:uppercase; letter-spacing:.08em; margin:14px 0 8px; }

.stTabs [data-baseweb="tab-list"] { background:#08152a; border-bottom:1px solid #112240; gap:0; }
.stTabs [data-baseweb="tab"]      { color:#5a7fa8; padding:8px 20px; border-radius:0; }
.stTabs [aria-selected="true"]    { color:#1D9E75 !important; border-bottom:2px solid #1D9E75; }
.stTabs [data-baseweb="tab-panel"]{ background:#060f1e; padding:14px 0; }
</style>
""", unsafe_allow_html=True)


# ── constants ────────────────────────────────────────────────
PORT_DATA = {
    "Mumbai, India":          [18.93, 72.83],
    "Chennai, India":         [13.08, 80.28],
    "Karachi, Pakistan":      [24.86, 67.01],
    "Colombo, Sri Lanka":     [6.92,  79.86],
    "Singapore Port":         [1.26,  103.83],
    "Aden, Yemen":            [12.78, 45.01],
    "Mauritius (Port Louis)": [-20.1, 57.5 ],
    "Mombasa, Kenya":         [-4.05, 39.67],
    "Djibouti":               [11.59, 43.14],
}

SHIP_PROFILES = {
    "Container Ship": {"speed":{"safety":13,"fuel":10,"speed":20},"fuel_factor":{"safety":1.0,"fuel":0.72,"speed":1.5}},
    "Tanker":         {"speed":{"safety":11,"fuel":9, "speed":15},"fuel_factor":{"safety":1.1,"fuel":0.80,"speed":1.6}},
    "Bulk Carrier":   {"speed":{"safety":12,"fuel":10,"speed":16},"fuel_factor":{"safety":1.0,"fuel":0.75,"speed":1.4}},
    "Passenger Ship": {"speed":{"safety":18,"fuel":14,"speed":22},"fuel_factor":{"safety":0.9,"fuel":0.85,"speed":1.3}},
    "Naval Vessel":   {"speed":{"safety":22,"fuel":18,"speed":30},"fuel_factor":{"safety":0.8,"fuel":0.80,"speed":1.2}},
}

MODE_META = {
    "safety": {"label":"Safety First",  "icon":"🛡️","sub":"Avoid storms & piracy","color":"#1D9E75"},
    "fuel":   {"label":"Fuel Efficient","icon":"⛽","sub":"Use ocean currents",    "color":"#f59e0b"},
    "speed":  {"label":"Max Speed",     "icon":"⚡","sub":"Shortest path",         "color":"#3b82f6"},
}

# ── session state ────────────────────────────────────────────
for k, v in {
    "route":None,"active":False,"nodes":None,"tree":None,"graph":None,
    "weather_loaded":False,"replan_log":[],"stats":{},"current_mode":"safety",
    "compare_results":None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── helpers ──────────────────────────────────────────────────
def douglas_peucker(points, epsilon=0.3):
    if len(points) < 3:
        return points
    dmax, idx = 0.0, 0
    start, end = np.array(points[0]), np.array(points[-1])
    line = end - start
    norm = np.linalg.norm(line)
    for i in range(1, len(points)-1):
        d = (np.linalg.norm(np.cross(line, start - np.array(points[i]))) / norm
             if norm > 0 else np.linalg.norm(np.array(points[i]) - start))
        if d > dmax:
            dmax, idx = d, i
    if dmax > epsilon:
        return douglas_peucker(points[:idx+1], epsilon)[:-1] + douglas_peucker(points[idx:], epsilon)
    return [points[0], points[-1]]


def fuel_bar_html(pct):
    color  = "#34d399" if pct >= 50 else "#fbbf24" if pct >= 25 else "#f87171"
    status = "Normal" if pct >= 50 else "Low — conservative routing" if pct >= 25 else "Critical — max efficiency"
    bcls   = "badge-ok" if pct >= 50 else "badge-warn" if pct >= 25 else "badge-bad"
    return f"""<div class="fuel-wrap">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:13px;font-weight:700;color:#e2ecff">{pct}%</span>
    <span class="m-badge {bcls}">{status.split(' — ')[0]}</span>
  </div>
  <div class="fuel-track"><div class="fuel-fill" style="width:{pct}%;background:{color}"></div></div>
  <div style="font-size:10px;color:#3a6080;margin-top:4px">{status}</div>
</div>"""


def metric_card(label, value, unit="", badge="", badge_cls="badge-ok"):
    b = f'<div class="m-badge {badge_cls}">{badge}</div>' if badge else ""
    return f"""<div class="m-card">
  <div class="m-label">{label}</div>
  <div class="m-value">{value}<span class="m-unit"> {unit}</span></div>
  {b}
</div>"""


def build_map(route_coords, start_p, end_p, mode,
              obstacle_active=False, obs_lat=0, obs_lon=0, obs_radius=200):
    m = folium.Map(location=[3, 68], zoom_start=4, tiles="CartoDB dark_matter")
    col = MODE_META[mode]["color"]
    smooth = douglas_peucker(route_coords, 0.25)
    folium.PolyLine(smooth, color=col, weight=4, opacity=0.92,
                    tooltip=f"{mode.upper()} route").add_to(m)
    for coord in route_coords[::6][1:-1]:
        folium.CircleMarker(coord, radius=3, color=col, fill=True, fill_opacity=0.8).add_to(m)
    folium.Marker(PORT_DATA[start_p], popup=f"ORIGIN: {start_p}",
                  icon=folium.Icon(color="green", icon="anchor", prefix="fa")).add_to(m)
    folium.Marker(PORT_DATA[end_p], popup=f"DESTINATION: {end_p}",
                  icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
    for z in PROTECTED_ZONES:
        folium.Circle([z["lat"],z["lon"]], radius=z["radius_nm"]*1852,
                      color="#1D9E75", fill=True, fill_opacity=0.1,
                      tooltip=f"Marine Reserve: {z['name']}").add_to(m)
    for z in PIRACY_ZONES:
        folium.Circle([z["lat"],z["lon"]], radius=z["radius_nm"]*1852,
                      color="#ef4444", fill=True, fill_opacity=0.1,
                      tooltip="High Piracy Risk Zone").add_to(m)
    if obstacle_active:
        folium.Circle([obs_lat,obs_lon], radius=obs_radius*1852,
                      color="#f59e0b", fill=True, fill_opacity=0.28,
                      tooltip=f"Storm — {obs_radius} NM").add_to(m)
        folium.Circle([obs_lat,obs_lon], radius=obs_radius*1852*1.12,
                      color="#f59e0b", fill=False, weight=2,
                      dash_array="8", tooltip="Avoidance boundary").add_to(m)
    wx_fg = folium.FeatureGroup(name="Weather overlay", show=False)
    for slat in np.arange(-25, 22, 7):
        for slon in np.arange(35, 108, 7):
            try:
                from global_land_mask import globe
                if globe.is_land(slat, slon): continue
            except Exception:
                pass
            wp = get_live_weather_penalty(slat, slon)
            if wp > 2.5:
                c = "#ef4444" if wp>10 else "#f59e0b" if wp>5 else "#facc15"
                folium.CircleMarker([slat,slon], radius=min(14,max(4,wp*1.3)),
                                    color=c, fill=True, fill_opacity=0.28,
                                    tooltip=f"{get_weather_description(slat,slon)} ({wp:.1f}x)").add_to(wx_fg)
    wx_fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m


# ── one-time init ────────────────────────────────────────────
if st.session_state.nodes is None:
    with st.spinner("Building Indian Ocean grid…"):
        n, t, g = build_grid(step=2.5)
        st.session_state.nodes = n
        st.session_state.tree  = t
        st.session_state.graph = g

if not st.session_state.weather_loaded:
    with st.spinner("Computing weather simulation…"):
        preload_weather_grid()
        st.session_state.weather_loaded = True

nodes = st.session_state.nodes
tree  = st.session_state.tree
graph = st.session_state.graph


# ════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🚢 Route Planner")
    st.markdown("---")

    # mode buttons
    st.markdown('<div class="sec-header">Routing objective</div>', unsafe_allow_html=True)
    mode = st.session_state.current_mode
    for m_key, meta in MODE_META.items():
        btn_label = f"{meta['icon']}  {meta['label']}  —  {meta['sub']}"
        if st.button(btn_label, key=f"mbtn_{m_key}", use_container_width=True):
            st.session_state.current_mode = m_key
            st.rerun()
    mode = st.session_state.current_mode

    # current mode badge
    meta_cur = MODE_META[mode]
    st.markdown(
        f'<div style="font-size:11px;color:{meta_cur["color"]};margin:4px 0 8px;'
        f'padding:4px 10px;border:1px solid {meta_cur["color"]}33;border-radius:6px;">'
        f'{meta_cur["icon"]} <b>{meta_cur["label"]}</b> selected</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    st.markdown('<div class="sec-header">Route</div>', unsafe_allow_html=True)
    ports   = list(PORT_DATA.keys())
    start_p = st.selectbox("🟢 Origin",      ports, index=0)
    end_p   = st.selectbox("🔴 Destination", ports, index=6)
    if start_p == end_p:
        st.error("Origin and destination must differ.")

    st.markdown("---")

    st.markdown('<div class="sec-header">Vessel type</div>', unsafe_allow_html=True)
    ship_type = st.selectbox("Ship type", list(SHIP_PROFILES.keys()), index=0)

    st.markdown("---")

    st.markdown('<div class="sec-header">Fuel level</div>', unsafe_allow_html=True)
    fuel_pct = st.slider("", 10, 100, 80, 5, label_visibility="collapsed")
    st.markdown(fuel_bar_html(fuel_pct), unsafe_allow_html=True)

    st.markdown("---")

    st.markdown('<div class="sec-header">Real-time events</div>', unsafe_allow_html=True)
    obstacle_active = st.toggle("Simulate storm / obstacle", value=False)
    obs_lat, obs_lon, obs_radius = 5.0, 75.0, 200
    if obstacle_active:
        obs_lat    = st.slider("Latitude",  -25.0, 20.0,  5.0, 0.5)
        obs_lon    = st.slider("Longitude",  35.0, 105.0, 75.0, 0.5)
        obs_radius = st.slider("Radius (NM)", 50, 600, 200, 50)
        st.warning(f"Storm at {obs_lat}°N, {obs_lon}°E — {obs_radius} NM")

    st.markdown("---")

    run     = st.button("🗺️  Calculate Optimal Route", type="primary",
                        disabled=(start_p==end_p), use_container_width=True)
    compare = st.button("📊  Compare All 3 Modes",    use_container_width=True)
    if st.button("🗑️  Clear",                         use_container_width=True):
        for k in ["route","stats","compare_results"]:
            st.session_state[k] = None
        st.session_state.active      = False
        st.session_state.replan_log  = []
        st.rerun()


# ════════════════════════════════════════════════════════════
# ROUTE CALCULATION HELPER
# ════════════════════════════════════════════════════════════
def run_route(m_mode, m_fuel, m_blocked):
    s_idx = tree.query(PORT_DATA[start_p])[1]
    e_idx = tree.query(PORT_DATA[end_p])[1]
    route, _ = dynamic_astar(s_idx, e_idx, nodes, graph,
                              mode=m_mode, fuel_level_pct=m_fuel,
                              blocked_nodes=m_blocked)
    return route


def apply_ship_profile(stats_dict, m_mode, ship):
    sp = SHIP_PROFILES[ship]
    d  = stats_dict["distance_nm"]
    stats_dict["speed_knots"]  = sp["speed"][m_mode]
    stats_dict["est_hours"]    = round(d / sp["speed"][m_mode], 1)
    stats_dict["est_days"]     = round(d / sp["speed"][m_mode] / 24, 1)
    stats_dict["est_fuel_tons"]= round((d/100) * sp["fuel_factor"][m_mode], 1)
    return stats_dict


if run and start_p != end_p:
    blocked = set()
    if obstacle_active:
        for i, nd in enumerate(nodes):
            if haversine_nm(nd, [obs_lat, obs_lon]) < obs_radius:
                blocked.add(i)

    with st.status("Calculating optimal route…", expanded=True) as status:
        st.write(f"Mode **{mode.upper()}** · Fuel **{fuel_pct}%** · "
                 f"Ship **{ship_type}** · Blocked **{len(blocked)}** nodes")
        route = run_route(mode, fuel_pct, blocked)
        if route:
            st.session_state.route  = [nodes[i].tolist() for i in route]
            raw_stats = analyze_route(route, nodes, mode)
            st.session_state.stats  = apply_ship_profile(raw_stats, mode, ship_type)
            st.session_state.active = True
            if obstacle_active:
                ts = datetime.now().strftime("%H:%M:%S")
                st.session_state.replan_log.append({
                    "ts": ts, "level": "warn",
                    "msg": f"Storm at ({obs_lat}°N, {obs_lon}°E) radius {obs_radius} NM "
                           f"— {len(blocked)} nodes blocked, route replanned",
                })
            status.update(label="✅ Route calculated!", state="complete")
        else:
            status.update(label="❌ No route found — try reducing obstacle size.", state="error")


if compare and start_p != end_p:
    blocked = set()
    if obstacle_active:
        for i, nd in enumerate(nodes):
            if haversine_nm(nd, [obs_lat, obs_lon]) < obs_radius:
                blocked.add(i)
    results = {}
    with st.status("Comparing all 3 modes…", expanded=True) as status:
        for mk in ["safety", "fuel", "speed"]:
            st.write(f"Computing **{mk}** mode…")
            r = run_route(mk, fuel_pct, blocked)
            if r:
                s = analyze_route(r, nodes, mk)
                results[mk] = apply_ship_profile(s, mk, ship_type)
        st.session_state.compare_results = results
        status.update(label="✅ Comparison ready!", state="complete")


# ════════════════════════════════════════════════════════════
# MAIN DISPLAY
# ════════════════════════════════════════════════════════════
meta_cur = MODE_META[mode]
st.markdown(
    f"<h1 style='margin-bottom:2px'>🚢 Dynamic Maritime Routing DSS</h1>"
    f"<p style='color:#3a6080;font-size:13px;margin-top:0'>"
    f"Indian Ocean · Multi-Objective A* · {ship_type} · "
    f"<span style='color:{meta_cur['color']}'>{meta_cur['icon']} {meta_cur['label']} mode</span></p>",
    unsafe_allow_html=True,
)

# ── empty / welcome state ────────────────────────────────────
if not st.session_state.active and st.session_state.compare_results is None:
    st.markdown("""
<div style="background:#08152a;border:1px solid #112240;border-radius:12px;
            padding:24px 28px;margin-top:12px">
<h3 style="color:#e2ecff;margin:0 0 12px">Getting started</h3>
<ol style="color:#7a9cc0;font-size:13px;line-height:2.1">
  <li>Pick a <b style="color:#c8d8f0">routing objective</b> in the sidebar</li>
  <li>Select <b style="color:#c8d8f0">origin and destination</b> ports</li>
  <li>Choose your <b style="color:#c8d8f0">vessel type</b> and fuel level</li>
  <li>Optionally <b style="color:#c8d8f0">simulate a storm</b> for real-time replanning</li>
  <li>Click <b style="color:#1D9E75">Calculate Optimal Route</b> or <b style="color:#3b82f6">Compare All 3 Modes</b></li>
</ol>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, (mk, meta) in zip([c1,c2,c3], MODE_META.items()):
        col.markdown(f"""<div class="m-card" style="margin-top:12px">
  <div style="font-size:28px">{meta['icon']}</div>
  <div class="m-label" style="margin-top:6px">{meta['label']}</div>
  <div style="font-size:11px;color:#3a6080;margin-top:4px">{meta['sub']}</div>
</div>""", unsafe_allow_html=True)


# ── active route ─────────────────────────────────────────────
if st.session_state.active and st.session_state.route:
    stats = st.session_state.stats

    # metrics
    cols = st.columns(6)
    wx_val = stats.get("avg_weather_index", 1.0)
    card_data = [
        ("Distance",     f"{stats.get('distance_nm',0):.0f}",  "NM",  "Calculated",         "badge-ok"),
        ("Duration",     f"{stats.get('est_hours',0):.0f}",    "hrs", f"{stats.get('est_days',0):.1f} days","badge-ok"),
        ("Speed",        str(stats.get("speed_knots",0)),       "kts", ship_type.split()[0], "badge-blue"),
        ("Fuel est.",    f"{stats.get('est_fuel_tons',0):.0f}", "t",
         "Normal" if fuel_pct>40 else "Low fuel mode",
         "badge-ok" if fuel_pct>40 else "badge-warn"),
        ("Avg weather",  f"{wx_val:.1f}",                       "",
         "Clear" if wx_val<3 else "Moderate" if wx_val<6 else "Rough",
         "badge-ok" if wx_val<3 else "badge-warn" if wx_val<6 else "badge-bad"),
        ("Waypoints",    str(stats.get("waypoints",0)),          "", "Smoothed", "badge-ok"),
    ]
    for col, (lbl, val, unit, badge, bcls) in zip(cols, card_data):
        col.markdown(metric_card(lbl, val, unit, badge, bcls), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # map
    fmap = build_map(st.session_state.route, start_p, end_p, mode,
                     obstacle_active, obs_lat, obs_lon, obs_radius)
    st_folium(fmap, width=None, height=500, returned_objects=[])

    # tabs
    tab_analysis, tab_constraints, tab_log, tab_export = st.tabs(
        ["📊 Route Analysis", "⚙️ Active Constraints", "📋 Event Log", "💾 Export"])

    # ── analysis ─────────────────────────────────────────────
    with tab_analysis:
        ca, cb = st.columns(2)
        with ca:
            st.markdown('<div class="sec-header">Route summary</div>', unsafe_allow_html=True)
            max_wi = stats.get("max_weather_index", 0)
            if max_wi > 10:
                st.error(f"High weather risk — max index {max_wi:.1f}")
            elif max_wi > 5:
                st.warning(f"Moderate weather — max index {max_wi:.1f}")
            else:
                st.success(f"Clear route — max weather index {max_wi:.1f}")

            df_s = pd.DataFrame({
                "Parameter": ["Distance","Duration","Speed","Fuel","Waypoints",
                               "Avg weather","Max weather","Mode"],
                "Value":     [f"{stats.get('distance_nm',0):.0f} NM",
                               f"{stats.get('est_hours',0):.0f} hrs ({stats.get('est_days',0):.1f} d)",
                               f"{stats.get('speed_knots',0)} kts",
                               f"{stats.get('est_fuel_tons',0):.1f} t",
                               str(stats.get("waypoints",0)),
                               f"{stats.get('avg_weather_index',0):.2f}",
                               f"{stats.get('max_weather_index',0):.2f}",
                               mode.upper()],
            })
            st.dataframe(df_s, hide_index=True, use_container_width=True)

        with cb:
            st.markdown('<div class="sec-header">A* cost weights</div>', unsafe_allow_html=True)
            wx_w  = {"safety":"^1.3 (amplified)","fuel":"×0.8","speed":"×0.4 (reduced)"}[mode]
            pi_w  = "15×" if mode=="safety" else "8×"
            cur   = "0.85–0.92× bonus" if mode=="fuel" else "Not applied"
            fc    = "Active — 2× westward" if (mode=="fuel" and fuel_pct<40) else "Inactive"
            st.markdown(f"""
| Component | Weight (`{mode}`) |
|---|---|
| Weather penalty | `{wx_w}` |
| Piracy zones | `{pi_w}` |
| Marine reserves | `up to 5×` |
| Ocean currents | `{cur}` |
| Fuel-critical | `{fc}` |
""")

    # ── constraints ──────────────────────────────────────────
    with tab_constraints:
        st.markdown('<div class="sec-header">Active cost chips</div>', unsafe_allow_html=True)
        chips = {
            "safety": [("chip-red","Weather ^1.3"),("chip-red","Piracy 15×"),
                       ("chip-teal","Marine 5×"),("chip-blue","Safety boost")],
            "fuel":   [("chip-amber","Weather ×0.8"),("chip-teal","Current 0.88×"),
                       ("chip-teal","Marine 5×"),("chip-blue","Piracy 8×")],
            "speed":  [("chip-blue","Weather ×0.4"),("chip-blue","Direct path"),
                       ("chip-teal","Marine 5×"),("chip-amber","Piracy 8×")],
        }[mode]
        if fuel_pct < 40:
            chips.append(("chip-red","Fuel critical 2×"))
        if obstacle_active:
            chips.append(("chip-amber",f"Storm {obs_radius}NM"))
        st.markdown("".join(f'<span class="chip {c}">{t}</span>' for c,t in chips),
                    unsafe_allow_html=True)

        st.markdown('<div class="sec-header" style="margin-top:18px">Zone inventory</div>',
                    unsafe_allow_html=True)
        rows = ([{"Zone":z["name"],"Type":"Marine Reserve",
                  "Center":f"{z['lat']}°, {z['lon']}°","Radius":f"{z['radius_nm']} NM",
                  "Penalty":"up to 5×"} for z in PROTECTED_ZONES] +
                [{"Zone":"Piracy zone","Type":"High-risk",
                  "Center":f"{z['lat']}°, {z['lon']}°","Radius":f"{z['radius_nm']} NM",
                  "Penalty":"15×" if mode=="safety" else "8×"} for z in PIRACY_ZONES])
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # ── log ───────────────────────────────────────────────────
    with tab_log:
        if not st.session_state.replan_log:
            st.info("No replanning events. Activate a storm to trigger real-time rerouting.")
        else:
            items = []
            for ev in reversed(st.session_state.replan_log):
                dot = "#f59e0b" if ev["level"]=="warn" else "#34d399"
                items.append(f'<div class="log-row">'
                              f'<div class="log-dot" style="background:{dot}"></div>'
                              f'<div><div class="log-time">{ev["ts"]}</div>'
                              f'<div class="log-text">{ev["msg"]}</div></div></div>')
            st.markdown("".join(items), unsafe_allow_html=True)

    # ── export ────────────────────────────────────────────────
    with tab_export:
        st.markdown('<div class="sec-header">Waypoints CSV</div>', unsafe_allow_html=True)
        smooth_coords = douglas_peucker(st.session_state.route, 0.25)
        df_wp = pd.DataFrame(smooth_coords, columns=["latitude","longitude"])
        df_wp.insert(0,"waypoint", range(1, len(df_wp)+1))
        df_wp["lat_fmt"] = df_wp["latitude"].map( lambda x: f"{'N' if x>=0 else 'S'}{abs(x):.3f}°")
        df_wp["lon_fmt"] = df_wp["longitude"].map(lambda x: f"{'E' if x>=0 else 'W'}{abs(x):.3f}°")
        st.dataframe(df_wp, hide_index=True, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️  Download waypoints CSV",
                data=df_wp.to_csv(index=False).encode(),
                file_name=f"route_{start_p.split(',')[0]}_{end_p.split(',')[0]}_{mode}.csv",
                mime="text/csv", use_container_width=True,
            )
        with c2:
            summary = (
                f"Route: {start_p} → {end_p}\n"
                f"Mode: {mode.upper()} | Ship: {ship_type}\n"
                f"Distance: {stats.get('distance_nm',0):.0f} NM\n"
                f"Duration: {stats.get('est_hours',0):.0f} hrs ({stats.get('est_days',0):.1f} days)\n"
                f"Speed: {stats.get('speed_knots',0)} kts | Fuel: {stats.get('est_fuel_tons',0):.1f} t\n"
                f"Avg weather index: {stats.get('avg_weather_index',0):.2f}\n"
                f"Waypoints: {len(smooth_coords)} (smoothed from {len(st.session_state.route)})\n"
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            st.download_button(
                "⬇️  Download voyage summary TXT",
                data=summary.encode(),
                file_name=f"voyage_{mode}.txt",
                mime="text/plain", use_container_width=True,
            )


# ── comparison table ─────────────────────────────────────────
if st.session_state.compare_results:
    st.markdown("---")
    st.markdown(
        "<h3 style='color:#e2ecff;margin-bottom:10px'>📊 Mode Comparison</h3>",
        unsafe_allow_html=True)
    res = st.session_state.compare_results
    best_dist = min(res, key=lambda k: res[k]["distance_nm"])
    best_time = min(res, key=lambda k: res[k]["est_hours"])
    best_fuel = min(res, key=lambda k: res[k]["est_fuel_tons"])
    best_wx   = min(res, key=lambda k: res[k]["avg_weather_index"])

    rows_html = []
    for mk, meta in MODE_META.items():
        if mk not in res: continue
        s = res[mk]
        def cell(val, best_key, fmt):
            cls = ' class="best"' if mk==best_key else ""
            return f"<td{cls}>{fmt(val)}</td>"
        rows_html.append(
            f"<tr>"
            f'<td><b style="color:{meta["color"]}">{meta["icon"]} {meta["label"]}</b></td>'
            + cell(s["distance_nm"],   best_dist, lambda v: f"{v:.0f} NM")
            + cell(s["est_hours"],     best_time, lambda v: f"{v:.0f} hrs / {s['est_days']:.1f}d")
            + cell(s["speed_knots"],   best_time, lambda v: f"{v} kts")
            + cell(s["est_fuel_tons"], best_fuel, lambda v: f"{v:.1f} t")
            + cell(s["avg_weather_index"], best_wx, lambda v: f"{v:.2f}")
            + "</tr>"
        )

    st.markdown(f"""
<table class="cmp-table">
<thead><tr>
  <th>Mode</th><th>Distance</th><th>Duration</th>
  <th>Speed</th><th>Fuel est.</th><th>Avg weather</th>
</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table>
<p style="font-size:11px;color:#3a6080;margin-top:6px">
  <span style="color:#34d399;font-weight:700">Green</span> = best in that column
</p>""", unsafe_allow_html=True)
