import click
from flask.cli import with_appcontext
from src.config.database import db, db_config

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
    db.session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {db_config.schema_name}"))
    db.session.commit()
    click.echo(f'Created {db_config.schema_name} schema.')

def init_app(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(init_db)
    app.cli.add_command(create_schema)
