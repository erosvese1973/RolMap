#!/usr/bin/env python3
"""
Script per processare e ottimizzare i dati GeoJSON dei comuni italiani.
Questo script:
1. Legge il file GeoJSON scaricato
2. Lo elabora con geopandas per aggiungere informazioni utili
3. Ottimizza i confini per migliorare le performance
4. Salva una versione ottimizzata del file

Utile per migliorare le performance di visualizzazione con Leaflet.
"""

import os
import json
import logging
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import mapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Percorsi per i file
INPUT_DIR = Path("static/data/geojson")
OUTPUT_DIR = Path("static/data/geojson/optimized")

def ensure_output_dir():
    """Assicura che la directory di output esista"""
    if not OUTPUT_DIR.exists():
        logger.info(f"Creazione directory {OUTPUT_DIR}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def simplify_geometry(gdf, tolerance=0.001):
    """
    Semplifica le geometrie di un GeoDataFrame per migliorare le performance
    
    Args:
        gdf (GeoDataFrame): GeoDataFrame con geometrie da semplificare
        tolerance (float): Tolleranza per la semplificazione (valore più alto = più semplificazione)
    
    Returns:
        GeoDataFrame: GeoDataFrame con geometrie semplificate
    """
    logger.info(f"Semplificazione geometrie con tolleranza {tolerance}")
    return gdf.copy().geometry.simplify(tolerance)

def process_comuni(simplify_tolerance=0.001):
    """
    Elabora il file GeoJSON dei comuni italiani
    
    Args:
        simplify_tolerance (float): Tolleranza per la semplificazione delle geometrie
    
    Returns:
        bool: True se l'elaborazione è riuscita, False altrimenti
    """
    # Creazione directory se non esiste
    ensure_output_dir()
    
    input_path = INPUT_DIR / "comuni_italiani.geojson"
    output_path = OUTPUT_DIR / "comuni_italiani_optimized.geojson"
    
    if not input_path.exists():
        logger.error(f"File di input {input_path} non trovato. Esegui prima download_italy_geojson.py")
        return False
    
    try:
        # Lettura del file GeoJSON con geopandas
        logger.info(f"Lettura del file GeoJSON: {input_path}")
        comuni_gdf = gpd.read_file(str(input_path))
        
        # Informazioni sul GeoDataFrame
        logger.info(f"GeoDataFrame caricato: {len(comuni_gdf)} righe, colonne: {comuni_gdf.columns.tolist()}")
        
        # Rinomina alcune colonne per chiarezza
        remap_columns = {
            "com_name": "name",
            "com_istat_code": "istat_code",
            "prov_name": "province",
            "reg_name": "region"
        }
        
        # Rinomina solo le colonne che esistono
        cols_to_rename = {old: new for old, new in remap_columns.items() if old in comuni_gdf.columns}
        if cols_to_rename:
            comuni_gdf = comuni_gdf.rename(columns=cols_to_rename)
        
        # Semplifica le geometrie per migliorare le performance
        logger.info("Semplificazione delle geometrie...")
        comuni_gdf['geometry'] = simplify_geometry(comuni_gdf, tolerance=simplify_tolerance)
        
        # Crea un dizionario con il codice ISTAT come chiave
        logger.info("Creazione di un dizionario ottimizzato...")
        
        # Controlla se la colonna 'istat_code' esiste, altrimenti usa una alternativa
        id_column = 'istat_code' if 'istat_code' in comuni_gdf.columns else 'com_istat_code'
        if id_column not in comuni_gdf.columns:
            id_column = comuni_gdf.columns[0]  # Usa la prima colonna come fallback
            logger.warning(f"Colonna ISTAT non trovata, uso {id_column} come identificativo")
        
        name_column = 'name' if 'name' in comuni_gdf.columns else 'com_name'
        if name_column not in comuni_gdf.columns:
            name_column = comuni_gdf.columns[1]  # Usa la seconda colonna come fallback
            logger.warning(f"Colonna nome non trovata, uso {name_column} come nome")
        
        # Crea un GeoJSON con solo le informazioni necessarie
        comuni_dict = {}
        
        for idx, row in comuni_gdf.iterrows():
            # Estrai l'ID (codice ISTAT)
            comune_id = str(row[id_column]).zfill(6)  # Assicura che sia una stringa di 6 caratteri
            
            # Estrai il nome e altre informazioni utili
            comune_name = row[name_column] if name_column in row else f"Comune {comune_id}"
            
            # Crea un oggetto GeoJSON per questo comune
            comuni_dict[comune_id] = {
                "type": "Feature",
                "properties": {
                    "id": comune_id,
                    "name": comune_name
                },
                "geometry": mapping(row.geometry)
            }
        
        # Salva il dizionario come JSON
        output_dict_path = OUTPUT_DIR / "comuni_dict.json"
        with open(output_dict_path, 'w') as f:
            json.dump(comuni_dict, f)
        logger.info(f"Dizionario salvato in {output_dict_path}")
        
        # Salva il GeoDataFrame come GeoJSON
        logger.info(f"Salvataggio del file GeoJSON ottimizzato: {output_path}")
        comuni_gdf.to_file(str(output_path), driver="GeoJSON")
        
        logger.info("Elaborazione completata con successo!")
        return True
        
    except Exception as e:
        logger.error(f"Errore durante l'elaborazione: {e}")
        return False

def main():
    """Funzione principale"""
    logger.info("Inizio elaborazione dei dati geografici")
    
    # Elabora i comuni
    process_comuni(simplify_tolerance=0.001)
    
    logger.info("Elaborazione completata!")

if __name__ == "__main__":
    main()