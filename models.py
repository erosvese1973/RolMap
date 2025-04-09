from datetime import datetime
from database import db

class Agent(db.Model):
    """Model for sales agents"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)  # Numero di cellulare
    email = db.Column(db.String(100), nullable=True)  # Indirizzo email
    registration_date = db.Column(db.DateTime, default=datetime.now)
    color = db.Column(db.String(20), default='#ff9800')  # Colore predefinito arancione
    assignments = db.relationship('Assignment', backref='agent', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Agent {self.name}>'

class Assignment(db.Model):
    """Model for agent-municipality assignments"""
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=False)
    comune_id = db.Column(db.String(20), nullable=False, index=True)
    assignment_date = db.Column(db.DateTime, default=datetime.now)
    
    # Ensure each municipality is assigned to only one agent
    __table_args__ = (db.UniqueConstraint('comune_id'),)
    
    def __repr__(self):
        return f'<Assignment {self.agent_id}:{self.comune_id}>'
