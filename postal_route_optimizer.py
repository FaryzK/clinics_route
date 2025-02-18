import numpy as np
from math import ceil

class PostalRouteOptimizer:
    def __init__(self, postal_codes, group_size=5):
        self.postal_codes = postal_codes
        self.group_size = group_size
        self.num_groups = ceil(len(postal_codes) / group_size)
        
    def calculate_distance(self, code1, code2):
        """
        Calculate distance between Singapore postal codes.
        First two digits represent the sector code, which is geographically meaningful
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

    def optimize_route(self, start_postal):
        """
        Optimize routes starting from given postal code
        Returns list of groups, each containing ordered postal codes for that day
        """
        # Create a copy of postal codes to work with
        remaining = self.postal_codes.copy()
        if start_postal in remaining:
            remaining.remove(start_postal)
            
        # Initialize result structure
        routes = []
        
        # While we have postal codes to process
        while remaining:
            # Start a new group
            current_group = []
            current = start_postal
            
            # Fill the group up to group_size
            while len(current_group) < self.group_size and remaining:
                next_postal = self.find_nearest_unvisited(current, remaining)
                current_group.append(next_postal)
                remaining.remove(next_postal)
                current = next_postal
            
            routes.append(current_group)
            
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
    
    # Get group size
    while True:
        try:
            group_size = int(input("\nEnter group size (e.g., 5): "))
            if group_size > 0:
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
    
    return postal_codes, group_size, start_postal

def main():
    # Get input from user
    postal_codes, group_size, start_postal = get_user_input()
    
    # Validate inputs
    if not postal_codes:
        print("Error: No postal codes provided")
        return
    
    # Create optimizer instance
    optimizer = PostalRouteOptimizer(postal_codes, group_size=group_size)
    
    # Get optimized routes
    routes = optimizer.optimize_route(start_postal)
    
    # Print results
    print("\n=== Optimized Routes ===")
    print(f"Starting from: {start_postal}")
    print(f"Group size: {group_size}")
    print(f"Total postal codes: {len(postal_codes)}")
    print(f"Number of days: {len(routes)}\n")
    
    for i, route in enumerate(routes, 1):
        print(f"\nDay {i}:")
        print("Route:", " -> ".join(route))

if __name__ == "__main__":
    main() 