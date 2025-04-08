# Sistema di Gestione Territori Agenti

Un'applicazione web Flask per la gestione intelligente dei territori di vendita nei comuni italiani.

## Funzionalità Principali

- Assegnazione di comuni a agenti di vendita
- Prevenzione di duplicati nelle assegnazioni dei territori
- Visualizzazione geospaziale con mappe interattive
- Gestione completa degli agenti (creazione, modifica, eliminazione)
- Visualizzazione dettagliata dei territori assegnati
- Mappa completa con tutti i territori assegnati

## Stack Tecnologico

- Backend: Flask 3.1.0
- Database: SQLAlchemy con PostgreSQL
- Visualizzazione mappe: Leaflet.js
- Dati geografici: Integrazione con database ISTAT dei comuni italiani
- Design: Layout responsivo per accesso multi-dispositivo

## Requisiti

Le dipendenze del progetto sono elencate nel file `dependencies.txt`. In ambiente Replit, queste dipendenze sono gestite automaticamente.

```
email-validator>=2.2.0
flask>=3.1.0
flask-sqlalchemy>=3.1.1
geopandas>=1.0.1
gunicorn>=23.0.0
pandas>=2.2.3
psycopg2-binary>=2.9.10
requests>=2.32.3
shapely>=2.1.0
sqlalchemy>=2.0.40
trafilatura>=2.0.0
werkzeug>=3.1.3
```

## Struttura del Progetto

- `app.py`: Applicazione principale Flask con tutte le route e la logica
- `models.py`: Modelli del database SQLAlchemy
- `data_utils.py`: Funzioni di utilità per la gestione dei dati
- `geo_utils.py`: Funzioni per elaborare dati geografici
- `/templates`: Template HTML per le pagine web
- `/static`: File statici (CSS, JavaScript, dati)

## Funzionalità Avanzate

- Mappatura intelligente dei territori con colorazione per agente
- Informazioni dettagliate sui popup delle mappe
- Salvataggio automatico delle modifiche agli agenti
- Ordinamento alfabetico degli agenti per cognome
- Prevenzione di assegnazioni duplicate di comuni