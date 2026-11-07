#!/bin/sh
set -eu
BASE=/userdata/ota-block
TARGET=/usr/bin/ota_mgr
STUB=$BASE/blocked-worker.sh
ORIGINAL_SHA=b61db6ccacbc8f3b58e6b29dd784e42591d02cfd80516dc3fd8ee49b23921597

mounted() {
    awk '$2 == "/usr/bin/ota_mgr" {found=1} END {exit !found}' /proc/mounts
}

native_pids() {
    for pid in $(pidof ota_mgr 2>/dev/null || true); do
        exe=$(readlink "/proc/$pid/exe" 2>/dev/null || true)
        [ "$exe" = "$TARGET" ] && printf '%s\n' "$pid"
    done
    return 0
}

check_idle() {
    for service in ota_download update_engine; do
        if pidof "$service" >/dev/null 2>&1; then
            echo "Refusing to interrupt active $service" >&2
            return 1
        fi
    done
    [ ! -e /tmp/install_ota ] || { echo 'An OTA installation marker exists' >&2; return 1; }
}

apply_block() {
    [ -f "$BASE/enabled" ] || return 0
    check_idle
    if mounted; then
        cmp -s "$TARGET" "$STUB" || { echo 'Unexpected existing updater mount' >&2; return 1; }
    else
        actual=$(sha256sum "$TARGET" | awk '{print $1}')
        [ "$actual" = "$ORIGINAL_SHA" ] || { echo 'Unrecognized firmware updater; stopping' >&2; return 1; }
        mount --bind "$STUB" "$TARGET"
    fi
    # Only terminate native instances of the exact updater executable.
    for pid in $(native_pids); do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 1
    for pid in $(native_pids); do
        kill -KILL "$pid" 2>/dev/null || true
    done
    echo 'OTA worker blocked; original firmware bytes preserved underneath the bind mount.'
}

restore() {
    if mounted; then
        cmp -s "$TARGET" "$STUB" || { echo 'Unexpected updater mount; not changing it' >&2; return 1; }
        # The shell currently executing the stub holds the file mount open.
        # Pause only the OTA supervisor, stop its worker, then release the mount.
        guardians=''
        for pid in $(pidof guardian_run 2>/dev/null || true); do
            args=$(tr '\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
            if [ "$args" = '/usr/bin/guardian_run /usr/bin/runOtaMgr ' ]; then
                kill -STOP "$pid"
                guardians="$guardians $pid"
            fi
        done
        trap 'for gp in $guardians; do kill -CONT "$gp" 2>/dev/null || true; done' 0
        for pid in $(pidof ota_mgr 2>/dev/null || true); do
            args=$(tr '\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
            case "$args" in
                '/bin/sh /usr/bin/ota_mgr '|'/usr/bin/ota_mgr ')
                    kill -TERM "$pid" 2>/dev/null || true ;;
            esac
        done
        count=0
        while mounted; do
            umount "$TARGET" 2>/dev/null && break
            count=$((count + 1))
            [ "$count" -lt 8 ] || { echo 'Updater mount remains busy' >&2; return 1; }
            sleep 1
        done
    fi
    actual=$(sha256sum "$TARGET" | awk '{print $1}')
    [ "$actual" = "$ORIGINAL_SHA" ] || { echo 'Original updater checksum mismatch' >&2; return 1; }
    rm -f "$BASE/enabled"
    for pid in ${guardians:-}; do kill -CONT "$pid" 2>/dev/null || true; done
    trap - 0
    echo 'Original OTA worker restored. Its existing supervisor may restart it within a few seconds.'
}

status() {
    if [ -f "$BASE/enabled" ]; then echo 'enabled=yes'; else echo 'enabled=no'; fi
    if mounted; then echo 'worker_bind_mount=yes'; else echo 'worker_bind_mount=no'; fi
    if cmp -s "$TARGET" "$STUB"; then echo 'worker_is_blocked_stub=yes'; else echo 'worker_is_blocked_stub=no'; fi
    pids=$(native_pids)
    if [ -n "$pids" ]; then echo "native_updater_pids=$pids"; else echo 'native_updater_pids=none'; fi
    printf 'worker_sha256='; sha256sum "$TARGET" | awk '{print $1}'
}

case "${1:-status}" in
    enable) check_idle; touch "$BASE/enabled"; apply_block; status ;;
    apply) apply_block ;;
    restore) restore ;;
    status) status ;;
    *) echo 'Usage: control.sh {enable|apply|restore|status}' >&2; exit 2 ;;
esac
