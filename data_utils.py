import os
import pandas as pd
import logging
from io import StringIO

logger = logging.getLogger(__name__)

# Sample ISTAT data for elenco_comuni.csv
SAMPLE_CSV_DATA = """codice,comune,provincia,regione
01001,Agliè,Torino,Piemonte
01002,Airasca,Torino,Piemonte
01003,Ala di Stura,Torino,Piemonte
01004,Albiano d'Ivrea,Torino,Piemonte
01005,Alice Superiore,Torino,Piemonte
02001,Alagna Valsesia,Vercelli,Piemonte
02002,Albano Vercellese,Vercelli,Piemonte
03001,Agrate Conturbia,Novara,Piemonte
04001,Acceglio,Cuneo,Piemonte
05001,Agliano Terme,Asti,Piemonte
06001,Acqui Terme,Alessandria,Piemonte
07001,Airole,Imperia,Liguria
07002,Apricale,Imperia,Liguria
08001,Alassio,Savona,Liguria
09001,Arenzano,Genova,Liguria
10001,Ameglia,La Spezia,Liguria
12001,Alagna,Pavia,Lombardia
13001,Abbadia Cerreto,Lodi,Lombardia
15001,Abbiategrasso,Milano,Lombardia
16001,Adrara San Martino,Bergamo,Lombardia
17001,Acquafredda,Brescia,Lombardia
18001,Albaredo per San Marco,Sondrio,Lombardia
19001,Almenno San Bartolomeo,Como,Lombardia
20001,Angera,Varese,Lombardia
21001,Aldeno,Trento,Trentino-Alto Adige
22001,Aldino,Bolzano,Trentino-Alto Adige
23001,Affi,Verona,Veneto
24001,Agordo,Belluno,Veneto
25001,Abano Terme,Padova,Veneto
26001,Adria,Rovigo,Veneto
27001,Altivole,Treviso,Veneto
28001,Annone Veneto,Venezia,Veneto
29001,Adria,Vicenza,Veneto
30001,Aiello del Friuli,Udine,Friuli-Venezia Giulia
31001,Andreis,Pordenone,Friuli-Venezia Giulia
32001,Ampezzo,Gorizia,Friuli-Venezia Giulia
33001,Albareto,Parma,Emilia-Romagna
34001,Albinea,Reggio Emilia,Emilia-Romagna
35001,Anzola dell'Emilia,Bologna,Emilia-Romagna
36001,Argenta,Ferrara,Emilia-Romagna
37001,Alfonsine,Ravenna,Emilia-Romagna
38001,Bagno di Romagna,Forlì-Cesena,Emilia-Romagna
39001,Casteldelci,Rimini,Emilia-Romagna
40001,Aulla,Massa-Carrara,Toscana
41001,Altopascio,Lucca,Toscana
42001,Abetone,Pistoia,Toscana
43001,Agliana,Prato,Toscana
44001,Bagno a Ripoli,Firenze,Toscana
45001,Arezzo,Arezzo,Toscana
46001,Abbadia San Salvatore,Siena,Toscana
47001,Bibbona,Livorno,Toscana
48001,Bientina,Pisa,Toscana
49001,Arcidosso,Grosseto,Toscana
51001,Alviano,Terni,Umbria
52001,Assisi,Perugia,Umbria
53001,Acquacanina,Macerata,Marche
54001,Agugliano,Ancona,Marche
55001,Acquasanta Terme,Ascoli Piceno,Marche
56001,Acquaviva Picena,Fermo,Marche
57001,Accumoli,Rieti,Lazio
58001,Affile,Roma,Lazio
59001,Acquafondata,Frosinone,Lazio
60001,Aprilia,Latina,Lazio
61001,Accumoli,Viterbo,Lazio
64001,Alba Adriatica,Teramo,Abruzzo
65001,Abbateggio,Pescara,Abruzzo
66001,Altino,Chieti,Abruzzo
67001,Acciano,L'Aquila,Abruzzo
68001,Acquaviva Collecroce,Campobasso,Molise
69001,Agnone,Isernia,Molise
70001,Accadia,Foggia,Puglia
71001,Acquaviva delle Fonti,Bari,Puglia
72001,Avetrana,Taranto,Puglia
73001,Alessano,Lecce,Puglia
74001,Andria,Barletta-Andria-Trani,Puglia
75001,Abriola,Potenza,Basilicata
76001,Accettura,Matera,Basilicata
77001,Acquaformosa,Cosenza,Calabria
78001,Antonimina,Reggio Calabria,Calabria
79001,Albi,Catanzaro,Calabria
80001,Arena,Vibo Valentia,Calabria
81001,Acri,Crotone,Calabria
82001,Aci Castello,Catania,Sicilia
83001,Agrigento,Agrigento,Sicilia
84001,Alcamo,Trapani,Sicilia
85001,Acquedolci,Messina,Sicilia
86001,Assoro,Enna,Sicilia
87001,Augusta,Siracusa,Sicilia
88001,Caltanissetta,Caltanissetta,Sicilia
89001,Assemini,Cagliari,Sardegna
90001,Alghero,Sassari,Sardegna
91001,Aritzo,Nuoro,Sardegna
92001,Ales,Oristano,Sardegna
93001,Arbus,Medio Campidano,Sardegna
94001,Arzachena,Olbia-Tempio,Sardegna
95001,Arzana,Ogliastra,Sardegna
96001,Iglesias,Carbonia-Iglesias,Sardegna
"""

def load_comuni_data():
    """
    Load Italian municipalities data from CSV file.
    Returns a pandas DataFrame with the data.
    """
    try:
        # Try to load from the ISTAT list first (complete, ufficiale)
        csv_path_istat = os.path.join('static', 'data', 'elenco_comuni_istat.csv')
        # Try to load from the complete list next
        csv_path_completo = os.path.join('static', 'data', 'elenco_comuni_completo.csv')
        # Base list as last resort
        csv_path_base = os.path.join('static', 'data', 'elenco_comuni.csv')
        
        # Check if the ISTAT file exists (preferito)
        if os.path.exists(csv_path_istat):
            logger.info(f"Loading comuni data from {csv_path_istat}")
            df = pd.read_csv(csv_path_istat)
        # Check if the complete file exists
        elif os.path.exists(csv_path_completo):
            logger.info(f"Loading comuni data from {csv_path_completo}")
            df = pd.read_csv(csv_path_completo)
        # Otherwise check if the base file exists
        elif os.path.exists(csv_path_base):
            logger.info(f"Loading comuni data from {csv_path_base}")
            df = pd.read_csv(csv_path_base)
        else:
            # If no file exists, create the directory and write sample data
            logger.warning(f"CSV files not found, using sample data")
            os.makedirs(os.path.dirname(csv_path_base), exist_ok=True)
            
            # Write sample data to CSV file
            with open(csv_path_base, 'w') as f:
                f.write(SAMPLE_CSV_DATA)
            
            # Load the sample data
            df = pd.read_csv(StringIO(SAMPLE_CSV_DATA))
        
        # Ensure codice is treated as a string
        df['codice'] = df['codice'].astype(str)
        
        logger.info(f"Loaded {len(df)} municipalities from CSV")
        return df
    
    except Exception as e:
        logger.error(f"Error loading comuni data: {str(e)}")
        # Return empty DataFrame in case of error
        return pd.DataFrame(columns=['codice', 'comune', 'provincia', 'regione'])

def backup_data():
    """
    Create a backup of the SQLite database.
    """
    try:
        import shutil
        from datetime import datetime
        
        # Source database file
        src = 'agent_territories.db'
        
        # Create backup directory if it doesn't exist
        backup_dir = 'backups'
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = os.path.join(backup_dir, f'agent_territories_{timestamp}.db')
        
        # Copy the database file
        shutil.copy2(src, dst)
        logger.info(f"Database backup created: {dst}")
        
        return True
    except Exception as e:
        logger.error(f"Error creating database backup: {str(e)}")
        return False
