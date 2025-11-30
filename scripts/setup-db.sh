#!/bin/bash
# Setup script for BENCHCOM PostgreSQL database
# Run this on your production server to initialize the database

set -e

# Load .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Defaults
POSTGRES_USER="${POSTGRES_USER:-benchcom}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-benchcom}"
POSTGRES_DB="${POSTGRES_DB:-benchcom}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

echo "BENCHCOM Database Setup"
echo "======================="
echo "Host: $POSTGRES_HOST:$POSTGRES_PORT"
echo "Database: $POSTGRES_DB"
echo "User: $POSTGRES_USER"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "Error: psql not found. Install postgresql-client."
    exit 1
fi

# Check connection
echo "Testing connection..."
if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" > /dev/null 2>&1; then
    echo ""
    echo "Cannot connect. You may need to create the database first:"
    echo ""
    echo "  sudo -u postgres psql"
    echo "  CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';"
    echo "  CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"
    echo "  \\q"
    echo ""
    exit 1
fi

echo "Connection OK"
echo ""

# Apply schema
echo "Applying schema..."
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f api/schema.sql

echo ""
echo "Database setup complete!"
