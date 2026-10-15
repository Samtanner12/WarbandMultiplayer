/* Isolated engine capability experiment. Never enabled in playable modules.
   Uses the full graphical engine's campaign server personality so both
   campaign and mission implementations are available in the same process.
   This alone does not implement combat replication or concurrent missions. */
static int g_full_host_probe_request_idx = -1;
static int g_full_host_probe_enabled = 0;
static int g_full_host_probe_attempted = 0;
static DWORD g_full_host_probe_clock_tick = 0;
static int g_full_host_probe_mission_live = 0;
static DWORD g_full_host_probe_mission_tick = 0;
static DWORD g_full_host_probe_game_trampoline = 0;
static BYTE g_full_host_probe_game_saved[16];
static int g_full_probe_inside_world_tick = 0;
static DWORD g_full_probe_world_tick = 0;
static DWORD g_full_probe_wall_anchor = 0;
static __int64 g_full_probe_timer_anchor = 0;
static int g_full_probe_client_enabled = 0;
static int g_full_probe_client_live = 0;
static int g_full_probe_client_return_pending = 0;
static int g_full_probe_resume_wait = 0;
static DWORD g_full_probe_player_update_trampoline = 0;
static BYTE g_full_probe_player_update_saved[16];
static int g_full_probe_peer_ready_idx = -1;
static int g_full_probe_expected_peers = 1;
static int g_full_probe_started_idx = -1;
static int g_full_probe_cycle_requested_idx = -1;
static int g_full_probe_map_ready_idx = -1;
static int g_full_probe_resume_ready_idx = -1;
static int g_full_probe_remote_request_idx = -1;
static int g_full_probe_remote_scene_idx = -1;
static int g_full_probe_remote_template_idx = -1;
static int g_full_probe_retreat_question_idx = -1;
static DWORD g_full_probe_server_send_trampoline = 0;
static DWORD g_full_probe_server_update_trampoline = 0;
static DWORD g_full_probe_server_listen_trampoline = 0;
static DWORD g_full_probe_client_send_trampoline = 0;
static DWORD g_full_probe_client_listen_trampoline = 0;
static BYTE g_full_probe_network_saved[5][16];
static DWORD g_full_probe_packet_trampoline = 0;
static BYTE g_full_probe_packet_saved[16];
/* Native sender runs on a worker thread. Its personality and replication
   tables must not change while the main thread initializes a mission. */
static CRITICAL_SECTION g_full_probe_role_lock;
static int g_full_probe_role_lock_initialized = 0;

/* Keep campaign replication dictionaries alive while the native initializer
   uses separate dictionaries for scene agents. Both streams share one socket,
   but their entity indices and delta histories are incompatible. */
static BYTE g_full_probe_campaign_peer_vectors[250][36];
static BYTE g_full_probe_campaign_peer_cursors[250][12];
static BYTE g_full_probe_campaign_data_vectors[2][12];
static BYTE g_full_probe_campaign_data_cursors[80];
static int g_full_probe_campaign_state_saved = 0;
static int g_full_probe_campaign_state_players = 0;
static void full_probe_save_campaign_replication(BYTE *players, int count) {
    int i;
    BYTE *data = (BYTE *)ADDR_NETMGR_DATA;
    if (g_full_probe_campaign_state_saved) return;
    for (i = 0; i < count; ++i) {
        BYTE *player = players+i*0x348;
        memcpy(g_full_probe_campaign_peer_vectors[i], player+0x170, 36);
        memcpy(g_full_probe_campaign_peer_cursors[i], player+0x334, 12);
        memset(player+0x170, 0, 36);
    }
    memcpy(g_full_probe_campaign_data_vectors[0], data+0x1B0, 12);
    memcpy(g_full_probe_campaign_data_vectors[1], data+0x1D4, 12);
    memcpy(g_full_probe_campaign_data_cursors, data+0x80, 80);
    memset(data+0x1B0, 0, 12); memset(data+0x1D4, 0, 12);
    g_full_probe_campaign_state_players = count;
    g_full_probe_campaign_state_saved = 1;
}
static void full_probe_restore_campaign_replication(void) {
    typedef void (__cdecl *native_free_fn)(void *);
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    BYTE *data = (BYTE *)ADDR_NETMGR_DATA;
    int i, v;
    if (!g_full_probe_campaign_state_saved || !players) return;
    /* Same primitive vector disposal as mbnetData::startMission. */
    for (i = 0; i < g_full_probe_campaign_state_players; ++i) {
        BYTE *player = players+i*0x348;
        for (v = 0; v < 3; ++v) {
            void *begin = *(void **)(player+0x170+v*12);
            if (begin) ((native_free_fn)0x852CCE)(begin);
        }
        memcpy(player+0x170, g_full_probe_campaign_peer_vectors[i], 36);
        memcpy(player+0x334, g_full_probe_campaign_peer_cursors[i], 12);
    }
    if (*(void **)(data+0x1B0)) ((native_free_fn)0x852CCE)(*(void **)(data+0x1B0));
    if (*(void **)(data+0x1D4)) ((native_free_fn)0x852CCE)(*(void **)(data+0x1D4));
    memcpy(data+0x1B0, g_full_probe_campaign_data_vectors[0], 12);
    memcpy(data+0x1D4, g_full_probe_campaign_data_vectors[1], 12);
    memcpy(data+0x80, g_full_probe_campaign_data_cursors, 80);
    g_full_probe_campaign_state_saved = 0;
    coop_log("[full-probe] campaign replication dictionaries restored on retained peer\n");
}

static int full_probe_participant(int player) {
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    __int64 *begin, *end;
    if (!players || player < 1 || player >= 250) return 0;
    begin = *(__int64 **)(players + player*0x348 + 0x210);
    end = *(__int64 **)(players + player*0x348 + 0x214);
    return begin && end-begin > 6015 && begin[6015] == 1;
}
static int full_probe_required_peers(void) {
    int i, count = 0;
    for (i=1; i<250; ++i) if (full_probe_participant(i)) ++count;
    return count ? count : g_full_probe_expected_peers;
}
/* Invitation is not a decoder switch. The joining client first resets its
   scene state and acknowledges event 44 on the reliable campaign channel. */
static int full_probe_combat_peer(int player) {
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    __int64 *begin, *end;
    if (!full_probe_participant(player)) return 0;
    begin = *(__int64 **)(players + player*0x348 + 0x210);
    end = *(__int64 **)(players + player*0x348 + 0x214);
    return begin && end-begin > 6000 && begin[6000] == 1;
}
static int full_probe_route_combat(void) {
    return g_full_host_probe_mission_live;
}
static void full_probe_exchange(void *live, void *saved, int size) {
    BYTE temp[80];
    memcpy(temp, live, size); memcpy(live, saved, size); memcpy(saved, temp, size);
}
/* Temporarily install the map dictionaries while processing a map peer.
   Swapping back keeps mutations in the saved map stream. Never copy/free
   either owner's allocations here; the final restore disposes combat only. */
static void full_probe_exchange_map(int player) {
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    BYTE *data = (BYTE *)ADDR_NETMGR_DATA;
    int i;
    if (!g_full_probe_campaign_state_saved || !players) return;
    full_probe_exchange(data+0x1B0, g_full_probe_campaign_data_vectors[0], 12);
    full_probe_exchange(data+0x1D4, g_full_probe_campaign_data_vectors[1], 12);
    full_probe_exchange(data+0x80, g_full_probe_campaign_data_cursors, 80);
    for (i=0; i<g_full_probe_campaign_state_players; ++i) {
        if (player >= 0 && i != player) continue;
        full_probe_exchange(players+i*0x348+0x170, g_full_probe_campaign_peer_vectors[i], 36);
        full_probe_exchange(players+i*0x348+0x334, g_full_probe_campaign_peer_cursors[i], 12);
    }
}
static void *g_full_probe_server_object = NULL;
static void full_probe_scene_admission(void);
static void __fastcall full_probe_receive_packet(void *server, void *unused, int player, void *buffer, void *control) {
    typedef void (__fastcall *method)(void *, void *, int, void *, void *);
    EnterCriticalSection(&g_full_probe_role_lock);
    int type = *(int *)ADDR_MAP_INTERACTION_MODE;
    int map = g_full_probe_campaign_state_saved && !full_probe_combat_peer(player);
    (void)unused;
    g_full_probe_server_object = server;
    if (map) { full_probe_exchange_map(player); *(int *)ADDR_MAP_INTERACTION_MODE = 5; }
    ((method)g_full_probe_packet_trampoline)(server, NULL, player, buffer, control);
    if (map) full_probe_exchange_map(player);
    *(int *)ADDR_MAP_INTERACTION_MODE = type;
    /* The scene acknowledgement (module event 44) was just applied. Release
       the hold before the mission trigger sends its confirmation, which a
       not-ready peer would otherwise never receive. */
    if (g_full_host_probe_mission_live) full_probe_scene_admission();
    LeaveCriticalSection(&g_full_probe_role_lock);
}

/* A disconnected participant cannot acknowledge scene exit. Check each
   remaining campaign peer instead of waiting forever for the original count. */
static int full_probe_return_peers_ready(int slot) {
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    int count = *(int *)ADDR_NUM_PLAYERS_LIMIT;
    int i;
    for (i = 1; players && i < count && i < 250; ++i) {
        BYTE *player = players+i*0x348;
        __int64 *begin, *end;
        if (*(int *)player != 2 || *(int *)(player+0x344) < 0) continue;
        if (!full_probe_participant(i)) continue;
        begin = *(__int64 **)(player+0x210);
        end = *(__int64 **)(player+0x214);
        if (!begin || end-begin <= slot || begin[slot] != 1) return 0;
    }
    return 1;
}

/* Native joiners are synchronized by mbnetNetworkServer::syncPlayer when the
   loading window reports ready; retained peers skip that window. Until a
   peer confirms its scene, scene events (agents, missiles, hits, props) are
   dropped from its queue: they name agents it never received. Its ready flag
   is left alone, since a not-ready peer's own messages are ignored. On
   confirmation the full scene state goes ahead of anything still queued. */
#define ADDR_SYNC_PLAYER       0x560CC0  /* mbnetNetworkServer::syncPlayer(int) */
#define ADDR_EVENT_PUSH_BACK   0x5685C0  /* vector<mbnetEvent>::push_back */
#define NET_EVENT_SIZE         0x228     /* mbnetEvent; type is the WORD at +4 */
static BYTE g_full_probe_scene_state[250];   /* 0 idle, 2 synchronized */

/* Types from the pinned mbnetNetworkManager::fill*ClientEvent writers. */
static int net_event_is_scene(WORD type) {
    return (type >= 5 && type <= 13) || (type >= 17 && type <= 23) ||
           (type >= 25 && type <= 30) || type == 40 || (type >= 42 && type <= 48) ||
           (type >= 50 && type <= 52) || (type >= 57 && type <= 60);
}

static void full_probe_drop_scene_events(BYTE *peer) {
    BYTE **queue = (BYTE **)(peer + 0x21C);
    BYTE *read, *write;
    if (!queue[0] || queue[1] <= queue[0]) return;
    write = queue[0];
    for (read = queue[0]; read < queue[1]; read += NET_EVENT_SIZE) {
        if (net_event_is_scene(*(WORD *)(read + 4))) continue;
        if (write != read) memmove(write, read, NET_EVENT_SIZE);
        write += NET_EVENT_SIZE;
    }
    queue[1] = write;
}

static void full_probe_sync_scene_peer(BYTE *peer, int player) {
    typedef void (__fastcall *sync_fn)(void *, void *, int);
    typedef void (__fastcall *push_fn)(void *, void *, const void *);
    BYTE **queue = (BYTE **)(peer + 0x21C);
    int pending = (queue[0] && queue[1] > queue[0]) ? (int)((queue[1] - queue[0]) / NET_EVENT_SIZE) : 0;
    int type = *(int *)ADDR_MAP_INTERACTION_MODE, i, kept = 0;
    BYTE ready = peer[0x1B4];
    BYTE *saved = NULL;
    if (pending) {
        saved = (BYTE *)malloc(pending * NET_EVENT_SIZE);
        if (!saved) return;
        memcpy(saved, queue[0], pending * NET_EVENT_SIZE);
        queue[1] = queue[0];   /* POD events: rep movs copies, no destructor */
    }
    *(int *)ADDR_MAP_INTERACTION_MODE = 3;
    peer[0x1B4] = 1;
    ((sync_fn)ADDR_SYNC_PLAYER)(g_full_probe_server_object, NULL, player);
    peer[0x1B4] = ready;
    *(int *)ADDR_MAP_INTERACTION_MODE = type;
    for (i = 0; i < pending; ++i) {
        BYTE *event = saved + i * NET_EVENT_SIZE;
        if (net_event_is_scene(*(WORD *)(event + 4))) continue;
        ((push_fn)ADDR_EVENT_PUSH_BACK)(peer + 0x21C, NULL, event);
        ++kept;
    }
    free(saved);
    coop_log("[full-host-probe] scene state synchronized for peer %d (%d queued events kept)\n", player, kept);
}

static void full_probe_scene_admission(void) {
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    int count = *(int *)ADDR_NUM_PLAYERS_LIMIT, i;
    if (!players || count < 1 || count > 250) return;
    for (i = 1; i < count; ++i) {
        BYTE *peer = players + i*0x348;
        int connected = *(int *)peer == 2;
        int admitting = g_full_host_probe_mission_live && connected && full_probe_participant(i) &&
            modglobals_get_int(g_full_host_probe_request_idx, 0) == 3;
        if (!admitting) { g_full_probe_scene_state[i] = 0; continue; }
        if (full_probe_combat_peer(i) && g_full_probe_scene_state[i] != 2 && g_full_probe_server_object) {
            full_probe_sync_scene_peer(peer, i);
            g_full_probe_scene_state[i] = 2;
        }
    }
}

static void __fastcall full_probe_server_send(void *server, void *unused, int player) {
    typedef void (__fastcall *method)(void *, void *, int);
    int type;
    EnterCriticalSection(&g_full_probe_role_lock);
    type = *(int *)ADDR_MAP_INTERACTION_MODE;
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    BYTE *peer = players && player > 0 && player < 250 ? players + player*0x348 : NULL;
    BYTE ready = peer ? peer[0x1B4] : 0;
    __int64 *slots = peer ? *(__int64 **)(peer+0x210) : NULL;
    __int64 *end = peer ? *(__int64 **)(peer+0x214) : NULL;
    (void)unused;
    int participant = full_probe_participant(player);
    int combat_peer = full_probe_combat_peer(player);
    int map = g_full_probe_campaign_state_saved && !combat_peer;
    if (map) full_probe_exchange_map(player);
    if (full_probe_route_combat() && combat_peer) *(int *)ADDR_MAP_INTERACTION_MODE = 3;
    else *(int *)ADDR_MAP_INTERACTION_MODE = 5;
    /* During admission send reliable events, but no campaign delta stream.
       The client has reset its replication state for the new scene. */
    if (peer && participant && ((!g_full_host_probe_mission_live && *(BYTE *)ADDR_MP_MODE_PENDING) ||
        (g_full_host_probe_mission_live && modglobals_get_int(g_full_host_probe_request_idx, 0) == 4)))
        peer[0x1B4] = 0;
    if (peer && participant && g_full_probe_resume_wait && (!slots || end-slots <= 6006 || slots[6006] != 1))
        peer[0x1B4] = 0;
    if (peer && participant && g_full_host_probe_mission_live && (!slots || end-slots <= 6000 || slots[6000] != 1)) peer[0x1B4] = 0;
    if (peer && participant && !combat_peer && g_full_host_probe_mission_live &&
        modglobals_get_int(g_full_host_probe_request_idx, 0) == 3)
        full_probe_drop_scene_events(peer);
    ((method)g_full_probe_server_send_trampoline)(server, NULL, player);
    if (peer) peer[0x1B4] = ready;
    if (map) full_probe_exchange_map(player);
    *(int *)ADDR_MAP_INTERACTION_MODE = type;
    LeaveCriticalSection(&g_full_probe_role_lock);
}
static void __fastcall full_probe_server_update(void *server, void *unused) {
    typedef void (__fastcall *method)(void *, void *);
    int type;
    EnterCriticalSection(&g_full_probe_role_lock);
    g_full_probe_server_object = server;
    type = *(int *)ADDR_MAP_INTERACTION_MODE;
    (void)unused;
    if (full_probe_route_combat()) *(int *)ADDR_MAP_INTERACTION_MODE = 3;
    {
        BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
        BYTE ready[250];
        int count = *(int *)ADDR_NUM_PLAYERS_LIMIT;
        int i, returning = g_full_host_probe_mission_live && modglobals_get_int(g_full_host_probe_request_idx, 0) == 4;
        if (count < 0 || count > 250) count = 0;
        for (i = 0; players && i < count; ++i) {
            ready[i] = players[i*0x348+0x1B4];
            if (returning || (g_full_host_probe_mission_live && !full_probe_combat_peer(i))) players[i*0x348+0x1B4] = 0;
        }
        ((method)g_full_probe_server_update_trampoline)(server, NULL);
        for (i = 0; players && i < count; ++i) players[i*0x348+0x1B4] = ready[i];
        if (g_full_probe_campaign_state_saved) {
            full_probe_exchange_map(-1);
            *(int *)ADDR_MAP_INTERACTION_MODE = 5;
            for (i=0; players && i<count; ++i) if (full_probe_combat_peer(i) || full_probe_participant(i)) players[i*0x348+0x1B4] = 0;
            ((method)g_full_probe_server_update_trampoline)(server, NULL);
            for (i=0; players && i<count; ++i) players[i*0x348+0x1B4] = ready[i];
            full_probe_exchange_map(-1);
        }
    }
    *(int *)ADDR_MAP_INTERACTION_MODE = type;
    LeaveCriticalSection(&g_full_probe_role_lock);
}
static void __fastcall full_probe_server_listen(void *server, void *unused) {
    typedef void (__fastcall *method)(void *, void *);
    int type;
    EnterCriticalSection(&g_full_probe_role_lock);
    type = *(int *)ADDR_MAP_INTERACTION_MODE;
    (void)unused;
    if (full_probe_route_combat()) *(int *)ADDR_MAP_INTERACTION_MODE = 3;
    ((method)g_full_probe_server_listen_trampoline)(server, NULL);
    *(int *)ADDR_MAP_INTERACTION_MODE = type;
    LeaveCriticalSection(&g_full_probe_role_lock);
}
static void __fastcall full_probe_client_send(void *client, void *unused) {
    typedef void (__fastcall *method)(void *, void *);
    int type = *(int *)ADDR_MAP_INTERACTION_MODE;
    (void)unused;
    if (g_full_probe_client_live) *(int *)ADDR_MAP_INTERACTION_MODE = 1;
    ((method)g_full_probe_client_send_trampoline)(client, NULL);
    *(int *)ADDR_MAP_INTERACTION_MODE = type;
}
static void __fastcall full_probe_player_update(void *client, void *unused) {
    typedef void (__fastcall *method)(void *, void *);
    if (g_full_probe_client_enabled && !g_full_host_probe_mission_live) return;
    ((method)g_full_probe_player_update_trampoline)(client, unused);
}
static unsigned char __fastcall full_probe_client_listen(void *client, void *unused, int poll) {
    typedef unsigned char (__fastcall *method)(void *, void *, int);
    int type = *(int *)ADDR_MAP_INTERACTION_MODE;
    unsigned char result;
    (void)unused;
    if (g_full_probe_client_live) *(int *)ADDR_MAP_INTERACTION_MODE = 1;
    result = ((method)g_full_probe_client_listen_trampoline)(client, NULL, poll);
    if (g_full_probe_client_live && !g_full_host_probe_mission_live &&
        modglobals_get_int(g_full_probe_remote_request_idx, 0) == 7) {
        full_probe_restore_campaign_replication();
        g_full_probe_client_live = 0;
        modglobals_set(g_full_probe_remote_request_idx, 0);
        coop_log("[full-client-probe] campaign decoder resumed after host barrier\n");
    }
    /* Native mission-info normally schedules the multiplayer loading window.
       This peer's scene is already initialized by the admission protocol.
       Re-entering that loader clears its character/party and repeats every
       mission-info retry, preventing an avatar from ever becoming ready. */
    if (g_full_probe_client_live && *(BYTE *)ADDR_MP_MODE_PENDING &&
        *(int *)ADDR_MP_SCENE_NO == modglobals_get_int(g_full_probe_remote_scene_idx, -1) &&
        *(int *)ADDR_MP_MT_NO == modglobals_get_int(g_full_probe_remote_template_idx, -1)) {
        *(BYTE *)ADDR_MP_MODE_PENDING = 0;
        coop_log("[full-client-probe] accepted mission information for initialized scene\n");
    }
    *(int *)ADDR_MAP_INTERACTION_MODE = type;
    return result;
}

static void full_host_probe_prepare_world_tick(void) {
    BYTE *game = (BYTE *)*(void **)ADDR_CUR_GAME;
    if (!g_full_host_probe_enabled || !game || *(int *)ADDR_MAP_INTERACTION_MODE != 5) return;
    game[OFF_PAUSED] = 0;
    *(float *)(game + 0x13E4C) = 1000000.0f;
    *(int *)(game + 0x13E58) = 1;
}

__declspec(naked) static void full_host_probe_game_tick_detour(void) {
    __asm {
        cmp dword ptr [g_full_host_probe_enabled], 0
        je world_tick_pass
        cmp dword ptr [g_full_host_probe_mission_live], 0
        je world_tick_pass
        cmp dword ptr [g_full_probe_inside_world_tick], 0
        jne world_tick_pass
        ret
    world_tick_pass:
        sub esp, 16
        movups [esp], xmm1
        pushad
        call full_host_probe_prepare_world_tick
        popad
        movups xmm1, [esp]
        add esp, 16
        jmp dword ptr [g_full_host_probe_game_trampoline]
    }
}

/* All these entry points are from the exact client PDB. The native loading
   window's sequence at 0x51AE15-0x51AEA7 preserves the network manager. */
static void full_host_probe_start_mission(void) {
    typedef void (__fastcall *native_void_fn)(void *, void *);
    typedef void (__fastcall *native_params_fn)(void *, void *, int, int, int);
    typedef void (__fastcall *native_slots_resize_fn)(void *, void *, int);
    typedef void (__fastcall *native_spawn_item_fn)(void *, void *, int, int);
    struct slot_copy { int count, party, troop; BYTE ready; __int64 *values; } copies[250];
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    void *peer_host = *(void **)ADDR_MBNET_HOST_PTR;
    int player_count = *(int *)ADDR_NUM_PLAYERS_LIMIT;
    int i, scene, mission_template;
    int mission_type = g_full_host_probe_enabled ? 3 : 1;
    if (g_full_host_probe_mission_live || !*(BYTE *)ADDR_MP_MODE_PENDING) return;
    /* Campaign clients must load before any native agent-spawn event can
       enter their reliable queue. Native ready alone refers to the map. */
    if (g_full_host_probe_enabled && (g_full_probe_peer_ready_idx < 0 ||
        modglobals_get_int(g_full_probe_peer_ready_idx, 0) < full_probe_required_peers())) return;
    if (!players || player_count < 1 || player_count > 250) return;
    memset(copies, 0, sizeof(copies));
    for (i = 0; i < player_count; ++i) {
        BYTE *player = players + i*0x348;
        __int64 *begin = *(__int64 **)(player + 0x210);
        __int64 *end = *(__int64 **)(player + 0x214);
        int count = (int)(end - begin);
        copies[i].party = *(int *)(player + 0x344);
        copies[i].troop = *(int *)(player + 0x1AC);
        copies[i].ready = player[0x1B4];
        if (count < 0 || count > 65536) goto failed_snapshot;
        copies[i].count = count;
        if (count) {
            copies[i].values = (__int64 *)malloc(count*sizeof(__int64));
            if (!copies[i].values) goto failed_snapshot;
            memcpy(copies[i].values, begin, count*sizeof(__int64));
        }
    }
    full_probe_save_campaign_replication(players, player_count);
    *(int *)ADDR_MAP_INTERACTION_MODE = mission_type;
    ((native_void_fn)0x53C240)((void *)ADDR_NETMGR_DATA, NULL);
    /* Native startMission clears player battle state and slot lengths.
       Restore campaign ownership/party state before mission triggers run. */
    for (i = 0; i < player_count; ++i) {
        BYTE *player = players + i*0x348;
        ((native_slots_resize_fn)0x5BE0E0)(player + 0x210, NULL, copies[i].count);
        if (copies[i].count) memcpy(*(void **)(player + 0x210), copies[i].values, copies[i].count*sizeof(__int64));
        *(int *)(player + 0x344) = copies[i].party;
        *(int *)(player + 0x1AC) = copies[i].troop;
        player[0x1B4] = copies[i].ready;
    }
    mission_template = *(int *)0xA808A8;
    scene = *(int *)0xA8089C;
    coop_log("[full-host-probe] starting native mission template=%d scene=%d host=%p\n",
             mission_template, scene, peer_host);
    ((native_params_fn)0x4EFE10)((void *)ADDR_META_MISSION, NULL, mission_template, scene, 0);
    ((native_void_fn)0x4EFE40)((void *)ADDR_META_MISSION, NULL);
    *((BYTE *)*(void **)ADDR_CUR_MISSION + 0x9B19) = 1;
    for (i = 0; i < player_count; ++i) {
        BYTE *player = players + i*0x348;
        ((native_slots_resize_fn)0x5BE0E0)(player + 0x210, NULL, copies[i].count);
        if (copies[i].count) memcpy(*(void **)(player + 0x210), copies[i].values, copies[i].count*sizeof(__int64));
        *(int *)(player + 0x344) = copies[i].party;
        *(int *)(player + 0x1AC) = copies[i].troop;
        player[0x1B4] = copies[i].ready;
        free(copies[i].values);
        /* The native initializer clears ready state before its after-start
           module trigger. Prepare this diagnostic player's spawn loadout
           after restoring that state and before the first native frame can
           automatically spawn its avatar. Item 17 is the pinned Native
           practice sword; this experiment never changes troop inventory. */
        if (g_full_host_probe_enabled && i > 0 && copies[i].party >= 0 &&
            copies[i].troop >= 0 && copies[i].ready && full_probe_participant(i))
            ((native_spawn_item_fn)0x567400)(player, NULL, 0, 17);
    }
    *(int *)ADDR_MAP_INTERACTION_MODE = g_full_host_probe_enabled ? 5 : 4;
    *(BYTE *)ADDR_MP_MODE_PENDING = 0;
    g_full_host_probe_mission_tick = GetTickCount();
    g_full_probe_world_tick = g_full_host_probe_mission_tick;
    g_full_probe_wall_anchor = g_full_host_probe_mission_tick;
    g_full_probe_timer_anchor = *(__int64 *)0xA4F600;
    g_full_host_probe_mission_live = 1;
    coop_log("[full-host-probe] mission started; retained host=%p receive_active=%d\n",
             *(void **)ADDR_MBNET_HOST_PTR, *(BYTE *)ADDR_NET_RUN_FLAG);
    return;
failed_snapshot:
    for (i = 0; i < player_count; ++i) free(copies[i].values);
    coop_log("[full-host-probe] invalid player slot snapshot; mission request not executed\n");
}

static void full_host_probe_mission_pump(void) {
    DWORD now;
    float delta;
    DWORD frame = 0x4FC450;
    void *mission;
    if (!g_full_host_probe_mission_live) {
        full_host_probe_start_mission();
        return;
    }
    if (g_full_host_probe_enabled && modglobals_get_int(g_full_host_probe_request_idx, 0) == 4) return;
    now = GetTickCount();
    delta = (DWORD)(now - g_full_host_probe_mission_tick) / 1000.0f;
    g_full_host_probe_mission_tick = now;
    if (delta <= 0) return;
    if (delta > 0.1f) delta = 0.1f;
    mission = *(void **)ADDR_CUR_MISSION;
    if (!mission) return;
    *(int *)ADDR_MAP_INTERACTION_MODE = 3;
    BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    BYTE ready[250];
    int pi;
    for (pi=0; players && pi<250; ++pi) {
        ready[pi]=players[pi*0x348+0x1B4];
        if (!full_probe_combat_peer(pi)) players[pi*0x348+0x1B4]=0;
    }
    /* Verified native ABI: this in ECX, delta in XMM1, bool on stack,
       callee removes the bool (see tactical call at 0x5C4892). */
    __asm {
        mov ecx, mission
        movss xmm1, delta
        push 1
        call dword ptr [frame]
    }
    for (pi=0; players && pi<250; ++pi) players[pi*0x348+0x1B4]=ready[pi];
    *(int *)ADDR_MAP_INTERACTION_MODE = 5;
}

static void full_host_probe_campaign_during_mission(void) {
    DWORD now;
    DWORD advance_timer = 0x682140;
    DWORD game_frame = ADDR_CAMPAIGN_TICK;
    float delta, correction;
    __int64 target, current;
    void *game;
    if (!g_full_host_probe_enabled || !g_full_host_probe_mission_live) return;
    game = *(void **)ADDR_CUR_GAME;
    if (!game) return;
    now = GetTickCount();
    delta = (DWORD)(now - g_full_probe_world_tick) / 1000.0f;
    g_full_probe_world_tick = now;
    if (delta <= 0) return;
    if (delta > 0.1f) delta = 0.1f;
    /* Mission startup suspends the graphical engine's ordinary real-time
       timer. Keep it on its wall-clock anchor, allowing the native network
       queue and retransmission timers to continue on the same peer. */
    target = g_full_probe_timer_anchor + (__int64)(DWORD)(now - g_full_probe_wall_anchor)*100;
    current = *(__int64 *)0xA4F600;
    if (current < target) {
        correction = (float)(target-current)/100000.0f;
        __asm {
            xor ecx, ecx
            movss xmm1, correction
            call dword ptr [advance_timer]
        }
    }
    *(int *)ADDR_MAP_INTERACTION_MODE = 5;
    g_full_probe_inside_world_tick = 1;
    full_probe_exchange_map(-1);
    __asm {
        mov ecx, game
        movss xmm1, delta
        call dword ptr [game_frame]
    }
    g_full_probe_inside_world_tick = 0;
    full_probe_exchange_map(-1);
}

static void full_host_probe_world_pump(void) {
    BYTE *game = (BYTE *)*(void **)ADDR_CUR_GAME;
    DWORD now;
    int timer;
    __int64 elapsed;
    if (!game || *(int *)ADDR_MAP_INTERACTION_MODE != 5) return;
    game[OFF_PAUSED] = 0;
    /* The graphical map tick normally waits for a local army's input.
       Its disassembly at 0x4B21E9-0x4B2237 uses these two fields for a
       waiting interval and a speed multiplier. Zero selects a 10.0 default;
       one explicitly selects the normal 1.0 multiplier.
       Keep the authoritative probe world running at that normal rate. */
    *(float *)(game + 0x13E4C) = 1000000.0f;
    *(int *)(game + 0x13E58) = 1;
    now = GetTickCount();
    if ((DWORD)(now - g_full_host_probe_clock_tick) < 200) return;
    g_full_host_probe_clock_tick = now;
    timer = *(int *)(game + 0x13E90);
    if (timer < 0 || timer > 2 || g_clock_sequence_idx < 0) return;
    elapsed = *(__int64 *)(0xA4F600 + timer*8) - *(__int64 *)(game + 0x13E98);
    if (elapsed < 0) return;
    modglobals_set(g_clock_hours_idx, elapsed / 100000);
    modglobals_set(g_clock_fraction_idx, (elapsed % 100000) / 100);
    modglobals_set(g_clock_sequence_idx, modglobals_get_int(g_clock_sequence_idx, 0) + 1);
}

static void full_host_probe_configure(void) {
    char ini[MAX_PATH], variables[MAX_PATH];
    const char *names[10] = { "g_full_host_probe_request", "g_full_probe_peer_ready",
        "g_full_probe_remote_request", "g_full_probe_remote_scene", "g_full_probe_remote_template",
        "g_native_probe_started", "g_encounter_cycle_requested", "g_full_probe_map_ready", "g_full_probe_resume_ready", "g_retained_retreat_question" };
    int indices[10];
    int host_requested, client_requested;
    if (strcmp(g_module_name, "NativeCoopProbe") != 0 ||
        g_steam_cfg.role != STEAM_ROLE_OFF) return;
    _snprintf(ini, sizeof(ini), "%s\\coop.ini", g_game_dir);
    ini[sizeof(ini)-1] = 0;
    /* Private two-PC testing is explicit. Keep the default localhost gate;
       this flag only enables the same mission hooks over a routed connection.
       It does not alter native serial-key/authentication checks or identities. */
    if (strcmp(g_host_ip, "127.0.0.1") != 0 &&
        GetPrivateProfileIntA("Development", "PrivateNetworkTest", 0, ini) != 1) return;
    host_requested = GetPrivateProfileIntA("Development", "FullHostProbe", 0, ini) == 1;
    client_requested = GetPrivateProfileIntA("Development", "FullClientProbe", 0, ini) == 1;
    g_full_probe_expected_peers = GetPrivateProfileIntA("Development", "ExpectedPeers", 1, ini);
    if (g_full_probe_expected_peers < 1 || g_full_probe_expected_peers > 2) return;
    if (!host_requested && !client_requested) return;
    _snprintf(variables, sizeof(variables), "%s\\Modules\\%s\\variables.txt", g_game_dir, g_module_name);
    variables[sizeof(variables)-1] = 0;
    modglobals_resolve(variables, names, indices, 10);
    g_full_host_probe_request_idx = indices[0];
    g_full_probe_peer_ready_idx = indices[1];
    g_full_probe_remote_request_idx = indices[2];
    g_full_probe_remote_scene_idx = indices[3];
    g_full_probe_remote_template_idx = indices[4];
    g_full_probe_started_idx = indices[5];
    g_full_probe_cycle_requested_idx = indices[6];
    g_full_probe_map_ready_idx = indices[7];
    g_full_probe_resume_ready_idx = indices[8];
    g_full_probe_retreat_question_idx = indices[9];
    if (g_full_host_probe_request_idx < 0) return;
    if (client_requested && !host_requested) {
        if (g_full_probe_remote_request_idx < 0 || g_full_probe_remote_scene_idx < 0 || g_full_probe_remote_template_idx < 0) return;
        if (!hook_install(0x545540, full_probe_client_send, 7, g_full_probe_network_saved[3], &g_full_probe_client_send_trampoline) ||
            !hook_install(0x53EED0, full_probe_client_listen, 6, g_full_probe_network_saved[4], &g_full_probe_client_listen_trampoline) ||
            !hook_install(0x545350, full_probe_player_update, 8, g_full_probe_player_update_saved, &g_full_probe_player_update_trampoline)) return;
        g_full_probe_client_enabled = 1;
        g_test_keep_campaign_connection = 1;
        coop_log("[full-client-probe] isolated native combat routing armed\n");
        return;
    }
    /* PDB-derived entry points, validated against the pinned x86 prologues. */
    if (memcmp((void *)ADDR_SERVER_CREATE, "\x55\x8B\xEC\x64\xA1\x00\x00\x00\x00", 9) != 0) {
        coop_log("[full-host-probe] unsupported server-start bytes; disabled\n");
        return;
    }
    InitializeCriticalSection(&g_full_probe_role_lock);
    g_full_probe_role_lock_initialized = 1;
    g_full_host_probe_enabled = 1;
    if (memcmp((void *)0x55A360, "\x55\x8B\xEC\x81\xEC\xE4\x00\x00\x00", 9) != 0 ||
        !hook_install(0x55A360, full_probe_receive_packet, 9,
                      g_full_probe_packet_saved, &g_full_probe_packet_trampoline)) {
        g_full_host_probe_enabled = 0;
        coop_log("[full-host-probe] per-peer decoder hook failed; disabled\n");
        return;
    }
    if (!hook_install(0x55CB10, full_probe_server_send, 6, g_full_probe_network_saved[0], &g_full_probe_server_send_trampoline) ||
        !hook_install(0x5602C0, full_probe_server_update, 9, g_full_probe_network_saved[1], &g_full_probe_server_update_trampoline) ||
        !hook_install(0x559F00, full_probe_server_listen, 6, g_full_probe_network_saved[2], &g_full_probe_server_listen_trampoline)) {
        g_full_host_probe_enabled = 0;
        coop_log("[full-host-probe] native routing hook failed; disabled\n");
        return;
    }
    if (memcmp((void *)ADDR_CAMPAIGN_TICK, "\x55\x8B\xEC\x83\xEC\x18\x56", 7) != 0 ||
        !hook_install(ADDR_CAMPAIGN_TICK, full_host_probe_game_tick_detour, 7,
                      g_full_host_probe_game_saved, &g_full_host_probe_game_trampoline)) {
        g_full_host_probe_enabled = 0;
        coop_log("[full-host-probe] world tick hook failed; disabled\n");
        return;
    }
    coop_log("[full-host-probe] isolated experiment armed; waiting for initialized SP world\n");
}

static void full_client_probe_pump(void) {
    typedef void (__fastcall *native_void_fn)(void *, void *);
    typedef void (__fastcall *native_event_fn)(void *, void *, void *);
    typedef void (__stdcall *native_window_fn)(int);
    char event[0x228];
    BYTE *players;
    int local_player, scene, mission_template;
    if (!g_full_probe_client_enabled) return;
    /* Native's modal retreat question stops its tactical update. Keep the
       retained socket alive while the player decides; combat stays on host. */
    if (g_full_probe_client_live && *(BYTE *)ADDR_NET_RUN_FLAG &&
        modglobals_get_int(g_full_probe_retreat_question_idx, 0) == 1) {
        static DWORD dialog_network_tick = 0;
        static int dialog_network_busy = 0;
        DWORD now = GetTickCount();
        if (!dialog_network_busy && (DWORD)(now-dialog_network_tick) >= 50) {
            dialog_network_tick = now;
            dialog_network_busy = 1;
            full_probe_client_send((void *)ADDR_NET_CLIENT_THIS, NULL);
            full_probe_client_listen((void *)ADDR_NET_CLIENT_THIS, NULL, 0);
            dialog_network_busy = 0;
        }
    }
    if (g_full_probe_client_return_pending) {
        g_full_probe_client_return_pending = 0;
        ((native_window_fn)ADDR_SET_WINDOW)(6);
        modglobals_set(g_full_probe_remote_request_idx, g_full_probe_resume_ready_idx >= 0 ? 8 : 0);
        coop_log("[full-client-probe] encounter menu closed; retained campaign map opened\n");
        return;
    }
    if (g_full_probe_client_live) {
        if (modglobals_get_int(g_full_probe_remote_request_idx, 0) != 3) return;
        modglobals_set(g_full_probe_remote_request_idx, 4);
        players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
        if (!players) return;
        *(int *)ADDR_MAP_INTERACTION_MODE = 1;
        ((native_void_fn)0x539F10)(event, NULL);
        ((native_event_fn)0x54D410)((void *)ADDR_NETMGR_HOST, NULL, event);
        ((native_event_fn)0x567720)(players, NULL, event);
        *(int *)ADDR_MAP_INTERACTION_MODE = 4;
        coop_log("[full-client-probe] requested mission information after host scene confirmation\n");
        return;
    }
    if (*(int *)ADDR_MAP_INTERACTION_MODE != 4 ||
        modglobals_get_int(g_full_probe_remote_request_idx, 0) != 1) return;
    scene = modglobals_get_int(g_full_probe_remote_scene_idx, -1);
    mission_template = modglobals_get_int(g_full_probe_remote_template_idx, -1);
    if (scene < 0 || mission_template < 0) return;
    modglobals_set(g_full_probe_remote_request_idx, 2);
    *(int *)ADDR_MP_SCENE_NO = scene;
    *(int *)ADDR_MP_MT_NO = mission_template;
    *(BYTE *)ADDR_MP_MODE_PENDING = 1;
    full_host_probe_start_mission();
    if (!g_full_host_probe_mission_live) return;
    players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
    local_player = *(int *)ADDR_LOCAL_PLAYER_IDX;
    if (!players || local_player < 0 || local_player >= *(int *)ADDR_NUM_PLAYERS_LIMIT) return;
    players[local_player*0x348 + 0x1B4] = 1;
    g_full_probe_client_live = 1;
    *(int *)ADDR_MAP_INTERACTION_MODE = 1;
    /* Native multiplayer loading window recipe, with no connection reset. */
    /* Reset the tactical window before opening it. Its previous campaign
       visit can retain an agent index, which onOpen otherwise dereferences
       before the server has assigned the combat avatar. */
    {
        void *window = *(void **)0xABB978;
        native_void_fn reset_window = (native_void_fn)(*(DWORD **)window)[6];
        reset_window(window, NULL);
    }
    *(int *)(*(BYTE **)0xABB978 + 0x14) = 100;
    ((native_window_fn)ADDR_SET_WINDOW)(10);
    *(int *)ADDR_MAP_INTERACTION_MODE = 4;
    coop_log("[full-client-probe] tactical scene opened; original host=%p player=%d\n",
             *(void **)ADDR_MBNET_HOST_PTR, local_player);
}

static void full_host_probe_pump_locked(void) {
    typedef void (__fastcall *winsock_fn)(void *, void *);
    typedef unsigned char (__fastcall *start_server_fn)(void *, void *);
    unsigned char started;
    full_client_probe_pump();
    if (!g_full_host_probe_enabled) return;
    if (g_full_host_probe_attempted) {
        if (g_full_probe_resume_wait && g_full_probe_resume_ready_idx >= 0 &&
            full_probe_return_peers_ready(6006))
            g_full_probe_resume_wait = 0;
        static DWORD return_requested_at = 0;
        if (g_full_host_probe_mission_live && modglobals_get_int(g_full_host_probe_request_idx, 0) == 4) {
            typedef void (__fastcall *native_end_fn)(void *, void *, int);
            BYTE *players = *(BYTE **)ADDR_NET_PLAYERS_VEC;
            int count = *(int *)ADDR_NUM_PLAYERS_LIMIT;
            int i;
            if (!return_requested_at) return_requested_at = GetTickCount();
            /* Let the native reliable queues deliver the end-of-scene event
               before changing the host's outgoing replication personality. */
            if ((DWORD)(GetTickCount() - return_requested_at) >= 200 &&
                ((g_full_probe_map_ready_idx >= 0 && full_probe_return_peers_ready(6004)) ||
                 (g_full_probe_map_ready_idx < 0 && (DWORD)(GetTickCount() - return_requested_at) >= 2000))) {
                *(int *)ADDR_MAP_INTERACTION_MODE = 5;
                ((native_end_fn)0x4EFEC0)((void *)ADDR_META_MISSION, NULL, 1);
                full_probe_restore_campaign_replication();
                g_full_probe_resume_wait = g_full_probe_resume_ready_idx >= 0;
                g_full_host_probe_mission_live = 0;
                for (i = 1; players && i < count && i < 250; ++i) {
                    BYTE *player = players + i*0x348;
                    __int64 *slots = *(__int64 **)(player + 0x210);
                    __int64 *end = *(__int64 **)(player + 0x214);
                    *(int *)(player + 0x1A0) = -1;
                    if (slots && end-slots > 6001) { slots[6000] = 0; slots[6001] = 0; }
                }
                modglobals_set(g_full_probe_peer_ready_idx, 0);
                if (g_full_probe_started_idx >= 0) modglobals_set(g_full_probe_started_idx, 0);
                if (g_full_probe_cycle_requested_idx >= 0) modglobals_set(g_full_probe_cycle_requested_idx, 0);
                modglobals_set(g_full_host_probe_request_idx, 3);
                coop_log("[full-host-probe] scene cleanup completed; retained campaign host=%p\n", *(void **)ADDR_MBNET_HOST_PTR);
                return_requested_at = 0;
            }
        }
        full_probe_scene_admission();
        if (modglobals_get_int(g_full_host_probe_request_idx, 0) >= 3)
            full_host_probe_world_pump();
        full_host_probe_mission_pump();
        full_host_probe_campaign_during_mission();
        full_host_probe_prepare_world_tick();
        return;
    }
    if (modglobals_get_int(g_full_host_probe_request_idx, 0) != 1) return;
    if (*(int *)ADDR_MAP_INTERACTION_MODE != 0 || !*(void **)ADDR_CUR_GAME ||
        *(BYTE *)ADDR_NET_RUN_FLAG != 0) return;
    /* startServer indexes g_multiplayerData's profile list (0xA80744) by the
       selected profile (0xA80740); with no profiles.dat both are empty. */
    if (*(int *)0xA80740 < 0 || !*(void **)0xA80744) {
        static int warned = 0;
        if (!warned) {
            warned = 1;
            coop_log("[full-host-probe] no multiplayer profile loaded; create one under Multiplayer, then restart the host\n");
        }
        return;
    }
    g_full_host_probe_attempted = 1;
    modglobals_set(g_full_host_probe_request_idx, 2);
    ((winsock_fn)ADDR_WSA_INIT)((void *)ADDR_NETMGR_HOST, NULL);
    *(unsigned short *)(ADDR_NETMGR_HOST + NETMGR_OFF_PORT) = (unsigned short)g_port;
    *(int *)ADDR_MAP_INTERACTION_MODE = 5;
    started = ((start_server_fn)ADDR_SERVER_CREATE)((void *)ADDR_NETMGR_HOST, NULL);
    if (!started) {
        *(int *)ADDR_MAP_INTERACTION_MODE = 0;
        modglobals_set(g_full_host_probe_request_idx, -1);
        coop_log("[full-host-probe] native server start failed; SP personality restored\n");
        return;
    }
    /* startServer initializes a generic MP mission. The isolated campaign
       keeps its existing map; scene creation is a separate controlled probe. */
    *(BYTE *)ADDR_MP_MODE_PENDING = 0;
    modglobals_set(g_full_host_probe_request_idx, 3);
    coop_log("[full-host-probe] native campaign listener started on %d; gameType=%d\n",
             g_port, *(int *)ADDR_MAP_INTERACTION_MODE);
}

static void full_host_probe_pump(void) {
    if (g_full_probe_role_lock_initialized) EnterCriticalSection(&g_full_probe_role_lock);
    full_host_probe_pump_locked();
    if (g_full_probe_role_lock_initialized) LeaveCriticalSection(&g_full_probe_role_lock);
}
