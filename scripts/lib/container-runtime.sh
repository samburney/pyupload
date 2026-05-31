# shellcheck shell=bash
# Sourced by start-app.sh and stop-app.sh. Do not execute directly.
#
# Exports:
#   DOCKER_CMD            — "podman" or "docker"
#   DOCKER_COMPOSE_CMD    — bash array, e.g. (podman compose) or (docker compose)
#                           Expand as: "${DOCKER_COMPOSE_CMD[@]}"

detect_container_runtime() {
    if command -v podman &> /dev/null && podman compose version &> /dev/null; then
        DOCKER_CMD="podman"
        DOCKER_COMPOSE_CMD=(podman compose)
    elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
        DOCKER_CMD="docker"
        DOCKER_COMPOSE_CMD=(docker compose)
    else
        echo "Error: Neither docker nor podman with a valid compose provider (e.g., podman-compose) is installed and functional."
        exit 1
    fi
}
