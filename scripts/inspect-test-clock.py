"""Read-only diagnostic for the pinned isolated host. Never writes memory."""
import ctypes
from ctypes import wintypes
import json
import re
import struct
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
mode = sys.argv[1] if len(sys.argv) > 1 else 'Host'
assert mode in ['Host', 'Client1', 'Client2', 'Probe', 'FullHost', 'FullClient', 'FullClient2']
server = mode in ['Host', 'Probe']
record_path = ('build/full-host-probe-client2.json' if mode == 'FullClient2' else
               'build/full-host-probe-client.json' if mode == 'FullClient' else
               'build/full-host-probe-process.json' if mode == 'FullHost' else
               'build/native-mission-probe-process.json' if mode == 'Probe' else 'build/local-process-%s.json' % mode)
record = json.loads((root / record_path).read_text(encoding='utf-8-sig'))
if server:
    log_path = 'runtime/NativeMissionProbe/Game/warband_coop_host.log' if mode == 'Probe' else 'runtime/LocalTest/Host/warband_coop_host.log'
    log = (root / log_path).read_text()
    slide = int(re.search(r'aslr_slide=0x([0-9A-Fa-f]+)', log).group(1), 16)
else:
    slide = 0
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k.OpenProcess.restype = wintypes.HANDLE
k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k.CloseHandle.argtypes = [wintypes.HANDLE]
handle = k.OpenProcess(0x10, False, record['id'])
if not handle:
    raise ctypes.WinError(ctypes.get_last_error())
def read(address, fmt):
    buf = ctypes.create_string_buffer(struct.calcsize(fmt))
    count = ctypes.c_size_t()
    if not k.ReadProcessMemory(handle, address, buf, len(buf), ctypes.byref(count)) or count.value != len(buf):
        raise ctypes.WinError(ctypes.get_last_error())
    values = struct.unpack(fmt, buf.raw)
    return values[0] if len(values) == 1 else values
try:
    game = read((0x8CC4AC if server else 0xA4F6A4) + slide, '<I')
    first = read((0x8D2A88 if server else 0xA84E88) + slide, '<I')
    variables_path = 'runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe/variables.txt' if mode in ['Probe', 'FullHost', 'FullClient', 'FullClient2'] else 'runtime/LocalTest/%s/Modules/NativeCoopTest/variables.txt' % mode
    variables = (root / variables_path).read_text().splitlines()
    timer_offset = 0x13E78 if server else 0x13E90
    result = {'game':hex(game), 'timer_index':read(game + timer_offset, '<i'),
              'timer_origin':read(game + timer_offset + 8, '<q'),
              'timers':read((0x8CC420 if server else 0xA4F600) + slide, '<qqq'),
              'cached_hour':read(game + timer_offset + 16, '<i')}
    result['mission'] = hex(read((0x8CC4B0 if server else 0xA4F6A8) + slide, '<I'))
    result['game_type'] = read((0x8D70F4 if server else 0xA89524) + slide, '<i')
    result['paused'] = read(game + (0x39C if server else 0x3B0), '<B')
    if not server:
        result['simple_trigger_count'] = read(game + 0x13D34, '<i')
    result['globals'] = {name:read(first + variables.index(name)*8, '<q') for name in
        ['g_coop_clock_sequence', 'g_coop_clock_hours', 'g_coop_clock_fraction', 'g_coop_pending_menu', 'g_coop_pending_menu_armed', 'g_coop_encounter_done']}
    if mode in ['Probe', 'FullHost', 'FullClient', 'FullClient2']:
        result['probe_globals'] = {name:read(first + variables.index(name)*8, '<q') for name in ['g_native_probe_started', 'g_probe_agent_a', 'g_probe_agent_b']}
        if mode in ['FullHost', 'FullClient', 'FullClient2']:
            result['probe_globals']['g_full_host_probe_request'] = read(first + variables.index('g_full_host_probe_request')*8, '<q')
            for name in ['g_full_probe_peer_ready', 'g_full_probe_remote_request', 'g_full_probe_remote_scene', 'g_full_probe_remote_template', 'g_probe_campaign_hour', 'g_probe_mission_seconds', 'g_probe_alive', 'g_probe_human_agent']:
                result['probe_globals'][name] = read(first + variables.index(name)*8, '<q')
            result['native_host'] = hex(read(0xAF771C, '<I'))
            result['receive_active'] = read(0xAF7701, '<B')
            for name in ['g_encounter_cycle_requested', 'g_cycle_result_sent', 'g_cycle_attacker', 'g_cycle_defender', 'g_cycle_armies_spawned', 'g_cycle_map_restore', 'g_full_probe_map_ready', 'g_full_probe_resume_ready', 'g_cycle_retreat_requested', 'g_autotest_round', 'g_autotest_phase', 'g_autotest_step', 'g_autotest_takeover_agent', 'g_autotest_order_observed', 'g_autotest_a', 'g_autotest_b']:
                if name in variables: result['probe_globals'][name] = read(first + variables.index(name)*8, '<q')
            result['native_mission_pending'] = read(0xA808C0, '<B')
            for name in variables:
                if name.startswith('g_retained_'):
                    result['probe_globals'][name]=read(first+variables.index(name)*8,'<q')
            result['native_next_scene'] = read(0xA808AC, '<i')
            result['native_next_template'] = read(0xA808B4, '<i')
            players = read(0xA80810, '<I')
            result['players'] = [dict(index=i, state=read(players+i*0x348, '<i'),
                ready=read(players+i*0x348+0x1B4, '<B'),
                team=read(players+i*0x348+0x1A8, '<i'),
                troop=read(players+i*0x348+0x1AC, '<i'),
                agent=read(players+i*0x348+0x1A0, '<i'),
                party=read(players+i*0x348+0x344, '<i')) for i in range(min(max(read(0xA44D68, '<i'), 0), 250))]
            for player in result['players']:
                if player['state'] != 2: continue
                slot_begin = read(players+player['index']*0x348+0x210, '<I')
                slot_end = read(players+player['index']*0x348+0x214, '<I')
                player['battle_slots'] = {slot:read(slot_begin+slot*8, '<q') for slot in range(6015,6029)
                    if slot_begin and slot_begin+(slot+1)*8 <= slot_end}
            party_chunks = read(game + 0x13D10, '<I')
            party_chunks_end = read(game + 0x13D14, '<I')
            wanted_parties = {player['party'] for player in result['players'] if player['party'] >= 0}
            for name in ['g_retained_fixture_enemy', 'g_cycle_attacker_party', 'g_cycle_defender_party']:
                if name in variables:
                    value = read(first + variables.index(name)*8, '<q')
                    if value > 0: wanted_parties.add(value)
            result['campaign_parties'] = []
            result['troop_health'] = {}
            troops=read(game+0x13D40,'<I')
            result['recent_hero_health']={i:read(troops+i*0x978+0x168,'<f') for i in [4,5,6,7,8,9,446,447]}
            for chunk_index in range(min((party_chunks_end-party_chunks)//4, 256)):
                party_chunk = read(party_chunks+chunk_index*4, '<I')
                if not party_chunk: continue
                for party_index in range(16):
                    party_address = party_chunk+party_index*0x5718
                    party_no = read(party_address+8, '<i')
                    if party_no not in wanted_parties or not read(party_address+4, '<i'): continue
                    stacks = read(party_address+0x138, '<I')
                    count = read(party_address+0x144, '<i')
                    result['campaign_parties'].append(dict(party=party_no,
                        flags=hex(read(party_address+0xC, '<I')), faction=read(party_address+0xF8, '<i'),
                        battle_opponent=read(party_address+0x10C, '<i'),
                        position=read(party_address+0x90, '<ff'),
                        stacks=[read(stacks+stack_index*0x1C, '<iiiiiii') for stack_index in range(min(max(count,0),128))]))
                    troops=read(game+0x13D40,'<I')
                    for stack in result['campaign_parties'][-1]['stacks']:
                        troop=stack[1]
                        result['troop_health'][troop]=read(troops+troop*0x978+0x168,'<f')
            mission = int(result['mission'], 16)
            chunks = read(mission+0x18, '<I')
            positions = []
            for player in result['players']:
                agent = player['agent']
                if agent < 0 or agent >= read(mission+8, '<i'): continue
                chunk = read(chunks+(agent>>4)*4, '<I')
                address = chunk+(agent & 15)*0x72E0
                entity = read(address+0x870, '<I')
                position = read(entity+0x84 if entity else address+0x38, '<fff')
                positions.append(dict(player=player['index'], agent=agent, position=position))
            result['player_positions'] = positions
            agent_count = read(mission+8, '<i')
            actors = []
            for agent in range(min(max(agent_count, 0), 4096)):
                chunk = read(chunks+(agent>>4)*4, '<I')
                address = chunk+(agent & 15)*0x72E0
                if read(address+4, '<i') == 0: continue
                actors.append(dict(agent=agent, team=read(address+0x7B8, '<i'),group=read(address+0x7BC, '<i'),health=read(address+0x6FDC, '<f'),
                    max_health=read(address+0x6FD8, '<f')))
            result['agent_health'] = actors
    print(json.dumps(result, indent=2))
finally:
    k.CloseHandle(handle)
