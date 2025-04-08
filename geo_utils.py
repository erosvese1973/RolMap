import requests
import logging
import json
import math
import hashlib
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
    # Here we're creating a more complex GeoJSON response with realistic polygons
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
        
        # Per rendere la visualizzazione più realistica, creiamo poligoni più complessi
        # rappresentando i comuni della provincia di Lecco
        features = []
        
        # Mappa di poligoni campione per alcuni comuni della provincia di Lecco
        # Coordinate approssimative
        sample_polygons = {
            # Lecco (capoluogo)
            "097042": [
                [9.380, 45.830], [9.410, 45.835], [9.430, 45.850], 
                [9.420, 45.870], [9.400, 45.880], [9.380, 45.885],
                [9.360, 45.875], [9.350, 45.860], [9.360, 45.840],
                [9.380, 45.830]
            ],
            # Abbadia Lariana
            "097001": [
                [9.320, 45.890], [9.340, 45.895], [9.350, 45.910], 
                [9.330, 45.920], [9.310, 45.915], [9.300, 45.900],
                [9.320, 45.890]
            ],
            # Galbiate
            "097036": [
                [9.360, 45.800], [9.380, 45.810], [9.390, 45.825], 
                [9.370, 45.835], [9.350, 45.830], [9.340, 45.815],
                [9.360, 45.800]
            ],
            # Malgrate
            "097045": [
                [9.370, 45.840], [9.385, 45.845], [9.390, 45.855],
                [9.380, 45.865], [9.365, 45.860], [9.360, 45.850],
                [9.370, 45.840]
            ],
            # Valmadrera
            "097077": [
                [9.340, 45.830], [9.360, 45.840], [9.365, 45.855],
                [9.350, 45.865], [9.330, 45.855], [9.325, 45.840],
                [9.340, 45.830]
            ],
            # Oggiono
            "097057": [
                [9.320, 45.780], [9.340, 45.790], [9.350, 45.800],
                [9.330, 45.810], [9.315, 45.805], [9.310, 45.790],
                [9.320, 45.780]
            ],
            # Cesana Brianza
            "097021": [
                [9.300, 45.800], [9.315, 45.810], [9.325, 45.820],
                [9.310, 45.825], [9.290, 45.815], [9.285, 45.805],
                [9.300, 45.800]
            ],
            # Civate
            "097024": [
                [9.345, 45.815], [9.360, 45.825], [9.365, 45.835],
                [9.350, 45.845], [9.335, 45.835], [9.330, 45.825],
                [9.345, 45.815]
            ],
            # Garlate
            "097037": [
                [9.380, 45.800], [9.395, 45.810], [9.400, 45.820],
                [9.390, 45.830], [9.375, 45.825], [9.370, 45.810],
                [9.380, 45.800]
            ],
            # Olginate
            "097058": [
                [9.395, 45.790], [9.410, 45.800], [9.415, 45.810],
                [9.405, 45.820], [9.390, 45.815], [9.385, 45.800],
                [9.395, 45.790]
            ],
            # Sirone
            "097074": [
                [9.330, 45.770], [9.345, 45.775], [9.350, 45.785],
                [9.340, 45.795], [9.325, 45.790], [9.320, 45.780],
                [9.330, 45.770]
            ],
            # Rogeno
            "097068": [
                [9.290, 45.775], [9.305, 45.780], [9.310, 45.790],
                [9.300, 45.800], [9.285, 45.795], [9.280, 45.785],
                [9.290, 45.775]
            ],
            # Nibionno
            "097055": [
                [9.270, 45.760], [9.285, 45.765], [9.290, 45.775],
                [9.280, 45.785], [9.265, 45.780], [9.260, 45.770],
                [9.270, 45.760]
            ],
            # Garbagnate Monastero
            "097035": [
                [9.310, 45.760], [9.325, 45.765], [9.330, 45.775],
                [9.320, 45.785], [9.305, 45.780], [9.300, 45.770],
                [9.310, 45.760]
            ]
        }
        
        # Default polygon - forma più complessa per sembrare un comune reale
        def generate_default_polygon(id):
            # Creiamo un poligono leggermente diverso per ogni id
            # per dare l'impressione di confini comunali reali
            seed = int(hashlib.md5(str(id).encode()).hexdigest(), 16) % 1000
            
            # Coordinate base area Lecco/Como
            base_lat = 45.8 + (seed % 100) / 1000
            base_lon = 9.3 + (seed % 100) / 1000
            
            # Creiamo un poligono irregolare
            coords = []
            for i in range(8):
                angle = i * 45
                rad_variation = (seed % 10 + 1) / 1000 * (0.8 + (angle % 90) / 100)
                lat = base_lat + rad_variation * 1.2 * (0.9 + (seed % 7) / 10) * (1 if i % 2 == 0 else -1)
                lon = base_lon + rad_variation * (0.9 + (seed % 13) / 10) * (1 if i % 3 == 0 else -1)
                coords.append([lon, lat])
            
            # Chiudi il poligono
            coords.append(coords[0])
            return coords
        
        # Generazione dei GeoJSON features per ogni comune
        for comune_id in comune_ids:
            # Usa coordinate specifiche per i comuni di Lecco, altrimenti genera un poligono
            # Se il comune inizia con 097 (codice Lecco), cerchiamo di usare coordinate realistiche
            is_lecco = comune_id.startswith('097') if isinstance(comune_id, str) else False
            
            # Se è un comune di Lecco e non abbiamo coordinate specifiche, 
            # generiamo un poligono vicino a Lecco
            if is_lecco and comune_id not in sample_polygons:
                # Generiamo un poligono nella zona di Lecco
                seed = int(hashlib.md5(str(comune_id).encode()).hexdigest(), 16) % 1000
                
                # Coordinate base area Lecco
                base_lat = 45.8 + (seed % 100) / 500
                base_lon = 9.35 + (seed % 100) / 500
                
                # Creiamo un poligono irregolare ma più piccolo, adatto a un comune
                coords = []
                for i in range(6):
                    angle = i * 60
                    rad = 0.01 + (seed % 10) / 1000  # Raggio ridotto
                    lat = base_lat + rad * math.cos(math.radians(angle))
                    lon = base_lon + rad * math.sin(math.radians(angle))
                    coords.append([lon, lat])
                
                # Chiudi il poligono
                coords.append(coords[0])
                polygon_coords = coords
            else:
                # Usa coordinate specifiche se disponibili, altrimenti genera un poligono
                polygon_coords = sample_polygons.get(comune_id, generate_default_polygon(comune_id))
            
            # Crea il GeoJSON feature con il poligono
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
        
        # Crea la collezione GeoJSON
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
