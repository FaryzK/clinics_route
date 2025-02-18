from flask import Flask, render_template, request, jsonify
from postal_route_optimizer import PostalRouteOptimizer
import tempfile
import os

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/optimize', methods=['POST'])
def optimize():
    try:
        # Get data from request
        data = request.json
        
        # Clean and deduplicate postal codes
        postal_codes = data['postal_codes'].split('\n')
        postal_codes = [code.strip() for code in postal_codes if code.strip()]  # Remove empty lines and whitespace
        postal_codes = list(dict.fromkeys(postal_codes))  # Remove duplicates while preserving order
        
        group_size = int(data['group_size'])
        start_postal = data['start_postal'].strip()

        # Create optimizer and get routes
        optimizer = PostalRouteOptimizer(postal_codes, group_size=group_size)
        routes = optimizer.optimize_route(start_postal)

        # Create map for first route
        if routes:
            route_map = optimizer.create_route_map(routes[0])
            if route_map:
                # Save map to temporary file
                _, map_path = tempfile.mkstemp(suffix='.html', dir='static')
                map_filename = os.path.basename(map_path)
                route_map.save(f'static/{map_filename}')
            else:
                map_filename = None
        else:
            map_filename = None

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

if __name__ == '__main__':
    # Create static folder if it doesn't exist
    os.makedirs('static', exist_ok=True)
    app.run(debug=True) 