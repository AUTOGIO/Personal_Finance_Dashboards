# Spencer CLI helpers for Personal Finance workspace restore.
# Source after personal-finance-layout.env.

SPENCER_APP="/Applications/Spencer.app"
SPENCER_CLI="${SPENCER_APP}/Contents/MacOS/SpencerCLI"

spencer_cli() {
  if [[ -x "$SPENCER_CLI" ]]; then
    "$SPENCER_CLI" "$@"
    return $?
  fi
  if command -v spencer >/dev/null 2>&1; then
    spencer "$@"
    return $?
  fi
  echo "error: Spencer CLI not found at $SPENCER_CLI" >&2
  return 127
}

ensure_spencer_installed() {
  if [[ ! -d "$SPENCER_APP" ]]; then
    echo "error: Spencer.app not installed at $SPENCER_APP" >&2
    return 1
  fi
  if [[ ! -x "$SPENCER_CLI" ]]; then
    echo "error: SpencerCLI binary missing" >&2
    return 1
  fi
  return 0
}

ensure_spencer_running() {
  local elapsed=0
  local interval=1

  if ! pgrep -x Spencer >/dev/null 2>&1; then
    open -a Spencer
  fi

  while (( elapsed < SPENCER_POLL_TIMEOUT_SEC )); do
    if spencer_cli --list >/dev/null 2>&1; then
      return 0
    fi
    sleep "$interval"
    (( elapsed += interval ))
  done

  echo "error: Spencer did not become ready within ${SPENCER_POLL_TIMEOUT_SEC}s" >&2
  return 1
}

restore_layout() {
  local name="$1"
  local launch_apps="${2:-false}"

  spencer_cli --restore "$name" --launch-apps="$launch_apps"
}

_count_online_displays() {
  system_profiler SPDisplaysDataType 2>/dev/null | grep -c "Resolution:"
}

_count_ultrawide_displays() {
  system_profiler SPDisplaysDataType 2>/dev/null \
    | grep "UI Looks like:" \
    | grep -c "${ULTRAWIDE_WIDTH} x ${ULTRAWIDE_HEIGHT}"
}

verify_displays() {
  local count ultrawides

  count=$(_count_online_displays)
  if (( count != REQUIRED_DISPLAY_COUNT )); then
    echo "error: expected ${REQUIRED_DISPLAY_COUNT} displays, found ${count}" >&2
    echo "hint: see WORKSPACE_LAYOUT.md for required monitor arrangement" >&2
    return 1
  fi

  ultrawides=$(_count_ultrawide_displays)
  if (( ultrawides < 2 )); then
    echo "error: expected at least 2 ultrawide displays (${ULTRAWIDE_WIDTH}x${ULTRAWIDE_HEIGHT}), found ${ultrawides}" >&2
    echo "hint: check System Settings → Displays → Arrangement" >&2
    return 1
  fi

  return 0
}

# Electron apps (Cursor, Obsidian) don't expose windows via the standard
# AppleScript suite, so titles come from System Events instead.
_list_window_titles() {
  /usr/bin/osascript <<'EOF'
tell application "System Events"
  set out to ""
  repeat with p in (every application process whose background only is false)
    set pn to name of p
    try
      repeat with w in windows of p
        set out to out & pn & " :: " & (name of w) & linefeed
      end repeat
    end try
  end repeat
  return out
end tell
EOF
}

# Returns 0 if all expected window title substrings are present.
verify_windows() {
  local titles
  local -a missing
  titles=$(_list_window_titles 2>/dev/null) || {
    echo "warn: could not read window titles (grant Accessibility permission)" >&2
    return 1
  }

  missing=()
  grep -Fq "$EXPECT_COMET_TITLE"    <<< "$titles" || missing+=("Comet")
  grep -Fq "$EXPECT_EXCEL_TITLE"    <<< "$titles" || missing+=("Excel")
  grep -Fq "$EXPECT_CURSOR_TITLE"   <<< "$titles" || missing+=("Cursor")
  grep -Fq "$EXPECT_OBSIDIAN_TITLE" <<< "$titles" || missing+=("Obsidian")

  if (( ${#missing[@]} == 0 )); then
    return 0
  fi

  echo "warn: windows not ready: ${(j:, :)missing}" >&2
  return 1
}

wait_for_windows() {
  local start=$SECONDS

  while (( SECONDS - start < APP_WAIT_TIMEOUT_SEC )); do
    if verify_windows; then
      return 0
    fi
    sleep 2
  done

  echo "error: timed out after ${APP_WAIT_TIMEOUT_SEC}s waiting for expected windows" >&2
  verify_windows || true
  return 1
}

retry_restore() {
  local name="$1"
  local launch_apps="${2:-false}"
  local attempt=0

  while (( attempt <= SPENCER_RESTORE_RETRIES )); do
    if restore_layout "$name" "$launch_apps" && verify_windows; then
      return 0
    fi
    (( attempt++ ))
    if (( attempt <= SPENCER_RESTORE_RETRIES )); then
      echo "info: retrying Spencer restore (${attempt}/${SPENCER_RESTORE_RETRIES})..." >&2
      sleep "$SPENCER_RETRY_DELAY_SEC"
    fi
  done

  return 1
}
