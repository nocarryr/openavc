#!/bin/bash
# OpenAVC macOS launchd run wrapper.
#
# This script is the LaunchDaemon's ProgramArguments. launchd runs it as root
# on every (re)launch (RunAtLoad + KeepAlive). On each launch it applies any
# pending update or rollback instruction (it runs as root, so it can swap the
# .app under /Applications), then exec's the server. A clean server exit 0
# (self-update / cloud restart) and a crash both bring launchd back here.
#
# It mirrors the Linux update-helper.sh swap/recovery logic. macOS differences:
# the "app dir" is the OpenAVC.app bundle; there is no venv to preserve and no
# user content inside the bundle (data lives under OPENAVC_DATA_DIR), so the
# swap is a plain bundle replace.
#
# The script MUST always end by exec'ing the server, even when an apply step
# fails, so a bad instruction can never take the service down.

set -u

DATA_DIR="${OPENAVC_DATA_DIR:-/Library/Application Support/OpenAVC}"
APP="${OPENAVC_APP:-/Applications/OpenAVC.app}"
SERVER="$APP/Contents/MacOS/openavc-server"
UPDATE_FILE="$DATA_DIR/apply-update.json"
ROLLBACK_FILE="$DATA_DIR/apply-rollback"
LOG_TAG="openavc-macos-run"
PYTHON="${PYTHON:-/usr/bin/python3}"

# A candidate bundle is usable only if it carries the server executable.
is_app_valid() {
    [ -x "$1/Contents/MacOS/openavc-server" ]
}

handle_update() {
    ARTIFACT=$("$PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1]))['artifact'])" "$UPDATE_FILE" 2>/dev/null)
    TO_VER=$("$PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1]))['to_version'])" "$UPDATE_FILE" 2>/dev/null)

    if [ -z "$ARTIFACT" ] || [ ! -f "$ARTIFACT" ]; then
        echo "$LOG_TAG: update artifact missing or unparseable, skipping"
        rm -f "$UPDATE_FILE"
        return
    fi

    echo "$LOG_TAG: applying update to v$TO_VER from $ARTIFACT"
    PREVIOUS="$APP.previous"
    STAGING="$APP.new"

    # 1. Extract the new release into a clean staging dir (no stragglers from
    #    the running install). The tarball carries OpenAVC.app at its root.
    rm -rf "$STAGING"
    if ! mkdir -p "$STAGING"; then
        echo "$LOG_TAG: could not create staging dir, skipping"
        rm -f "$UPDATE_FILE"
        return
    fi
    if ! tar xzf "$ARTIFACT" -C "$STAGING"; then
        echo "$LOG_TAG: extraction failed, leaving current install untouched"
        rm -rf "$STAGING"
        rm -f "$UPDATE_FILE"
        return
    fi
    NEW_APP="$STAGING/OpenAVC.app"
    if ! is_app_valid "$NEW_APP"; then
        echo "$LOG_TAG: staged bundle is invalid, leaving current install untouched"
        rm -rf "$STAGING"
        rm -f "$UPDATE_FILE"
        return
    fi

    # 2. Snapshot the current bundle so rollback has a complete copy.
    rm -rf "$PREVIOUS"
    if ! cp -a "$APP" "$PREVIOUS"; then
        echo "$LOG_TAG: snapshot to $PREVIOUS failed, skipping update"
        rm -rf "$PREVIOUS" "$STAGING"
        rm -f "$UPDATE_FILE"
        return
    fi

    # 3. Swap: remove the old bundle (already snapshotted) and promote staging.
    if ! rm -rf "$APP"; then
        echo "$LOG_TAG: could not remove old bundle, recovering from snapshot"
        mv "$PREVIOUS" "$APP" 2>/dev/null || echo "$LOG_TAG: recovery failed; manual fix required"
        rm -rf "$STAGING"
        rm -f "$UPDATE_FILE"
        return
    fi
    if ! mv "$NEW_APP" "$APP"; then
        echo "$LOG_TAG: could not promote new bundle, recovering from snapshot"
        mv "$PREVIOUS" "$APP" 2>/dev/null || echo "$LOG_TAG: recovery failed; manual fix required"
        rm -rf "$STAGING"
        rm -f "$UPDATE_FILE"
        return
    fi

    rm -rf "$STAGING"
    rm -f "$UPDATE_FILE"
    echo "$LOG_TAG: update to v$TO_VER applied"
}

handle_rollback() {
    PREVIOUS="$APP.previous"
    # Refuse to promote a missing or partial snapshot (a prior cp -a could have
    # been interrupted) — that would crash the service with nothing to fall
    # back to. Mirrors update-helper.sh's integrity guard.
    if [ ! -d "$PREVIOUS" ] || ! is_app_valid "$PREVIOUS"; then
        echo "$LOG_TAG: no valid previous bundle at $PREVIOUS, cannot rollback"
        rm -f "$ROLLBACK_FILE"
        return
    fi

    echo "$LOG_TAG: rolling back to previous version"
    FAILED="$APP.failed"
    rm -rf "$FAILED"
    if ! mv "$APP" "$FAILED"; then
        echo "$LOG_TAG: could not move current bundle aside, skipping rollback"
        rm -f "$ROLLBACK_FILE"
        return
    fi
    if ! mv "$PREVIOUS" "$APP"; then
        echo "$LOG_TAG: restore failed, putting the failed bundle back"
        mv "$FAILED" "$APP" 2>/dev/null || true
        rm -f "$ROLLBACK_FILE"
        return
    fi
    rm -rf "$FAILED"
    rm -f "$ROLLBACK_FILE"
    echo "$LOG_TAG: rollback complete"
}

[ -f "$UPDATE_FILE" ] && handle_update
[ -f "$ROLLBACK_FILE" ] && handle_rollback

# Always launch the server. exec so launchd tracks the server as the job's
# process (the wrapper itself is replaced, not left hanging around).
exec "$SERVER"
