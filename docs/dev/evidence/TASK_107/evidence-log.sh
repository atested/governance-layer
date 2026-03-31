#!/usr/bin/env bash

set -u

usage() {
  cat <<'EOF' >&2
Usage: evidence-log.sh <TESTS.txt> -- <command> [args...]

Appends a standardized evidence block to <TESTS.txt>:
  $ <shell-escaped command line>
  <command output>
  [exit=<status>]
EOF
}

if [[ $# -lt 3 ]]; then
  usage
  exit 2
fi

out_file=$1
shift

if [[ ${1:-} != "--" ]]; then
  usage
  exit 2
fi
shift

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

mkdir -p "$(dirname "$out_file")"

if [[ -e "$out_file" && -s "$out_file" ]]; then
  printf '\n' >>"$out_file"
fi

cmd_line='$'
for arg in "$@"; do
  printf -v quoted ' %q' "$arg"
  cmd_line+="$quoted"
done

printf '%s\n' "$cmd_line" | tee -a "$out_file"

tmp_output=$(mktemp)
cleanup() {
  rm -f "$tmp_output"
}
trap cleanup EXIT

"$@" >"$tmp_output" 2>&1
status=$?

if [[ -s "$tmp_output" ]]; then
  cat "$tmp_output" | tee -a "$out_file"
  last_byte_hex=$(tail -c 1 "$tmp_output" 2>/dev/null | od -An -t x1 | tr -d '[:space:]')
  if [[ "$last_byte_hex" != "0a" ]]; then
    printf '\n' | tee -a "$out_file"
  fi
fi

printf '[exit=%d]\n' "$status" | tee -a "$out_file"
exit "$status"
