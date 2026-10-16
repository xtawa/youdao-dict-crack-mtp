"""Small Windows WPD adapter, restricted to this Rockchip dictionary pen."""
import ctypes
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'comtypes-1.4.17-py3-none-any.whl'))
import comtypes
import comtypes.client

cache = Path(os.environ.get('X7PRO_MTP_CACHE', str(ROOT / '.cache')))
cache.mkdir(parents=True, exist_ok=True)
comtypes.client.gen_dir = str(cache)
api = comtypes.client.GetModule(r'C:\Windows\System32\PortableDeviceApi.dll')
types = comtypes.client.GetModule(r'C:\Windows\System32\PortableDeviceTypes.dll')

def key(pid):
    return api._tagpropertykey(comtypes.GUID('{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}'), pid)

PARENT, NAME, FORMAT, CONTENT_TYPE, SIZE, ORIGINAL_NAME = [key(i) for i in (3, 4, 6, 7, 11, 12)]

def values():
    return comtypes.client.CreateObject(types.PortableDeviceValues, interface=api.IPortableDeviceValues)

def checked(hr):
    if hr < 0:
        raise OSError(f'HRESULT 0x{hr & 0xffffffff:08x}')

class Pen:
    def __init__(self):
        manager = comtypes.client.CreateObject(api.PortableDeviceManager, interface=api.IPortableDeviceManager)
        count = ctypes.c_ulong(0)
        get = manager._IPortableDeviceManager__com_GetDevices
        checked(get(None, ctypes.byref(count)))
        ids = (ctypes.c_wchar_p * count.value)()
        checked(get(ids, ctypes.byref(count)))
        targets = [ids[i] for i in range(count.value)
                   if 'vid_2207&pid_0011&mi_00' in ids[i].lower()]
        if len(targets) != 1:
            raise RuntimeError(f'Expected one pen MTP interface, got {len(targets)}')
        self.device = comtypes.client.CreateObject(api.PortableDevice, interface=api.IPortableDevice)
        self.device.Open(targets[0], values())
        self.content = self.device.Content()
        self.properties = self.content.Properties()

    def children(self, parent='DEVICE'):
        enum = self.content.EnumObjects(0, parent, None)
        result = []
        while True:
            obj = ctypes.c_wchar_p()
            fetched = ctypes.c_ulong(0)
            hr = enum._IEnumPortableDeviceObjectIDs__com_Next(1, ctypes.byref(obj), ctypes.byref(fetched))
            checked(hr)
            if not fetched.value:
                break
            object_id = obj.value
            ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(obj, ctypes.c_void_p))
            prop = self.properties.GetValues(object_id, None)
            try:
                name = prop.GetStringValue(NAME)
            except Exception:
                try:
                    name = prop.GetStringValue(ORIGINAL_NAME)
                except Exception:
                    name = ''
            result.append({'id': object_id, 'name': name})
        return result

    def close(self):
        self.device.Close()

if __name__ == '__main__':
    pen = Pen()
    try:
        stores = pen.children()
        listing = [{'storage': store, 'children': pen.children(store['id'])} for store in stores]
        print(json.dumps(listing, ensure_ascii=False, indent=2))
        (ROOT/'wpd_listing.json').write_text(json.dumps(listing, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        pen.close()
