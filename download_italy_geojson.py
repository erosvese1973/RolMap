#!/usr/bin/env python3
"""
Script per scaricare i confini dei comuni italiani in formato GeoJSON
dal repository Openpolis.
"""

import os
import json
import requests
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL di base per i dati Openpolis (aggiornato)
BASE_URL = "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/"

# Cartella dove salvare i dati
OUTPUT_DIR = Path("static/data/geojson")

def ensure_output_dir():
    """Assicura che la directory di output esista"""
    if not OUTPUT_DIR.exists():
        logger.info(f"Creazione directory {OUTPUT_DIR}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def download_file(url, output_path):
    """
    Scarica un file dall'URL specificato e lo salva nel percorso indicato.
    
    Args:
        url (str): URL del file da scaricare
        output_path (Path): Percorso dove salvare il file
    
    Returns:
        bool: True se il download è riuscito, False altrimenti
    """
    logger.info(f"Scaricamento di {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
            
        logger.info(f"File salvato in {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Errore durante il download: {e}")
        return False

def download_comuni():
    """
    Scarica i confini dei comuni italiani in formato GeoJSON
    """
    # Creazione directory se non esiste
    ensure_output_dir()
    
    # Tentiamo con diversi URL noti per i dati dei comuni italiani
    # Lista di URL da provare in ordine
    urls_to_try = [
        f"{BASE_URL}limits_IT_municipalities.geojson",
        f"{BASE_URL}limits_IT_municipalities_2021.geojson", 
        f"{BASE_URL}limits_IT_municipalities_2020.geojson",
        f"{BASE_URL}comuni.geojson",
        f"{BASE_URL}limits_IT_municipalities_2019.geojson",
        "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/comuni.geojson",
        "https://raw.githubusercontent.com/teamdigitale/confini-amministrativi-istat/master/geojson/comuni.geojson"
    ]
    
    comuni_path = OUTPUT_DIR / "comuni_italiani.geojson"
    
    # Proviamo ciascun URL fino a quando uno funziona
    success = False
    for url in urls_to_try:
        logger.info(f"Tentativo con URL: {url}")
        success = download_file(url, comuni_path)
        if success:
            logger.info(f"Download riuscito da {url}")
            break
    
    if not success:
        logger.error("Impossibile scaricare i dati dei comuni da tutti gli URL disponibili.")
        return False
    
    # Verifica che il file sia valido
    try:
        with open(comuni_path, 'r') as f:
            data = json.load(f)
            logger.info(f"File GeoJSON valido con {len(data.get('features', []))} comuni")
        return True
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"File GeoJSON non valido: {e}")
        return False

def download_province():
    """
    Scarica i confini delle province italiane in formato GeoJSON
    """
    # Creazione directory se non esiste
    ensure_output_dir()
    
    # URL per le province italiane
    province_url = f"{BASE_URL}/limits_IT_provinces_2023.geojson"
    province_path = OUTPUT_DIR / "province_italiane.geojson"
    
    # Download del file
    success = download_file(province_url, province_path)
    if not success:
        # Prova con l'anno precedente se quello corrente non è disponibile
        logger.info("Impossibile scaricare i dati del 2023, provo con il 2022...")
        province_url = f"{BASE_URL}/limits_IT_provinces_2022.geojson"
        success = download_file(province_url, province_path)
    
    if not success:
        logger.error("Impossibile scaricare i dati delle province.")
        return False
    
    return True

def download_regioni():
    """
    Scarica i confini delle regioni italiane in formato GeoJSON
    """
    # Creazione directory se non esiste
    ensure_output_dir()
    
    # URL per le regioni italiane
    regioni_url = f"{BASE_URL}/limits_IT_regions_2023.geojson"
    regioni_path = OUTPUT_DIR / "regioni_italiane.geojson"
    
    # Download del file
    success = download_file(regioni_url, regioni_path)
    if not success:
        # Prova con l'anno precedente se quello corrente non è disponibile
        logger.info("Impossibile scaricare i dati del 2023, provo con il 2022...")
        regioni_url = f"{BASE_URL}/limits_IT_regions_2022.geojson"
        success = download_file(regioni_url, regioni_path)
    
    if not success:
        logger.error("Impossibile scaricare i dati delle regioni.")
        return False
    
    return True

def main():
    """Funzione principale"""
    logger.info("Inizio download dei dati geografici dall'Italia")
    
    # Scarica i confini dei comuni
    comuni_success = download_comuni()
    
    # Scarica i confini delle province
    province_success = download_province()
    
    # Scarica i confini delle regioni
    regioni_success = download_regioni()
    
    if comuni_success and province_success and regioni_success:
        logger.info("Download completato con successo!")
        return True
    else:
        logger.warning("Download completato con errori.")
        return False

if __name__ == "__main__":
    main()