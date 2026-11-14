#!/bin/sh
# Create the Hermes profile that directs hn.fm's story videos, and hand its
# key to hn.fm. Safe to run again: it keeps an existing profile and key.
#
#   deploy/hermes-profile.sh [hermes-namespace] [hnfm-namespace]
#
# What it makes:
#   - a Hermes profile `hnfm` with NO tools, its own API key, and the LOCAL
#     Nemotron 3.5 Lightning (spark, via LiteLLM) with thinking turned off;
#   - the `hnfm-video` skill, read-only, in that profile and in the default
#     one (for use by hand);
#   - a secret `hnfm-hermes` (key HERMES_API_KEY) in the hn.fm namespace.
#
# WARNING. Never run `hermes -p hnfm gateway run` inside the pod. The one
# gateway process already serves every profile; starting a second one for
# this profile takes the port and puts the main agent's API offline until
# that process is stopped (`s6-svc -d /run/hermes-service/gateway-hnfm`).
# The profile is picked up by itself within a minute of being created.
set -eu

HERMES_NS="${1:-hermes}"
HNFM_NS="${2:-hnfm}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
IN="kubectl -n $HERMES_NS exec -i deploy/hermes -c hermes --"
AS="runuser -u hermes -- env HOME=/opt/data HERMES_HOME=/opt/data"
P=/opt/data/profiles/hnfm

echo "1/5 profile"
$IN sh -c "[ -d $P ] && echo '  exists' || $AS hermes profile create hnfm --no-skills --no-alias \
  --description 'Directs hn.fm story videos. No tools.' 2>&1 | grep -i 'created'"

echo "2/5 config: no tools, thinking off"
$IN $AS /opt/hermes/.venv/bin/python3 - <<'PY'
import os, re, secrets
p = "/opt/data/profiles/hnfm"
OFF = ["skills", "web", "browser", "terminal", "file", "code_execution", "vision", "video", "image_gen",
       "video_gen", "x_search", "tts", "stt", "todo", "kanban", "memory", "context_engine", "session_search",
       "connections", "clarify", "delegation", "cronjob", "discord", "discord_admin", "yuanbao", "computer_use", "a2a"]
MODEL = "nemotron-lightning"
cfg = f"""model:
  default: {MODEL}
  provider: custom:local-lightning
providers:
  # Nemotron 3.5 Lightning on the spark box, through the LiteLLM gateway's
  # local-only route (no fallbacks there, so it cannot quietly become a cloud
  # model). Nothing this profile does leaves the home lab. Asked not to think:
  # with thinking on a card takes minutes, off it takes seconds.
  local-lightning:
    api: http://litellm.observability.svc.cluster.local:4000/v1
    key_env: LITELLM_API_KEY
    transport: chat_completions
    default_model: {MODEL}
    models:
      {MODEL}:
        context_length: 81920
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
fallback_providers: []
platform_toolsets:
  api_server: []
  cli: []
agent:
  disabled_toolsets:
""" + "".join(f"    - {t}\n" for t in OFF) + """  max_turns: 4
memory:
  enabled: false
"""
old = open(p + "/config.yaml").read()
version = re.search(r"^_config_version:.*$", old, re.M)
open(p + "/config.yaml", "w").write(cfg + (version.group(0) + "\n" if version else ""))

def read(path):
    out = {}
    try:
        for line in open(path):
            m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
            if m:
                out[m.group(1)] = m.group(2)
    except FileNotFoundError:
        pass
    return out

mine = read(p + "/.env")
# No cloud key in this profile: drop one left by an older version. A profile
# reads keys only from its own .env, so the gateway key the pod already holds
# (LITELLM_API_KEY, from the hermes secret) is copied in.
mine.pop("NVIDIA_API_KEY", None)
if os.environ.get("LITELLM_API_KEY"):
    mine["LITELLM_API_KEY"] = os.environ["LITELLM_API_KEY"]
else:
    raise SystemExit("LITELLM_API_KEY is not in the hermes pod's environment")
mine.setdefault("API_SERVER_KEY", secrets.token_urlsafe(36))
with open(p + "/.env", "w") as f:
    f.write("# Per-profile secrets for the hnfm profile.\n")
    for k, v in mine.items():
        f.write(f"{k}={v}\n")
os.chmod(p + "/.env", 0o600)
print("  written; keys held:", ", ".join(mine))
PY

echo "3/5 skills (hnfm-video: the text card; hnfm-shots: the shot plan)"
for dest in "$P/skills" /opt/data/skills; do
  $IN sh -c "mkdir -p $dest/hnfm-video && chmod -R u+w $dest/hnfm-video && cat > $dest/hnfm-video/SKILL.md" \
    < "$HERE/src/hnfm/hyperframes/skill/SKILL.md"
  $IN sh -c "mkdir -p $dest/hnfm-shots && chmod -R u+w $dest/hnfm-shots && cat > $dest/hnfm-shots/SKILL.md" \
    < "$HERE/src/hnfm/hyperframes/skill/SHOTS.md"
done
# The profile cannot change its own skill: owned by root, not writable.
$IN sh -c "chown -R root:root $P/skills && chmod -R a-w,a+rX $P/skills && chown -R hermes:hermes /opt/data/skills/hnfm-video /opt/data/skills/hnfm-shots"

echo "4/5 secret in $HNFM_NS"
$IN sh -c "grep ^API_SERVER_KEY= $P/.env | cut -d= -f2 | tr -d '\n'" \
  | kubectl -n "$HNFM_NS" create secret generic hnfm-hermes --from-file=HERMES_API_KEY=/dev/stdin \
      --dry-run=client -o yaml | kubectl apply -f - >/dev/null
echo "  hnfm-hermes applied"

echo "5/5 check (the gateway re-reads profiles within a minute)"
sleep 20
$IN sh -c "K=\$(grep ^API_SERVER_KEY= $P/.env | cut -d= -f2); \
  echo \"  profile key on its own route: \$(curl -s -m 8 -o /dev/null -w '%{http_code}' -H \"Authorization: Bearer \$K\" localhost:8642/p/hnfm/v1/models)\"; \
  echo \"  profile key on the main route: \$(curl -s -m 8 -o /dev/null -w '%{http_code}' -H \"Authorization: Bearer \$K\" localhost:8642/v1/models) (401 is right)\"; \
  echo \"  main key on the profile route: \$(curl -s -m 8 -o /dev/null -w '%{http_code}' -H \"Authorization: Bearer \$API_SERVER_KEY\" localhost:8642/p/hnfm/v1/models) (401 is right)\""
