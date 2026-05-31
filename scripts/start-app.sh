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
# shellcheck source=lib/container-runtime.sh
source "${SCRIPT_DIR}/lib/container-runtime.sh"
FILES_DIR="${APP_DIR}/data/files"
TAILWIND_PID_FILE="/tmp/pyupload-tailwind.pid"

# Default options
CLEAN_DB=false
DEV_MODE=false
DB_ONLY=false
SEED_DB=false
TAILWIND_PID=""
CONTAINERS_STARTED=false

cleanup() {
    local exit_code=$?
    [ $exit_code -eq 0 ] && return
    echo ""
    echo "Startup failed. Cleaning up..."
    if [ -n "$TAILWIND_PID" ] && kill -0 "$TAILWIND_PID" 2>/dev/null; then
        echo "Stopping Tailwind CSS watcher..."
        kill "$TAILWIND_PID" 2>/dev/null || true
        rm -f "$TAILWIND_PID_FILE"
    fi
    if [ "$CONTAINERS_STARTED" = true ]; then
        echo "Stopping containers..."
        "${DOCKER_COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yaml" stop 2>/dev/null || true
    fi
}
trap cleanup EXIT

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
    detect_container_runtime
    export COMPOSE_PROJECT_NAME="$(basename "$APP_DIR")"
    if ! command -v uv &> /dev/null; then
        echo "Error: 'uv' is required but not installed. See https://docs.astral.sh/uv/"
        exit 1
    fi

    # Check for Node/npm for Tailwind CSS
    if ! command -v npm &> /dev/null; then
        echo "Error: npm is not installed. Required for Tailwind CSS."
        exit 1
    fi

    # Check for Python virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        # Check for local venv directory
        if [ -d "${APP_DIR}/.venv" ]; then
            source "${APP_DIR}/.venv/bin/activate"
            echo "Activated local virtual environment."
        else
            echo "Python virtual environment is not activated. Please activate it to proceed."
            exit 1
        fi
    fi

    echo "Checking Python dependencies..."
    if [ "$DEV_MODE" = true ]; then
        uv sync --frozen --all-extras
    else
        uv sync --frozen
    fi
}

start_database() {
    echo "Starting database container..."

    if [ "$CLEAN_DB" = true ]; then
        echo "Cleaning database volume and local files..."
        "${DOCKER_COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yaml" down --volumes
        rm -rf "$FILES_DIR"
    fi

    # Ensure files directory exists
    if [ ! -d "$FILES_DIR" ]; then
        mkdir -p "$FILES_DIR"
        echo "Created local files directory: $FILES_DIR"
    fi

    # Track whether containers were already running so cleanup only stops what we started
    if [ "$DOCKER_CMD" = "podman" ]; then
        _running=$($DOCKER_CMD ps \
            --filter label=com.docker.compose.project="${COMPOSE_PROJECT_NAME}" \
            --filter label=com.docker.compose.service=db \
            --format '{{.ID}}')
    else
        _running=$("${DOCKER_COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yaml" ps -q db 2>/dev/null || true)
    fi
    [ -z "$_running" ] && CONTAINERS_STARTED=true

    "${DOCKER_COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yaml" up -d db adminer

    # Wait for health check
    if [ "$DOCKER_CMD" = "podman" ]; then
        # podman ps with label filter is reliable; avoids parsing compose ps table output
        DB_CONTAINER=$($DOCKER_CMD ps \
            --filter label=com.docker.compose.project="${COMPOSE_PROJECT_NAME}" \
            --filter label=com.docker.compose.service=db \
            --format '{{.ID}}' | head -1)
    else
        DB_CONTAINER=$("${DOCKER_COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yaml" ps -q db)
    fi
    if [ -z "$DB_CONTAINER" ]; then
        echo "Error: Could not find database container."
        exit 1
    fi
    echo "Waiting for database to be ready..."
    MAX_WAIT=120
    ELAPSED=0
    while true; do
        health=$($DOCKER_CMD inspect --format='{{.State.Health.Status}}' "$DB_CONTAINER" 2>/dev/null) || {
            echo ""
            echo "Error: Could not inspect database container (it may have crashed)."
            exit 1
        }
        [ "$health" = "healthy" ] && break
        sleep 2
        ELAPSED=$((ELAPSED + 2))
        if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
            echo ""
            echo "Error: Timed out waiting for database to become healthy after ${MAX_WAIT}s."
            exit 1
        fi
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

start_css_watcher() {
    echo "Installing/updating Node dependencies..."
    cd "$APP_DIR"
    npm install --silent

    # Stop any existing watcher
    if [ -f "$TAILWIND_PID_FILE" ]; then
        OLD_PID=$(cat "$TAILWIND_PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "Stopping existing Tailwind watcher (PID: $OLD_PID)..."
            kill "$OLD_PID"
        fi
        rm "$TAILWIND_PID_FILE"
    fi

    echo "Starting Tailwind CSS watcher..."
    npm run watch:css &
    TAILWIND_PID=$!
    echo $TAILWIND_PID > "$TAILWIND_PID_FILE"
    echo "Tailwind CSS watcher started (PID: $TAILWIND_PID)"
}

start_app() {
    if [ "$DEV_MODE" = true ]; then
        echo "Starting application in development mode with auto-reload..."
        APP_RELOAD="${DEV_MODE}" python -m app.main
    else
        # TODO: Support running in app container in prod mode
        echo "Starting application..."
        APP_RELOAD="${DEV_MODE}" python -m app.main
    fi
}

run() {
    check_prerequisites
    check_config
    start_css_watcher
    start_database
    initialise_database

    seed_app

    if [ "$DB_ONLY" = false ]; then
        start_app
    fi
}

run
