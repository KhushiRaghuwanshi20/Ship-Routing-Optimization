import numpy as np
from scipy.spatial import KDTree

# 1. We take your valid water points (lat, lon)
# For now, let's regenerate them quickly in this script
from global_land_mask import globe

nodes = []
for lat in np.arange(-30, 25, 2.5):
    for lon in np.arange(30, 110, 2.5):
        if not globe.is_land(lat, lon):
            nodes.append([lat, lon])

nodes = np.array(nodes)

# 2. Build a 'Search Tree' to find neighbors very fast
# tree = KDTree(nodes)

# 3. Create the Network (Connections)
# We say dots within 3.6 degrees are neighbors (covers diagonals)
graph = {}
for i, point in enumerate(nodes):
    # Find indices of all points within 3.6 degrees
    neighbor_indices = tree.query_ball_point(point, r=3.6)
    
    # Remove the point itself from its neighbors
    neighbor_indices.remove(i)
    
    # Store the connections: {NodeIndex: [Neighbor1, Neighbor2, ...]}
    graph[i] = neighbor_indices

print(f"Network built successfully!")
print(f"Total Nodes: {len(nodes)}")
print(f"Example: Node 0 is connected to {len(graph[0])} other dots.")