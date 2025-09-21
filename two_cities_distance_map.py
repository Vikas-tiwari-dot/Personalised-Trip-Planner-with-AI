import folium
import requests
import json
import os
import webbrowser

# IMPORTANT: You'll need to use a routing API. For this example, we'll use a public
# one that may have usage limits. For production, you would need an API key.
# A good free option is the OpenRouteService API. You'll need an API key from them.
# The code below is a placeholder to demonstrate the concept.

def get_coordinates(city_name):
    """
    Uses a geocoding service to get the latitude and longitude of a city.
    """
    # Placeholder for a geocoding API call
    # In a real app, you would use an API like OpenStreetMap's Nominatim
    # or Google Maps Geocoding API.
    url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json"
    headers = {'User-Agent': 'TravelRoutePlanner'}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching coordinates for {city_name}: {e}")
    return None, None

def get_route(start_coords, end_coords):
    """
    Uses a routing service to get the route and distance between two points.
    """
    # Placeholder for a routing API call
    # For a real application, you would need a service like OpenRouteService
    # or a similar free or paid service.
    # OpenRouteService API example (requires an API key):
    # url = "https://api.openrouteservice.org/v2/directions/driving-car"
    # headers = {
    #     'Accept': 'application/json, application/geo+json, application/gpx+xml, application/x-protobuf',
    #     'Authorization': 'YOUR_API_KEY'
    # }
    # body = {"coordinates": [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]]}
    # response = requests.post(url, headers=headers, json=body)
    # data = response.json()
    # return data['routes'][0]['geometry']['coordinates'], data['routes'][0]['summary']['distance']

    # Mock data to demonstrate functionality without an API key
    mock_distance = 1500 # Mock distance in km
    mock_route = [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]]
    
    return mock_route, mock_distance

def create_map_with_route(start_loc, end_loc, route, distance):
    """
    Generates an HTML map with the route and distance.
    """
    # Create the map
    m = folium.Map(location=start_loc, zoom_start=6)

    # Add start and end markers
    folium.Marker(
        location=start_loc,
        popup=f"Start: {start_loc}",
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)
    
    folium.Marker(
        location=end_loc,
        popup=f"End: {end_loc}",
        icon=folium.Icon(color='red', icon='stop', prefix='fa')
    ).add_to(m)

    # Add the route line
    folium.PolyLine(
        locations=route,
        color='blue',
        weight=5
    ).add_to(m)

    # Add a popup with the distance
    folium.Popup(f"Distance: {distance:.2f} km", parse_html=True).add_to(m)
    
    # Save the map to an HTML file
    filename = "route_map.html"
    m.save(filename)
    
    return filename

if __name__ == "__main__":
    start_city = input("Enter start location: ")
    end_city = input("Enter end location: ")

    start_coords = get_coordinates(start_city)
    end_coords = get_coordinates(end_city)

    if start_coords and end_coords:
        route, distance = get_route(start_coords, end_coords)
        if route and distance is not None:
            # Swap lat/lon for folium
            folium_route = [[r[1], r[0]] for r in route]
            
            filename = create_map_with_route(start_coords, end_coords, folium_route, distance)
            print(f"Map saved to {filename}")
            webbrowser.open(f'file://{os.path.abspath(filename)}')
        else:
            print("Failed to get route data. Check API key or service status.")
    else:
        print("Failed to get coordinates for one or both cities. Please check the spelling.")