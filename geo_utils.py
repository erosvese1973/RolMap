import requests
import logging
import json
import math
import hashlib
import os.path
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)

def get_geojson_from_wfs(comune_ids):
    """
    Retrieve GeoJSON data for the given municipality IDs.
    
    Args:
        comune_ids (list): List of municipality IDs to fetch
    
    Returns:
        dict: GeoJSON data with the requested municipalities
    """
    logger.info(f"Fetching GeoJSON for comune IDs: {comune_ids}")
    
    try:
        # Verifica se il file JSON con i dati dei comuni esiste già
        comuni_dict_path = Path("static/data/geojson/optimized/comuni_dict.json")
        geojson_path = Path("static/data/geojson/comuni_italiani.geojson")
        
        # Se non abbiamo ancora dati GeoJSON, proviamo a scaricarli
        if not geojson_path.exists():
            # Prova a scaricare i dati
            try:
                # Importa il modulo di download solo quando necessario
                logger.info("GeoJSON data not found. Downloading from Openpolis...")
                import download_italy_geojson
                download_italy_geojson.main()
                
                # Processa i dati
                import process_geojson
                process_geojson.main()
            except Exception as e:
                logger.error(f"Failed to download GeoJSON data: {e}")
                # In caso di errore, torniamo ai poligoni generati
                return _generate_fallback_geojson(comune_ids)
                
        # Verifichiamo se abbiamo i dati ottimizzati
        if comuni_dict_path.exists():
            try:
                with open(comuni_dict_path, 'r') as f:
                    comuni_dict = json.load(f)
                    
                logger.info(f"Loaded comuni dictionary with {len(comuni_dict)} items")
                
                # Crea una feature collection con solo i comuni richiesti
                features = []
                
                # Normalizziamo gli ID dei comuni per gestire diverse formattazioni
                normalized_comuni_ids = []
                for comune_id in comune_ids:
                    # Assicurati che sia una stringa
                    comune_id_str = str(comune_id).strip()
                    
                    # Se è un codice ISTAT completo (es. 097042), usalo così com'è
                    if len(comune_id_str) == 6:
                        normalized_comuni_ids.append(comune_id_str)
                    # Se è solo un ID di comune senza prefisso della provincia (es. 042 per Lecco)
                    elif len(comune_id_str) <= 3:
                        # Aggiungiamo codici per diverse province per aumentare la compatibilità
                        normalized_comuni_ids.append(f"097{comune_id_str.zfill(3)}")  # Lecco
                        normalized_comuni_ids.append(f"013{comune_id_str.zfill(3)}")  # Como
                        normalized_comuni_ids.append(f"016{comune_id_str.zfill(3)}")  # Bergamo
                    # Per altri formati (es. 97042 o 13042)
                    else:
                        # Se inizia con 97, è probabilmente un comune della provincia di Lecco (097)
                        if comune_id_str.startswith('97'):
                            normalized_comuni_ids.append(f"0{comune_id_str}")
                        # Se inizia con 13, è probabilmente un comune della provincia di Como (013)
                        elif comune_id_str.startswith('13'):
                            # Aggiungiamo sempre sia la versione con che senza lo zero
                            normalized_comuni_ids.append(comune_id_str)
                            normalized_comuni_ids.append(f"0{comune_id_str}")
                        # Per tutti gli altri formati
                        else:
                            # Proviamo sia il formato originale che con uno zero davanti
                            normalized_comuni_ids.append(comune_id_str)
                            normalized_comuni_ids.append(f"0{comune_id_str}")
                
                logger.info(f"Normalized comune IDs: {normalized_comuni_ids}")
                
                # Raggruppa gli IDs per facilitare la ricerca evitando duplicati
                # La chiave è il comune senza zeri iniziali, il valore è una lista di tutti i formati provati
                comuni_groups = {}
                for comune_id in normalized_comuni_ids:
                    comune_orig = comune_id.lstrip('0')  # Versione senza zeri iniziali
                    if comune_orig not in comuni_groups:
                        comuni_groups[comune_orig] = []
                    comuni_groups[comune_orig].append(comune_id)
                
                # Cerca le feature per ciascun comune richiesto
                missing_comuni = []
                found_comuni = set()  # Teniamo traccia dei comuni già trovati
                
                # Per ogni gruppo di IDs dello stesso comune
                for comune_orig, id_variants in comuni_groups.items():
                    # Se questo comune è già stato trovato, continua
                    if comune_orig in found_comuni:
                        continue
                    
                    # Prova tutte le varianti di ID
                    found = False
                    for comune_id in id_variants:
                        if comune_id in comuni_dict:
                            features.append(comuni_dict[comune_id])
                            found_comuni.add(comune_orig)  # Segna come trovato
                            found = True
                            break
                    
                    # Se nessuna variante è stata trovata, aggiungi una variante all'elenco dei mancanti
                    if not found:
                        # Prendi la prima variante come rappresentante per il fallback
                        first_variant = id_variants[0]
                        missing_comuni.append(first_variant)
                        logger.warning(f"Comune ID not found in GeoJSON data: {first_variant} (tried variants: {id_variants})")
                
                # Se abbiamo comuni mancanti, genera poligoni per loro
                if missing_comuni:
                    logger.warning(f"Generating fallback polygons for {len(missing_comuni)} missing comuni")
                    fallback_geojson = _generate_fallback_geojson(missing_comuni)
                    features.extend(fallback_geojson['features'])
                
                # Crea il GeoJSON finale
                geojson = {
                    "type": "FeatureCollection",
                    "features": features
                }
                
                logger.info(f"Created GeoJSON with {len(features)} features")
                return geojson
                
            except Exception as e:
                logger.error(f"Error loading comuni dictionary: {e}")
                # In caso di errore, torniamo ai poligoni generati
                return _generate_fallback_geojson(comune_ids)
        else:
            logger.warning("Comuni dictionary not found, using fallback")
            # Se non abbiamo i dati ottimizzati, torniamo ai poligoni generati
            return _generate_fallback_geojson(comune_ids)
    
    except Exception as e:
        logger.error(f"Error fetching GeoJSON data: {str(e)}")
        raise Exception(f"Failed to retrieve GeoJSON data: {str(e)}")

def _generate_fallback_geojson(comune_ids):
    """
    Genera poligoni di fallback per i comuni richiesti.
    
    Args:
        comune_ids (list): Lista degli ID dei comuni
        
    Returns:
        dict: GeoJSON data con poligoni generati
    """
    logger.info(f"Generating fallback GeoJSON for {len(comune_ids)} comuni")
    
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
        # Altri comuni...
    }
    
    # Funzione per generare un poligono predefinito
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
    
    # Elimina duplicati: se abbiamo '13001' e '013001', teniamo solo una versione
    unique_comuni = {}
    for comune_id in comune_ids:
        comune_id_str = str(comune_id).strip()
        stripped_id = comune_id_str.lstrip('0')  # Rimuovi gli zeri iniziali
        
        # Mantieni la versione con lo zero per coerenza con il GeoJSON
        if stripped_id not in unique_comuni:
            # Preferisci la versione con lo zero iniziale quando disponibile
            if comune_id_str.startswith('0'):
                unique_comuni[stripped_id] = comune_id_str
            else:
                unique_comuni[stripped_id] = comune_id_str
    
    # Generazione dei GeoJSON features per ogni comune
    for comune_orig, comune_id_str in unique_comuni.items():
        # Normalizza l'ID
        if len(comune_id_str) == 6 and comune_id_str.startswith('0'):
            normalized_id = comune_id_str
        elif comune_id_str.startswith('97'):
            normalized_id = '0' + comune_id_str
        else:
            normalized_id = comune_id_str
            
        # Usa coordinate specifiche per i comuni di Lecco, altrimenti genera un poligono
        # Se il comune inizia con 097 (codice Lecco), cerchiamo di usare coordinate realistiche
        is_lecco = normalized_id.startswith('097')
        
        # Se è un comune di Lecco e non abbiamo coordinate specifiche, 
        # generiamo un poligono vicino a Lecco
        if is_lecco and normalized_id not in sample_polygons:
            # Generiamo un poligono nella zona di Lecco
            seed = int(hashlib.md5(str(normalized_id).encode()).hexdigest(), 16) % 1000
            
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
            polygon_coords = sample_polygons.get(normalized_id, generate_default_polygon(normalized_id))
        
        # Crea il GeoJSON feature con il poligono
        feature = {
            "type": "Feature",
            "properties": {
                "id": normalized_id,
                "name": f"Comune {normalized_id}",
                "is_fallback": True  # Flag per identificare i poligoni generati artificialmente
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
    
    logger.info(f"Generated fallback GeoJSON with {len(features)} features")
    return geojson

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
