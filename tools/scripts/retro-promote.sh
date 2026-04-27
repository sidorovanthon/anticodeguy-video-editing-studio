#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then echo "Usage: $0 <slug>"; exit 1; fi
SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"
PROMOTE="$EP/promote.txt"
CHANGELOG="$REPO_ROOT/standards/retro-changelog.md"

[ -d "$EP" ]       || { echo "ERROR: $EP not found"; exit 1; }
[ -f "$PROMOTE" ]  || { echo "ERROR: $PROMOTE not found. Write proposals there first."; exit 1; }

DATE="$(date +%Y-%m-%d)"
declare -a touched_files=()
declare -a changelog_lines=()

while IFS= read -r line; do
  [ -z "$line" ] && continue
  case "$line" in
    \#*) continue ;;
  esac

  if [[ "$line" != PROMOTE* ]]; then
    echo "ERROR: line does not start with PROMOTE: $line"
    exit 1
  fi

  # Parse: PROMOTE <file> <key> <value> episode=<slug> reason="..."
  file="$(awk '{print $2}' <<<"$line")"
  key="$(awk '{print $3}'  <<<"$line")"
  value="$(awk '{print $4}' <<<"$line")"
  reason="$(sed -n 's/.*reason="\([^"]*\)".*/\1/p' <<<"$line")"

  target="$REPO_ROOT/standards/$file"
  [ -f "$target" ] || { echo "ERROR: standards/$file not found"; exit 1; }

  if grep -q "^- $key " "$target" 2>/dev/null; then
    echo "skip: $file already has $key"
    continue
  fi

  printf "\n## Promoted %s\n- %s %s (episode %s; %s)\n" \
    "$DATE" "$key" "$value" "$SLUG" "$reason" >> "$target"

  touched_files+=("$file")
  changelog_lines+=("- $file: $key=$value (reason: $reason)")
done < "$PROMOTE"

if [ "${#touched_files[@]}" -eq 0 ]; then
  echo "No proposals applied."
  exit 0
fi

{
  echo
  echo "## $DATE — promoted from $SLUG"
  printf "%s\n" "${changelog_lines[@]}"
} >> "$CHANGELOG"

echo "Promoted ${#touched_files[@]} proposal(s)."
echo "Updated standards: ${touched_files[*]}"
echo "Appended to: $CHANGELOG"
