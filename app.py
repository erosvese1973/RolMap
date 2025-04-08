import os
import logging
import time
from datetime import datetime
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
    """Main page with the agent registration and municipality selection form"""
    # Force refresh of database tables to ensure we have the latest data
    db.session.expire_all()
    db.session.close()
    
    # Generate a timestamp to force cache invalidation on client side
    import_time = int(time.time())
    
    regions = sorted(comuni_data['regione'].unique())
    agents = models.Agent.query.all()
    
    # Get agent_id from query parameter if provided
    edit_agent_id = request.args.get('edit', type=int)
    edit_agent = None
    if edit_agent_id:
        edit_agent = models.Agent.query.get(edit_agent_id)
    
    return render_template('index.html', regions=regions, agents=agents, edit_agent=edit_agent, import_time=import_time)

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

@app.route('/submit', methods=['POST'])
def submit():
    """Process form submission for agent and selected municipalities"""
    try:
        agent_name = request.form.get('agent_name')
        agent_color = request.form.get('agent_color', '#ff9800')  # Default to orange if not provided
        comune_ids = request.form.getlist('comuni')
        agent_id = request.form.get('agent_id')  # Ottieni l'ID dell'agente dalla richiesta
        
        # In caso di "Cancella Tutti", possiamo avere agent_name ma nessun comune
        # In questo caso, non dobbiamo richiedere comuni se abbiamo l'ID di un agente esistente
        if not agent_name:
            flash('Nome agente obbligatorio', 'danger')
            return redirect(url_for('index'))
        
        # Se non abbiamo comuni e non abbiamo un ID agente, è un errore
        # Ma se abbiamo un ID agente, stiamo cancellando tutti i comuni dell'agente
        if not comune_ids and not agent_id:
            flash('Seleziona almeno un comune', 'danger')
            return redirect(url_for('index'))
        
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
                return redirect(url_for('index'))
        
        if existing_agent:
            # Update existing agent's municipalities and color
            existing_agent.registration_date = datetime.now()
            existing_agent.color = agent_color  # Update color
            
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
        return redirect(url_for('index'))

@app.route('/visualizza_mappa')
def visualizza_mappa():
    """Display the map with selected municipalities"""
    agent_name = session.get('agent_name')
    comune_ids = session.get('comune_ids', [])
    
    if not agent_name or not comune_ids:
        flash('Seleziona prima un agente e i comuni', 'warning')
        return redirect(url_for('index'))
    
    # Get comune details for display
    comuni_details = []
    for comune_id in comune_ids:
        comune_row = comuni_data[comuni_data['codice'] == comune_id]
        if not comune_row.empty:
            comuni_details.append({
                'id': comune_id,
                'name': comune_row.iloc[0]['comune'],
                'province': comune_row.iloc[0]['provincia'],
                'region': comune_row.iloc[0]['regione']
            })
    
    # Get agent details including color
    agent = models.Agent.query.filter_by(name=agent_name).first()
    agent_color = agent.color if agent else '#ff9800'  # Default orange if not found
    
    # Get Google Maps API key from environment
    google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    
    return render_template('mappa.html', 
                          agent_name=agent_name, 
                          agent_color=agent_color,
                          comuni=comuni_details,
                          comune_ids=comune_ids,
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
        
        # Richiamiamo il servizio WFS per ottenere i poligoni
        geojson = get_geojson_from_wfs(comune_ids)
        
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
    
    agents = models.Agent.query.all()
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
            'registration_date': agent.registration_date,
            'color': agent.color,
            'comuni': comuni
        })
    
    return render_template('agents.html', agents=agent_data, import_time=import_time)

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

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
