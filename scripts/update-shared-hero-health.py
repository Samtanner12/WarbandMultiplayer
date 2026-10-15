"""Add host health broadcasts to the source and isolated probe, without staging."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
for source in [root/'WarbandTogether/wse2work/Native-Coop-master', root/'runtime/NativeMissionProbe/Source']:
    path=source/'header_common.py'; text=path.read_text(encoding='cp1254')
    marker='multiplayer_event_multiplayer_campaign_server_event_player_faction = 65'
    if 'multiplayer_event_multiplayer_campaign_server_event_hero_health = 66' not in text:
        text=text.replace(marker, marker+'\n# Shared hero health: troop id, percentage. Host authority, no XP transfer.\nmultiplayer_event_multiplayer_campaign_server_event_hero_health = 66')
    path.write_text(text,encoding='cp1254')
    path=source/'module_campaign_sync.py';text=path.read_text(encoding='cp1254')
    marker='        # Native hourly healing writes health directly, bypassing setter hooks.'
    if 'Shared health of rival armies' not in text:
        text=text.replace(marker, '''        # Shared health of rival armies also needs a host refresh. Character
        # packets only update their owner; do not transfer another hero's XP.
        (try_for_range, ":stack", 0, ":stacks"),
            (party_stack_get_troop_id, ":troop", ":party", ":stack"),
            (troop_is_hero, ":troop"), (store_troop_health, ":percent", ":troop"),
            (try_for_players, ":recipient", 1), (player_is_active, ":recipient"),
                (player_slot_eq, ":recipient", slot_player_coop_char_state, coop_char_state_ready),
                (multiplayer_send_3_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
                    multiplayer_event_multiplayer_campaign_server_event_hero_health, ":troop", ":percent"),
            (try_end),
        (try_end),
'''+marker,1)
    path.write_text(text,encoding='cp1254')
    path=source/'module_coop_scripts.py';text=path.read_text(encoding='cp1254')
    marker='            (eq, ":event_type", multiplayer_event_multiplayer_campaign_server_event_clock),'
    if '(eq, ":event_type", multiplayer_event_multiplayer_campaign_server_event_hero_health)' not in text:
        text=text.replace(marker,'''            (eq, ":event_type", multiplayer_event_multiplayer_campaign_server_event_hero_health),
            (store_script_param, ":hero", 2), (store_script_param, ":percent", 3),
            (is_between, ":hero", 0, heroes_end), (troop_is_hero, ":hero"),
            (is_between, ":percent", 0, 101), (troop_set_health, ":hero", ":percent"),
        (else_try),
'''+marker,1)
    path.write_text(text,encoding='cp1254')
print('Shared hero health source updated; stop probe processes before staging.')
