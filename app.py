import os
import logging
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
    regions = sorted(comuni_data['regione'].unique())
    agents = models.Agent.query.all()
    
    # Get agent_id from query parameter if provided
    edit_agent_id = request.args.get('edit', type=int)
    edit_agent = None
    if edit_agent_id:
        edit_agent = models.Agent.query.get(edit_agent_id)
    
    return render_template('index.html', regions=regions, agents=agents, edit_agent=edit_agent)

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
        comune_ids = request.form.getlist('comuni')
        
        if not agent_name or not comune_ids:
            flash('Nome agente e almeno un comune sono obbligatori', 'danger')
            return redirect(url_for('index'))
        
        # Check if agent already exists
        existing_agent = models.Agent.query.filter_by(name=agent_name).first()
        
        # First, process all inputs to validate them BEFORE any database changes
        valid_comune_ids = []
        invalid_comuni = []
        
        for comune_id in comune_ids:
            # Check if the comune is valid
            comune_data = comuni_data[comuni_data['codice'] == comune_id]
            if comune_data.empty:
                continue
                
            # Check if comune is already assigned to another agent
            existing_assignment = models.Assignment.query.filter_by(comune_id=comune_id).first()
            
            if existing_agent and existing_assignment and existing_assignment.agent_id == existing_agent.id:
                # Already assigned to this agent - keep it
                valid_comune_ids.append(comune_id) 
            elif existing_assignment:
                # Assigned to another agent - not valid
                comune_name = comune_data.iloc[0]['comune']
                other_agent = models.Agent.query.get(existing_assignment.agent_id)
                other_agent_name = other_agent.name if other_agent else "un altro agente"
                invalid_comuni.append(f'{comune_name} (già assegnato a {other_agent_name})')
            else:
                # Not assigned to anyone - valid
                valid_comune_ids.append(comune_id)
                
        # If there are invalid comuni, alert the user but don't stop the process for valid ones
        if invalid_comuni:
            invalid_list = ", ".join(invalid_comuni)
            flash(f'Comuni non assegnabili: {invalid_list}', 'warning')
            
            # If no valid comuni are left, stop the process
            if not valid_comune_ids:
                flash('Nessun comune valido da assegnare', 'danger')
                return redirect(url_for('index'))
        
        if existing_agent:
            # Update existing agent's municipalities
            existing_agent.registration_date = datetime.now()
            
            # Get existing comune assignments for this agent
            existing_comuni_ids = [assignment.comune_id for assignment in existing_agent.assignments]
            
            # Remove assignments that are no longer selected
            for assignment in list(existing_agent.assignments):
                if assignment.comune_id not in valid_comune_ids:
                    db.session.delete(assignment)
            
            # Add new comune assignments
            for comune_id in valid_comune_ids:
                if comune_id not in existing_comuni_ids:
                    new_assignment = models.Assignment(
                        agent_id=existing_agent.id,
                        comune_id=comune_id
                    )
                    db.session.add(new_assignment)
            
            db.session.commit()
            flash(f'Aggiornate le assegnazioni per l\'agente {agent_name}', 'success')
        else:
            # Create new agent
            new_agent = models.Agent(
                name=agent_name,
                registration_date=datetime.now()
            )
            db.session.add(new_agent)
            db.session.flush()  # Get the ID of the new agent
            
            # Add comune assignments
            for comune_id in valid_comune_ids:
                new_assignment = models.Assignment(
                    agent_id=new_agent.id,
                    comune_id=comune_id
                )
                db.session.add(new_assignment)
            
            db.session.commit()
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
    
    return render_template('mappa.html', 
                          agent_name=agent_name, 
                          comuni=comuni_details,
                          comune_ids=comune_ids)

@app.route('/get_geojson', methods=['POST'])
def get_geojson():
    """Get GeoJSON data for the selected municipalities"""
    comune_ids = request.json.get('comune_ids', [])
    
    if not comune_ids:
        return jsonify({'error': 'No municipalities selected'})
    
    try:
        # This would call an actual GeoServer, but we'll simulate the response for now
        geojson = get_geojson_from_wfs(comune_ids)
        return jsonify(geojson)
    except Exception as e:
        logger.error(f"Error fetching GeoJSON: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/agents')
def list_agents():
    """List all registered agents and their assigned municipalities"""
    agents = models.Agent.query.all()
    agent_data = []
    
    for agent in agents:
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
            'comuni': comuni
        })
    
    return render_template('agents.html', agents=agent_data)

@app.route('/get_agent_comuni', methods=['POST'])
def get_agent_comuni():
    """Get municipalities assigned to an agent"""
    agent_id = request.form.get('agent_id', type=int)
    if not agent_id:
        return jsonify([])
    
    agent = models.Agent.query.get(agent_id)
    if not agent:
        return jsonify([])
    
    # Get agent's assigned comuni
    assignments = models.Assignment.query.filter_by(agent_id=agent.id).all()
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
    
    return jsonify(comuni_list)

@app.route('/delete_agent/<int:agent_id>', methods=['POST'])
def delete_agent(agent_id):
    """Delete an agent and their municipality assignments"""
    try:
        agent = models.Agent.query.get(agent_id)
        if not agent:
            flash('Agente non trovato', 'danger')
            return redirect(url_for('list_agents'))
        
        # Delete agent and all assignments (cascade delete)
        db.session.delete(agent)
        db.session.commit()
        
        flash(f'Agente {agent.name} eliminato con successo', 'success')
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
