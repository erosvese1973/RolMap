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

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///agent_territories.db"
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
    return render_template('index.html', regions=regions)

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
    
    comuni = comuni_data[comuni_data['provincia'] == province][['codice', 'comune']].to_dict('records')
    return jsonify(comuni)

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
        
        if existing_agent:
            # Update existing agent's municipalities
            existing_agent.registration_date = datetime.now()
            
            # Get existing comune assignments for this agent
            existing_comuni_ids = [assignment.comune_id for assignment in existing_agent.assignments]
            
            # Add new comune assignments
            for comune_id in comune_ids:
                if comune_id not in existing_comuni_ids:
                    # Validate comune_id exists in our data
                    comune_data = comuni_data[comuni_data['codice'] == comune_id]
                    if comune_data.empty:
                        continue
                    
                    # Check if the comune is already assigned to another agent
                    existing_assignment = models.Assignment.query.filter_by(comune_id=comune_id).first()
                    if existing_assignment and existing_assignment.agent_id != existing_agent.id:
                        comune_name = comune_data.iloc[0]['comune']
                        flash(f'Il comune {comune_name} è già assegnato a un altro agente', 'warning')
                        continue
                    
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
            for comune_id in comune_ids:
                # Validate comune_id exists in our data
                comune_data = comuni_data[comuni_data['codice'] == comune_id]
                if comune_data.empty:
                    continue
                
                # Check if the comune is already assigned to another agent
                existing_assignment = models.Assignment.query.filter_by(comune_id=comune_id).first()
                if existing_assignment:
                    comune_name = comune_data.iloc[0]['comune']
                    flash(f'Il comune {comune_name} è già assegnato a un altro agente', 'warning')
                    continue
                
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

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
