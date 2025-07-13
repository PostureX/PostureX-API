#!/usr/bin/env python3
"""
Database setup and migration script for PostureX API

This script helps with:
1. Installing dependencies
2. Setting up the database schema
3. Running initial migrations
4. Creating sample data (optional)
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a shell command and handle errors."""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(e.stderr)
        return False

def main():
    """Main setup function."""
    print("PostureX API Database Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("flask_requirements.txt").exists():
        print("Error: flask_requirements.txt not found. Please run this script from the project root.")
        sys.exit(1)
    
    # Install dependencies
    if not run_command("pip install -r flask_requirements.txt", "Installing dependencies"):
        print("Failed to install dependencies. Please check your pip installation.")
        sys.exit(1)
    
    # Check if .env file exists
    if not Path(".env").exists():
        print("Warning: .env file not found. Please create one based on .env.example")
        if Path(".env.example").exists():
            print("📋 Example .env file contents:")
            with open(".env.example", "r") as f:
                print(f.read())
    
    # Set FLASK_APP environment variable
    os.environ["FLASK_APP"] = "app.py"
    
    # Create schema
    if not run_command("flask create-schema", "Creating database schema"):
        print("Schema creation failed. The schema might already exist.")
    
    # Initialize migration repository
    if not Path("migrations").exists():
        if not run_command("flask db init", "Initializing migration repository"):
            print("Failed to initialize migration repository")
            sys.exit(1)
    else:
        print("Migration repository already exists")
    
    # Create initial migration
    if not run_command("flask db migrate -m 'Initial migration'", "Creating initial migration"):
        print("Migration creation failed. There might be no changes to migrate.")
    
    # Apply migrations
    if not run_command("flask db upgrade", "Applying migrations"):
        print("Failed to apply migrations")
        sys.exit(1)
    
    print("\nDatabase setup completed successfully!")
    print("\nNext steps:")
    print("1. Ensure your .env file is properly configured")
    print("2. Start the Flask development server: python app.py")
    print("3. Test the API endpoints")
    
    print("\nUseful commands:")
    print("- Create new migration: flask db migrate -m 'Description'")
    print("- Apply migrations: flask db upgrade")
    print("- Rollback migration: flask db downgrade")
    print("- Initialize database: flask init-db")

if __name__ == "__main__":
    main()
