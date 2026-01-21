#!/usr/bin/env bash

## Script to gracefully stop the application and its environment.
#
# Usage:
#   ./scripts/stop-app.sh [OPTIONS]
#
# Options:
#   --help       Display this help message.
#   --clean      Drop the database volume AND remove local files (DATA WILL BE LOST).

set -e

print_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help       Display this help message."
    echo "  --clean      Drop the database volume AND remove local files (DATA WILL BE LOST)."
}

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILES_DIR="${APP_DIR}/data/files"
TAILWIND_PID_FILE="/tmp/pyupload-tailwind.pid"
CLEAN_DB=false

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
        *)
            echo "Unknown option: $arg"
            print_help
            exit 1
            ;;
    esac
done

# Stop Tailwind watcher
if [ -f "$TAILWIND_PID_FILE" ]; then
    TAILWIND_PID=$(cat "$TAILWIND_PID_FILE")
    if kill -0 "$TAILWIND_PID" 2>/dev/null; then
        echo "Stopping Tailwind CSS watcher (PID: $TAILWIND_PID)..."
        kill "$TAILWIND_PID"
    fi
    rm "$TAILWIND_PID_FILE"
fi

echo "Stopping Docker services..."
docker compose --project-directory "$APP_DIR" stop

if [ "$CLEAN_DB" = true ]; then
    echo "Removing containers, volumes, and local files..."
    docker compose --project-directory "$APP_DIR" down --volumes
    if [ -d "$FILES_DIR" ]; then
        echo "Removing local files directory: $FILES_DIR"
        rm -rf "$FILES_DIR"
    fi
else
    # Just remove containers, keep volumes
    docker compose --project-directory "$APP_DIR" down
fi

echo "Environment stopped."
