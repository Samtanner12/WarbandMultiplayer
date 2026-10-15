"""Build an isolated native mission capability probe, not a playable mod.

It never changes the live LocalTest modules or their campaign save namespace.
"""
from pathlib import Path
import shutil
import os
import subprocess

root = Path(__file__).resolve().parents[1]
probe = root / 'runtime/NativeMissionProbe'
source = probe / 'Source'
game = probe / 'Game'
module = game / 'Modules/NativeCoopProbe'
resume = '--resume-preparation' in __import__('sys').argv
if probe.exists() and not resume:
    raise SystemExit('Probe directory already exists; inspect it before rebuilding.')
if resume and (game / 'rgl_log.txt').exists():
    raise SystemExit('A probe already ran here; do not overwrite its records.')
probe.mkdir(exist_ok=True)
shutil.copytree(root / 'WarbandTogether/wse2work/Native-Coop-master', source,
                ignore=shutil.ignore_patterns('*.pyc', '__pycache__'), dirs_exist_ok=resume)
shutil.copytree(root / 'build/overlay/Modules/NativeCoop', module, dirs_exist_ok=resume)
game.mkdir(exist_ok=True)
base = root / 'runtime/LocalTest/Host'
for item in base.iterdir():
    if item.is_file() and item.suffix.lower() in ['.exe', '.dll', '.asi', '.ini', '.lua', '.txt'] and 'log' not in item.name.lower():
        shutil.copy2(item, game / item.name)
# A host may have a minimal PostFx.fx. The graphical client needs the complete
# client shader set, including globals/includes and precompiled shader files.
client_base = root / 'runtime/LocalTest/Client1'
for item in client_base.iterdir():
    if item.is_file() and item.suffix.lower() in ['.fx', '.fxo', '.pp', '.h', '.bmp']:
        shutil.copy2(item, game / item.name)
shutil.copy2(client_base / 'mb_warband_wse2_multiclient.exe',
             game / 'mb_warband_wse2_multiclient.exe')
for name in ['CommonRes', 'Data', 'Languages', 'Music', 'Sounds', 'Textures']:
    if (base / name).is_dir() and not (game / name).exists():
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(game / name), str(base / name)], check=True, capture_output=True)

with (source / 'module_mission_templates.py').open('a', encoding='cp1254') as output:
    output.write('''
mission_templates += [("native_session_probe", mtf_battle_mode, -1, "Native session probe", [], [
    (ti_after_mission_start, 0, 0, [], [
        (team_set_relation, 0, 1, -1),
        (entry_point_get_position, pos1, 0), (set_spawn_position, pos1),
        (spawn_agent, "trp_looter"), (assign, "$g_probe_agent_a", reg0), (agent_set_team, reg0, 0),
        (entry_point_get_position, pos2, 1), (set_spawn_position, pos2),
        (spawn_agent, "trp_looter"), (assign, "$g_probe_agent_b", reg0), (agent_set_team, reg0, 1),
        (agent_set_scripted_destination, "$g_probe_agent_a", pos2),
        (agent_set_scripted_destination, "$g_probe_agent_b", pos1),
        (display_message, "@[PROBE] native mission started; two AI agents spawned"),
    ]),
    (1, 0, 0, [], [
        (store_current_hours, reg1), (store_mission_timer_a, reg2),
        (assign, reg3, 0),
        (try_begin), (multiplayer_is_campaign), (assign, reg3, 1), (try_end),
        (assign, reg4, 0),
        (try_for_agents, ":agent"), (agent_is_alive, ":agent"), (val_add, reg4, 1), (try_end),
        (display_message, "@[PROBE MISSION] campaign={reg3} hour={reg1} mission_seconds={reg2} alive={reg4}"),
    ]),
])]
''')
with (source / 'module_simple_triggers.py').open('a', encoding='cp1254') as output:
    output.write('''
simple_triggers += [
    (0, [
        (multiplayer_is_server), (multiplayer_is_campaign),
        (eq, "$g_native_probe_started", 0),
        (assign, ":probe_peers", 0), (get_max_players, ":probe_max"),
        (try_for_range, ":probe_player", 1, ":probe_max"),
            (player_is_active, ":probe_player"), (val_add, ":probe_peers", 1),
        (try_end),
        (gt, ":probe_peers", 0), (assign, "$g_native_probe_started", 1),
        (store_current_hours, reg1),
        (display_message, "@[PROBE] requesting native multiplayer mission at hour {reg1}"),
        (start_multiplayer_mission, "mt_native_session_probe", "scn_town_1_arena", 1),
    ]),
    (1, [
        (multiplayer_is_server), (multiplayer_is_campaign),
        (eq, "$g_native_probe_started", 1), (store_current_hours, reg1),
        (display_message, "@[PROBE CAMPAIGN] hour={reg1}"),
    ]),
]
''')
env = dict(os.environ, WARBAND_EXPORT_DIR=str(module))
with (root / 'logs/native-mission-probe-build.log').open('w') as output:
    subprocess.run([str(root / 'tools/python27-extract/SourceDir/python.exe'), '-B', str(source / 'run_module_build.py')],
                   cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
(game / 'WSE').mkdir(exist_ok=True)
(game / 'coop.ini').write_text('[Coop]\nHostIP=127.0.0.1\nPort=7440\nIpcPort=7442\nModule=NativeCoopProbe\n[Steam]\nSteamHost=0\n', encoding='ascii')
(game / 'probe_config.ini').write_text('[General]\niMaxFrameRate=60\nsStoragePath=%s\\\n[Network]\nbLoopbackServer=true\niNumPlayersLimit=250\niServerPort=7440\n' % (game / 'WSE'), encoding='ascii')
(game / 'ProbeHost.txt').write_text('set_max_players 10 10\nset_port 7440\nset_server_name NativeMissionProbe\nset_add_to_game_servers_list 0\nstart\n', encoding='ascii')
print('Native mission probe built at %s. No live modules modified.' % game)
