#!/bin/sh
# Prove that every model hn.fm uses runs on the home lab's own hardware.
#
#   deploy/check-local-inference.sh [hnfm-namespace] [hermes-namespace]
#
# Read-only except for one short Hermes turn ("ready") at the end. Prints one
# line per check and exits non-zero if any check fails, so it can gate a
# deploy or run on a schedule.
#
# What it checks:
#   1. hn.fm's own model settings: every *_BASE_URL is an in-cluster service,
#      and the LLM routes it names are local gateway routes.
#   2. The LiteLLM gateway: each route hn.fm (and its Hermes profile) uses has
#      only in-cluster deployments, and no fallback list names it.
#   3. The Hermes `hnfm` profile: its provider is the in-cluster gateway, its
#      model is the local route, it has no fallback providers and holds no
#      cloud key.
#   4. Live: one turn through the profile is answered, and the spark vLLM's
#      completed-request counter goes up while it is.
set -u

HNFM_NS="${1:-hnfm}"
HERMES_NS="${2:-hermes}"
LOCAL_ROUTES="nemotron-lightning"
fail=0
ok()  { printf '  ok    %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1"; fail=1; }

echo "1. hn.fm settings"
ENV=$(kubectl -n "$HNFM_NS" get cm hnfm-env -o go-template='{{range $k, $v := .data}}{{$k}}={{$v}}{{"\n"}}{{end}}')
for key in LLM_BASE_URL TTS_BASE_URL IMAGE_GENERATION_BASE_URL ASR_BASE_URL ACESTEP_BASE_URL \
           FIRECRAWL_BASE_URL HERMES_BASE_URL HYPERFRAMES_BASE_URL; do
  url=$(printf '%s\n' "$ENV" | sed -n "s/^$key=//p")
  [ -z "$url" ] && continue
  host=$(printf '%s' "$url" | sed -E 's#^[a-z]+://([^/:]+).*#\1#')
  case "$host" in
    *.svc.cluster.local|*.svc|hnfm-*) ok "$key -> $host" ;;
    *) bad "$key points outside the cluster: $host" ;;
  esac
done
for key in LLM_MODEL TRIAGE_LLM_MODEL LLM_VISION_MODEL; do
  m=$(printf '%s\n' "$ENV" | sed -n "s/^$key=//p")
  [ -z "$m" ] && continue
  case " $LOCAL_ROUTES " in
    *" $m "*) ok "$key = $m" ;;
    *) bad "$key = $m is not a known local route ($LOCAL_ROUTES)" ;;
  esac
done

echo "2. LiteLLM routes"
INFO=$(kubectl -n "$HERMES_NS" exec deploy/hermes -c hermes -- sh -c \
  'curl -s -m 20 http://litellm.observability.svc.cluster.local:4000/v1/model/info -H "Authorization: Bearer $LITELLM_API_KEY"')
CFG=$(kubectl -n observability get cm litellm-config -o go-template='{{index .data "config.yaml"}}')
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
for route in $LOCAL_ROUTES; do
  printf '%s' "$INFO" | ROUTE="$route" python3 -c '
import json, os, sys
rows = [m for m in json.load(sys.stdin).get("data", []) if m.get("model_name") == os.environ["ROUTE"]]
if not rows:
    print("none"); sys.exit()
for m in rows:
    print((m.get("litellm_params") or {}).get("api_base") or "no-api-base")
' > "$TMP"
  while read -r base; do
    case "$base" in
      http://*.svc.cluster.local:*) ok "$route -> $base" ;;
      *) bad "$route has a deployment outside the cluster: $base" ;;
    esac
  done < "$TMP"
  if printf '%s\n' "$CFG" | sed -n '/^router_settings:/,/^[a-z]/p' | grep -E "^\s+- *$route:" >/dev/null; then
    bad "$route has gateway fallbacks (could leave the lab)"
  else
    ok "$route has no gateway fallbacks"
  fi
done

echo "3. Hermes profile hnfm"
PCFG=$(kubectl -n "$HERMES_NS" exec deploy/hermes -c hermes -- cat /opt/data/profiles/hnfm/config.yaml)
api=$(printf '%s\n' "$PCFG" | sed -n 's/^    api: *//p' | head -1)
model=$(printf '%s\n' "$PCFG" | sed -n '/^model:/,/^[a-z]/s/^  default: *//p' | head -1)
case "$api" in http://*.svc.cluster.local:*) ok "provider -> $api" ;; *) bad "provider is not in-cluster: $api" ;; esac
case " $LOCAL_ROUTES " in *" $model "*) ok "model = $model" ;; *) bad "model = $model is not local" ;; esac
printf '%s\n' "$PCFG" | grep -qE '^fallback_providers: *\[\]' && ok "no fallback providers" || bad "fallback providers are set"
keys=$(kubectl -n "$HERMES_NS" exec deploy/hermes -c hermes -- sh -c "cut -d= -f1 /opt/data/profiles/hnfm/.env | grep -v '^#'" | tr '\n' ' ')
case "$keys" in *NVIDIA*|*OPENAI*|*ANTHROPIC*|*GROQ*|*OPENROUTER*) bad "profile holds a cloud key: $keys" ;; *) ok "profile keys: $keys" ;; esac

echo "4. live turn"
count() {
  kubectl -n inference-club exec deploy/spark-llm -- python3 -c '
import urllib.request
t = sum(float(l.split()[-1]) for l in urllib.request.urlopen("http://localhost:8000/metrics").read().decode().splitlines()
        if l.startswith("vllm:request_success_total"))
print(int(t))' 2>/dev/null
}
before=$(count)
reply=$(kubectl -n "$HNFM_NS" exec deploy/hnfm-worker-render -- python3 -c '
from hnfm.hyperframes import hermes
print(hermes.ask("Reply with the single word: ready", timeout=120)["text"].strip()[:40])' 2>&1 | tail -1)
after=$(count)
case "$reply" in *eady*) ok "profile answered: $reply" ;; *) bad "profile did not answer: $reply" ;; esac
if [ -n "$before" ] && [ -n "$after" ] && [ "$after" -gt "$before" ]; then
  ok "spark vLLM served it (completed requests $before -> $after)"
else
  bad "spark vLLM count did not move ($before -> $after)"
fi

[ "$fail" = 0 ] && echo "PASS: all inference is local" || echo "FAIL: see above"
exit "$fail"
