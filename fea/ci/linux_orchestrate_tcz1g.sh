#!/usr/bin/env bash
set -euo pipefail

repo=${REPO:-quemanhmcr/bfm-5-modal-collar}
branch=${BRANCH:-research/tcz1f-action-grid}
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"

git fetch origin "$branch"
git checkout "$branch"
git reset --hard "origin/$branch"
git config user.name "quemanhmcr"
git config user.email "102531563+quemanhmcr@users.noreply.github.com"

request_id=$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)
python - "$request_id" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import sys, yaml
p=Path('fea/config/tcz1g_request.yml')
d=yaml.safe_load(p.read_text())
d.update({
  'profile':'dynamic_geometry_benchmark',
  'requested_by':'linux-mcp',
  'purpose':'independent-github-crosscheck-of-tcz1g',
  'request_id':sys.argv[1],
  'requested_at_utc':datetime.now(timezone.utc).isoformat(),
})
p.write_text(yaml.safe_dump(d,sort_keys=False),encoding='utf-8')
PY

git add fea/config/tcz1g_request.yml
git commit -m "ci(fea): request TCZ-1G dynamic benchmark [$request_id]"
git push origin "$branch"
sha=$(git rev-parse HEAD)
echo "submitted_sha=$sha request_id=$request_id"

run_id=""
for _ in $(seq 1 60); do
  run_id=$(gh run list --repo "$repo" --workflow 'TCZ-1G Dynamic Geometry Benchmark' --branch "$branch" --limit 10 --json databaseId,headSha --jq ".[] | select(.headSha == \"$sha\") | .databaseId" | head -1)
  [[ -n "$run_id" ]] && break
  sleep 2
done
[[ -n "$run_id" ]] || { echo 'Could not resolve workflow run' >&2; exit 3; }
echo "run_id=$run_id"
gh run watch "$run_id" --repo "$repo" --exit-status
out=${OUTPUT_ROOT:-/root/bfm5-artifacts/$run_id}
mkdir -p "$out"
gh run download "$run_id" --repo "$repo" --dir "$out"
find "$out" -maxdepth 3 -type f -print
