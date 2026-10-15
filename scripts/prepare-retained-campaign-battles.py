"""Install the participant coordinator without overwriting saves or identities."""
from pathlib import Path
import os, shutil, subprocess
root=Path(__file__).resolve().parents[1]
source=root/'runtime/NativeMissionProbe/Source'
shutil.copy2(root/'scripts/module_retained_campaign_battles.py',source/'module_retained_campaign_battles.py')
shutil.copy2(root/'scripts/module_retained_rewards.py',source/'module_retained_rewards.py')
for filename,function,collection in [('module_coop_scripts.py','install_scripts','coop_scripts'),
                                    ('module_mission_templates.py','install_missions','mission_templates'),
                                    ('module_simple_triggers.py','install_triggers','simple_triggers'),
                                    ('module_presentations.py','install_presentations','presentations'),
                                    ('module_game_menus.py','install_menus','game_menus'),
                                    ('module_scripts.py','install_native_scripts','scripts')]:
    path=source/filename;text=path.read_text(encoding='cp1254')
    marker='# RETAINED_CAMPAIGN_PARTICIPANTS'
    text=text.partition(marker)[0]
    text+='\n'+marker+'\nfrom module_retained_campaign_battles import '+function+'\n'+function+'('+collection+')\n'
    path.write_text(text,encoding='cp1254')
env=dict(os.environ,WARBAND_EXPORT_DIR=str(root/'runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe'))
with (root/'logs/retained-campaign-module-build.log').open('w') as log:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'),'-B',str(source/'run_module_build.py')],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
print('Retained participant campaign module compiled.')
