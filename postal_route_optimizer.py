import numpy as np
from math import ceil
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import openrouteservice as ors
from openrouteservice import convert
import os
from dotenv import load_dotenv
import requests
import time  # Add this import at the top
from sklearn.cluster import KMeans
from collections import defaultdict

# Load environment variables
load_dotenv()

# Main class that handles route optimization and map generation
class PostalRouteOptimizer:
    def __init__(self, postal_codes, num_groups=5):
        # Initialize with list of postal codes and desired number of groups
        self.postal_codes = postal_codes
        self.num_groups = num_groups
        # Calculate group size based on number of postal codes and desired groups
        self.group_size = ceil(len(postal_codes) / num_groups)
        # Initialize geocoding services
        self.geolocator = Nominatim(user_agent="postal_route_optimizer")
        self.ors_client = ors.Client(key=os.getenv('ORS_API_KEY'))
        # Store coordinates to avoid repeated geocoding
        self.coord_cache = {}
        
    def geocode_postal(self, postal_code):
        """
        Converts postal codes to coordinates using:
        1. OneMap API (Singapore's official service)
        2. Fallback to Nominatim if OneMap fails
        """
        # Try OneMap API first (Singapore's official geocoding service)
        try:
            # Use HTTPS URL and verify SSL
            onemap_url = "https://www.onemap.gov.sg/api/common/elastic/search"
            params = {
                'searchVal': postal_code,
                'returnGeom': 'Y',
                'getAddrDetails': 'Y'
            }
            
            response = requests.get(
                onemap_url, 
                params=params,
                verify=True,  # Verify SSL certificate
                timeout=10    # Set timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    result = data['results'][0]
                    lat = float(result['LATITUDE'])
                    lon = float(result['LONGITUDE'])
                    address = result.get('ADDRESS', 'No address found')
                    print(f"Found location for {postal_code}: {address}")
                    return (lat, lon)
                else:
                    print(f"No results found for postal code: {postal_code}")
            else:
                print(f"OneMap API returned status code: {response.status_code}")
            
        except Exception as e:
            print(f"OneMap API failed for {postal_code}: {str(e)}")

        # If OneMap fails, try using a Singapore postal code geocoding service
        try:
            # Format postal code query
            query = f"Singapore {postal_code}"
            location = self.geolocator.geocode(
                query,
                timeout=10,
                country_codes="sg",
                exactly_one=True,
                view_box=(103.6, 1.1, 104.1, 1.5)  # Singapore bounding box
            )
            
            if location:
                print(f"Found location for {postal_code} using fallback: {location.address}")
                return (location.latitude, location.longitude)
            
        except Exception as e:
            print(f"Fallback geocoding failed for {postal_code}: {str(e)}")
        
        print(f"All geocoding attempts failed for {postal_code}")
        return None

    def create_route_map(self, route):
        """Creates an interactive map showing routes"""
        coordinates = []
        print(f"Processing route: {route}")
        
        # Process starting point
        start_coords = self.geocode_postal(self.start_postal)
        if start_coords:
            coordinates.append((start_coords, self.start_postal))
        
        # Process each stop in the route
        for i, postal in enumerate(route, 1):
            coords = self.geocode_postal(postal)
            if coords:
                coordinates.append((coords, postal))

        if len(coordinates) < 2:
            return None

        # Create map centered on first coordinate
        m = folium.Map(location=coordinates[0][0], zoom_start=12)

        # Add markers for each point
        for i, (coords, postal) in enumerate(coordinates):
            label = f"{'Start' if i == 0 else f'Stop {i}'}: {postal}"
            folium.Marker(
                coords,
                popup=label,
                tooltip=label,
                icon=folium.Icon(color='red' if i == 0 else 'blue', icon='info-sign')
            ).add_to(m)

        # Get route directions between consecutive points with rate limiting
        for i in range(len(coordinates) - 1):
            retry_count = 0
            max_retries = 3
            delay_seconds = 2  # Start with 2 second delay

            while retry_count < max_retries:
                try:
                    coords1 = coordinates[i][0]
                    coords2 = coordinates[i + 1][0]
                    
                    # Add delay before each API call
                    time.sleep(delay_seconds)
                    
                    route_coords = self.ors_client.directions(
                        coordinates=[[coords1[1], coords1[0]], [coords2[1], coords2[0]]],
                        profile='driving-car',
                        format='geojson'
                    )
                    
                    if route_coords and 'features' in route_coords and len(route_coords['features']) > 0:
                        # Add route to map
                        folium.GeoJson(
                            route_coords,
                            style_function=lambda x: {
                                'color': 'blue',
                                'weight': 3,
                                'opacity': 0.7
                            }
                        ).add_to(m)
                        break  # Success, exit retry loop
                    
                except Exception as e:
                    print(f"Attempt {retry_count + 1} failed: {str(e)}")
                    retry_count += 1
                    delay_seconds *= 2  # Exponential backoff
                    
                    if retry_count == max_retries:
                        print("Falling back to straight line...")
                        # Fallback to straight line if all retries fail
                        folium.PolyLine(
                            locations=[coords1, coords2],
                            weight=2,
                            color='red',
                            opacity=0.5,
                            dash_array='10'
                        ).add_to(m)

        # Fit map bounds to include all points
        if len(coordinates) > 1:
            bounds = [coords[0] for coords in coordinates]
            m.fit_bounds(bounds)

        return m

    def calculate_distance(self, code1, code2):
        """
        Calculates "distance" between postal codes based on:
        1. Sector code (first 2 digits)
        2. Remaining digits
        Used for initial route optimization
        """
        # Convert to strings and ensure 6 digits
        code1, code2 = str(code1).zfill(6), str(code2).zfill(6)
        
        # Get sector codes (first 2 digits)
        sector1 = code1[:2]
        sector2 = code2[:2]
        
        # Calculate primary distance based on sector difference
        sector_distance = abs(int(sector1) - int(sector2)) * 100
        
        # Add secondary distance based on remaining digits
        remaining_distance = sum(abs(int(a) - int(b)) for a, b in zip(code1[2:], code2[2:]))
        
        return sector_distance + remaining_distance

    def find_nearest_unvisited(self, current, unvisited):
        """Find the nearest unvisited postal code to the current one"""
        distances = [(code, self.calculate_distance(current, code)) for code in unvisited]
        return min(distances, key=lambda x: x[1])[0]

    def get_coordinates(self, postal_codes):
        """Get coordinates for all postal codes"""
        coordinates = []
        # Keep track of indices to maintain duplicates
        postal_indices = []
        
        for i, code in enumerate(postal_codes):
            if code not in self.coord_cache:
                coords = self.geocode_postal(code)
                if coords:
                    self.coord_cache[code] = coords
            if code in self.coord_cache:
                coordinates.append(self.coord_cache[code])
                postal_indices.append(i)  # Store original index
            
        return np.array(coordinates), postal_indices

    def cluster_postal_codes(self):
        """Cluster postal codes using K-means"""
        # Get coordinates for clustering
        coords, postal_indices = self.get_coordinates(self.postal_codes)
        
        if len(coords) < self.num_groups:
            return {0: self.postal_codes}  # Return single cluster if too few points
            
        # Perform K-means clustering
        kmeans = KMeans(n_clusters=self.num_groups, random_state=42)
        cluster_labels = kmeans.fit_predict(coords)
        
        # Group postal codes by cluster, maintaining duplicates
        clusters = defaultdict(list)
        for idx, label in zip(postal_indices, cluster_labels):
            clusters[label].append(self.postal_codes[idx])
            
        return clusters

    def optimize_cluster_route(self, cluster_codes, start_postal):
        """Optimize route within a cluster using nearest neighbor"""
        if not cluster_codes:
            return []
            
        route = []
        unvisited = set(cluster_codes)
        current = start_postal
        
        while unvisited:
            if current in unvisited:
                unvisited.remove(current)
            route.append(current)
            
            if not unvisited:
                break
                
            # Find nearest unvisited postal code
            current = min(
                unvisited,
                key=lambda x: self.calculate_distance(current, x)
            )
            
        return route

    def optimize_route(self, start_postal):
        """
        Optimize routes using clustering and nearest neighbor:
        1. Cluster postal codes into groups
        2. For each cluster:
           - Find nearest postal code to start_postal
           - Optimize route within cluster
        3. Return optimized routes
        """
        self.start_postal = start_postal
        
        # Get clusters
        clusters = self.cluster_postal_codes()
        routes = []
        
        # Process each cluster
        for cluster_codes in clusters.values():
            # Find nearest code to start_postal in this cluster
            cluster_start = min(
                cluster_codes,
                key=lambda x: self.calculate_distance(start_postal, x)
            )
            
            # Optimize route within cluster
            cluster_route = self.optimize_cluster_route(cluster_codes, cluster_start)
            
            # Split into groups of appropriate size if needed
            for i in range(0, len(cluster_route), self.group_size):
                route_segment = cluster_route[i:i + self.group_size]
                if route_segment:
                    routes.append(route_segment)
        
        return routes

def get_user_input():
    """Get postal codes and parameters from user input"""
    print("\n=== Postal Route Optimizer ===\n")
    
    # Get postal codes from file
    while True:
        file_path = input("Enter the path to your postal codes file (one code per line): ").strip()
        try:
            with open(file_path, 'r') as file:
                postal_codes = [line.strip() for line in file if line.strip()]
            if postal_codes:
                print(f"Successfully loaded {len(postal_codes)} postal codes")
                break
            else:
                print("Error: File is empty")
        except FileNotFoundError:
            print("Error: File not found. Please check the path and try again.")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
    
    # Get number of routes (instead of group size)
    while True:
        try:
            num_routes = int(input("\nEnter number of routes: "))
            if num_routes > 0:
                break
            print("Please enter a positive number")
        except ValueError:
            print("Please enter a valid number")
    
    # Get starting postal code
    while True:
        start_postal = input("\nEnter starting postal code: ").strip()
        if start_postal:
            break
        print("Starting postal code cannot be empty")
    
    return postal_codes, num_routes, start_postal

def main():
    # Get input from user
    postal_codes, num_routes, start_postal = get_user_input()
    
    # Validate inputs
    if not postal_codes:
        print("Error: No postal codes provided")
        return
    
    # Create optimizer instance with number of routes
    optimizer = PostalRouteOptimizer(postal_codes, num_groups=num_routes)
    
    # Get optimized routes
    routes = optimizer.optimize_route(start_postal)
    
    # Print results
    print("\n=== Optimized Routes ===")
    print(f"Starting from: {start_postal}")
    print(f"Number of routes: {num_routes}")
    print(f"Total postal codes: {len(postal_codes)}")
    print(f"Actual routes created: {len(routes)}\n")
    
    for i, route in enumerate(routes, 1):
        print(f"\nRoute {i}:")
        print("Route:", " -> ".join(route))

if __name__ == "__main__":
    main() 