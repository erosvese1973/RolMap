import os
import logging
import time
from datetime import datetime
from collections import OrderedDict
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create DeclarativeBase class
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database (PostgreSQL)
# Fallback to SQLite if DATABASE_URL is not available
database_url = os.environ.get("DATABASE_URL", "sqlite:///agent_territories.db")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the database extension
db.init_app(app)

# Import data utilities after app is created to avoid circular imports
from data_utils import load_comuni_data
from geo_utils import get_geojson_from_wfs
import models

# Initialize database
with app.app_context():
    db.create_all()
    # Load CSV data into memory
    comuni_data = load_comuni_data()

@app.route('/')
def index():
    """Home page with complete map visualization of all territories"""
    return redirect(url_for('mappa_completa'))

@app.route('/assegnazione')
def assegnazione():
    """Page with the municipality selection form for an agent"""
    # Force refresh of database tables to ensure we have the latest data
    db.session.expire_all()
    db.session.close()
    
    # Generate a timestamp to force cache invalidation on client side
    import_time = int(time.time())
    
    regions = sorted(comuni_data['regione'].unique())
    
    # Verifica prima se è stato passato agent_id nel percorso
    agent_id = request.args.get('agent_id', type=int)
    
    # Se non c'è agent_id, controlliamo se c'è il parametro 'edit' per retrocompatibilità
    if not agent_id:
        agent_id = request.args.get('edit', type=int)
    
    edit_agent = None
    
    if agent_id:
        edit_agent = models.Agent.query.get(agent_id)
        # Carichiamo anche gli agenti per mantenere compatibilità con altri funzioni JS
        agents = models.Agent.query.all()
        return render_template('index.html', regions=regions, agents=agents, edit_agent=edit_agent, import_time=import_time)
    else:
        # Se non abbiamo un agente preselezionato, reindiriziamo alla lista agenti
        flash('Seleziona un agente dalla lista prima di assegnare i comuni', 'info')
        return redirect(url_for('list_agents'))

@app.route('/get_provinces', methods=['POST'])
def get_provinces():
    """Get provinces for the selected region"""
    region = request.form.get('region')
    if not region:
        return jsonify([])
    
    provinces = sorted(comuni_data[comuni_data['regione'] == region]['provincia'].unique())
    return jsonify(provinces)

@app.route('/get_comuni', methods=['POST'])
def get_comuni():
    """Get municipalities for the selected province"""
    province = request.form.get('province')
    if not province:
        return jsonify([])
    
    # Get all comuni for this province
    province_comuni = comuni_data[comuni_data['provincia'] == province][['codice', 'comune']].to_dict('records')
    
    # Get list of all assigned comuni
    assigned_comuni = []
    try:
        # Execute a fresh query to ensure we have the latest data
        db.session.expire_all()  # Expire cached objects to force a fresh load
        assigned_comuni = [a.comune_id for a in models.Assignment.query.all()]
    except Exception as e:
        logger.error(f"Error getting assigned comuni: {str(e)}")
    
    # Mark comuni that are already assigned to other agents
    for comune in province_comuni:
        if comune['codice'] in assigned_comuni:
            comune['assigned'] = True
        else:
            comune['assigned'] = False
    
    return jsonify(province_comuni)

@app.route('/remove_comune', methods=['POST'])
def remove_comune():
    """Remove a single municipality from an agent's assignments"""
    try:
        agent_id = request.form.get('agent_id', type=int)
        comune_id = request.form.get('comune_id')
        
        if not agent_id or not comune_id:
            return jsonify({'success': False, 'error': 'Dati mancanti'}), 400
        
        # Elimina l'assegnazione se esiste
        assignment = models.Assignment.query.filter_by(
            agent_id=agent_id, 
            comune_id=comune_id
        ).first()
        
        if assignment:
            logger.debug(f"Removing assignment: comune {comune_id} from agent {agent_id}")
            db.session.delete(assignment)
            db.session.commit()
            db.session.expire_all()
            db.session.close()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Assegnazione non trovata'}), 404
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing comune: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/submit', methods=['POST'])
def submit():
    """Process form submission for agent and selected municipalities"""
    try:
        agent_name = request.form.get('agent_name')
        agent_color = request.form.get('agent_color', '#ff9800')  # Default to orange if not provided
        agent_phone = request.form.get('agent_phone', '')  # Numero di cellulare (opzionale)
        agent_email = request.form.get('agent_email', '')  # Email (opzionale)
        comune_ids = request.form.getlist('comuni')
        agent_id = request.form.get('agent_id')  # Ottieni l'ID dell'agente dalla richiesta
        
        # In caso di "Cancella Tutti", possiamo avere agent_name ma nessun comune
        # In questo caso, non dobbiamo richiedere comuni se abbiamo l'ID di un agente esistente
        if not agent_name:
            flash('Nome agente obbligatorio', 'danger')
            return redirect(url_for('assegnazione'))
        
        # Se non abbiamo comuni e non abbiamo un ID agente, è un errore
        # Ma se abbiamo un ID agente, stiamo cancellando tutti i comuni dell'agente
        if not comune_ids and not agent_id:
            flash('Seleziona almeno un comune', 'danger')
            return redirect(url_for('assegnazione'))
        
        # Check if agent already exists
        existing_agent = models.Agent.query.filter_by(name=agent_name).first()
        
        # First, process all inputs to validate them BEFORE any database changes
        # Use a set to ensure no duplicate comune_ids
        valid_comune_ids = set()
        invalid_comuni = []
        
        for comune_id in comune_ids:
            # Skip if already processed
            if comune_id in valid_comune_ids:
                continue
                
            # Check if the comune is valid
            comune_data = comuni_data[comuni_data['codice'] == comune_id]
            if comune_data.empty:
                continue
                
            # Check if comune is already assigned to another agent
            # Force a fresh query to ensure we're working with the latest data
            db.session.expire_all()
            existing_assignment = models.Assignment.query.filter_by(comune_id=comune_id).first()
            
            if existing_agent and existing_assignment and existing_assignment.agent_id == existing_agent.id:
                # Already assigned to this agent - keep it
                valid_comune_ids.add(comune_id) 
            elif existing_assignment:
                # Assigned to another agent - not valid
                comune_name = comune_data.iloc[0]['comune']
                other_agent = models.Agent.query.get(existing_assignment.agent_id)
                other_agent_name = other_agent.name if other_agent else "un altro agente"
                invalid_comuni.append(f'{comune_name} (già assegnato a {other_agent_name})')
            else:
                # Not assigned to anyone - valid
                valid_comune_ids.add(comune_id)
                
        # Convert set back to list for further processing
        valid_comune_ids = list(valid_comune_ids)
                
        # If there are invalid comuni, alert the user but don't stop the process for valid ones
        if invalid_comuni:
            invalid_list = ", ".join(invalid_comuni)
            flash(f'Comuni non assegnabili: {invalid_list}', 'warning')
            
            # If no valid comuni are left, stop the process
            if not valid_comune_ids:
                flash('Nessun comune valido da assegnare', 'danger')
                return redirect(url_for('assegnazione'))
        
        if existing_agent:
            # Update existing agent's municipalities, color, phone, and email
            existing_agent.registration_date = datetime.now()
            existing_agent.color = agent_color  # Update color
            existing_agent.phone = agent_phone  # Update phone number
            existing_agent.email = agent_email  # Update email
            
            # Get existing comune assignments for this agent
            # Ensure we're using fresh data
            db.session.expire_all()
            existing_assignments = models.Assignment.query.filter_by(agent_id=existing_agent.id).all()
            existing_comuni_ids = [assignment.comune_id for assignment in existing_assignments]
            
            # Remove assignments that are no longer selected
            for assignment in existing_assignments:
                if assignment.comune_id not in valid_comune_ids:
                    logger.debug(f"Removing comune {assignment.comune_id} from agent {existing_agent.id}")
                    db.session.delete(assignment)
            
            # Add new comune assignments
            for comune_id in valid_comune_ids:
                if comune_id not in existing_comuni_ids:
                    logger.debug(f"Adding comune {comune_id} to agent {existing_agent.id}")
                    new_assignment = models.Assignment(
                        agent_id=existing_agent.id,
                        comune_id=comune_id
                    )
                    db.session.add(new_assignment)
            
            db.session.commit()
            
            # Ensure the cache is cleared after commit
            db.session.expire_all()
            db.session.close()
            
            flash(f'Aggiornate le assegnazioni per l\'agente {agent_name}', 'success')
        else:
            # Create new agent with color
            new_agent = models.Agent(
                name=agent_name,
                phone=agent_phone,
                email=agent_email,
                registration_date=datetime.now(),
                color=agent_color
            )
            db.session.add(new_agent)
            db.session.flush()  # Get the ID of the new agent
            
            # Add comune assignments
            for comune_id in valid_comune_ids:
                logger.debug(f"Adding comune {comune_id} to new agent {new_agent.id}")
                new_assignment = models.Assignment(
                    agent_id=new_agent.id,
                    comune_id=comune_id
                )
                db.session.add(new_assignment)
            
            db.session.commit()
            
            # Ensure the cache is cleared after commit
            db.session.expire_all()
            db.session.close()
            
            flash(f'Nuovo agente {agent_name} registrato con successo', 'success')
        
        # Store in session for map display
        session['agent_name'] = agent_name
        session['comune_ids'] = comune_ids
        
        return redirect(url_for('visualizza_mappa'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in submit: {str(e)}")
        flash(f'Errore durante il salvataggio: {str(e)}', 'danger')
        return redirect(url_for('assegnazione'))

@app.route('/visualizza_mappa', methods=['GET', 'POST'])
def visualizza_mappa():
    """Display the map with selected municipalities"""
    # Inizializziamo agent_id per evitare warning
    agent_id = None
    
    if request.method == 'POST':
        # Nuova logica: gestisci i dati inviati direttamente dal pulsante "Mappa"
        agent_id = request.form.get('agent_id')
        agent_name = request.form.get('agent_name')
        agent_color = request.form.get('agent_color', '#ff9800')  # Default orange if not specified
        
        # Ottieni i comuni selezionati dal form
        comune_ids = request.form.getlist('comuni')
        
        logger.info(f"Visualizzazione mappa richiesta direttamente: Agente={agent_name}, Comuni={comune_ids}")
        
        # Salva i dati in sessione per retrocompatibilità
        session['agent_name'] = agent_name
        session['comune_ids'] = comune_ids
    else:
        # Logica originale per richieste GET (retrocompatibilità)
        agent_name = session.get('agent_name')
        comune_ids = session.get('comune_ids', [])
        
        if not agent_name:
            flash('Seleziona prima un agente', 'warning')
            return redirect(url_for('assegnazione'))
        
        # Verifica se esiste un agente con il nome specificato
        agent = models.Agent.query.filter_by(name=agent_name).first()
        agent_color = agent.color if agent else '#ff9800'  # Default orange
    
    # Get comune details for display, removing duplicates
    comuni_details = []
    processed_ids = set()  # Set per tracciare gli ID già elaborati
    for comune_id in comune_ids:
        # Salta se questo ID è già stato elaborato
        if comune_id in processed_ids:
            continue
            
        processed_ids.add(comune_id)  # Marca questo ID come elaborato
        comune_row = comuni_data[comuni_data['codice'] == comune_id]
        if not comune_row.empty:
            comuni_details.append({
                'id': comune_id,
                'name': comune_row.iloc[0]['comune'],
                'province': comune_row.iloc[0]['provincia'],
                'region': comune_row.iloc[0]['regione']
            })
    
    # Se siamo in modalità POST ma l'agente non esiste nel database, 
    # usiamo direttamente i dati del form
    agent_phone = None  # Inizializziamo la variabile
    if request.method == 'POST':
        # Cerca l'agente nel database solo se ha un ID valido
        if agent_id and agent_id != 'new':
            existing_agent = models.Agent.query.get(agent_id)
            if existing_agent:
                agent_color = existing_agent.color
                agent_id = existing_agent.id  # Assicuriamoci di avere l'ID corretto
                agent_phone = existing_agent.phone  # Recuperiamo il numero di telefono
        else:
            agent_id = None
    else:
        # Logica per richieste GET (la stessa di prima)
        agent = models.Agent.query.filter_by(name=agent_name).first()
        agent_color = agent.color if agent else '#ff9800'  # Default orange
        agent_id = agent.id if agent else None
        agent_phone = agent.phone if agent else None  # Recuperiamo il numero di telefono
    
    # Get Google Maps API key from environment
    google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    
    # Aggiorna anche la lista degli ID dei comuni eliminando i duplicati
    unique_comune_ids = list(processed_ids)
    
    return render_template('mappa.html', 
                          agent_name=agent_name, 
                          agent_color=agent_color,
                          agent_id=agent_id,  # Passa l'ID dell'agente al template
                          agent_phone=agent_phone,  # Passiamo il numero di telefono al template
                          comuni=comuni_details,
                          comune_ids=unique_comune_ids,
                          google_maps_api_key=google_maps_api_key)

@app.route('/get_geojson', methods=['POST'])
def get_geojson():
    """Get GeoJSON data for the selected municipalities"""
    comune_ids = request.json.get('comune_ids', [])
    
    if not comune_ids:
        logger.warning("No municipality IDs received in /get_geojson request")
        return jsonify({'error': 'No municipalities selected', 'type': 'FeatureCollection', 'features': []})
    
    logger.info(f"Processing GeoJSON request for {len(comune_ids)} municipalities: {comune_ids}")
    
    try:
        # Prima di ottenere il GeoJSON, otteniamo i nomi reali dei comuni per i popup
        comuni_names = {}
        # Creiamo un dizionario per mappare i formati diversi degli ID dei comuni
        id_mapping = {}
        
        for comune_id in comune_ids:
            # Costruiamo le possibili varianti per l'ID del comune
            comune_id_str = str(comune_id).strip()
            variants = [comune_id_str]
            
            # Se è un codice di 6 cifre che inizia con 0, aggiungiamo anche la versione senza 0
            if len(comune_id_str) == 6 and comune_id_str.startswith('0'):
                variants.append(comune_id_str[1:])  # senza lo zero iniziale
            
            # Se è un id che inizia con 13 (Como), aggiungiamo anche con lo 0 davanti
            if comune_id_str.startswith('13') and len(comune_id_str) == 5:
                variants.append(f"0{comune_id_str}")
                
            # Se è un codice di 5 cifre che inizia con 97, aggiungiamo la versione con 0
            if len(comune_id_str) == 5 and comune_id_str.startswith('97'):
                variants.append(f"0{comune_id_str}")
            
            # Cerchiamo in tutte le varianti possibili
            found = False
            for variant in variants:
                comune_row = comuni_data[comuni_data['codice'] == variant]
                if not comune_row.empty:
                    name = comune_row.iloc[0]['comune']
                    comuni_names[comune_id_str] = name
                    for v in variants:
                        id_mapping[v] = comune_id_str
                    logger.debug(f"Found name for comune {variant}: {name}")
                    found = True
                    break
            
            if not found:
                logger.warning(f"Comune ID not found in dataset: {comune_id_str} (tried variants: {variants})")
        
        # Eliminiamo i duplicati per evitare problemi di visualizzazione
        unique_comune_ids = list(OrderedDict.fromkeys(comune_ids))
        logger.info(f"Removed duplicates: {len(comune_ids)} -> {len(unique_comune_ids)} unique IDs")
        
        # Richiamiamo il servizio WFS per ottenere i poligoni
        geojson = get_geojson_from_wfs(unique_comune_ids)
        
        # Verifichiamo che il GeoJSON sia valido e contenga features
        if not geojson or 'features' not in geojson or not isinstance(geojson['features'], list):
            logger.error(f"Invalid GeoJSON structure received from WFS service")
            return jsonify({'error': 'Invalid GeoJSON structure', 'type': 'FeatureCollection', 'features': []})
            
        # Arricchiamo il GeoJSON con i nomi reali dei comuni
        for feature in geojson['features']:
            if 'properties' in feature and 'id' in feature['properties']:
                comune_id = feature['properties']['id']
                
                # Cerchiamo nel mapping degli ID (normalizzati)
                mapped_id = id_mapping.get(comune_id, comune_id)
                
                if mapped_id in comuni_names:
                    feature['properties']['name'] = comuni_names[mapped_id]
                else:
                    # Se non troviamo il nome, proviamo a cercarlo direttamente nel dataframe
                    comune_row = comuni_data[comuni_data['codice'] == comune_id]
                    if not comune_row.empty:
                        feature['properties']['name'] = comune_row.iloc[0]['comune']
                    else:
                        # Se ancora non troviamo il nome, manteniamo almeno l'ID come identificativo
                        feature['properties']['name'] = f"Comune {comune_id}"
        
        logger.info(f"Returning GeoJSON with {len(geojson['features'])} features")
        return jsonify(geojson)
    except Exception as e:
        logger.error(f"Error fetching GeoJSON: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'error': str(e), 
            'type': 'FeatureCollection', 
            'features': []
        })

@app.route('/agents')
def list_agents():
    """List all registered agents and their assigned municipalities"""
    # Force refresh of database tables to ensure we have the latest data
    db.session.expire_all()
    db.session.close()
    
    # Generate a timestamp to force cache invalidation on client side
    import_time = int(time.time())
    
    # Ottieni tutti gli agenti
    agents = models.Agent.query.all()
    
    # Ordina gli agenti per cognome (assumendo che il cognome sia l'ultima parola del nome completo)
    # Esempio: da "Mario Rossi" prende "Rossi" come chiave di ordinamento
    agents = sorted(agents, key=lambda agent: agent.name.split()[-1] if agent.name and ' ' in agent.name else agent.name)
    
    agent_data = []
    
    # Colori predefiniti per gli agenti
    default_colors = [
        '#f44336', '#9c27b0', '#3f51b5', '#2196f3', '#00bcd4', 
        '#009688', '#4caf50', '#8bc34a', '#cddc39', '#ffeb3b',
        '#ffc107', '#ff9800', '#ff5722', '#795548', '#607d8b'
    ]
    
    for i, agent in enumerate(agents):
        # Assicuriamoci che ogni agente abbia un colore
        if not agent.color:
            # Assegniamo un colore predefinito se non ne ha uno
            agent.color = default_colors[i % len(default_colors)]
            db.session.commit()
            
        assignments = models.Assignment.query.filter_by(agent_id=agent.id).all()
        comuni = []
        
        for assignment in assignments:
            comune_row = comuni_data[comuni_data['codice'] == assignment.comune_id]
            if not comune_row.empty:
                comuni.append({
                    'id': assignment.comune_id,
                    'name': comune_row.iloc[0]['comune'],
                    'province': comune_row.iloc[0]['provincia'],
                    'region': comune_row.iloc[0]['regione']
                })
        
        agent_data.append({
            'id': agent.id,
            'name': agent.name,
            'phone': agent.phone,
            'email': agent.email,
            'registration_date': agent.registration_date,
            'color': agent.color,
            'comuni': comuni
        })
    
    return render_template('agents.html', agents=agent_data, import_time=import_time)

@app.route('/mappa_completa')
def mappa_completa():
    """Visualizza la mappa completa con i territori di tutti gli agenti"""
    # Force refresh of database tables to ensure we have the latest data
    db.session.expire_all()
    db.session.close()
    
    # Get Google Maps API key from environment
    google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    
    # Ottieni tutti gli agenti con i loro colori e comuni assegnati
    agents = models.Agent.query.all()
    agent_data = []
    
    # Mappa per tenere traccia di tutti i comuni e degli agenti associati
    all_comuni_ids = []  # Lista di tutti gli ID dei comuni
    all_comuni_details = []  # Lista con i dettagli di tutti i comuni
    
    # Colori predefiniti per gli agenti (backup)
    default_colors = [
        '#f44336', '#9c27b0', '#3f51b5', '#2196f3', '#00bcd4', 
        '#009688', '#4caf50', '#8bc34a', '#cddc39', '#ffeb3b',
        '#ffc107', '#ff9800', '#ff5722', '#795548', '#607d8b'
    ]
    
    # Raccogliamo tutti i dati
    for i, agent in enumerate(agents):
        # Assicuriamoci che ogni agente abbia un colore
        agent_color = agent.color if agent.color else default_colors[i % len(default_colors)]
        
        assignments = models.Assignment.query.filter_by(agent_id=agent.id).all()
        agent_comuni = []
        
        for assignment in assignments:
            comune_id = assignment.comune_id
            all_comuni_ids.append(comune_id)
            
            comune_row = comuni_data[comuni_data['codice'] == comune_id]
            if not comune_row.empty:
                comune_info = {
                    'id': comune_id,
                    'name': comune_row.iloc[0]['comune'],
                    'province': comune_row.iloc[0]['provincia'],
                    'region': comune_row.iloc[0]['regione'],
                    'agent_id': agent.id,
                    'agent_name': agent.name,
                    'agent_color': agent_color,
                    'agent_phone': agent.phone  # Aggiungiamo il numero di telefono
                }
                agent_comuni.append(comune_info)
                all_comuni_details.append(comune_info)
        
        agent_data.append({
            'id': agent.id,
            'name': agent.name,
            'phone': agent.phone,
            'email': agent.email,
            'color': agent_color,
            'comuni': agent_comuni,
            'count': len(agent_comuni)
        })
    
    # Rimuoviamo i comuni duplicati, preservando l'assegnazione univoca
    # (Questo non dovrebbe essere necessario data la constraint sulla tabella Assignment,
    # ma è un controllo di sicurezza)
    processed_ids = set()
    unique_comuni_details = []
    for comune in all_comuni_details:
        if comune['id'] not in processed_ids:
            processed_ids.add(comune['id'])
            unique_comuni_details.append(comune)
    
    # Ordiniamo gli agenti per cognome per la visualizzazione nella legenda
    # Assumendo che il cognome sia l'ultima parola del nome completo
    agent_data.sort(key=lambda x: x['name'].split()[-1] if x['name'] and ' ' in x['name'] else x['name'])
    
    return render_template('mappa_completa.html',
                          agents=agent_data,
                          all_comuni=unique_comuni_details,
                          comune_ids=all_comuni_ids,
                          google_maps_api_key=google_maps_api_key)

@app.route('/get_agent_comuni', methods=['POST'])
def get_agent_comuni():
    """Get municipalities assigned to an agent"""
    agent_id = request.form.get('agent_id', type=int)
    if not agent_id:
        return jsonify([])
    
    # Force database refresh to ensure we're working with the latest data
    db.session.expire_all()
    
    agent = models.Agent.query.get(agent_id)
    if not agent:
        return jsonify([])
    
    # Get agent's assigned comuni with a fresh query
    assignments = models.Assignment.query.filter_by(agent_id=agent.id).all()
    logger.debug(f"Found {len(assignments)} assignments for agent {agent_id}")
    
    comuni_list = []
    
    for assignment in assignments:
        comune_row = comuni_data[comuni_data['codice'] == assignment.comune_id]
        if not comune_row.empty:
            comuni_list.append({
                'id': assignment.comune_id,
                'name': comune_row.iloc[0]['comune'],
                'province': comune_row.iloc[0]['provincia'],
                'region': comune_row.iloc[0]['regione']
            })
    
    # Close the session to prevent stale data
    db.session.close()
    
    return jsonify(comuni_list)

@app.route('/delete_agent/<int:agent_id>', methods=['POST'])
def delete_agent(agent_id):
    """Delete an agent and their municipality assignments"""
    try:
        agent = models.Agent.query.get(agent_id)
        if not agent:
            flash('Agente non trovato', 'danger')
            return redirect(url_for('list_agents'))
        
        # Registra il nome dell'agente prima di eliminarlo
        agent_name = agent.name
        
        # Delete agent and all assignments (cascade delete)
        db.session.delete(agent)
        db.session.commit()
        
        # Pulizia esplicita della cache delle sessioni per assicurarsi che i dati siano aggiornati
        db.session.expire_all()
        
        # Invalida la cache anche per le richieste future
        db.session.close()
        
        flash(f'Agente {agent_name} eliminato con successo', 'success')
        return redirect(url_for('list_agents'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_agent: {str(e)}")
        flash(f'Errore durante l\'eliminazione: {str(e)}', 'danger')
        return redirect(url_for('list_agents'))

@app.route('/update_agent_contacts/<agent_id>', methods=['POST'])
def update_agent_contacts(agent_id):
    """Update agent contact information or create a new agent"""
    try:
        # Caso speciale per nuovi agenti
        if agent_id == 'new':
            # Recupera i dati dal form
            agent_name = request.form.get('agent_name', '')
            if not agent_name:
                flash('Nome agente obbligatorio', 'danger')
                return redirect(url_for('list_agents'))
                
            # Verifica se l'agente esiste già
            existing_agent = models.Agent.query.filter_by(name=agent_name).first()
            if existing_agent:
                flash(f'Un agente con il nome "{agent_name}" esiste già', 'warning')
                return redirect(url_for('list_agents'))
                
            # Crea un nuovo agente
            new_agent = models.Agent(
                name=agent_name,
                phone='',
                email='',
                registration_date=datetime.now(),
                color='#ff9800'  # Arancione default
            )
            db.session.add(new_agent)
            db.session.commit()
            db.session.expire_all()
            
            flash(f'Nuovo agente {agent_name} creato con successo', 'success')
            return redirect(url_for('list_agents'))
        
        # Caso standard: aggiornamento agente esistente
        agent_id = int(agent_id)  # Converti a intero
        agent = models.Agent.query.get(agent_id)
        if not agent:
            flash('Agente non trovato', 'danger')
            return redirect(url_for('list_agents'))
        
        # Recupera i dati dal form
        agent_phone = request.form.get('agent_phone', '')
        agent_email = request.form.get('agent_email', '')
        agent_name = request.form.get('agent_name', agent.name)
        
        # Verifico se il nome è già utilizzato da un altro agente
        if agent_name != agent.name:
            existing_agent = models.Agent.query.filter_by(name=agent_name).first()
            if existing_agent and existing_agent.id != agent_id:
                flash(f'Un agente con il nome "{agent_name}" esiste già', 'warning')
                return redirect(url_for('list_agents'))
        
        # Aggiorna i contatti dell'agente
        agent.phone = agent_phone
        agent.email = agent_email
        agent.name = agent_name
        
        # Salva le modifiche
        db.session.commit()
        
        # Invalida la cache per assicurarsi che i dati siano aggiornati
        db.session.expire_all()
        
        flash(f'Informazioni per {agent.name} aggiornate con successo', 'success')
        return redirect(url_for('list_agents'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_agent_contacts: {str(e)}")
        flash(f'Errore durante l\'aggiornamento: {str(e)}', 'danger')
        return redirect(url_for('list_agents'))
        
@app.route('/update_agent_color/<int:agent_id>', methods=['POST'])
def update_agent_color(agent_id):
    """Update agent color"""
    try:
        agent = models.Agent.query.get(agent_id)
        if not agent:
            flash('Agente non trovato', 'danger')
            return redirect(url_for('list_agents'))
        
        # Recupera il colore dal form
        agent_color = request.form.get('agent_color', '#ff9800')  # Default arancione
        
        # Aggiorna il colore dell'agente
        agent.color = agent_color
        
        # Salva le modifiche
        db.session.commit()
        
        # Invalida la cache per assicurarsi che i dati siano aggiornati
        db.session.expire_all()
        
        flash(f'Colore per {agent.name} aggiornato con successo', 'success')
        return redirect(url_for('list_agents'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_agent_color: {str(e)}")
        
@app.route('/api/update_agent_field/<int:agent_id>', methods=['POST'])
def update_agent_field(agent_id):
    """API per aggiornare un singolo campo di un agente senza ricaricare la pagina"""
    try:
        agent = models.Agent.query.get(agent_id)
        if not agent:
            return jsonify({'success': False, 'error': 'Agente non trovato'}), 404
        
        # Ottieni i dati dal JSON della richiesta
        data = request.json
        field_type = data.get('field_type')
        value = data.get('value', '').strip()
        
        # Gestisci i diversi tipi di campo
        if field_type == 'name':
            # Controllo che il nome non sia già utilizzato da un altro agente
            if value:
                existing = models.Agent.query.filter_by(name=value).first()
                if existing and existing.id != agent_id:
                    return jsonify({'success': False, 'error': 'Nome già in uso da un altro agente'}), 400
                agent.name = value
            else:
                return jsonify({'success': False, 'error': 'Il nome non può essere vuoto'}), 400
                
        elif field_type == 'phone':
            agent.phone = value
            
        elif field_type == 'email':
            agent.email = value
            
        elif field_type == 'color':
            agent.color = value
            
        else:
            return jsonify({'success': False, 'error': 'Tipo di campo non valido'}), 400
            
        # Salva le modifiche
        db.session.commit()
        
        # Invalida la cache
        db.session.expire_all()
        
        return jsonify({
            'success': True, 
            'message': f'Campo {field_type} aggiornato per {agent.name}',
            'agent': {
                'id': agent.id,
                'name': agent.name,
                'phone': agent.phone,
                'email': agent.email,
                'color': agent.color
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_agent_field API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
