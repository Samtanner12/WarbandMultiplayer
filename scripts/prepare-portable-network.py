"""Compile private-network configuration into the isolated playable module."""
from pathlib import Path
import os, subprocess
root=Path(__file__).resolve().parents[1]
source=root/'runtime/NativeMissionProbe/Source'
path=source/'module_simple_triggers.py'
text=path.read_text(encoding='cp1254')
if 'g_autotest_' in text or 'g_autotest_' in (source/'module_mission_templates.py').read_text(encoding='cp1254'):
    raise RuntimeError('Remove automated fixtures before packaging a playable build.')
if '# PRIVATE_NETWORK_HOST_PASSWORD' not in text:
    text+='''
# PRIVATE_NETWORK_HOST_PASSWORD
# ASI publishes the configured password into s57. This graphical host does
# not use the dedicated plugin's server-config dictionary path.
simple_triggers += [(0.1, [
    (multiplayer_is_server), (multiplayer_is_campaign),
    (eq, "$g_full_host_probe_request", 3),
    (server_set_password, s57),
])]
'''
path.write_text(text,encoding='cp1254')
env=dict(os.environ,WARBAND_EXPORT_DIR=str(root/'runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe'))
with (root/'logs/portable-module-build.log').open('w') as log:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'),'-B',str(source/'run_module_build.py')],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
print('Private-network playable module compiled, no automated combat fixtures.')
