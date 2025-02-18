from flask import Flask, render_template, request, jsonify
from postal_route_optimizer import PostalRouteOptimizer
import tempfile
import os

app = Flask(__name__)

# Global storage to maintain state between requests
# Stores the current optimizer instance and route data
current_session = {
    'optimizer': None,
    'routes': None,
    'start_postal': None
}

# Main route - serves the web interface
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

# API endpoint for optimizing routes
@app.route('/optimize', methods=['POST'])
def optimize():
    try:
        # Get and clean input data from the POST request
        data = request.json
        postal_codes = data['postal_codes'].split('\n')
        postal_codes = [code.strip() for code in postal_codes if code.strip()]
        postal_codes = list(dict.fromkeys(postal_codes))  # Remove duplicates
        
        group_size = int(data['group_size'])
        start_postal = data['start_postal'].strip()

        # Create optimizer and generate routes
        optimizer = PostalRouteOptimizer(postal_codes, group_size=group_size)
        routes = optimizer.optimize_route(start_postal)

        # Store in session for later use when switching between routes
        current_session['optimizer'] = optimizer
        current_session['routes'] = routes
        current_session['start_postal'] = start_postal

        # Generate map for the first route
        if routes:
            route_map = optimizer.create_route_map(routes[0])
            if route_map:
                # Save map as temporary HTML file
                _, map_path = tempfile.mkstemp(suffix='.html', dir='static')
                map_filename = os.path.basename(map_path)
                route_map.save(f'static/{map_filename}')
            else:
                map_filename = None
        else:
            map_filename = None

        # Return JSON response with all route data
        return jsonify({
            'success': True,
            'routes': routes,
            'total_codes': len(postal_codes),
            'total_days': len(routes),
            'map_filename': map_filename
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# API endpoint for getting maps of specific routes
@app.route('/get_route_map', methods=['POST'])
def get_route_map():
    try:
        data = request.json
        route_index = int(data['route_index'])
        
        # Validate that we have route data available
        if (current_session['optimizer'] is None or 
            current_session['routes'] is None or 
            route_index >= len(current_session['routes'])):
            raise ValueError("No valid route data available")

        # Generate new map for selected route
        route_map = current_session['optimizer'].create_route_map(
            current_session['routes'][route_index]
        )
        
        if route_map:
            # Save new map as temporary HTML file
            _, map_path = tempfile.mkstemp(suffix='.html', dir='static')
            map_filename = os.path.basename(map_path)
            route_map.save(f'static/{map_filename}')
            return jsonify({
                'success': True,
                'map_filename': map_filename
            })
        else:
            return jsonify({
                'success': False,
                'error': "Failed to create route map"
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Add this route to app.py
@app.route('/export_csv', methods=['POST'])
def export_csv():
    try:
        data = request.json
        routes = data['routes']
        
        # Create CSV content with comma-separated postal codes
        csv_content = "Route Number,Postal Codes\n"
        for i, route in enumerate(routes, 1):
            csv_content += f"Route {i},{','.join(route)}\n"  # Changed from ' -> ' to ','
            
        return jsonify({
            'success': True,
            'csv_content': csv_content,
            'filename': 'postal_routes.csv'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    app.run(debug=True) 