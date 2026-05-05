import { useState, useEffect, useCallback } from 'react'
import { Users, Plus, Trash2, UserPlus, UserMinus, Play, Power, Server, Settings, Cpu, Gauge, Cloud, Map, Car, Trophy, Timer, Flag, Sun, Clock, ChevronRight, ChevronDown, Zap, Filter, X, Download } from 'lucide-react'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface RigGroup {
    id: string
    name: string
    mode: 'multiplayer' | 'solo'
    rig_ids: string[]
    track: string
    track_layout: string | null
    weather: string
    car_pool: string[]
    ai_count: number
    ai_difficulty: number
    practice_enabled: boolean
    practice_time: number
    qualy_enabled: boolean
    qualy_time: number
    race_enabled: boolean
    race_laps: number
    penalties_enabled: boolean
    sun_angle: number
    time_mult: number
    session_duration_min: number
    ambient_temp: number
    track_grip: number
    freeplay: boolean
}

const AI_STEPS = [
    { value: 0, label: 'Rookie' },
    { value: 20, label: 'Beginner' },
    { value: 40, label: 'Easy' },
    { value: 60, label: 'Medium' },
    { value: 80, label: 'Hard' },
    { value: 100, label: 'Pro' },
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

/* ------------------------------------------------------------------ */
/*  Helper Components                                                  */
/* ------------------------------------------------------------------ */

const SmartNumberInput = ({ value, onChange, min, max, className, placeholder = "0" }: any) => {
    const [local, setLocal] = useState(value?.toString() || '')
    
    // Sync external changes (like presets) into local state, but only if they differ when parsed
    useEffect(() => {
        if (parseInt(local) !== value && local !== '') {
            setLocal(value?.toString() || '0')
        }
    }, [value])

    return (
        <input
            type="number"
            min={min}
            max={max}
            className={className}
            placeholder={placeholder}
            value={local}
            onChange={e => {
                setLocal(e.target.value)
                const parsed = parseInt(e.target.value)
                if (!isNaN(parsed)) {
                    onChange(parsed)
                }
            }}
            onBlur={e => {
                if (e.target.value === '' || isNaN(parseInt(e.target.value))) {
                    setLocal('0')
                    onChange(0)
                }
            }}
            onKeyDown={e => {
                if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
            }}
        />
    )
}

interface CatalogCar { id: string; name: string; brand: string; car_class: string }
interface CatalogTrack { id: string; name: string; layouts?: { id: string; name: string }[] }
interface CatalogWeather { id: string; name: string }

interface GroupManagerProps {
    rigs: Rig[]
    activeCarPool: string[]
    activeMapPool: string[]
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const TIME_STEPS = [
    { angle: -16, label: 'Dawn' },
    { angle: 8, label: 'Sunrise' },
    { angle: 24, label: 'Morning' },
    { angle: 40, label: 'Late Morning' },
    { angle: 56, label: 'Midday' },
    { angle: 72, label: 'Early Afternoon' },
    { angle: 88, label: 'Afternoon' },
    { angle: 104, label: 'Late Afternoon' },
    { angle: 120, label: 'Sunset' },
    { angle: 136, label: 'Dusk' },
    { angle: 163, label: 'Night' },
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

/* Reusable select wrapper with dropdown arrow */
function Select({ value, onChange, children, className = '' }: {
    value: string, onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void, children: React.ReactNode, className?: string
}) {
    return (
        <div className="relative">
            <select value={value} onChange={onChange}
                className={`w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand appearance-none cursor-pointer pr-7 ${className}`}
            >{children}</select>
            <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
        </div>
    )
}

/* Reusable slider row with min/max/label and editable value */
function SliderRow({ label, icon: Icon, value, min, max, step, unit, onChange }: {
    label: string, icon: any, value: number, min: number, max: number, step?: number, unit: string,
    onChange: (v: number) => void
}) {
    const [editing, setEditing] = useState(false)
    const [editVal, setEditVal] = useState(String(value))

    const commitEdit = () => {
        setEditing(false)
        let v = parseFloat(editVal)
        if (isNaN(v)) v = value
        v = Math.max(min, Math.min(max, v))
        setEditVal(String(v))
        onChange(v)
    }

    return (
        <div className="flex items-center gap-3">
            <label className="flex items-center gap-1 text-[9px] uppercase font-black text-white/50 tracking-widest w-20 shrink-0">
                <Icon size={9} /> {label}
            </label>
            <span className="text-[8px] text-white/25 font-mono tabular-nums w-6 text-right shrink-0">{min}</span>
            <input type="range" min={min} max={max} step={step || 1} value={value}
                onChange={e => onChange(parseFloat(e.target.value))}
                className="flex-1 accent-ridge-brand cursor-pointer h-1" />
            <span className="text-[8px] text-white/25 font-mono tabular-nums w-6 shrink-0">{max}</span>
            {editing ? (
                <input
                    type="text"
                    value={editVal}
                    onChange={e => setEditVal(e.target.value)}
                    onBlur={commitEdit}
                    onKeyDown={e => e.key === 'Enter' && commitEdit()}
                    autoFocus
                    className="w-24 text-right bg-white/10 border border-ridge-brand/50 rounded px-1.5 py-0.5 text-xs font-black tabular-nums outline-none"
                />
            ) : (
                <span
                    onClick={() => { setEditVal(String(value)); setEditing(true) }}
                    className="text-xs font-black tabular-nums w-24 text-right text-white/70 cursor-text hover:text-ridge-brand transition-colors"
                >{value}{unit}</span>
            )}
        </div>
    )
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function GroupManager({ rigs, activeCarPool, activeMapPool }: GroupManagerProps) {
    const [groups, setGroups] = useState<RigGroup[]>([])
    const [servers, setServers] = useState<ServerInfo[]>([])
    const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
    const [newGroupName, setNewGroupName] = useState('')
    const [newGroupMode, setNewGroupMode] = useState<'multiplayer' | 'solo'>('multiplayer')

    // Catalogs from backend
    const [cars, setCars] = useState<CatalogCar[]>([])
    const [tracks, setTracks] = useState<CatalogTrack[]>([])
    const [weather, setWeather] = useState<CatalogWeather[]>([])

    // Car filters (category + brand)
    const [filterCategory, setFilterCategory] = useState('All')
    const [filterBrand, setFilterBrand] = useState('All')

    // Preview Config modal state
    const [previewConfig, setPreviewConfig] = useState<string | null>(null)

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
                car_pool: activeCarPool.length > 0 ? activeCarPool : group.car_pool,
                use_server: group.mode === 'multiplayer',
            })
        })
    }

    const sendRigCommand = async (groupId: string, rigId: string, action: string) => {
        const group = groups.find(g => g.id === groupId)
        if (!group) return
        await fetch(`/api/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rig_id: rigId,
                action,
                track: group.track,
                weather: group.weather,
                practice_time: group.practice_time,
                qualy_time: group.qualy_time,
                race_laps: group.race_laps,
                ai_count: group.ai_count,
                ai_difficulty: group.ai_difficulty,
                car_pool: activeCarPool.length > 0 ? activeCarPool : group.car_pool,
                use_server: group.mode === 'multiplayer',
            })
        })
    }

    const startServerForGroup = async (groupId: string): Promise<boolean> => {
        const group = groups.find(g => g.id === groupId)
        if (!group) return false
        const res = await fetch('/api/server/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                group_id: groupId,
                track: group.track,
                cars: activeCarPool.length > 0 ? activeCarPool : group.car_pool,
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
        fetchServers()
        if (data.status === 'error') {
            let msg = `Server failed: ${data.message}\n`

            // Show cars that likely caused the crash
            if (data.problem_cars?.length) {
                msg += `\n⚠️ PROBLEM CARS (found in crash log):\n`
                msg += data.problem_cars.map((c: string) => `  • ${c}`).join('\n')
            }

            // Show cars rejected during validation
            if (data.rejected_cars?.length) {
                msg += `\n\n❌ REJECTED CARS (not on disk):\n`
                msg += data.rejected_cars.map((c: {id: string, reason: string}) => `  • ${c.id} — ${c.reason}`).join('\n')
            }

            // Show validated cars for reference
            if (data.validated_cars?.length) {
                msg += `\n\n✅ Valid cars (${data.validated_cars.length}): ${data.validated_cars.slice(0, 10).join(', ')}${data.validated_cars.length > 10 ? '...' : ''}`
            }

            // Raw log snippet at the end
            if (data.server_log) {
                msg += `\n\n── Server Log (last 300 chars) ──\n${data.server_log.slice(-300)}`
            }

            alert(msg)
            return false
        }
        return true
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
                    <Select value={newGroupMode} onChange={e => setNewGroupMode(e.target.value as 'multiplayer' | 'solo')}
                        className="text-[10px] uppercase">
                        <option value="multiplayer">Multiplayer</option>
                        <option value="solo">Solo</option>
                    </Select>
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
                                className={`w-full text-left p-4 border-b border-white/5 transition-all group ${isActive
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
                                        <span className={`px-1.5 py-0.5 rounded text-[7px] font-black uppercase tracking-widest ${group.mode === 'multiplayer'
                                                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                            }`}>{group.mode === 'multiplayer' ? 'MP' : 'SOLO'}</span>
                                        {isLive && (
                                            <span className="px-1.5 py-0.5 rounded text-[7px] font-black uppercase tracking-widest bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1 animate-pulse">
                                                <div className="w-1.5 h-1.5 rounded-full bg-red-500" /> LIVE
                                            </span>
                                        )}
                                        <ChevronRight size={12} className="text-white/25" />
                                    </div>
                                </div>
                                <div className="text-[9px] text-white/40 font-mono mt-1">
                                    {group.rig_ids.length} rigs · {group.ai_count} AI · {group.race_laps} laps
                                </div>
                            </button>
                        )
                    })}
                    {groups.length === 0 && (
                        <div className="p-8 text-center">
                            <Users size={32} className="mx-auto mb-3 text-white/10" />
                            <p className="text-xs text-white/30 font-bold uppercase">No groups</p>
                        </div>
                    )}
                </div>

                {/* Unassigned rigs tray */}
                {unassignedRigs.length > 0 && (
                    <div className="border-t border-white/10 p-3">
                        <h4 className="text-[9px] text-white/40 font-black uppercase tracking-widest mb-2 flex items-center gap-1.5">
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
                                    <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${selectedGroup.mode === 'multiplayer'
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
                                {/* Single START RACE button — auto-deploys server for multiplayer */}
                                <button
                                    onClick={async () => {
                                        if (selectedGroup.mode === 'multiplayer' && !isSelectedServerRunning) {
                                            // Deploy server first — abort if it fails
                                            const ok = await startServerForGroup(selectedGroup.id)
                                            if (!ok) return
                                            // Let the server spin up before connecting clients
                                            await new Promise(r => setTimeout(r, 3000))
                                        }
                                        sendGroupCommand(selectedGroup.id, 'LAUNCH_RACE')
                                    }}
                                    className="bg-ridge-brand/10 hover:bg-ridge-brand/20 text-ridge-brand px-5 py-2 rounded-xl transition-all flex items-center gap-2 text-xs font-black uppercase">
                                    <Play size={14} /> Start Race
                                </button>

                                {/* Single STOP button — kills race on all rigs + stops server */}
                                <button onClick={async () => {
                                    // Fire KILL_RACE directly to each rig (same path as the working rig power button)
                                    // instead of the group command route, which queues background tasks.
                                    const killPromises: Promise<unknown>[] = selectedGroup.rig_ids.map(rigId =>
                                        fetch('/api/command', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({ rig_id: rigId, action: 'KILL_RACE' })
                                        })
                                    )
                                    if (selectedGroup.mode === 'multiplayer') {
                                        killPromises.push(stopServerForGroup(selectedGroup.id))
                                    }
                                    await Promise.all(killPromises)
                                    fetchGroups()
                                }}
                                    className="bg-red-500/10 hover:bg-red-500/20 text-red-400 px-4 py-2 rounded-xl transition-all flex items-center gap-2 text-xs font-black uppercase">
                                    <Power size={14} /> Stop
                                </button>
                                {selectedGroup.mode === 'multiplayer' && (
                                    <button onClick={async () => {
                                        try {
                                            const res = await fetch(`/api/server/preview-config/${selectedGroup.id}`)
                                            if (!res.ok) {
                                                const text = await res.text()
                                                alert(`Error fetching config: ${res.status}\n${text}`)
                                                return
                                            }
                                            const data = await res.json()
                                            if (data.status === 'success') {
                                                setPreviewConfig(data.config)
                                            } else {
                                                alert(data.message)
                                            }
                                        } catch (e) { console.error(e) }
                                    }}
                                        className="bg-white/5 hover:bg-white/10 text-white/20 hover:text-white/60 px-3 py-2 rounded-xl transition-all flex items-center gap-1.5 text-xs font-black uppercase" title="Preview Server Config">
                                        <Server size={14} /> <span className="hidden sm:inline">Config</span>
                                    </button>
                                )}
                                <button onClick={() => deleteGroup(selectedGroup.id)}
                                    className="bg-white/5 hover:bg-red-500/20 text-white/20 hover:text-red-400 p-2 rounded-xl transition-all">
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        </div>

                        {/* ---- Rig Assignment Row ---- */}
                        <div className="glass rounded-2xl p-5 border border-white/10">
                            <h3 className="text-[9px] font-black uppercase tracking-widest text-white/50 mb-3 flex items-center gap-1.5">
                                <Users size={10} /> Assigned Rigs ({selectedGroup.rig_ids.length})
                            </h3>

                            {/* Car Filters */}
                            {(() => {
                                const enabledCars = activeCarPool.length > 0
                                    ? cars.filter(c => activeCarPool.includes(c.id))
                                    : cars;
                                const categories = ['All', ...Array.from(new Set(enabledCars.map(c => c.car_class).filter(Boolean))).sort()]
                                const brands = ['All', ...Array.from(new Set(enabledCars.map(c => c.brand).filter(Boolean))).sort()]
                                return (
                                    <div className="flex gap-3 mb-3">
                                        <div className="flex-1">
                                            <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/40 tracking-widest mb-1">Category</label>
                                            <Select value={filterCategory} onChange={e => setFilterCategory(e.target.value)}>
                                                {categories.map(c => <option key={c} value={c}>{c}</option>)}
                                            </Select>
                                        </div>
                                        <div className="flex-1">
                                            <label className="flex items-center gap-1 text-[8px] uppercase font-black text-white/40 tracking-widest mb-1">Brand</label>
                                            <Select value={filterBrand} onChange={e => setFilterBrand(e.target.value)}>
                                                {brands.map(b => <option key={b} value={b}>{b}</option>)}
                                            </Select>
                                        </div>
                                    </div>
                                )
                            })()}

                            <div className="flex flex-wrap gap-2">
                                {selectedGroup.rig_ids.map(rigId => {
                                    const rig = rigs.find(r => r.rig_id === rigId)
                                    return (
                                        <div key={rigId} className="bg-black/30 border border-white/5 rounded-xl px-3 py-2.5 flex items-center gap-3 group hover:border-white/15 transition-all">
                                            <div className={`w-2 h-2 rounded-full ${rig?.status === 'racing' ? 'bg-ridge-brand animate-pulse' :
                                                    rig?.status === 'ready' ? 'bg-green-500' :
                                                        rig?.status === 'setup' ? 'bg-blue-500 animate-pulse' :
                                                            rig ? 'bg-white/20' : 'bg-red-500'
                                                }`} />
                                            <span className="font-black italic text-xs">{rigId}</span>

                                            {/* Per-rig car selector (filtered) */}
                                            <div className="relative">
                                                <select
                                                    value={rig?.selected_car || ''}
                                                    onChange={e => setRigCar(rigId, e.target.value)}
                                                    className="bg-white/5 border border-white/10 rounded-lg px-2 py-0.5 text-[10px] font-bold outline-none focus:border-ridge-brand appearance-none max-w-40 cursor-pointer pr-5"
                                                >
                                                    <option value="">🎲 Random</option>
                                                    {(() => {
                                                        const seen = new Set<string>();
                                                        // Only show cars enabled in the Cars tab
                                                        let enabledCars = activeCarPool.length > 0
                                                            ? cars.filter(c => activeCarPool.includes(c.id))
                                                            : cars;
                                                        // Apply category filter
                                                        if (filterCategory !== 'All') {
                                                            enabledCars = enabledCars.filter(c => c.car_class === filterCategory)
                                                        }
                                                        // Apply brand filter
                                                        if (filterBrand !== 'All') {
                                                            enabledCars = enabledCars.filter(c => c.brand === filterBrand)
                                                        }
                                                        return enabledCars
                                                            .filter(c => { if (seen.has(c.id)) return false; seen.add(c.id); return true; })
                                                            .sort((a, b) => displayName(a.id).localeCompare(displayName(b.id)))
                                                            .map(car => (
                                                                <option key={car.id} value={car.id}>{displayName(car.id)}</option>
                                                            ));
                                                    })()}
                                                </select>
                                                <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
                                            </div>

                                            <button onClick={() => sendRigCommand(selectedGroup.id, rigId, 'LAUNCH_RACE')}
                                                className="text-white/10 hover:text-green-400 transition-colors opacity-0 group-hover:opacity-100 mr-0.5" title={selectedGroup.mode === 'multiplayer' ? "Join Race" : "Start Race"}>
                                                <Play size={12} />
                                            </button>
                                            <button onClick={async () => { await sendRigCommand(selectedGroup.id, rigId, 'KILL_RACE'); removeRigFromGroup(selectedGroup.id, rigId) }}
                                                className="text-white/10 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100" title="Stop Race">
                                                <UserMinus size={12} />
                                            </button>
                                        </div>
                                    )
                                })}

                                {/* Add / move rig dropdown */}
                                {rigs.filter(r => !selectedGroup.rig_ids.includes(r.rig_id)).length > 0 && (
                                    <div className="relative">
                                        <select
                                            className="bg-white/5 border border-dashed border-white/10 rounded-xl px-3 py-2.5 text-[10px] font-bold outline-none cursor-pointer hover:border-ridge-brand/40 transition-all appearance-none pr-7"
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
                                        <ChevronDown size={10} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
                                    </div>
                                )}

                                {selectedGroup.rig_ids.length === 0 && rigs.length === 0 && (
                                    <div className="text-[10px] text-white/30 font-bold uppercase py-2">No rigs available</div>
                                )}
                            </div>
                        </div>

                        {/* ---- ENVIRONMENT ---- */}
                        <div className="glass rounded-2xl p-5 border border-white/10 space-y-3">
                            <h4 className="text-[9px] uppercase font-black text-white/50 tracking-[0.3em] mb-1">Environment</h4>

                            {/* Track + Weather + Time dropdowns row */}
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <label className="flex items-center gap-1 text-[9px] uppercase font-black text-white/50 tracking-widest mb-1"><Map size={9} /> Circuit</label>
                                    <div className="flex gap-2">
                                        <div className="flex-1">
                                            <Select value={selectedGroup.track} onChange={e => {
                                                const trackId = e.target.value
                                                const t = tracks.find(x => x.id === trackId)
                                                updateGroup(selectedGroup.id, { 
                                                    track: trackId, 
                                                    track_layout: t?.layouts && t.layouts.length > 0 ? t.layouts[0].id : null 
                                                })
                                            }}>
                                                {(activeMapPool.length > 0
                                                    ? tracks.filter(t => activeMapPool.includes(t.id))
                                                    : tracks
                                                ).map(t => <option key={t.id} value={t.id}>{displayName(t.id)}</option>)}
                                            </Select>
                                        </div>
                                        {(() => {
                                            const t = tracks.find(x => x.id === selectedGroup.track)
                                            if (t && t.layouts && t.layouts.length > 0) {
                                                return (
                                                    <div className="flex-1">
                                                        <Select value={selectedGroup.track_layout || ''} onChange={e => updateGroup(selectedGroup.id, { track_layout: e.target.value })}>
                                                            {t.layouts.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                                                        </Select>
                                                    </div>
                                                )
                                            }
                                            return null
                                        })()}
                                    </div>
                                    
                                    {/* Track Map Image */}
                                    <div className="mt-3 aspect-video bg-black/40 rounded-lg border border-white/5 overflow-hidden relative flex items-center justify-center">
                                        <img 
                                            src={`/api/tracks/${selectedGroup.track}${selectedGroup.track_layout ? '/' + selectedGroup.track_layout : ''}/map`} 
                                            alt="Track Map"
                                            className="w-full h-full object-contain p-2"
                                            onError={(e) => {
                                                (e.target as HTMLImageElement).style.display = 'none';
                                            }}
                                        />
                                    </div>
                                </div>
                                <div>
                                    <label className="flex items-center gap-1 text-[9px] uppercase font-black text-white/50 tracking-widest mb-1"><Cloud size={9} /> Weather</label>
                                    <Select value={selectedGroup.weather} onChange={e => updateGroup(selectedGroup.id, { weather: e.target.value })}>
                                        {weather.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
                                    </Select>
                                </div>
                                <div>
                                    <label className="flex items-center gap-1 text-[9px] uppercase font-black text-white/50 tracking-widest mb-1"><Sun size={9} /> Time of Day</label>
                                    {(() => {
                                        const availableSteps = TIME_STEPS
                                        const currentIdx = (() => {
                                            let best = 0
                                            let minDiff = 999
                                            availableSteps.forEach((s, idx) => {
                                                const diff = Math.abs(s.angle - selectedGroup.sun_angle)
                                                if (diff < minDiff) { minDiff = diff; best = idx }
                                            })
                                            return best
                                        })()
                                        return (
                                            <Select value={currentIdx.toString()}
                                                onChange={e => updateGroup(selectedGroup.id, { sun_angle: availableSteps[parseInt(e.target.value)].angle })}>
                                                {availableSteps.map((s, idx) => (
                                                    <option key={idx} value={idx}>{s.label}</option>
                                                ))}
                                            </Select>
                                        )
                                    })()}
                                </div>
                            </div>

                            {/* Time Speed */}
                            <SliderRow label="Time Mult." icon={Clock} value={selectedGroup.time_mult ?? 1} min={1} max={100} unit="x"
                                onChange={v => updateGroup(selectedGroup.id, { time_mult: v })} />

                            {/* Temperature */}
                            <SliderRow label="Temp" icon={Sun} value={selectedGroup.ambient_temp ?? 26} min={5} max={45} unit="°C"
                                onChange={v => updateGroup(selectedGroup.id, { ambient_temp: v })} />

                            {/* Track Grip */}
                            <SliderRow label="Grip" icon={Gauge} value={selectedGroup.track_grip ?? 100} min={50} max={100} unit="%"
                                onChange={v => updateGroup(selectedGroup.id, { track_grip: v })} />
                        </div>

                        {/* ---- RACE SETTINGS ---- */}
                        <div className="glass rounded-2xl p-5 border border-white/10 space-y-3">
                            <div className="flex items-center justify-between mb-1">
                                <h4 className="text-[9px] uppercase font-black text-white/50 tracking-[0.3em]">Race Settings</h4>
                                <button
                                    onClick={() => updateGroup(selectedGroup.id, { penalties_enabled: !selectedGroup.penalties_enabled })}
                                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${selectedGroup.penalties_enabled
                                            ? 'bg-red-500/20 text-red-400 border-2 border-red-500/50 shadow-lg shadow-red-500/10'
                                            : 'bg-white/5 text-white/40 border border-white/10 hover:border-white/20'
                                        }`}
                                >
                                    <Settings size={10} /> {selectedGroup.penalties_enabled ? 'Penalties ON' : 'Penalties OFF'}
                                </button>
                            </div>

                            <div className="grid grid-cols-3 gap-3">
                                {/* Practice Card */}
                                <div className={`flex flex-col p-3 rounded-xl border transition-colors ${selectedGroup.practice_enabled ? 'border-ridge-brand bg-ridge-brand/5' : 'border-white/10 bg-white/5 opacity-50'}`}>
                                    <label className="flex items-center gap-2 cursor-pointer mb-2">
                                        <input type="checkbox" className="accent-ridge-brand w-3.5 h-3.5" checked={selectedGroup.practice_enabled ?? false}
                                            onChange={e => updateGroup(selectedGroup.id, { practice_enabled: e.target.checked })} />
                                        <span className="text-[10px] uppercase font-black text-white/70 tracking-widest flex items-center gap-1"><Timer size={10}/> Practice</span>
                                    </label>
                                    {selectedGroup.practice_enabled && (
                                        <div className="flex items-center gap-2 mt-auto">
                                            <SmartNumberInput min={1} max={120} value={selectedGroup.practice_time}
                                                onChange={(val: number) => updateGroup(selectedGroup.id, { practice_time: val })}
                                                className="w-16 bg-black/40 border border-white/10 rounded px-2 py-1 text-xs font-bold outline-none focus:border-ridge-brand text-center" />
                                            <span className="text-[9px] font-bold text-white/40 uppercase">Minutes</span>
                                        </div>
                                    )}
                                </div>
                                {/* Qualy Card */}
                                <div className={`flex flex-col p-3 rounded-xl border transition-colors ${selectedGroup.qualy_enabled ? 'border-ridge-brand bg-ridge-brand/5' : 'border-white/10 bg-white/5 opacity-50'}`}>
                                    <label className="flex items-center gap-2 cursor-pointer mb-2">
                                        <input type="checkbox" className="accent-ridge-brand w-3.5 h-3.5" checked={selectedGroup.qualy_enabled ?? false}
                                            onChange={e => updateGroup(selectedGroup.id, { qualy_enabled: e.target.checked })} />
                                        <span className="text-[10px] uppercase font-black text-white/70 tracking-widest flex items-center gap-1"><Trophy size={10}/> Qualify</span>
                                    </label>
                                    {selectedGroup.qualy_enabled && (
                                        <div className="flex items-center gap-2 mt-auto">
                                            <SmartNumberInput min={1} max={120} value={selectedGroup.qualy_time}
                                                onChange={(val: number) => updateGroup(selectedGroup.id, { qualy_time: val })}
                                                className="w-16 bg-black/40 border border-white/10 rounded px-2 py-1 text-xs font-bold outline-none focus:border-ridge-brand text-center" />
                                            <span className="text-[9px] font-bold text-white/40 uppercase">Minutes</span>
                                        </div>
                                    )}
                                </div>
                                {/* Race Card */}
                                <div className={`flex flex-col p-3 rounded-xl border transition-colors ${selectedGroup.race_enabled !== false ? 'border-ridge-brand bg-ridge-brand/5' : 'border-white/10 bg-white/5 opacity-50'}`}>
                                    <label className="flex items-center gap-2 cursor-pointer mb-2">
                                        <input type="checkbox" className="accent-ridge-brand w-3.5 h-3.5" checked={selectedGroup.race_enabled !== false}
                                            onChange={e => updateGroup(selectedGroup.id, { race_enabled: e.target.checked })} />
                                        <span className="text-[10px] uppercase font-black text-white/70 tracking-widest flex items-center gap-1"><Flag size={10}/> Race</span>
                                    </label>
                                    {selectedGroup.race_enabled !== false && (
                                        <div className="flex items-center gap-2 mt-auto">
                                            <SmartNumberInput min={1} max={200} value={selectedGroup.race_laps}
                                                onChange={(val: number) => updateGroup(selectedGroup.id, { race_laps: val })}
                                                className="w-16 bg-black/40 border border-white/10 rounded px-2 py-1 text-xs font-bold outline-none focus:border-ridge-brand text-center" />
                                            <span className="text-[9px] font-bold text-white/40 uppercase">Laps</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* AI Controls */}
                            <div className="flex items-center gap-4 mt-3">
                                <div className="w-1/3">
                                    <label className="flex items-center gap-1 text-[9px] uppercase font-black text-white/50 tracking-widest mb-1"><Cpu size={9} /> AI Cars</label>
                                    <SmartNumberInput min={0} max={30} value={selectedGroup.ai_count}
                                        onChange={(val: number) => updateGroup(selectedGroup.id, { ai_count: val })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand" />
                                </div>
                                <div className={`flex-1 flex flex-col ${selectedGroup.ai_count === 0 ? 'opacity-30 pointer-events-none' : ''}`}>
                                    <label className="flex items-center gap-1 text-[9px] uppercase font-black text-white/50 tracking-widest mb-1"><Gauge size={9} /> AI Skill</label>
                                    <div className="flex items-center gap-3">
                                        <span className="text-[8px] text-white/25 font-mono w-4 shrink-0">0</span>
                                        <input type="range" min={0} max={5} step={1}
                                            value={AI_STEPS.findIndex(s => s.value === selectedGroup.ai_difficulty) >= 0 ? AI_STEPS.findIndex(s => s.value === selectedGroup.ai_difficulty) : 3}
                                            onChange={e => updateGroup(selectedGroup.id, { ai_difficulty: AI_STEPS[parseInt(e.target.value)].value })}
                                            className="flex-1 accent-ridge-brand cursor-pointer h-1"
                                            disabled={selectedGroup.ai_count === 0} />
                                        <span className="text-[8px] text-white/25 font-mono w-4 shrink-0">5</span>
                                        <span className="text-xs font-black w-24 text-right text-white/70">
                                            {selectedGroup.ai_count === 0 ? 'No AI' : `${AI_STEPS.find(s => s.value === selectedGroup.ai_difficulty)?.label ?? 'Medium'} (${selectedGroup.ai_difficulty})`}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Session Timer + Freeplay */}
                            <div className="pt-3 border-t border-white/5">
                                <div className="flex items-center justify-between mb-2">
                                    <label className="flex items-center gap-1 text-[9px] uppercase font-black text-white/50 tracking-widest"><Clock size={9} /> Session Timer</label>
                                    <button
                                        onClick={() => updateGroup(selectedGroup.id, { freeplay: !selectedGroup.freeplay })}
                                        className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${selectedGroup.freeplay
                                                ? 'bg-amber-500/20 text-amber-400 border-2 border-amber-500/50 shadow-lg shadow-amber-500/10'
                                                : 'bg-white/5 text-white/40 border border-white/10 hover:border-white/20'
                                            }`}
                                    >
                                        <Zap size={10} /> {selectedGroup.freeplay ? '∞ Freeplay ON' : 'Freeplay'}
                                    </button>
                                </div>
                                {!selectedGroup.freeplay ? (
                                    <div className="flex items-center gap-3">
                                        <SmartNumberInput min={1} max={480} value={selectedGroup.session_duration_min ?? 30} placeholder="30"
                                            onChange={(val: number) => updateGroup(selectedGroup.id, { session_duration_min: val || 30 })}
                                            className="w-24 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand" />
                                        <span className="text-[10px] text-white/40 font-bold uppercase">minutes per session</span>
                                        <div className="flex items-center gap-1.5 ml-auto">
                                            <button onClick={() => updateGroup(selectedGroup.id, { session_duration_min: (selectedGroup.session_duration_min || 30) + 5 })}
                                                className="bg-white/5 hover:bg-ridge-brand/20 hover:text-ridge-brand text-[10px] font-black uppercase text-white/50 px-2 py-1 rounded transition-colors">
                                                +5m
                                            </button>
                                            <button onClick={() => updateGroup(selectedGroup.id, { session_duration_min: (selectedGroup.session_duration_min || 30) + 15 })}
                                                className="bg-white/5 hover:bg-ridge-brand/20 hover:text-ridge-brand text-[10px] font-black uppercase text-white/50 px-2 py-1 rounded transition-colors">
                                                +15m
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <p className="text-[10px] text-amber-400/60 font-bold uppercase tracking-widest">No time limit — session runs until manually stopped</p>
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
                            <p className="text-[10px] font-mono text-white/30 mt-2">Choose a group from the sidebar to configure it</p>
                        </div>
                    </div>
                )}
            </div>

            {/* Preview Config Modal */}
            {previewConfig && (
                <div className="fixed inset-0 bg-black/80 z-[100] flex items-center justify-center p-8 backdrop-blur-sm">
                    <div className="bg-[#111] border border-white/10 rounded-2xl p-6 w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-black italic uppercase text-ridge-brand flex items-center gap-2">
                                <Server size={18} /> Server Config Preview
                            </h3>
                            <button onClick={() => setPreviewConfig(null)} className="text-white/40 hover:text-white transition-colors">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="flex-1 overflow-auto bg-black border border-white/5 rounded-xl p-4 mb-4">
                            <pre className="text-[10px] font-mono text-white/70 whitespace-pre-wrap">{previewConfig}</pre>
                        </div>
                        <div className="flex justify-end gap-3">
                            <button onClick={() => setPreviewConfig(null)} className="px-4 py-2 rounded-xl text-xs font-bold text-white/50 hover:text-white transition-colors bg-white/5 hover:bg-white/10">
                                Close
                            </button>
                            <button onClick={() => {
                                const blob = new Blob([previewConfig], { type: 'text/plain' })
                                const url = URL.createObjectURL(blob)
                                const a = document.createElement('a')
                                a.href = url
                                a.download = `server_cfg.ini`
                                a.click()
                                URL.revokeObjectURL(url)
                            }} className="px-4 py-2 rounded-xl text-xs font-black uppercase tracking-widest text-white bg-ridge-brand/80 hover:bg-ridge-brand transition-colors flex items-center gap-2">
                                <Download size={14} /> Download Config
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
