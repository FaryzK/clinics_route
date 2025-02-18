# clinics_route

The current algorithm works like this:
1. Start from the given postal code
2. Find the nearest unvisited postal code
3. Move to that postal code and repeat until group size is reached
4. Start a new group, going back to the original starting point
5. Repeat until all postal codes are assigned