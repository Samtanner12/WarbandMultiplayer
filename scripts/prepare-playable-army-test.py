"""Remove finite automated battle fixtures from the isolated two-player build.
Run only after its host and both clients are stopped. Does not reset saves.
"""
from pathlib import Path
import os, re, subprocess
root=Path(__file__).resolve().parents[1]
source=root/'runtime/NativeMissionProbe/Source'
for name in ['module_simple_triggers.py','module_mission_templates.py']:
    path=source/name;text=path.read_text(encoding='cp1254')
    text=re.sub(r'(?ms)^# FINITE_AUTONOMOUS_ARMY_REGRESSION\r?\n.*?(?=^# [A-Z_]+\r?$|\Z)','',text)
    if 'g_autotest_' in text:raise RuntimeError('Unremoved test fixture in '+name)
    path.write_text(text,encoding='cp1254')
env=dict(os.environ,WARBAND_EXPORT_DIR=str(root/'runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe'))
with (root/'logs/playable-army-test-module-build.log').open('w') as output:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'),'-B',str(source/'run_module_build.py')],cwd=source,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
print('Isolated two-player battle build compiled without automated damage, movement, orders, or retreat.')
