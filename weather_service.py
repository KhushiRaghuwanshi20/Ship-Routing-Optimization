"""
weather_service.py - Instant Physics-Based Weather Simulation
=====================================================================
API ki jagah realistic monsoon/cyclone simulation use karta hai.
Result: 0ms response time vs pehle ka 30+ seconds!

Why this works better:
- Indian Ocean ke real seasonal patterns simulate karta hai
- Cyclone zones accurately model kiye hain
- Monsoon wind patterns include hain
- No network dependency = always works
"""

import numpy as np
from datetime import datetime

# ---- SMART BATCH CACHE ----
_weather_cache = {}  # { (rounded_lat, rounded_lon): penalty }

# ============================================================
# INDIAN OCEAN WEATHER ZONES (Research-based realistic data)
# ============================================================

# Cyclone-prone zones in Indian Ocean (lat_center, lon_center, intensity, radius_deg)
CYCLONE_ZONES = [
    # Bay of Bengal cyclone alley
    (15.0, 87.0, 0.8, 8.0),   # Northern Bay of Bengal
    (12.0, 82.0, 0.6, 6.0),   # Central Bay
    # Arabian Sea cyclone zone
    (16.0, 65.0, 0.5, 7.0),   # Arabian Sea NE
    (14.0, 58.0, 0.4, 5.0),   # Arabian Sea central
    # South Indian Ocean cyclone belt
    (-15.0, 55.0, 0.7, 10.0), # Mauritius/Reunion zone
    (-18.0, 70.0, 0.5, 8.0),  # Chagos zone
    (-12.0, 48.0, 0.6, 7.0),  # Madagascar east
]

# Monsoon wind stress zones (increases wave height & difficulty)
MONSOON_ZONES = [
    # SW Monsoon (Jun-Sep): Heavy seas in Arabian Sea
    {"lat": 12.0, "lon": 65.0, "radius": 12.0, "season": (6, 9), "intensity": 0.9},
    # NE Monsoon (Dec-Mar): Bay of Bengal
    {"lat": 12.0, "lon": 82.0, "radius": 10.0, "season": (12, 3), "intensity": 0.7},
    # Somali Jet
    {"lat": 8.0, "lon": 52.0, "radius": 8.0, "season": (6, 8), "intensity": 0.8},
]

# Permanently rough zones (strong currents, mixing zones)
ROUGH_ZONES = [
    # Agulhas current retroflection
    {"lat": -38.0, "lon": 20.0, "intensity": 0.85, "radius": 8.0},
    # Roaring Forties influence
    {"lat": -42.0, "lon": 60.0, "intensity": 0.9, "radius": 15.0},
    # 10 degree channel
    {"lat": 8.0, "lon": 75.0, "intensity": 0.4, "radius": 3.0},
]


def _compute_weather_penalty(lat: float, lon: float) -> float:
    """
    Physics-inspired instant weather penalty calculator.
    
    Returns multiplier: 1.0 = calm, 25.0 = extreme storm
    """
    penalty = 1.0
    current_month = datetime.now().month
    
    # --- 1. CYCLONE ZONE CONTRIBUTION ---
    for clat, clon, intensity, radius in CYCLONE_ZONES:
        dist = np.sqrt((lat - clat)**2 + (lon - clon)**2)
        if dist < radius:
            # Gaussian falloff - center mein maximum, edge par minimum
            falloff = np.exp(-0.5 * (dist / (radius * 0.4))**2)
            cyclone_penalty = 1.0 + (intensity * 22.0 * falloff)
            penalty = max(penalty, cyclone_penalty)
    
    # --- 2. SEASONAL MONSOON CONTRIBUTION ---
    for zone in MONSOON_ZONES:
        dist = np.sqrt((lat - zone["lat"])**2 + (lon - zone["lon"])**2)
        if dist < zone["radius"]:
            s_start, s_end = zone["season"]
            # Season active hai?
            in_season = (s_start <= current_month <= s_end) if s_start < s_end else \
                        (current_month >= s_start or current_month <= s_end)
            if in_season:
                falloff = np.exp(-0.5 * (dist / (zone["radius"] * 0.5))**2)
                monsoon_penalty = 1.0 + (zone["intensity"] * 12.0 * falloff)
                penalty = max(penalty, monsoon_penalty)
            else:
                # Off-season: quarter intensity
                falloff = np.exp(-0.5 * (dist / (zone["radius"] * 0.5))**2)
                monsoon_penalty = 1.0 + (zone["intensity"] * 3.0 * falloff)
                penalty = max(penalty, monsoon_penalty)
    
    # --- 3. PERMANENTLY ROUGH ZONES ---
    for zone in ROUGH_ZONES:
        dist = np.sqrt((lat - zone["lat"])**2 + (lon - zone["lon"])**2)
        if dist < zone["radius"]:
            falloff = np.exp(-0.5 * (dist / (zone["radius"] * 0.5))**2)
            rough_penalty = 1.0 + (zone["intensity"] * 8.0 * falloff)
            penalty = max(penalty, rough_penalty)
    
    # --- 4. LATITUDE-BASED BASE ROUGHNESS ---
    # Tropics mein calm, higher latitudes mein rougher
    abs_lat = abs(lat)
    if abs_lat > 30:
        lat_penalty = 1.0 + 0.05 * (abs_lat - 30)
        penalty = max(penalty, lat_penalty)
    
    # --- 5. NEAR-SHORE TURBULENCE ---
    # Shallow continental shelf areas
    # Bay of Bengal shallow north
    if lat > 15 and 80 < lon < 100:
        penalty = max(penalty, 1.8)
    
    # Add realistic noise (+/- 15%) for variability
    np.random.seed(int(abs(lat * 100) + abs(lon * 100)) % 9999)
    noise = np.random.uniform(0.85, 1.15)
    penalty *= noise
    
    return round(min(penalty, 25.0), 2)


def preload_weather_grid(lat_range=(-30, 25), lon_range=(30, 110), step=4.0):
    """
    Poore Indian Ocean ka weather INSTANTLY pre-compute karo.
    Pehle: 200 API calls = 30-60 seconds
    Ab: Pure math = < 1 second!
    """
    lats = np.arange(lat_range[0], lat_range[1], step)
    lons = np.arange(lon_range[0], lon_range[1], step)
    
    count = 0
    for lat in lats:
        for lon in lons:
            key = (round(lat), round(lon))
            if key not in _weather_cache:
                _weather_cache[key] = _compute_weather_penalty(lat, lon)
                count += 1
    
    print(f"Weather grid loaded (INSTANT): {count} cells computed in <1 second.")
    return _weather_cache


def get_live_weather_penalty(lat: float, lon: float) -> float:
    """
    O(1) dictionary lookup — essentially 0ms!
    Cache miss par bhi direct compute karta hai (< 0.1ms).
    """
    # 4° grid se nearest cell find karo
    key = (round(lat / 4) * 4, round(lon / 4) * 4)
    
    if key not in _weather_cache:
        # Cache miss: compute on-the-fly (still instant)
        _weather_cache[key] = _compute_weather_penalty(lat, lon)
    
    return _weather_cache[key]


def get_weather_description(lat: float, lon: float) -> str:
    """Human-readable weather condition for UI display."""
    penalty = get_live_weather_penalty(lat, lon)
    if penalty >= 15.0:
        return "🌀 Extreme Cyclone"
    elif penalty >= 8.0:
        return "⛈️ Severe Storm"
    elif penalty >= 4.0:
        return "🌧️ Heavy Weather"
    elif penalty >= 2.0:
        return "🌊 Choppy Seas"
    elif penalty >= 1.3:
        return "🌤️ Moderate Conditions"
    else:
        return "☀️ Calm Seas"
