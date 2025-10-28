#!/usr/bin/env bash
set -euo pipefail

# Simple version manager for neurosim
# - Reads/writes __version__ in src/neurosim/__init__.py
# - Supports bumping (patch/minor/major), setting explicit version, showing current, and rollback to previous git version

VERSION_FILE="src/neurosim/__init__.py"

get_current_version() {
  if [[ ! -f "${VERSION_FILE}" ]]; then
    echo "Error: version file not found at ${VERSION_FILE}" >&2
    exit 1
  fi
  # Extract value inside quotes for __version__ = "x.y.z"
  grep -Po '__version__\s*=\s*"\K[^"]+' "${VERSION_FILE}" || true
}

set_version() {
  local new_version="${1:?version required}"
  if [[ ! "${new_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version must be in SemVer format MAJOR.MINOR.PATCH (e.g., 0.2.1)" >&2
    exit 1
  fi
  if [[ ! -f "${VERSION_FILE}" ]]; then
    echo "Error: version file not found at ${VERSION_FILE}" >&2
    exit 1
  fi
  # Replace the __version__ assignment in-place using python for reliable cross-platform editing
  python3 - "$VERSION_FILE" "$new_version" <<'PY'
import sys, re
path, v = sys.argv[1], sys.argv[2]
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
# Use a function replacement to avoid backreference ambiguity like \10 when version starts with 0
new_content, n = re.subn(
    r'(__version__\s*=\s*")[^"]+("\s*)',
    lambda m: f"{m.group(1)}{v}{m.group(2)}",
    content,
    count=1,
)
if n == 0:
    print(f"Error: __version__ not found in {path}", file=sys.stderr)
    sys.exit(1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print(v)
PY
}

bump_version() {
  local part="${1:-patch}"
  local current
  current="$(get_current_version)"
  if [[ -z "${current}" ]]; then
    echo "Error: could not determine current version from ${VERSION_FILE}" >&2
    exit 1
  fi
  IFS='.' read -r major minor patch <<<"${current}"
  case "${part}" in
    patch)
      patch=$((patch + 1))
      ;;
    minor)
      minor=$((minor + 1))
      patch=0
      ;;
    major)
      major=$((major + 1))
      minor=0
      patch=0
      ;;
    *)
      echo "Error: unknown bump part '${part}'. Use: patch | minor | major" >&2
      exit 1
      ;;
  esac
  set_version "${major}.${minor}.${patch}"
}

previous_version_from_git() {
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # Read the version file from previous commit (HEAD) and extract version
    git show HEAD:"${VERSION_FILE}" 2>/dev/null | grep -Po '__version__\s*=\s*"\K[^"]+' || true
  else
    echo ""  # no git repo
  fi
}

rollback_version() {
  local prev
  prev="$(previous_version_from_git)"
  if [[ -z "${prev}" ]]; then
    echo "Error: cannot determine previous version from git history. Ensure you're in a git repo with a prior commit." >&2
    exit 1
  fi
  set_version "${prev}"
}

usage() {
  cat <<USAGE
Usage: $0 <command> [args]

Commands:
  current                   Print current version
  set <version>            Set explicit version (SemVer: MAJOR.MINOR.PATCH)
  bump [patch|minor|major] Bump version (default: patch)
  rollback                 Set version to previous commit's version (via git)
USAGE
}

cmd="${1:-}"
case "${cmd}" in
  current)
    get_current_version
    ;;
  set)
    shift
    set_version "${1:-}"
    ;;
  bump)
    shift
    bump_version "${1:-patch}"
    ;;
  rollback)
    rollback_version
    ;;
  *)
    usage
    exit 1
    ;;
esac


