import numpy as np
from global_land_mask import globe

# 1. Define the boundaries for the Indian Ocean (Min/Max Lat and Lon)
LAT_MIN, LAT_MAX = -30, 25  # From South Africa/Australia up to India
LON_MIN, LON_MAX = 30, 110  # From Africa coast to Indonesia

# 2. Define the Resolution (The "size" of our chessboard squares)
# 2.0 means every 2 degrees we create a navigation point
step = 2.0

# 3. Generate the Grid Points
lat_points = np.arange(LAT_MIN, LAT_MAX, step)
lon_points = np.arange(LON_MIN, LON_MAX, step)

valid_points = []

# 4. Loop through all points and check if they are in the Ocean
for lat in lat_points:
    for lon in lon_points:
        # globe.is_land returns True if the point is on land
        if not globe.is_land(lat, lon):
            valid_points.append([lat, lon])

print(f"Grid Created! Total navigation nodes in water: {len(valid_points)}")

# 5. Let's visualize a few points to confirm
print("Sample water nodes (Lat, Lon):")
print(valid_points[:5])