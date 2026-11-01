#!/usr/bin/env bash
# Build a stripped production version for the NanoPi from a git commit.
#   ./build_production.sh            -> production/<short-hash of HEAD>/
#   ./build_production.sh <commit>   -> production/<short-hash of commit>/
#   ./build_production.sh prod-<hash> -> rebuild a released version (git tag)
# production/ is local only (.gitignore) - tag the source commit, never commit the build.
# The files come from the commit (git archive), not from the working tree.
# Details: PRODUCTION.md
set -euo pipefail

cd "$(dirname "$0")"
COMMIT=$(git rev-parse --verify "${1:-HEAD}^{commit}")
SHORT=$(git rev-parse --short "$COMMIT")
OUT="production/$SHORT"

# Runtime files: everything the NanoPi needs, nothing else.
INCLUDE='LICENSE
tinybox
prcore
brocast/brocast
brocast/brocast-core.yaml
brocast/brocastd.conf.example
brocast/requirements.txt
brocast/zdict
dxfeed
dxfeed.conf.example
geosphere_station.py
geosphere_prognose.py
geosphere_warnungen.py
tbclient/__init__.py
tbclient/news
tinybox.conf.example
deploy'

# Known non-runtime files (docs, planning, tests, tools, Windows/Linux launchers;
# on the NanoPi systemd starts everything, KISS mode/kisshub is not a NanoPi target).
# Only used to warn about NEW files that are in neither list.
EXCLUDE='.gitattributes
.gitignore
*.md
*.bat
*.sh
*.odt
*.txt
docs
test
tests
production
build_production.sh
dxfeed_start.py
feederpi
pi_abholung.py
pi_sd_vorbereiten.py
fwdsim
fwdsim.conf.example
tbtest
tools
kisshub
kisshub.conf.example
brocast/brocast-core.v*
brocast/brocast.cddl
brocast/funktest
brocast/mockup
brocast/test
brocast/tests
brocast/tools
tbclient
tbclient.conf.example'

# true if path $1 equals or lies below one of the patterns in list $2
matches() {
    local path=$1 p
    while IFS= read -r p; do
        case $path in $p|$p/*) return 0 ;; esac
    done <<< "$2"
    return 1
}

if [ -e "$OUT" ]; then
    echo "$OUT already exists - delete it first to rebuild." >&2
    exit 1
fi

# --- warn about files not covered by either list ------------------------------
unknown=0
while IFS= read -r f; do
    if ! matches "$f" "$INCLUDE" && ! matches "$f" "$EXCLUDE"; then
        echo "WARNING: not classified (left out): $f" >&2
        unknown=1
    fi
done < <(git ls-tree -r --name-only "$COMMIT")

# --- export the runtime files from the commit ----------------------------------
mkdir -p "$OUT"
paths=()
deploy_src=commit
while IFS= read -r p; do
    if git cat-file -e "$COMMIT:$p" 2>/dev/null; then
        paths+=("$p")
    elif [ "$p" = deploy ] && [ -d deploy ]; then
        deploy_src="working tree (not in $SHORT)"
        cp -R deploy "$OUT/deploy"
    else
        echo "ERROR: $p missing in $SHORT" >&2
        rm -rf "$OUT"
        exit 1
    fi
done <<< "$INCLUDE"
git archive --format=tar "$COMMIT" -- "${paths[@]}" | tar -x -C "$OUT"

# no docs or tests inside the included folders either
find "$OUT" \( -name '*.md' -o -name 'test_*.py' -o -name '__pycache__' -o -name '*.py[co]' \) -print -exec rm -rf {} + >&2

# --- syntax check (bytecode goes to a temp dir, not into $OUT) -----------------
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
PYTHONPYCACHEPREFIX="$tmp" python3 -m compileall -q "$OUT" >/dev/null \
    || { echo "ERROR: syntax check failed" >&2; exit 1; }

cat > "$OUT/VERSION" <<EOF
commit=$COMMIT
commit_date=$(git show -s --format=%cI "$COMMIT")
subject=$(git show -s --format=%s "$COMMIT")
built=$(date -Iseconds)
deploy_files=$deploy_src
EOF

echo "Built $OUT ($(du -sh "$OUT" | cut -f1), $(find "$OUT" -type f | wc -l) files)"
[ "$deploy_src" = commit ] || echo "NOTE: deploy/ taken from the $deploy_src - commit it for reproducible builds."
[ "$unknown" -eq 0 ] || echo "NOTE: classify the files above in INCLUDE or EXCLUDE of $0."
