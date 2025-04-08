import requests
import logging
import json
from urllib.parse import quote

logger = logging.getLogger(__name__)

def get_geojson_from_wfs(comune_ids):
    """
    Retrieve GeoJSON data from a WFS (Web Feature Service) for the given municipality IDs.
    
    Args:
        comune_ids (list): List of municipality IDs to fetch
    
    Returns:
        dict: GeoJSON data with the requested municipalities
    """
    # In a real scenario, we would connect to an actual GeoServer
    # Here we're creating a simple GeoJSON response with a basic polygon
    # for each municipality to demonstrate the concept
    
    logger.info(f"Fetching GeoJSON for comune IDs: {comune_ids}")
    
    try:
        # This would be a real request to a GeoServer in production
        # Example:
        # wfs_url = "https://mio-geoserver.com/geoserver/wfs"
        # params = {
        #     "service": "WFS",
        #     "version": "2.0.0",
        #     "request": "GetFeature",
        #     "typeName": "comuni_italiani",
        #     "outputFormat": "application/json",
        #     "CQL_FILTER": f"codice_istat IN ({','.join(quoted_ids)})"
        # }
        # response = requests.get(wfs_url, params=params)
        # return response.json()
        
        # For demonstration, we'll create a sample GeoJSON response
        # with a simple polygon for each municipality
        
        features = []
        
        # Simple sample polygon coordinates (to be replaced with real data from GeoServer)
        sample_polygons = {
            "01001": [[7.7, 45.3], [7.75, 45.3], [7.75, 45.35], [7.7, 45.35], [7.7, 45.3]],
            "01002": [[7.5, 45.0], [7.55, 45.0], [7.55, 45.05], [7.5, 45.05], [7.5, 45.0]],
            "01003": [[7.3, 45.2], [7.35, 45.2], [7.35, 45.25], [7.3, 45.25], [7.3, 45.2]],
        }
        
        # Default polygon coordinates if no specific ones available
        default_polygon = [[10.0, 45.0], [10.1, 45.0], [10.1, 45.1], [10.0, 45.1], [10.0, 45.0]]
        
        for comune_id in comune_ids:
            # Get specific polygon if available, otherwise use default
            polygon_coords = sample_polygons.get(comune_id, default_polygon)
            
            # Create GeoJSON feature with the polygon
            feature = {
                "type": "Feature",
                "properties": {
                    "id": comune_id,
                    "name": f"Comune {comune_id}"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [polygon_coords]
                }
            }
            
            features.append(feature)
        
        # Create GeoJSON FeatureCollection
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        logger.info(f"Generated sample GeoJSON with {len(features)} features")
        return geojson
        
    except Exception as e:
        logger.error(f"Error fetching GeoJSON data: {str(e)}")
        raise Exception(f"Failed to retrieve GeoJSON data: {str(e)}")

def get_center_coordinates(geojson):
    """
    Calculate the center coordinates for a GeoJSON object.
    
    Args:
        geojson (dict): GeoJSON data
    
    Returns:
        tuple: (latitude, longitude) center coordinates
    """
    if not geojson or 'features' not in geojson or not geojson['features']:
        # Default to center of Italy if no features
        return (41.9, 12.5)
    
    # Extract all coordinates from all features
    all_points = []
    
    for feature in geojson['features']:
        if 'geometry' in feature and feature['geometry']:
            geometry = feature['geometry']
            
            if geometry['type'] == 'Polygon':
                # Extract points from polygon coordinates
                for ring in geometry['coordinates']:
                    for point in ring:
                        all_points.append(point)
            
            elif geometry['type'] == 'MultiPolygon':
                # Extract points from multipolygon coordinates
                for polygon in geometry['coordinates']:
                    for ring in polygon:
                        for point in ring:
                            all_points.append(point)
    
    if not all_points:
        # Default to center of Italy if no points found
        return (41.9, 12.5)
    
    # Calculate the average of all coordinates
    sum_lon = sum(point[0] for point in all_points)
    sum_lat = sum(point[1] for point in all_points)
    count = len(all_points)
    
    return (sum_lat / count, sum_lon / count)
