#!/usr/bin/env bash
set -euo pipefail

PROFILE=${1:-smoke}
REPO=${TCZ1F_REPO:-quemanhmcr/bfm-5-modal-collar}
BRANCH=${TCZ1F_BRANCH:-research/tcz1f-action-grid}
WORKTREE=${TCZ1F_WORKTREE:-/root/projects/bfm-5-modal-collar-tcz1f}
ARTIFACT_ROOT=${TCZ1F_ARTIFACT_ROOT:-/root/bfm5-artifacts}
PURPOSE=${TCZ1F_PURPOSE:-remote-root-atlas}

case "$PROFILE" in
  smoke|pilot|connection_cross|coarse|dense_local) ;;
  *) echo "Unsupported profile: $PROFILE" >&2; exit 2 ;;
esac

command -v gh >/dev/null
command -v git >/dev/null
command -v python3 >/dev/null
gh auth status >/dev/null

gh auth setup-git
if [[ ! -d "$WORKTREE/.git" ]]; then
  mkdir -p "$(dirname "$WORKTREE")"
  git clone --branch "$BRANCH" --single-branch "https://github.com/$REPO.git" "$WORKTREE"
fi
cd "$WORKTREE"
git fetch origin "$BRANCH"
git switch "$BRANCH"
git reset --hard "origin/$BRANCH"

REQUEST_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(python3 - <<'PY'
import secrets
print(secrets.token_hex(4))
PY
)"
REQUESTED_AT="$(date -u +%FT%TZ)"
python3 - "$PROFILE" "$REQUEST_ID" "$REQUESTED_AT" "$PURPOSE" <<'PY'
from pathlib import Path
import sys, yaml
profile, request_id, requested_at, purpose = sys.argv[1:]
path = Path('fea/config/tcz1f_request.yml')
data = yaml.safe_load(path.read_text(encoding='utf-8'))
data.update({
    'profile': profile,
    'request_id': request_id,
    'requested_at_utc': requested_at,
    'requested_by': 'linux-mcp',
    'purpose': purpose,
})
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
PY

git add fea/config/tcz1f_request.yml
if git diff --cached --quiet; then
  echo "Request file did not change" >&2
  exit 3
fi
git commit -m "ci(fea): request TCZ-1F $PROFILE atlas [$REQUEST_ID]"
git push origin "$BRANCH"
SHA=$(git rev-parse HEAD)
echo "submitted_sha=$SHA request_id=$REQUEST_ID profile=$PROFILE"

RUN_ID=""
for _ in $(seq 1 30); do
  RUN_ID=$(gh run list --repo "$REPO" --branch "$BRANCH" --event push --limit 20 \
    --json databaseId,headSha,name --jq ".[] | select(.headSha == \"$SHA\" and .name == \"TCZ-1F Remote Root Atlas\") | .databaseId" | head -1)
  [[ -n "$RUN_ID" ]] && break
  sleep 2
done
[[ -n "$RUN_ID" ]] || { echo "Could not locate workflow run for $SHA" >&2; exit 4; }
echo "run_id=$RUN_ID"

gh run watch "$RUN_ID" --repo "$REPO" --exit-status
DEST="$ARTIFACT_ROOT/$RUN_ID"
mkdir -p "$DEST"
gh run download "$RUN_ID" --repo "$REPO" --dir "$DEST"

ATLAS=$(find "$DEST" -type f -name atlas.json | head -1 || true)
if [[ -z "$ATLAS" ]]; then
  echo "No aggregate atlas.json found under $DEST" >&2
  exit 5
fi
python3 - "$ATLAS" <<'PY'
import json, sys
path=sys.argv[1]
data=json.load(open(path, encoding='utf-8'))
print(json.dumps({
  'atlas': path,
  'point_count': data.get('point_count'),
  'successful_count': data.get('successful_count'),
  'failed_count': data.get('failed_count'),
  'integrity_errors': data.get('integrity_errors'),
  'quality': data.get('quality'),
}, indent=2))
if data.get('integrity_errors') or data.get('failed_count'):
    raise SystemExit(6)
PY
