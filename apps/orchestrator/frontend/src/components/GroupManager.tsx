import { useState, useEffect, useCallback } from 'react'
import { Users, Plus, Trash2, UserPlus, UserMinus, Play, Power, Server, Settings, Cpu, Gauge, Cloud, Map, Car, Trophy, Timer, Flag, Sun, Clock, ChevronRight, Zap } from 'lucide-react'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface RigGroup {
    id: string
    name: string
    mode: 'multiplayer' | 'solo'
    rig_ids: string[]
    track: string
    weather: string
    car_pool: string[]
    ai_count: number
    ai_difficulty: number
    practice_time: number
    qualy_time: number
    race_laps: number
    sun_angle: number
    time_mult: number
    session_duration_min: number
    ambient_temp: number
    track_grip: number
    freeplay: boolean
}

const AI_STEPS = [
    { value: 0,   label: 'Off' },
    { value: 20,  label: 'Beginner' },
    { value: 40,  label: 'Easy' },
    { value: 60,  label: 'Medium' },
    { value: 80,  label: 'Hard' },
    { value: 100, label: 'Alien' },
]

interface ServerInfo {
    group_id: string
    group_name: string
    port: number
    http_port: number
    track: string
    cars: string[]
    status: string
    pid: number | null
    ai_count: number
    ai_difficulty: number
    max_clients: number
}

interface Rig {
    rig_id: string
    ip: string
    status: string
    selected_car?: string | null
    group_id?: string | null
    mode?: string
}

interface CatalogCar { id: string; name: string; brand: string; car_class: string }
interface CatalogTrack { id: string; name: string }
interface CatalogWeather { id: string; name: string }

interface GroupManagerProps {
    rigs: Rig[]
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const TIME_STEPS = [
    { angle: -16,  label: 'Dawn' },
    { angle: 8,    label: 'Sunrise' },
    { angle: 24,   label: 'Morning' },
    { angle: 40,   label: 'Late Morning' },
    { angle: 56,   label: 'Midday' },
    { angle: 72,   label: 'Early Afternoon' },
    { angle: 88,   label: 'Afternoon' },
    { angle: 104,  label: 'Late Afternoon' },
    { angle: 120,  label: 'Sunset' },
    { angle: 136,  label: 'Dusk' },
    { angle: 163,  label: 'Night' },
]

function angleToStepIndex(angle: number): number {
    let best = 0
    let bestDist = Math.abs(angle - TIME_STEPS[0].angle)
    for (let i = 1; i < TIME_STEPS.length; i++) {
        const d = Math.abs(angle - TIME_STEPS[i].angle)
        if (d < bestDist) { best = i; bestDist = d }
    }
    return best
}

/** Strip common AC prefixes (ks_, ac_, etc.) and format for display */
function displayName(id: string): string {
    let name = id
    // Strip common prefixes
    for (const prefix of ['ks_', 'ac_', 'acu_', 'rss_', 'tc_']) {
        if (name.toLowerCase().startsWith(prefix)) {
            name = name.slice(prefix.length)
            break
        }
    }
    // Replace underscores with spaces, title case
    return name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function GroupManager({ rigs }: GroupManagerProps) {
    const [groups, setGroups] = useState<RigGroup[]>([])
    const [servers, setServers] = useState<ServerInfo[]>([])
    const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
    const [newGroupName, setNewGroupName] = useState('')
    const [newGroupMode, setNewGroupMode] = useState<'multiplayer' | 'solo'>('multiplayer')

    // Catalogs from backend
    const [cars, setCars] = useState<CatalogCar[]>([])
    const [tracks, setTracks] = useState<CatalogTrack[]>([])
    const [weather, setWeather] = useState<CatalogWeather[]>([])

    /* ---- Data fetching ---- */

    const fetchGroups = useCallback(async () => {
        try {
            const res = await fetch('/api/groups/')
            const data = await res.json()
            if (Array.isArray(data)) {
                setGroups(prev => {
                    const nj = JSON.stringify(data)
                    return nj !== JSON.stringify(prev) ? data : prev
                })
            }
        } catch { /* offline */ }
    }, [])

    const fetchServers = useCallback(async () => {
        try {
            const res = await fetch('/api/server/list')
            const data = await res.json()
            if (Array.isArray(data)) {
                setServers(prev => {
                    const nj = JSON.stringify(data)
                    return nj !== JSON.stringify(prev) ? data : prev
                })
            }
        } catch { /* offline */ }
    }, [])

    const fetchCatalogs = useCallback(async () => {
        try {
            const res = await fetch('/api/catalogs')
            const data = await res.json()
            setCars(data.cars || [])
            setTracks(data.tracks || [])
            setWeather(data.weather || [])
        } catch { /* offline */ }
    }, [])

    useEffect(() => {
        fetchGroups(); fetchServers(); fetchCatalogs()
        const interval = setInterval(() => { fetchGroups(); fetchServers() }, 3000)
        return () => clearInterval(interval)
    }, [fetchGroups, fetchServers, fetchCatalogs])

    /* ---- Group CRUD ---- */

    const createGroup = async () => {
        if (!newGroupName.trim()) return
        const res = await fetch('/api/groups/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newGroupName, mode: newGroupMode })
        })
        const created = await res.json()
        setNewGroupName('')
        fetchGroups()
        if (created.id) setSelectedGroupId(created.id)
    }

    const deleteGroup = async (groupId: string) => {
        await fetch(`/api/groups/${groupId}`, { method: 'DELETE' })
        if (selectedGroupId === groupId) setSelectedGroupId(null)
        fetchGroups()
    }

    const updateGroup = async (groupId: string, updates: Partial<RigGroup>) => {
        await fetch(`/api/groups/${groupId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        })
        fetchGroups()
    }

    const addRigToGroup = async (groupId: string, rigId: string) => {
        await fetch(`/api/groups/${groupId}/rigs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rig_id: rigId })
        })
        fetchGroups()
    }

    const removeRigFromGroup = async (groupId: string, rigId: string) => {
        await fetch(`/api/groups/${groupId}/rigs/${rigId}`, { method: 'DELETE' })
        fetchGroups()
    }

    const setRigCar = async (rigId: string, carId: string) => {
        await fetch(`/api/rigs/${rigId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ selected_car: carId })
        })
    }

    /* ---- Group commands ---- */

    const sendGroupCommand = async (groupId: string, action: string) => {
        const group = groups.find(g => g.id === groupId)
        if (!group) return
        await fetch(`/api/command/group/${groupId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rig_id: 'GROUP',
                action,
                track: group.track,
                weather: group.weather,
                practice_time: group.practice_time,
                qualy_time: group.qualy_time,
                race_laps: group.race_laps,
                ai_count: group.ai_count,
                ai_difficulty: group.ai_difficulty,
                car_pool: group.car_pool,
                use_server: group.mode === 'multiplayer',
            })
        })
    }

    const startServerForGroup = async (groupId: string) => {
        const group = groups.find(g => g.id === groupId)
        if (!group) return
        const res = await fetch('/api/server/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                group_id: groupId,
                track: group.track,
                cars: group.car_pool,
                race_laps: group.race_laps,
                practice_time: group.practice_time,
                qualy_time: group.qualy_time,
                weather: group.weather,
                max_clients: group.rig_ids.length + group.ai_count + 2,
                ai_count: group.ai_count,
                ai_difficulty: group.ai_difficulty,
                sun_angle: group.sun_angle,
                time_mult: group.time_mult,
            })
        })
        const data = await res.json()
        if (data.status === 'error') alert(`Server failed: ${data.message}`)
        fetchServers()
    }

    const stopServerForGroup = async (groupId: string) => {
        await fetch(`/api/server/stop/${groupId}`, { method: 'POST' })
        fetchServers()
    }

    /* ---- Derived data ---- */

    const assignedRigIds = new Set(groups.flatMap(g => g.rig_ids))
    const unassignedRigs = rigs.filter(r => !assignedRigIds.has(r.rig_id))
    const getServerForGroup = (gid: string) => servers.find(s => s.group_id === gid)
    const selectedGroup = groups.find(g => g.id === selectedGroupId) || null
    const selectedServer = selectedGroupId ? getServerForGroup(selectedGroupId) : null
    const isSelectedServerRunning = selectedServer?.status === 'running'

    /* ---- Render ---- */

    return (
        <div className="flex h-[calc(100vh-120px)]">
            {/* ===== LEFT SIDEBAR — Group List ===== */}
            <div className="w-72 border-r border-white/10 bg-black/20 flex flex-col shrink-0">
                {/* Create group */}
                <div className="p-4 border-b border-white/10">
                    <div className="flex gap-2 mb-2">
                        <input
                            type="text"
                            placeholder="New group..."
                            value={newGroupName}
                            onChange={e => setNewGroupName(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && createGroup()}
                            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-ridge-brand transition-all font-bold text-xs"
                        />
                        <button
                            onClick={createGroup}
                            disabled={!newGroupName.trim()}
                            className="bg-ridge-brand hover:bg-orange-600 disabled:opacity-30 disabled:cursor-not-allowed p-2 rounded-lg transition-all"
                        >
                            <Plus size={14} />
                        </button>
                    </div>
                    <select
                        value={newGroupMode}
                        onChange={e => setNewGroupMode(e.target.value as 'multiplayer' | 'solo')}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 outline-none font-bold text-[10px] uppercase appearance-none cursor-pointer"
                    >
                        <option value="multiplayer">Multiplayer</option>
                        <option value="solo">Solo</option>
                    </select>
                </div>

                {/* Group list */}
                <div className="flex-1 overflow-y-auto">
                    {groups.map(group => {
                        const serverInfo = getServerForGroup(group.id)
                        const isActive = selectedGroupId === group.id
                        const isRunning = serverInfo?.status === 'running'
                        const isLive = group.rig_ids.some(rid => rigs.find(r => r.rig_id === rid && r.status === 'racing'))
                        return (
                            <button
                                key={group.id}
                                onClick={() => setSelectedGroupId(group.id)}
                                className={`w-full text-left p-4 border-b border-white/5 transition-all group ${
                                    isActive
                                        ? 'bg-ridge-brand/10 border-l-2 border-l-ridge-brand'
                                        : 'hover:bg-white/5 border-l-2 border-l-transparent'
                                }`}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 min-w-0">
                                        {isRunning && <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shrink-0" />}
                                        <span className="font-black italic text-sm uppercase tracking-tight truncate">{group.name}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5 shrink-0">
                                        <span className={`px-1.5 py-0.5 rounded text-[7px] font-black uppercase tracking-widest ${
                                            group.mode === 'multiplayer'
                                                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                        }`}>{group.mode === 'multiplayer' ? 'MP' : 'SOLO'}</span>
                                        {isLive && (
                                            <span className="px-1.5 py-0.5 rounded text-[7px] font-black uppercase tracking-widest bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1 animate-pulse">
                                                <div className="w-1.5 h-1.5 rounded-full bg-red-500" /> LIVE
                                            </span>
                                        )}
                                        <ChevronRight size={12} className="text-white/20" />
                                    </div>
                                </div>
                                <div className="text-[9px] text-white/30 font-mono mt-1">
                                    {group.rig_ids.length} rigs · {group.ai_count} AI · {group.race_laps} laps
                                </div>
                            </button>
                        )
                    })}
                    {groups.length === 0 && (
                        <div className="p-8 text-center">
                            <Users size={32} className="mx-auto mb-3 text-white/10" />
                            <p className="text-xs text-white/20 font-bold uppercase">No groups</p>
                        </div>
                    )}
                </div>

                {/* Unassigned rigs tray */}
                {unassignedRigs.length > 0 && (
                    <div className="border-t border-white/10 p-3">
                        <h4 className="text-[9px] text-white/30 font-black uppercase tracking-widest mb-2 flex items-center gap-1.5">
                            <UserPlus size={10} className="text-amber-400" /> Unassigned ({unassignedRigs.length})
                        </h4>
                        <div className="flex flex-wrap gap-1.5">
                            {unassignedRigs.map(rig => (
                                <div
                                    key={rig.rig_id}
                                    className="bg-black/30 px-2 py-1 rounded-lg border border-white/5 text-[9px] font-bold flex items-center gap-1.5 cursor-pointer hover:border-ridge-brand/30 transition-all"
                                    onClick={() => selectedGroupId && addRigToGroup(selectedGroupId, rig.rig_id)}
                                    title={selectedGroupId ? `Click to add to selected group` : 'Select a group first'}
                                >
                                    <div className={`w-1.5 h-1.5 rounded-full ${rig.status === 'racing' ? 'bg-ridge-brand' : 'bg-white/20'}`} />
                                    {rig.rig_id}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* ===== RIGHT PANEL — Selected Group Detail ===== */}
            <div className="flex-1 overflow-y-auto">
                {selectedGroup ? (
                    <div className="p-6 space-y-6 max-w-5xl">
                        {/* Group Header + Actions */}
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-2xl font-black italic uppercase tracking-tighter flex items-center gap-3">
                                    {selectedGroup.name}
                                    <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${
                                        selectedGroup.mode === 'multiplayer'
                                            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                            : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                    }`}>{selectedGroup.mode}</span>
                                    {isSelectedServerRunning && (
                                        <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase bg-green-500/20 text-green-400 border border-green-500/30 flex items-center gap-1">
                                            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" /> Server :{selectedServer?.port}
                                        </span>
                                    )}
                                </h2>
                            </div>
                            <div className="flex items-center gap-2">
                                {selectedGroup.mode === 'multiplayer' && (
                                    isSelectedServerRunning ? (
                                        <button onClick={() => stopServerForGroup(selectedGroup.id)}
                                            className="bg-red-500/10 hover:bg-red-500/20 text-red-400 px-4 py-2 rounded-xl transition-all flex items-center gap-2 text-xs font-black uppercase">
                                            <Server size={14} /> Stop Server
                                        </button>
                                    ) : (
                                        <button onClick={() => startServerForGroup(selectedGroup.id)}
                                            className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 px-4 py-2 rounded-xl transition-all flex items-center gap-2 text-xs font-black uppercase">
                                            <Server size={14} /> Deploy Server
                                        </button>
                                    )
                                )}
                                <button onClick={() => sendGroupCommand(selectedGroup.id, 'LAUNCH_RACE')}
                                    disabled={selectedGroup.mode === 'multiplayer' && !isSelectedServerRunning}
                                    className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 text-xs font-black uppercase ${
                                        selectedGroup.mode === 'multiplayer' && !isSelectedServerRunning
                                            ? 'bg-white/5 text-white/20 cursor-not-allowed'
                                            : 'bg-ridge-brand/10 hover:bg-ridge-brand/20 text-ridge-brand'
                                    }`}
                                    title={selectedGroup.mode === 'multiplayer' && !isSelectedServerRunning ? 'Deploy server first' : 'Start Race'}>
                                    <Play size={14} /> {selectedGroup.mode === 'multiplayer' && !isSelectedServerRunning ? 'Server Required' : 'Start Race'}
                                </button>
                                <button onClick={() => sendGroupCommand(selectedGroup.id, 'KILL_RACE')}
                                    className="bg-red-500/10 hover:bg-red-500/20 text-red-400 px-4 py-2 rounded-xl transition-all flex items-center gap-2 text-xs font-black uppercase">
                                    <Power size={14} /> Kill
                                </button>
                                <button onClick={() => deleteGroup(selectedGroup.id)}
                                    className="bg-white/5 hover:bg-red-500/20 text-white/20 hover:text-red-400 p-2 rounded-xl transition-all">
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        </div>

                        {/* ---- Rig Assignment Row ---- */}
                        <div className="glass rounded-2xl p-5 border border-white/10">
                            <h3 className="text-[9px] font-black uppercase tracking-widest text-white/40 mb-3 flex items-center gap-1.5">
                                <Users size={10} /> Assigned Rigs ({selectedGroup.rig_ids.length})
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {selectedGroup.rig_ids.map(rigId => {
                                    const rig = rigs.find(r => r.rig_id === rigId)
                                    return (
                                        <div key={rigId} className="bg-black/30 border border-white/5 rounded-xl px-3 py-2.5 flex items-center gap-3 group hover:border-white/15 transition-all">
                                            <div className={`w-2 h-2 rounded-full ${
                                                rig?.status === 'racing' ? 'bg-ridge-brand animate-pulse' :
                                                rig?.status === 'ready' ? 'bg-green-500' :
                                                rig?.status === 'setup' ? 'bg-blue-500 animate-pulse' :
                                                rig ? 'bg-white/20' : 'bg-red-500'
                                            }`} />
                                            <span className="font-black italic text-xs">{rigId}</span>

                                            {/* Per-rig car selector — shows all globally available cars */}
                                            <select
                                                value={rig?.selected_car || ''}
                                                onChange={e => setRigCar(rigId, e.target.value)}
                                                className="bg-white/5 border border-white/10 rounded-lg px-2 py-0.5 text-[10px] font-bold outline-none focus:border-ridge-brand appearance-none max-w-40 cursor-pointer"
                                            >
                                                <option value="">Auto</option>
                                                {cars.filter((car, i, arr) => arr.findIndex(c => c.id === car.id) === i).map(car => (
                                                    <option key={car.id} value={car.id}>{displayName(car.id)}</option>
                                                ))}
                                            </select>

                                            <button onClick={() => removeRigFromGroup(selectedGroup.id, rigId)}
                                                className="text-white/10 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100">
                                                <UserMinus size={12} />
                                            </button>
                                        </div>
                                    )
                                })}

                                {/* Add / move rig dropdown — shows ALL rigs with current group label */}
                                {rigs.filter(r => !selectedGroup.rig_ids.includes(r.rig_id)).length > 0 && (
                                    <select
                                        className="bg-white/5 border border-dashed border-white/10 rounded-xl px-3 py-2.5 text-[10px] font-bold outline-none cursor-pointer hover:border-ridge-brand/40 transition-all appearance-none"
                                        value=""
                                        onChange={e => { if (e.target.value) { addRigToGroup(selectedGroup.id, e.target.value) } }}
                                    >
                                        <option value="" disabled>+ Add / move rig...</option>
                                        {rigs.filter(r => !selectedGroup.rig_ids.includes(r.rig_id)).map(r => {
                                            const currentGroup = groups.find(g => g.rig_ids.includes(r.rig_id))
                                            return (
                                                <option key={r.rig_id} value={r.rig_id}>
                                                    {r.rig_id}{currentGroup ? ` (in ${currentGroup.name})` : ''}
                                                </option>
                                            )
                                        })}
                                    </select>
                                )}

                                {selectedGroup.rig_ids.length === 0 && rigs.length === 0 && (
                                    <div className="text-[10px] text-white/20 font-bold uppercase py-2">No rigs available</div>
                                )}
                            </div>
                        </div>

                        {/* ---- ENVIRONMENT ---- */}
                        <div className="glass rounded-2xl p-5 border border-white/10 space-y-3">
                            <h4 className="text-[9px] uppercase font-black text-white/30 tracking-[0.3em] mb-1">Environment</h4>

                            {/* Track + Weather row */}
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest mb-1"><Map size={8} /> Circuit</label>
                                    <select
                                        value={selectedGroup.track}
                                        onChange={e => updateGroup(selectedGroup.id, { track: e.target.value })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand appearance-none cursor-pointer"
                                    >
                                        {tracks.map(t => <option key={t.id} value={t.id}>{displayName(t.id)}</option>)}
                                    </select>
                                </div>
                                {selectedGroup.mode === 'solo' && (
                                    <div>
                                        <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest mb-1"><Cloud size={8} /> Weather</label>
                                        <select
                                            value={selectedGroup.weather}
                                            onChange={e => updateGroup(selectedGroup.id, { weather: e.target.value })}
                                            className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand appearance-none cursor-pointer"
                                        >
                                            {weather.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
                                        </select>
                                    </div>
                                )}
                            </div>

                            {/* Time of Day */}
                            <div className="flex items-center gap-3">
                                <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest w-20 shrink-0"><Sun size={8} /> Time</label>
                                <input
                                    type="range" min={0} max={TIME_STEPS.length - 1} step={1}
                                    value={angleToStepIndex(selectedGroup.sun_angle ?? 48)}
                                    onChange={e => updateGroup(selectedGroup.id, { sun_angle: TIME_STEPS[parseInt(e.target.value)].angle })}
                                    className="flex-1 accent-ridge-brand cursor-pointer h-1"
                                />
                                <span className="text-[10px] font-black w-24 text-right text-white/60">{TIME_STEPS[angleToStepIndex(selectedGroup.sun_angle ?? 48)].label}</span>
                            </div>

                            {/* Time Speed */}
                            <div className="flex items-center gap-3">
                                <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest w-20 shrink-0"><Clock size={8} /> Speed</label>
                                <input type="range" min={1} max={100} value={selectedGroup.time_mult ?? 1}
                                    onChange={e => updateGroup(selectedGroup.id, { time_mult: parseInt(e.target.value) })}
                                    className="flex-1 accent-ridge-brand cursor-pointer h-1" />
                                <span className="text-[10px] font-black tabular-nums w-24 text-right text-white/60">{selectedGroup.time_mult ?? 1}x</span>
                            </div>

                            {/* Temperature */}
                            <div className="flex items-center gap-3">
                                <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest w-20 shrink-0"><Sun size={8} /> Temp</label>
                                <input type="range" min={5} max={45} value={selectedGroup.ambient_temp ?? 26}
                                    onChange={e => updateGroup(selectedGroup.id, { ambient_temp: parseInt(e.target.value) })}
                                    className="flex-1 accent-ridge-brand cursor-pointer h-1" />
                                <span className="text-[10px] font-black tabular-nums w-24 text-right text-white/60">{selectedGroup.ambient_temp ?? 26}°C</span>
                            </div>

                            {/* Track Grip */}
                            <div className="flex items-center gap-3">
                                <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest w-20 shrink-0"><Gauge size={8} /> Grip</label>
                                <input type="range" min={50} max={100} value={selectedGroup.track_grip ?? 100}
                                    onChange={e => updateGroup(selectedGroup.id, { track_grip: parseInt(e.target.value) })}
                                    className="flex-1 accent-ridge-brand cursor-pointer h-1" />
                                <span className="text-[10px] font-black tabular-nums w-24 text-right text-white/60">{selectedGroup.track_grip ?? 100}%</span>
                            </div>
                        </div>

                        {/* ---- RACE SETTINGS ---- */}
                        <div className="glass rounded-2xl p-5 border border-white/10 space-y-3">
                            <h4 className="text-[9px] uppercase font-black text-white/30 tracking-[0.3em] mb-1">Race Settings</h4>

                            {/* Compact number inputs row */}
                            <div className="grid grid-cols-4 gap-3">
                                <div>
                                    <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest mb-1"><Flag size={8} /> Laps</label>
                                    <input type="number" min={1} max={100} value={selectedGroup.race_laps}
                                        onChange={e => updateGroup(selectedGroup.id, { race_laps: parseInt(e.target.value) || 10 })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand" />
                                </div>
                                <div>
                                    <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest mb-1"><Timer size={8} /> Practice</label>
                                    <input type="number" min={0} max={60} value={selectedGroup.practice_time}
                                        onChange={e => updateGroup(selectedGroup.id, { practice_time: parseInt(e.target.value) || 0 })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand" />
                                </div>
                                <div>
                                    <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest mb-1"><Trophy size={8} /> Qualy</label>
                                    <input type="number" min={0} max={60} value={selectedGroup.qualy_time}
                                        onChange={e => updateGroup(selectedGroup.id, { qualy_time: parseInt(e.target.value) || 0 })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand" />
                                </div>
                                <div>
                                    <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest mb-1"><Cpu size={8} /> AI Cars</label>
                                    <input type="number" min={0} max={30} value={selectedGroup.ai_count}
                                        onChange={e => updateGroup(selectedGroup.id, { ai_count: parseInt(e.target.value) || 0 })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand" />
                                </div>
                            </div>

                            {/* AI Difficulty — compact slider */}
                            {selectedGroup.ai_count > 0 && (
                                <div className="flex items-center gap-3">
                                    <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest w-20 shrink-0"><Gauge size={8} /> AI Skill</label>
                                    <input type="range" min={0} max={5} step={1}
                                        value={AI_STEPS.findIndex(s => s.value === selectedGroup.ai_difficulty) >= 0 ? AI_STEPS.findIndex(s => s.value === selectedGroup.ai_difficulty) : 3}
                                        onChange={e => updateGroup(selectedGroup.id, { ai_difficulty: AI_STEPS[parseInt(e.target.value)].value })}
                                        className="flex-1 accent-ridge-brand cursor-pointer h-1" />
                                    <span className="text-[10px] font-black w-24 text-right text-white/60">
                                        {AI_STEPS.find(s => s.value === selectedGroup.ai_difficulty)?.label ?? 'Medium'} ({selectedGroup.ai_difficulty})
                                    </span>
                                </div>
                            )}

                            {/* Session Timer + Freeplay */}
                            <div className="pt-2 border-t border-white/5">
                                <div className="flex items-center justify-between mb-2">
                                    <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/25 tracking-widest"><Clock size={8} /> Session Timer</label>
                                    <button
                                        onClick={() => updateGroup(selectedGroup.id, { freeplay: !selectedGroup.freeplay })}
                                        className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-[7px] font-black uppercase tracking-widest transition-all ${
                                            selectedGroup.freeplay
                                                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                                : 'bg-white/5 text-white/30 border border-white/10'
                                        }`}
                                    >
                                        <Zap size={7} /> {selectedGroup.freeplay ? 'Freeplay ON' : 'Freeplay'}
                                    </button>
                                </div>
                                {!selectedGroup.freeplay ? (
                                    <div className="flex items-center gap-3">
                                        <input type="number" min={1} max={480} value={selectedGroup.session_duration_min ?? 30}
                                            onChange={e => updateGroup(selectedGroup.id, { session_duration_min: parseInt(e.target.value) || 30 })}
                                            className="w-24 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand" />
                                        <span className="text-[9px] text-white/30 font-bold uppercase">minutes per session</span>
                                    </div>
                                ) : (
                                    <p className="text-[9px] text-amber-400/50 font-bold uppercase tracking-widest">No time limit — session runs until manually stopped</p>
                                )}
                            </div>
                        </div>


                    </div>
                ) : (
                    /* Empty state */
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center">
                            <Settings size={48} className="mx-auto mb-4 text-white/10" />
                            <p className="text-lg font-black italic tracking-tighter uppercase opacity-20">Select a Group</p>
                            <p className="text-[10px] font-mono text-white/20 mt-2">Choose a group from the sidebar to configure it</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
