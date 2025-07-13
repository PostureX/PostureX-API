# Database Migration Guide

This guide explains how to set up and use SQLAlchemy with Flask-Migrate for the PostureX API.

## Quick Setup

1. **Install dependencies:**
   ```bash
   pip install -r flask_requirements.txt
   ```

2. **Set up environment variables:**
   Copy `.env.example` to `.env` and configure your database settings:
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=your_database_name
   DB_USER=your_username
   DB_PASSWORD=your_password
   JWT_SECRET=your_secret_key
   ```

3. **Run the setup script:**
   ```bash
   python setup_database.py
   ```

## Manual Setup (Alternative)

If you prefer to set up manually:

1. **Create the database schema:**
   ```bash
   export FLASK_APP=app.py  # Linux/Mac
   set FLASK_APP=app.py     # Windows CMD
   $env:FLASK_APP="app.py"  # Windows PowerShell
   
   flask create-schema
   ```

2. **Initialize migrations:**
   ```bash
   flask db init
   ```

3. **Create initial migration:**
   ```bash
   flask db migrate -m "Initial migration"
   ```

4. **Apply migrations:**
   ```bash
   flask db upgrade
   ```

## Migration Workflow

### Creating New Migrations

When you modify models:

1. **Generate migration:**
   ```bash
   flask db migrate -m "Description of changes"
   ```

2. **Review the generated migration file** in `migrations/versions/`

3. **Apply the migration:**
   ```bash
   flask db upgrade
   ```

### Common Migration Commands

- **Show migration history:**
  ```bash
  flask db history
  ```

- **Show current migration:**
  ```bash
  flask db current
  ```

- **Rollback to previous migration:**
  ```bash
  flask db downgrade
  ```

- **Rollback to specific migration:**
  ```bash
  flask db downgrade <revision_id>
  ```

- **Upgrade to specific migration:**
  ```bash
  flask db upgrade <revision_id>
  ```

## Model Changes

### User Model
- Converted from dataclass to SQLAlchemy model
- Added relationship to Analysis model
- Uses `spfposture.users` table

### Analysis Model  
- Converted from dataclass to SQLAlchemy model
- Added foreign key relationship to User
- Uses `spfposture.analysis` table

## Database Schema

```sql
-- Schema
CREATE SCHEMA IF NOT EXISTS spfposture;

-- Users table
CREATE TABLE spfposture.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analysis table
CREATE TABLE spfposture.analysis (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES spfposture.users(id),
    video_url TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Benefits of SQLAlchemy Migration

1. **Version Control**: Database schema changes are tracked
2. **Team Collaboration**: Easy to sync database changes across team
3. **Rollback Capability**: Can revert database changes if needed
4. **Production Safety**: Controlled deployment of schema changes
5. **ORM Benefits**: Type safety, relationships, query builders

## Troubleshooting

### Migration Issues

1. **"Target database is not up to date"**
   ```bash
   flask db stamp head
   ```

2. **Migration conflicts**
   ```bash
   flask db merge <revision1> <revision2>
   ```

3. **Reset migrations (DANGER - will lose data)**
   ```bash
   rm -rf migrations/
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

### Database Connection Issues

1. Check your `.env` file configuration
2. Ensure PostgreSQL is running
3. Verify database credentials
4. Check if the database exists

### Common Errors

- **"relation does not exist"**: Run `flask create-schema` then `flask db upgrade`
- **"column does not exist"**: Check if migrations were applied: `flask db current`
- **Import errors**: Ensure all models are imported in `src/models/__init__.py`

## Development Workflow

1. Make changes to models in `src/models/`
2. Generate migration: `flask db migrate -m "Description"`
3. Review migration file in `migrations/versions/`
4. Apply migration: `flask db upgrade`
5. Test your changes
6. Commit migration files to version control

## Production Deployment

1. **Backup database** before applying migrations
2. **Test migrations** on staging environment first
3. **Apply migrations** during maintenance window:
   ```bash
   flask db upgrade
   ```
4. **Verify** application functionality
5. **Rollback plan** ready: `flask db downgrade`

## Files Modified

- `src/config/database.py` - SQLAlchemy configuration
- `src/config/app_config.py` - Added database config
- `src/models/user.py` - SQLAlchemy User model
- `src/models/analysis.py` - SQLAlchemy Analysis model  
- `src/controllers/auth_controller.py` - Updated to use ORM
- `src/controllers/analysis_controller.py` - Updated to use ORM
- `src/__init__.py` - Initialize SQLAlchemy and migrations
- `src/cli.py` - CLI commands for database setup
- `flask_requirements.txt` - Added SQLAlchemy and migration dependencies
