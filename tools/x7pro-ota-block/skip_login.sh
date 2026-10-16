#!/bin/sh
# X7PRO_OTA_BLOCK_BOOT_HOOK_V1 -- called by the stock S99_run_test_scripts.
BASE=/userdata/ota-block
[ -f "$BASE/enabled" ] || exit 0
[ -f "$BASE/control.sh" ] || exit 1
exec /bin/sh "$BASE/control.sh" apply >> "$BASE/boot-apply.log" 2>&1
