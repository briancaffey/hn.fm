#!/usr/bin/env bash
# One-time wiring for the hn.fm GitOps loop. Run from the Mac (kubectl + git
# creds for forgejo.lan). Safe to re-run: every step is create-or-already-exists.
#
#   1. Harbor robot with push/pull on the `apps` project
#   2. Forgejo access token (write:repository — pushes the tag bump to home-lab)
#   3. Public Forgejo repo brian/hn.fm + `forgejo` git remote here
#   4. Actions secrets on that repo (HARBOR_ROBOT_USER/TOKEN, DEPLOY_REPO_TOKEN)
#   5. Push webhook → Argo CD so syncs are instant instead of ~3 min polls
#   6. Push main to Forgejo (this is what fires the first build)
#
# Not done here (see deploy/README.md): the Vaultwarden item hnfm-hnfm-secrets,
# the hnfm.lan TLS secret, and the home-lab commit that registers the Argo app.
set -euo pipefail

HARBOR="https://harbor.lan"
FORGEJO="https://forgejo.lan"
OWNER="brian"
REPO="hn.fm"
DEPLOY_REPO="home-lab"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
jsonval(){ python3 -c 'import sys,json;print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }

say "1/6  Harbor robot (push+pull on the 'apps' project)"
read -rsp "    Harbor admin password: " ADMIN_PW; echo
CODE=$(curl -sk -u "admin:${ADMIN_PW}" "${HARBOR}/api/v2.0/users/current" -o /dev/null -w '%{http_code}')
[ "$CODE" = "200" ] || { echo "    ERROR: Harbor admin auth failed (HTTP ${CODE})"; exit 1; }
# Retire earlier hnfm-ci robots so they don't pile up; the unique name below
# is what actually prevents a CONFLICT.
for LIST in "${HARBOR}/api/v2.0/robots?page_size=100" "${HARBOR}/api/v2.0/projects/apps/robots?page_size=100"; do
  for RID in $(curl -sk -u "admin:${ADMIN_PW}" "$LIST" 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
if not isinstance(d,list): d=[]
[print(r["id"]) for r in d if "hnfm-ci" in str(r.get("name",""))]' 2>/dev/null); do
    curl -sk -u "admin:${ADMIN_PW}" -X DELETE "${HARBOR}/api/v2.0/robots/${RID}" -o /dev/null || true
  done
done
RNAME="hnfm-ci-${RANDOM}${RANDOM}"
BODY=$(printf '{"name":"%s","duration":-1,"level":"project","permissions":[{"kind":"project","namespace":"apps","access":[{"resource":"repository","action":"push"},{"resource":"repository","action":"pull"}]}]}' "$RNAME")
ROBOT=$(curl -sk -u "admin:${ADMIN_PW}" -X POST "${HARBOR}/api/v2.0/robots" -H 'Content-Type: application/json' -d "$BODY")
RUSER=$(printf '%s' "$ROBOT" | jsonval name 2>/dev/null || true)
RTOKEN=$(printf '%s' "$ROBOT" | jsonval secret 2>/dev/null || true)
[ -n "$RUSER" ] && [ -n "$RTOKEN" ] || { echo "    ERROR creating robot: ${ROBOT}"; exit 1; }
echo "    robot user: ${RUSER}"

say "2/6  Forgejo access token"
FJOUT=$(kubectl -n forgejo exec -i deploy/forgejo -- su git -c \
  "forgejo --config /data/gitea/conf/app.ini admin user generate-access-token --username ${OWNER} --token-name hnfm-ci-${RANDOM} --scopes write:repository,write:user --raw" 2>&1 | tr -d '\r')
FJ=$(printf '%s' "$FJOUT" | awk 'NF{t=$NF} END{print t}')
if [ -z "${FJ}" ] || printf '%s' "$FJOUT" | grep -qiE 'error|fail|usage|required|unknown|panic'; then
  echo "    ERROR minting Forgejo token:"; printf '    %s\n' "$FJOUT"; exit 1
fi
AUTH=(-H "Authorization: token ${FJ}")

say "3/6  Forgejo repo ${OWNER}/${REPO} (public) + local 'forgejo' remote"
RCODE=$(curl -sk -o /tmp/hnfm_repo.json -X POST "${FORGEJO}/api/v1/user/repos" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"${REPO}\",\"private\":false,\"default_branch\":\"main\",\"description\":\"hn.fm — Hacker News, watchable. Mirror of github.com/briancaffey/hn.fm; CI/CD source for the home cluster.\"}" \
  -w '%{http_code}')
case "$RCODE" in
  201) echo "    created" ;;
  409) echo "    already exists — fine" ;;
  *)   echo "    ERROR (HTTP ${RCODE}): $(cat /tmp/hnfm_repo.json)"; exit 1 ;;
esac
if ! git -C "$HERE" remote get-url forgejo >/dev/null 2>&1; then
  git -C "$HERE" remote add forgejo "${FORGEJO}/${OWNER}/${REPO}.git"
  echo "    added remote forgejo -> ${FORGEJO}/${OWNER}/${REPO}.git"
else
  echo "    remote forgejo already present"
fi

say "4/6  Actions secrets on ${OWNER}/${REPO}"
set_secret(){
  curl -sk -X PUT "${FORGEJO}/api/v1/repos/${OWNER}/${REPO}/actions/secrets/$1" "${AUTH[@]}" \
    -H 'Content-Type: application/json' \
    -d "$(python3 -c 'import json,sys;print(json.dumps({"data":sys.argv[1]}))' "$2")" \
    -o /dev/null -w "    $1 -> %{http_code}\n"
}
set_secret HARBOR_ROBOT_USER  "${RUSER}"
set_secret HARBOR_ROBOT_TOKEN "${RTOKEN}"
set_secret DEPLOY_REPO_TOKEN  "${FJ}"

say "5/6  Push webhook -> Argo CD"
ARGO_HOOK="http://argocd-server.argocd.svc.cluster.local/api/webhook"
if curl -sk "${FORGEJO}/api/v1/repos/${OWNER}/${REPO}/hooks" "${AUTH[@]}" | grep -q "$ARGO_HOOK"; then
  echo "    already present"
else
  curl -sk -X POST "${FORGEJO}/api/v1/repos/${OWNER}/${REPO}/hooks" "${AUTH[@]}" \
    -H 'Content-Type: application/json' \
    -d "{\"type\":\"forgejo\",\"active\":true,\"events\":[\"push\"],\"config\":{\"url\":\"${ARGO_HOOK}\",\"content_type\":\"json\"}}" \
    -o /dev/null -w "    webhook -> %{http_code}\n"
fi

say "6/6  Push main to Forgejo (fires the first build)"
git -C "$HERE" push -u forgejo main

say "DONE. Watch the run at ${FORGEJO}/${OWNER}/${REPO}/actions"
echo "    Then: Vaultwarden item hnfm-hnfm-secrets, lan-certs.sh for hnfm.lan, and the"
echo "    home-lab commit (clusters/home/argocd/apps/hnfm.yaml + clusters/home/hnfm/values.yaml)."
