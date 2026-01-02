#!/usr/bin/env bash

## Script to control startup of pre-requisites and the app itself.
#
# Usage:
#   ./scripts/start-app.sh [OPTIONS]
#
# Options:
#   --help       Display this help message.
#   --clean      Drop and recreate the database before starting.
#   --dev        Start only database in Docker and keep application server
#                local in development mode (with auto-reload).
#   --db-only    Only start the database container.
#   --restart    Stop and restart the application if it's already running.
#   --seed       Seed the database and filesystem with example data.

set -e

print_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help       Display this help message."
    echo "  --clean      Drop and recreate the database before starting."
    echo "  --dev        Start only database in Docker and keep application server"
    echo "               local in development mode (with auto-reload)."
    echo "  --db-only    Only start the database container."
    echo "  --restart    Stop and restart the application if it's already running."
    echo "  --seed       Seed the database and filesystem with example data."
}

# Common variables
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="${APP_DIR}/scripts"
FILES_DIR="${APP_DIR}/data/files"

# Default options
CLEAN_DB=false
DEV_MODE=false
DB_ONLY=false
SEED_DB=false

# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --help)
            print_help
            exit 0
            ;;
        --clean)
            CLEAN_DB=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --db-only)
            DB_ONLY=true
            shift
            ;;
        --restart)
            "$SCRIPT_DIR/stop-app.sh"
            exec "$0" "$@"
            ;;
        --seed)
            SEED_DB=true
            shift
            ;;
        *)
            echo "Unknown option: $arg"
            print_help
            exit 1
            ;;
    esac
done

# Check minimum config is defined
check_config() {
    echo "Checking application configuration..."
    if [ ! -f "${APP_DIR}/.env" ]; then
        cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
        echo "Created default .env file from example."
    fi
}

# Check prerequisites are available
check_prerequisites() {
    echo "Checking prerequisites..."
    if ! command -v docker &> /dev/null; then
        echo "Error: Docker is not installed."
        exit 1
    fi
    # Use uv if available, otherwise fallback checks could go here
    if ! command -v uv &> /dev/null; then
        echo "Warning: 'uv' not found. Ensure you have a python environment manager."
    fi
}

start_database() {
    echo "Starting database in Docker..."

    if [ "$CLEAN_DB" = true ]; then
        echo "Cleaning database volume and local files..."
        docker compose --project-directory "$APP_DIR" down --volumes
        rm -rf "$FILES_DIR"
    fi

    # Ensure files directory exists
    if [ ! -d "$FILES_DIR" ]; then
        mkdir -p "$FILES_DIR"
        echo "Created local files directory: $FILES_DIR"
    fi

    docker compose --project-directory "$APP_DIR" up -d db adminer
    
    # Wait for health check
    DB_CONTAINER=$(docker compose --project-directory "$APP_DIR" ps -q db)
    echo "Waiting for database to be ready..."
    until [ "$(docker inspect --format='{{.State.Health.Status}}' "$DB_CONTAINER")" == "healthy" ]; do
        sleep 2
        echo -n "."
    done
    echo " Database is ready."
}

# Initialise database and run migrations
initialise_database() {
    echo "Initialising database and running migrations..."

    # TODO: Support running in app container in prod mode
    aerich upgrade
}

seed_app() {
    if [ "$SEED_DB" = true ]; then
        echo "Seeding database and filesystem..."
        # Running the seeder script. Ensure dependencies are installed or env is active.
        uv run python -m app.lib.seeder
    fi
}

start_app() {
    # If using 'uv'
    if [ "$DEV_MODE" = true ]; then
        echo "Starting FastAPI app in development mode..."
        # Assuming main.py exists and uvicorn is installed.
        # We use 'uv run' to ensure we are in the venv
        uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    else
         echo "Starting FastAPI app..."
         uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
    fi
}

run() {
    check_prerequisites
    check_config
    start_database
    initialise_database

    seed_app

    if [ "$DB_ONLY" = false ]; then
        start_app
    fi
}

run
