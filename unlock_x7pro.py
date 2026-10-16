"""Temporary MTP-based ADB unlock, verified on Youdao X7 Pro PenOS 4.34.0.

Reference: https://github.com/orgs/PenUniverse/discussions/311
Uses Windows WPD, does not replace USB drivers or alter firmware/passwords.
The only target written by --unlock is /tmp/.adb_auth_verified (zero bytes).
"""
import argparse
import ctypes
import json
import shutil
import subprocess
import sys
from wpd_pen import Pen, values, api, PARENT, NAME, ORIGINAL_NAME, SIZE, checked

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Read status without creating a marker')
    mode.add_argument('--unlock', action='store_true', help='Create the temporary authentication marker')
    args = parser.parse_args()
    adb = shutil.which('adb')
    if not adb:
        raise RuntimeError('adb.exe must be installed and available on PATH')

    def adb_shell(command):
        p = subprocess.run([adb, '-d', 'shell', command], capture_output=True, timeout=8)
        return (p.stdout + p.stderr).decode(errors='replace').strip()

    before = adb_shell('id')
    if 'uid=0(root)' in before:
        print(json.dumps({'status': 'already_unlocked', 'identity': before}))
        return 0
    if 'login with "adb shell auth"' not in before:
        raise RuntimeError('Expected one locked USB pen. ADB response: ' + before)

    pen = Pen()
    try:
        stores = pen.children()
        if len(stores) != 1:
            raise RuntimeError('Expected exactly one MTP storage')
        music = [f for f in pen.children(stores[0]['id']) if f['name'] == 'Music']
        if len(music) != 1:
            raise RuntimeError('Expected exactly one Music folder')
        if args.check:
            print(json.dumps({'status': 'locked', 'mtp_available': True, 'writes': 0}))
            return 0

        props = values()
        props.SetStringValue(PARENT, music[0]['id'])
        props.SetStringValue(NAME, '.adb_auth_verified')
        props.SetStringValue(ORIGINAL_NAME, '../../../../tmp/.adb_auth_verified')
        props.SetUnsignedLargeIntegerValue(SIZE, 0)
        stream = ctypes.POINTER(api.IStream)()
        optimal = ctypes.c_ulong(0)
        checked(pen.content._IPortableDeviceContent__com_CreateObjectWithPropertiesAndData(
            props, ctypes.byref(stream), ctypes.byref(optimal), None))
        stream.Commit(0)
    finally:
        pen.close()

    after = adb_shell('id')
    if 'uid=0(root)' not in after:
        print(json.dumps({'status': 'not_unlocked', 'adb_response': after}))
        return 2
    proof = adb_shell('cat /Version; ls -l /tmp/.adb_auth_verified; stat -f -c %T /tmp')
    print(json.dumps({'status': 'unlocked', 'identity': after, 'proof': proof,
                      'scope': 'temporary marker only; firmware and password unchanged'}))
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}), file=sys.stderr)
        sys.exit(1)
