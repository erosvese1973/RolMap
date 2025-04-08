#!/usr/bin/env python3
"""
Script per generare un dizionario GeoJSON basato sui dati dei comuni di Lecco.
Questo script crea una struttura JSON con i confini dei comuni della provincia di Lecco,
utile per la visualizzazione sulla mappa dell'applicazione.
"""

import os
import json
import logging
import math
import hashlib
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cartella dove salvare i dati
OUTPUT_DIR = Path("static/data/geojson/optimized")

def ensure_output_dir():
    """Assicura che la directory di output esista"""
    if not OUTPUT_DIR.exists():
        logger.info(f"Creazione directory {OUTPUT_DIR}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_lecco_geojson():
    """
    Genera un dizionario GeoJSON con i confini dei comuni della provincia di Lecco.
    
    Returns:
        dict: Dizionario con i confini dei comuni della provincia di Lecco
    """
    # Coordinate di esempio per alcuni comuni di Lecco
    comuni_lecco = {
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
        ],
        # Castello Brianza
        "097019": [
            [9.315, 45.750], [9.330, 45.755], [9.335, 45.765],
            [9.325, 45.775], [9.310, 45.770], [9.305, 45.760],
            [9.315, 45.750]
        ],
        # Annone Brianza
        "097003": [
            [9.340, 45.780], [9.355, 45.785], [9.360, 45.795],
            [9.350, 45.805], [9.335, 45.800], [9.330, 45.790],
            [9.340, 45.780]
        ],
        # Bosisio Parini 
        "097009": [
            [9.245, 45.790], [9.260, 45.795], [9.265, 45.805],
            [9.255, 45.815], [9.240, 45.810], [9.235, 45.800],
            [9.245, 45.790]
        ],
    }
    
    # Crea un dizionario di features GeoJSON
    comuni_dict = {}
    
    # Aggiungi i comuni predefiniti
    for comune_id, coords in comuni_lecco.items():
        comuni_dict[comune_id] = {
            "type": "Feature",
            "properties": {
                "id": comune_id,
                "name": f"Comune {comune_id}"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        }
    
    # Genera altri comuni della provincia di Lecco (codice 097)
    # con geometrie procedurali
    for i in range(1, 90):
        comune_id = f"097{i:03d}"
        if comune_id not in comuni_dict:
            # Generiamo un poligono nella zona di Lecco
            seed = int(hashlib.md5(str(comune_id).encode()).hexdigest(), 16) % 1000
            
            # Coordinate base area Lecco
            base_lat = 45.8 + (seed % 100) / 500
            base_lon = 9.35 + (seed % 100) / 500
            
            # Creiamo un poligono irregolare ma più piccolo
            coords = []
            for j in range(6):
                angle = j * 60
                rad = 0.01 + (seed % 10) / 1000
                lat = base_lat + rad * math.cos(math.radians(angle))
                lon = base_lon + rad * math.sin(math.radians(angle))
                coords.append([lon, lat])
            
            # Chiudi il poligono
            coords.append(coords[0])
            
            # Aggiungi il comune al dizionario
            comuni_dict[comune_id] = {
                "type": "Feature",
                "properties": {
                    "id": comune_id,
                    "name": f"Comune {comune_id}"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            }
    
    return comuni_dict

def main():
    """Funzione principale"""
    logger.info("Creazione del dizionario GeoJSON per i comuni di Lecco")
    
    # Crea la directory di output se non esiste
    ensure_output_dir()
    
    # Genera il dizionario GeoJSON
    comuni_dict = generate_lecco_geojson()
    
    # Salva il dizionario come JSON
    output_dict_path = OUTPUT_DIR / "comuni_dict.json"
    with open(output_dict_path, 'w') as f:
        json.dump(comuni_dict, f)
    
    logger.info(f"Dizionario salvato in {output_dict_path} con {len(comuni_dict)} comuni")
    
    # Crea anche un GeoJSON completo per riferimento
    features = list(comuni_dict.values())
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    output_geojson_path = OUTPUT_DIR / "comuni_lecco.geojson"
    with open(output_geojson_path, 'w') as f:
        json.dump(geojson, f)
    
    logger.info(f"GeoJSON salvato in {output_geojson_path}")
    
    return True

if __name__ == "__main__":
    main()