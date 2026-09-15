#!/bin/sh
# CorridorComply on this machine, one command at a time.
#   scripts/shadow_run.sh install      build the image with today's lists, create .env, start, open the browser
#   scripts/shadow_run.sh start|stop|status|logs
#   scripts/shadow_run.sh update       refresh the lists inside the container and re-screen customers on file
#   scripts/shadow_run.sh reset        stop, move ./cc-data aside (keeps a timestamped copy), start clean
# Needs Docker Desktop (Mac/Windows) or Docker Engine (Linux).
set -e
cd "$(dirname "$0")/.."
PORT=8010
URL="http://127.0.0.1:$PORT/screen"

need_docker() { command -v docker >/dev/null 2>&1 || { echo "Docker is not installed. Install Docker Desktop first: https://docs.docker.com/desktop/"; exit 1; }; docker info >/dev/null 2>&1 || { echo "Docker is installed but not running. Start Docker Desktop and try again."; exit 1; }; }
make_env() {
  if [ ! -f .env ]; then
    PW=$(python3 -c "import secrets;print(secrets.token_urlsafe(12))" 2>/dev/null || date +%s | sha256sum | cut -c1-16)
    KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))" 2>/dev/null || date +%N | sha256sum | cut -c1-32)
    sed -e "s/^UI_PASSWORD=.*/UI_PASSWORD=$PW/" -e "s/^API_KEYS=.*/API_KEYS=default:$KEY/" deploy/.env.example > .env
    echo "Created .env with login compliance / $PW  (kept in .env; change it there)"
  fi
}
open_browser() { sleep 2; (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || (command -v start >/dev/null && start "$URL") || echo "Open $URL"; }
wait_healthy() { i=0; until curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 60 ] && { echo "The service did not come up; see: scripts/shadow_run.sh logs"; exit 1; }; sleep 2; done; }

case "${1:-}" in
  install)
    need_docker; make_env
    echo "Building the image with today's sanctions lists (a few minutes, needs internet once)..."
    docker compose build
    docker compose up -d
    wait_healthy
    echo "Running at $URL  (login is in .env). Internet can be switched off now."
    open_browser ;;
  start)  need_docker; make_env; docker compose up -d; wait_healthy; echo "Running at $URL"; open_browser ;;
  stop)   need_docker; docker compose down ;;
  status) need_docker; docker compose ps; curl -fs "http://127.0.0.1:$PORT/health" && echo " (healthy)" || echo "not responding" ;;
  logs)   need_docker; docker compose logs --tail=200 -f ;;
  update) need_docker; docker compose exec corridorcomply python scripts/update_sanctions.py; docker compose exec corridorcomply python -m app.monitoring rescreen; echo "Lists refreshed; customers on file re-screened. Check /alerts." ;;
  reset)  need_docker; docker compose down; [ -d cc-data ] && mv cc-data "cc-data.$(date +%Y%m%d-%H%M%S)"; docker compose up -d; wait_healthy; echo "Clean start at $URL" ;;
  *) sed -n 2,8p "$0"; exit 1 ;;
esac
