import click
from flask.cli import with_appcontext
from .config.database import db
from .models import User, Analysis

@click.command()
@with_appcontext
def init_db():
    """Initialize the database."""
    db.create_all()
    click.echo('Initialized the database.')

@click.command()
@with_appcontext
def create_schema():
    """Create the spfposture schema."""
    from sqlalchemy import text
    
    # Create schema if it doesn't exist
    db.session.execute(text("CREATE SCHEMA IF NOT EXISTS spfposture"))
    db.session.commit()
    click.echo('Created spfposture schema.')

def init_app(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(init_db)
    app.cli.add_command(create_schema)
