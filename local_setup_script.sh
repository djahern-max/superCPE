#!/bin/bash

echo "=== Setting up clean local migration ==="

# Clean up any existing migration files
echo "1. Cleaning up existing migration files..."
rm -rf alembic/versions/*
echo "✓ Cleared versions directory"

# Create initial migration
echo "2. Creating initial migration..."
alembic revision --autogenerate -m "Initial migration with all tables"

# Apply migration to local database
echo "3. Applying migration to local database..."
alembic upgrade head

# Verify tables were created
echo "4. Verifying tables were created..."
alembic current

echo "=== Local setup complete! ==="
