#!/usr/bin/env python3
"""
Script per scaricare la lista completa dei comuni italiani dall'ISTAT
e salvarla in un formato compatibile con l'applicazione.
"""

import os
import logging
import pandas as pd
import requests
from io import StringIO

# Configurazione del logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL dell'elenco dei comuni ISTAT
ISTAT_COMUNI_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"

def main():
    """Scarica e processa l'elenco dei comuni italiani"""
    output_dir = os.path.join('static', 'data')
    output_file = os.path.join(output_dir, 'elenco_comuni_istat.csv')
    
    # Crea la directory di output se non esiste
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        logger.info(f"Scaricamento dati dall'URL: {ISTAT_COMUNI_URL}")
        response = requests.get(ISTAT_COMUNI_URL)
        
        if response.status_code != 200:
            logger.error(f"Errore nello scaricamento dei dati: {response.status_code}")
            return False
        
        # Il file ISTAT è in formato CSV con encoding Latin-1 e separatore punto e virgola
        content = response.content.decode('latin-1')
        
        logger.info("Elaborazione dati CSV")
        # Leggi il CSV con pandas
        df = pd.read_csv(StringIO(content), sep=';')
        
        # Stampa i nomi delle colonne per debug
        logger.info(f"Colonne disponibili: {df.columns.tolist()}")
        
        # Seleziona solo le colonne che ci interessano
        df_cleaned = df[[
            'Codice Comune formato numerico',
            'Denominazione in italiano',
            'Denominazione Regione'
        ]]
        
        # Estrai la provincia dalla colonna 'Denominazione dell'Unità territoriale sovracomunale'
        if "Denominazione dell'Unità territoriale sovracomunale \n(valida a fini statistici)" in df.columns:
            provincia_col = "Denominazione dell'Unità territoriale sovracomunale \n(valida a fini statistici)"
        elif "Denominazione dell'Unit territoriale sovracomunale \n(valida a fini statistici)" in df.columns:
            provincia_col = "Denominazione dell'Unit territoriale sovracomunale \n(valida a fini statistici)"
        else:
            # Cerca una colonna che assomigli a quella della provincia
            provincia_candidates = [col for col in df.columns if 'provinciale' in col.lower() or 'provincia' in col.lower() or 'territoriale' in col.lower()]
            if provincia_candidates:
                provincia_col = provincia_candidates[0]
                logger.info(f"Colonna provincia (best guess): {provincia_col}")
            else:
                # Se non troviamo nessuna colonna adatta, creiamo una colonna fittizia
                df['Provincia'] = 'Sconosciuta'
                provincia_col = 'Provincia'
        
        df_cleaned['provincia'] = df[provincia_col]
        
        # Rinomina le colonne per adattarle al nostro formato
        df_cleaned = df_cleaned.rename(columns={
            'Codice Comune formato numerico': 'codice',
            'Denominazione in italiano': 'comune',
            'Denominazione Regione': 'regione'
        })
        
        # Seleziona solo le colonne che ci interessano
        df_cleaned = df_cleaned[['codice', 'comune', 'provincia', 'regione']]
        
        # Assicurati che i codici siano formattati come stringhe
        df_cleaned['codice'] = df_cleaned['codice'].astype(str).str.zfill(5)
        
        # Rimuovi comuni duplicati (mantieni il primo)
        df_cleaned = df_cleaned.drop_duplicates(subset=['codice'])
        
        # Ordina per regione, provincia e comune
        df_cleaned = df_cleaned.sort_values(by=['regione', 'provincia', 'comune'])
        
        # Salva il risultato
        logger.info(f"Salvataggio di {len(df_cleaned)} comuni nel file {output_file}")
        df_cleaned.to_csv(output_file, index=False)
        
        logger.info("Operazione completata con successo")
        return True
        
    except Exception as e:
        logger.error(f"Si è verificato un errore: {str(e)}")
        return False

if __name__ == "__main__":
    main()