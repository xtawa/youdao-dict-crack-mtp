#!/bin/sh
# Reversible OTA block: keep the supervisor child idle without running the updater.
while [ -f /userdata/ota-block/enabled ]; do
    sleep 5
done
exit 0
