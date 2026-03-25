import { useState, useEffect, useCallback } from 'react'
import { Users, Plus, Trash2, UserPlus, UserMinus, Play, Power, Server, ChevronDown, ChevronUp, Settings, Cpu, Gauge, Cloud, Map, Car, Trophy, Timer, Flag } from 'lucide-react'

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
}

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
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function GroupManager({ rigs }: GroupManagerProps) {
    const [groups, setGroups] = useState<RigGroup[]>([])
    const [servers, setServers] = useState<ServerInfo[]>([])
    const [newGroupName, setNewGroupName] = useState('')
    const [newGroupMode, setNewGroupMode] = useState<'multiplayer' | 'solo'>('multiplayer')
    const [expandedGroup, setExpandedGroup] = useState<string | null>(null)

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
        await fetch('/api/groups/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newGroupName, mode: newGroupMode })
        })
        setNewGroupName('')
        fetchGroups()
    }

    const deleteGroup = async (groupId: string) => {
        await fetch(`/api/groups/${groupId}`, { method: 'DELETE' })
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

    /* ---- Render ---- */

    return (
        <div className="space-y-6 max-w-6xl">
            {/* Header + Create */}
            <div className="glass rounded-2xl p-6 border border-white/10">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-ridge-brand/20 rounded-xl">
                            <Users className="text-ridge-brand" size={20} />
                        </div>
                        <div>
                            <h2 className="text-lg font-black italic uppercase tracking-tighter">Race Groups</h2>
                            <p className="text-[10px] text-white/30 uppercase tracking-widest font-bold">{groups.length} groups // {rigs.length} rigs online</p>
                        </div>
                    </div>
                </div>

                <div className="flex gap-3">
                    <input
                        type="text"
                        placeholder="New group name..."
                        value={newGroupName}
                        onChange={e => setNewGroupName(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && createGroup()}
                        className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 outline-none focus:border-ridge-brand transition-all font-bold text-sm"
                    />
                    <select
                        value={newGroupMode}
                        onChange={e => setNewGroupMode(e.target.value as 'multiplayer' | 'solo')}
                        className="bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 outline-none font-bold text-xs uppercase appearance-none cursor-pointer"
                    >
                        <option value="multiplayer">Multiplayer</option>
                        <option value="solo">Solo</option>
                    </select>
                    <button
                        onClick={createGroup}
                        disabled={!newGroupName.trim()}
                        className="bg-ridge-brand hover:bg-orange-600 disabled:opacity-30 disabled:cursor-not-allowed px-5 py-2.5 rounded-xl font-black uppercase text-xs flex items-center gap-2 transition-all"
                    >
                        <Plus size={14} /> Create
                    </button>
                </div>
            </div>

            {/* Group Cards */}
            {groups.map(group => {
                const serverInfo = getServerForGroup(group.id)
                const isServerRunning = serverInfo?.status === 'running'
                const isExpanded = expandedGroup === group.id
                const trackName = tracks.find(t => t.id === group.track)?.name || group.track
                const weatherName = weather.find(w => w.id === group.weather)?.name || group.weather

                return (
                    <div key={group.id} className="glass rounded-2xl border border-white/10 overflow-hidden">
                        {/* Group Header */}
                        <div className="p-5 flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className={`w-1 h-12 rounded-full ${isServerRunning ? 'bg-green-500' : 'bg-white/10'}`} />
                                <div>
                                    <div className="flex items-center gap-3">
                                        <h3 className="text-lg font-black italic uppercase tracking-tighter">{group.name}</h3>
                                        <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${
                                            group.mode === 'multiplayer'
                                                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                        }`}>{group.mode}</span>
                                        {isServerRunning && (
                                            <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase bg-green-500/20 text-green-400 border border-green-500/30 flex items-center gap-1" title={`PID: ${serverInfo?.pid}`}>
                                                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" /> Server :{serverInfo?.port} // PID:{serverInfo?.pid} // {serverInfo?.ai_count || 0} AI
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-3 mt-1 text-[10px] text-white/30 font-mono">
                                        <span className="flex items-center gap-1"><Map size={10} /> {trackName}</span>
                                        <span>|</span>
                                        <span className="flex items-center gap-1"><Cloud size={10} /> {weatherName}</span>
                                        <span>|</span>
                                        <span>{group.rig_ids.length} rigs + {group.ai_count} AI</span>
                                        <span>|</span>
                                        <span>{group.race_laps} laps</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                {/* Deploy / Stop Server */}
                                {group.mode === 'multiplayer' && (
                                    isServerRunning ? (
                                        <button onClick={() => stopServerForGroup(group.id)}
                                            className="bg-red-500/10 hover:bg-red-500/20 text-red-400 p-2.5 rounded-xl transition-all" title="Stop Server">
                                            <Server size={16} />
                                        </button>
                                    ) : (
                                        <button onClick={() => startServerForGroup(group.id)}
                                            className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 p-2.5 rounded-xl transition-all" title="Deploy Server">
                                            <Server size={16} />
                                        </button>
                                    )
                                )}

                                <button onClick={() => sendGroupCommand(group.id, 'SETUP_MODE')}
                                    className="bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 p-2.5 rounded-xl transition-all" title="Prepare Grid (Car Selection)">
                                    <Car size={16} />
                                </button>
                                <button onClick={() => sendGroupCommand(group.id, 'LAUNCH_RACE')}
                                    className="bg-ridge-brand/10 hover:bg-ridge-brand/20 text-ridge-brand p-2.5 rounded-xl transition-all" title="Start Race">
                                    <Play size={16} />
                                </button>
                                <button onClick={() => sendGroupCommand(group.id, 'KILL_RACE')}
                                    className="bg-red-500/10 hover:bg-red-500/20 text-red-400 p-2.5 rounded-xl transition-all" title="Kill Race">
                                    <Power size={16} />
                                </button>

                                {/* Settings Toggle */}
                                <button onClick={() => setExpandedGroup(isExpanded ? null : group.id)}
                                    className="bg-white/5 hover:bg-white/10 p-2.5 rounded-xl transition-all text-white/40 hover:text-white" title="Configure">
                                    {isExpanded ? <ChevronUp size={16} /> : <Settings size={16} />}
                                </button>

                                <button onClick={() => deleteGroup(group.id)}
                                    className="bg-white/5 hover:bg-red-500/20 text-white/20 hover:text-red-400 p-2.5 rounded-xl transition-all" title="Delete Group">
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>

                        {/* Rig Roster */}
                        <div className="px-5 pb-4">
                            <div className="flex flex-wrap gap-2 mb-3">
                                {group.rig_ids.map(rigId => {
                                    const rig = rigs.find(r => r.rig_id === rigId)
                                    return (
                                        <div key={rigId} className="bg-black/30 border border-white/5 rounded-xl px-3 py-2 flex items-center gap-3 group">
                                            <div className={`w-2 h-2 rounded-full ${
                                                rig?.status === 'racing' ? 'bg-ridge-brand animate-pulse' :
                                                rig?.status === 'ready' ? 'bg-green-500' :
                                                rig?.status === 'setup' ? 'bg-blue-500 animate-pulse' :
                                                rig ? 'bg-white/20' : 'bg-red-500'
                                            }`} />
                                            <span className="font-black italic text-xs">{rigId}</span>

                                            {/* Per-rig car selector */}
                                            <select
                                                value={rig?.selected_car || ''}
                                                onChange={e => setRigCar(rigId, e.target.value)}
                                                className="bg-white/5 border border-white/10 rounded-lg px-2 py-0.5 text-[10px] font-bold outline-none focus:border-ridge-brand appearance-none max-w-32 cursor-pointer"
                                            >
                                                <option value="">Auto</option>
                                                {(group.car_pool.length > 0 ? cars.filter(c => group.car_pool.includes(c.id)) : cars).map(car => (
                                                    <option key={car.id} value={car.id}>{car.name}</option>
                                                ))}
                                            </select>

                                            <button onClick={() => removeRigFromGroup(group.id, rigId)}
                                                className="text-white/10 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100">
                                                <UserMinus size={12} />
                                            </button>
                                        </div>
                                    )
                                })}

                                {/* Add rig dropdown inline */}
                                {unassignedRigs.length > 0 && (
                                    <select
                                        className="bg-white/5 border border-dashed border-white/10 rounded-xl px-3 py-2 text-[10px] font-bold outline-none cursor-pointer hover:border-ridge-brand/40 transition-all appearance-none"
                                        value=""
                                        onChange={e => { if (e.target.value) { addRigToGroup(group.id, e.target.value); e.target.value = '' } }}
                                    >
                                        <option value="" disabled>+ Add rig...</option>
                                        {unassignedRigs.map(r => (
                                            <option key={r.rig_id} value={r.rig_id}>{r.rig_id}</option>
                                        ))}
                                    </select>
                                )}

                                {group.rig_ids.length === 0 && unassignedRigs.length === 0 && (
                                    <div className="text-[10px] text-white/20 font-bold uppercase py-2">No rigs available</div>
                                )}
                            </div>
                        </div>

                        {/* Expanded Settings Panel */}
                        {isExpanded && (
                            <div className="border-t border-white/5 bg-black/20 p-5 space-y-5 animate-in slide-in-from-top-2 duration-200">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    {/* Track */}
                                    <div>
                                        <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-2">
                                            <Map size={10} /> Circuit
                                        </label>
                                        <select
                                            value={group.track}
                                            onChange={e => updateGroup(group.id, { track: e.target.value })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm font-bold outline-none focus:border-ridge-brand appearance-none cursor-pointer transition-all"
                                        >
                                            {tracks.map(t => (
                                                <option key={t.id} value={t.id}>{t.name}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Weather */}
                                    <div>
                                        <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-2">
                                            <Cloud size={10} /> Weather
                                        </label>
                                        <select
                                            value={group.weather}
                                            onChange={e => updateGroup(group.id, { weather: e.target.value })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm font-bold outline-none focus:border-ridge-brand appearance-none cursor-pointer transition-all"
                                        >
                                            {weather.map(w => (
                                                <option key={w.id} value={w.id}>{w.name}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Race Laps */}
                                    <div>
                                        <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-2">
                                            <Flag size={10} /> Race Laps
                                        </label>
                                        <input
                                            type="number" min={1} max={100}
                                            value={group.race_laps}
                                            onChange={e => updateGroup(group.id, { race_laps: parseInt(e.target.value) || 10 })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm font-bold outline-none focus:border-ridge-brand transition-all"
                                        />
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                    {/* Practice */}
                                    <div>
                                        <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-2">
                                            <Timer size={10} /> Practice (min)
                                        </label>
                                        <input
                                            type="number" min={0} max={60}
                                            value={group.practice_time}
                                            onChange={e => updateGroup(group.id, { practice_time: parseInt(e.target.value) || 0 })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm font-bold outline-none focus:border-ridge-brand transition-all"
                                        />
                                    </div>

                                    {/* Qualifying */}
                                    <div>
                                        <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-2">
                                            <Trophy size={10} /> Qualifying (min)
                                        </label>
                                        <input
                                            type="number" min={0} max={60}
                                            value={group.qualy_time}
                                            onChange={e => updateGroup(group.id, { qualy_time: parseInt(e.target.value) || 0 })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm font-bold outline-none focus:border-ridge-brand transition-all"
                                        />
                                    </div>

                                    {/* AI Count */}
                                    <div>
                                        <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-2">
                                            <Cpu size={10} /> AI Drivers
                                        </label>
                                        <input
                                            type="number" min={0} max={30}
                                            value={group.ai_count}
                                            onChange={e => updateGroup(group.id, { ai_count: parseInt(e.target.value) || 0 })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm font-bold outline-none focus:border-ridge-brand transition-all"
                                        />
                                    </div>

                                    {/* AI Difficulty */}
                                    <div>
                                        <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-2">
                                            <Gauge size={10} /> AI Difficulty
                                        </label>
                                        <div className="flex items-center gap-3">
                                            <input
                                                type="range" min={0} max={100}
                                                value={group.ai_difficulty}
                                                onChange={e => updateGroup(group.id, { ai_difficulty: parseInt(e.target.value) })}
                                                className="flex-1 accent-ridge-brand cursor-pointer"
                                            />
                                            <span className="text-xs font-black tabular-nums w-8 text-right">{group.ai_difficulty}%</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Car Pool */}
                                <div>
                                    <label className="flex items-center gap-1.5 text-[9px] uppercase font-black text-white/40 tracking-widest mb-3">
                                        <Car size={10} /> Available Cars
                                    </label>
                                    <div className="flex flex-wrap gap-2">
                                        {cars.map(car => {
                                            const active = group.car_pool.includes(car.id)
                                            return (
                                                <button
                                                    key={car.id}
                                                    onClick={() => {
                                                        const updated = active
                                                            ? group.car_pool.filter(c => c !== car.id)
                                                            : [...group.car_pool, car.id]
                                                        updateGroup(group.id, { car_pool: updated.length > 0 ? updated : [car.id] })
                                                    }}
                                                    className={`px-3 py-1.5 rounded-xl text-[10px] font-black uppercase transition-all border ${
                                                        active
                                                            ? 'bg-ridge-brand/15 border-ridge-brand/40 text-ridge-brand shadow-sm shadow-ridge-brand/10'
                                                            : 'bg-white/3 border-white/5 text-white/20 hover:text-white/40 hover:border-white/15'
                                                    }`}
                                                >
                                                    <span className="opacity-50 mr-1">{car.brand}</span> {car.name.replace(car.brand + ' ', '')}
                                                </button>
                                            )
                                        })}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )
            })}

            {/* Empty State */}
            {groups.length === 0 && (
                <div className="py-20 flex flex-col items-center justify-center border-2 border-dashed border-white/5 rounded-2xl">
                    <Users size={40} className="mb-4 text-white/10" />
                    <p className="text-lg font-black italic tracking-tighter uppercase opacity-20">No Groups Created</p>
                    <p className="text-[10px] font-mono text-white/20 mt-2">Create a group above, then assign rigs and configure race settings</p>
                </div>
            )}

            {/* Unassigned Rigs */}
            {unassignedRigs.length > 0 && groups.length > 0 && (
                <div className="glass rounded-2xl p-5 border border-white/10">
                    <h3 className="text-xs font-black italic uppercase tracking-tighter mb-3 flex items-center gap-2">
                        <UserPlus size={14} className="text-amber-400" /> Unassigned Rigs
                        <span className="text-white/20 font-mono">({unassignedRigs.length})</span>
                    </h3>
                    <div className="flex flex-wrap gap-2">
                        {unassignedRigs.map(rig => (
                            <div key={rig.rig_id} className="bg-black/20 px-3 py-1.5 rounded-xl border border-white/5 text-[10px] font-bold flex items-center gap-2">
                                <div className={`w-1.5 h-1.5 rounded-full ${rig.status === 'racing' ? 'bg-ridge-brand' : 'bg-white/20'}`} />
                                {rig.rig_id}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
