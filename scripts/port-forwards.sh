#!/usr/bin/env bash
# Start (and keep alive) the kubectl port-forwards hn.fm needs to reach the
# inference-club cluster services from the local docker stack.
#
#   ./scripts/port-forwards.sh          # start once
#   ./scripts/port-forwards.sh --watch  # start + auto-restart any that die
#
# Local port -> svc:port (matches .env host.docker.internal:<local> values):
#   ltx2 8023, flux2-klein 8500->8000, acestep 8015, nemotron-asr 8105,
#   magpie-tts 9000, firecrawl 3022->3002
# NOTE firecrawl uses 3022 (a stray process squats 127.0.0.1:3002).
set -u
NS=inference-club

# svc local remote  (one per line)
SERVICES="
ltx2 8023 8023
flux2-klein 8500 8000
acestep 8015 8015
nemotron-asr 8105 8105
magpie-tts 9000 9000
firecrawl 3022 3002
"

start_one() {
  local svc=$1 local_port=$2 remote=$3
  # already listening?
  if nc -z localhost "$local_port" 2>/dev/null; then return 0; fi
  echo "  ↻ port-forward $svc $local_port:$remote"
  nohup kubectl port-forward -n "$NS" "svc/$svc" "$local_port:$remote" \
    >"/tmp/pf-$svc.log" 2>&1 &
}

start_all() {
  echo "$SERVICES" | while read -r svc lp rp; do
    [ -z "$svc" ] && continue
    start_one "$svc" "$lp" "$rp"
  done
}

start_all
sleep 4

if [ "${1:-}" = "--watch" ]; then
  echo "watching (restart-on-death every 20s); Ctrl-C to stop"
  while true; do sleep 20; start_all; done
fi
echo "done — check health with: curl -s localhost:8023/health"
