import { Activity, Cpu, Monitor, Zap, Power, RotateCcw, Play, Check, Image, Car, Settings2, Flag, Clock, ShieldCheck, LayoutGrid, Users, Lock, Unlock, Wrench, ChevronLeft, ChevronRight, Thermometer, Fuel, Gauge, Square, ChevronDown, MapPin } from 'lucide-react'
import Kiosk from './Kiosk'
import Lobby from './Lobby'
import GroupManager from './components/GroupManager'
import SessionTimerBar from './components/SessionTimerBar'

interface Rig {
    rig_id: string
    ip: string
    status: 'idle' | 'racing' | 'offline' | 'setup' | 'ready'
    mode?: 'lockout' | 'freeuse'
    selected_car?: string | null
    driver_name?: string | null
    cpu_temp: number
    mod_version: string
    last_seen: number
    telemetry?: {
        [key: string]: any
    }
}

interface Branding {
    logo_url: string
    video_url: string
}

import { useState, useEffect, useCallback, memo } from 'react'

/* Sidebar button — defined OUTSIDE App to prevent re-creation every render (fixes flicker) */
const SidebarItem = memo(({ id, activeTab, setActiveTab, icon: Icon, label }: {
    id: string, activeTab: string, setActiveTab: (t: any) => void, icon: any, label: string
}) => (
    <button
        onClick={() => setActiveTab(id)}
        className={`w-full flex flex-col items-center gap-2 p-4 transition-all ${activeTab === id ? 'text-ridge-brand bg-white/5 border-r-2 border-ridge-brand' : 'text-white/50 hover:text-white/70 hover:bg-white/5 border-r-2 border-transparent'}`}
    >
        <Icon size={24} />
        <span className="text-[11px] font-black uppercase tracking-widest">{label}</span>
    </button>
))

function App() {
    const isKiosk = window.location.pathname === '/kiosk'
    const isLobby = window.location.pathname === '/lobby'

    if (isKiosk) {
        return <Kiosk />
    }
    if (isLobby) {
        return <Lobby />
    }

    const [activeTab, setActiveTab] = useState<'sims' | 'cars' | 'maps' | 'monitor' | 'leaderboard' | 'groups' | 'settings'>('groups')

    // Dynamic car catalog from backend
    const [catalogCars, setCatalogCars] = useState<{id: string; name: string; brand: string; car_class: string}[]>([])
    const [catalogTracks, setCatalogTracks] = useState<{id: string; name: string}[]>([])
    const [rigs, setRigs] = useState<Rig[]>([])

    // Global Session & Race Settings
    const [raceSettings, setRaceSettings] = useState({
        practice_time: 0,
        qualy_time: 10,
        race_laps: 10,
        race_time: 0,
        allow_drs: true,
        selected_track: 'monza',
        selected_weather: '3_clear',
        useMultiplayer: false,
        content_folder: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\assettocorsa'
    })
    const [serverStatus, setServerStatus] = useState<'online' | 'offline'>('offline')
    const [selectedCar, setSelectedCar] = useState('ks_ferrari_488_gt3')
    const [activeCarPool, setActiveCarPool] = useState<string[]>([])
    const [activeMapPool, setActiveMapPool] = useState<string[]>([])
    const [brandingFields, setBrandingFields] = useState<Branding>({
        logo_url: '/assets/ridge_logo.png',
        video_url: '/assets/idle_race.mp4'
    })
    const [leaderboard, setLeaderboard] = useState<any[]>([])
    const [leaderboardFilter, setLeaderboardFilter] = useState<'all' | 'recent'>('all')
    const [leaderboardTrack, setLeaderboardTrack] = useState<string>('')
    const [presets, setPresets] = useState<any[]>([])
    const [activeTelemFields, setActiveTelemFields] = useState<string[]>(['velocity', 'rpms', 'gforce', 'normalized_pos', 'gear', 'completed_laps', 'gas', 'brake', 'position'])
    const [showRigPanel, setShowRigPanel] = useState(true)

    // Categorized telemetry channels
    const TELEM_CATEGORIES = [
        { category: 'Driving', icon: Zap, fields: [
            { id: 'velocity', name: 'Speed (km/h)' },
            { id: 'rpms', name: 'Engine RPM' },
            { id: 'gear', name: 'Gear' },
            { id: 'gas', name: 'Throttle' },
            { id: 'brake', name: 'Brake' },
            { id: 'clutch', name: 'Clutch' },
            { id: 'gforce', name: 'G-Force' },
            { id: 'engine_torque', name: 'Torque' },
        ]},
        { category: 'Race', icon: Flag, fields: [
            { id: 'position', name: 'Position' },
            { id: 'completed_laps', name: 'Laps Done' },
            { id: 'remaining_laps', name: 'Laps Left' },
            { id: 'normalized_pos', name: 'Track Progress' },
            { id: 'current_lap_time', name: 'Current Lap' },
            { id: 'last_lap_time', name: 'Last Lap' },
            { id: 'best_lap_time', name: 'Best Lap' },
            { id: 'max_speed', name: 'Top Speed' },
            { id: 'is_lap_valid', name: 'Lap Valid' },
        ]},
        { category: 'Tyres', icon: Settings2, fields: [
            { id: 'tyre_temps', name: 'Tyre Temps' },
            { id: 'tyre_wear', name: 'Tyre Wear' },
            { id: 'tyre_psi', name: 'Tyre Pressure' },
        ]},
        { category: 'Brakes', icon: ShieldCheck, fields: [
            { id: 'brake_temps', name: 'Brake Temps' },
            { id: 'brake_bias', name: 'Brake Bias' },
        ]},
        { category: 'Fuel', icon: Fuel, fields: [
            { id: 'fuel_percent', name: 'Fuel Level' },
            { id: 'fuel', name: 'Fuel (L/gal)' },
        ]},
        { category: 'Electronics', icon: Cpu, fields: [
            { id: 'abs', name: 'ABS' },
            { id: 'tc', name: 'Traction Control' },
            { id: 'drs', name: 'DRS' },
        ]},
        { category: 'Conditions', icon: Thermometer, fields: [
            { id: 'air_temp', name: 'Air Temp' },
            { id: 'road_temp', name: 'Track Temp' },
        ]},
        { category: 'Damage', icon: Wrench, fields: [
            { id: 'damage', name: 'Car Damage' },
        ]},
    ]

    const ALL_CARS = [
        { id: 'ks_ferrari_488_gt3', name: 'Ferrari 488 GT3' },
        { id: 'ks_lamborghini_huracan_gt3', name: 'Lambo Huracán GT3' },
        { id: 'ks_porsche_911_gt3_rs', name: 'Porsche 911 GT3 RS' },
        { id: 'ks_mclaren_650s_gt3', name: 'McLaren 650S GT3' },
        { id: 'ks_audi_r8_lms', name: 'Audi R8 LMS' },
        { id: 'ks_mercedes_amg_gt3', name: 'Mercedes AMG GT3' },
        { id: 'ks_bmw_m6_gt3', name: 'BMW M6 GT3' },
        { id: 'ks_nissan_gt_r_gt3', name: 'Nissan GT-R GT3' },
        { id: 'ks_corvette_c7_r', name: 'Corvette C7.R' },
        { id: 'ks_ferrari_488_gte', name: 'Ferrari 488 GTE' },
        { id: 'tatuusfa1', name: 'Tatuus FA.01' },
        { id: 'ks_lotus_exos_125', name: 'Lotus Exos 125' }
    ]

    useEffect(() => {
        const fetchRigs = async () => {
            try {
                const res = await fetch('/api/rigs')
                const data = await res.json()
                if (Array.isArray(data)) {
                    setRigs((prev: Rig[]) => {
                        const newJson = JSON.stringify(data)
                        const oldJson = JSON.stringify(prev)
                        return newJson !== oldJson ? data : prev
                    })
                }

                const sRes = await fetch('/api/server/status')
                const sData = await sRes.json()
                setServerStatus((prev: string) => sData.status !== prev ? sData.status : prev)

                const lRes = await fetch('/api/leaderboard')
                const lData = await lRes.json()
                setLeaderboard((prev: any[]) => {
                    const newJson = JSON.stringify(lData)
                    const oldJson = JSON.stringify(prev)
                    return newJson !== oldJson ? lData : prev
                })
            } catch (err) {
                console.error("Failed to fetch rigs:", err)
            }
        }

        const fetchCarPool = async () => {
            try {
                const res = await fetch('/api/carpool')
                const data = await res.json()
                if (Array.isArray(data)) {
                    // If backend returns empty pool, auto-select all catalog cars
                    if (data.length === 0) {
                        try {
                            const catRes = await fetch('/api/catalogs')
                            const catData = await catRes.json()
                            const allIds = (catData.cars || []).map((c: any) => c.id)
                            if (allIds.length > 0) {
                                setActiveCarPool(allIds)
                                await fetch('/api/carpool', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ cars: allIds })
                                })
                            }
                        } catch { /* fall through */ }
                    } else {
                        setActiveCarPool(data)
                    }
                }
            } catch (err) {
                console.error("Failed to fetch car pool:", err)
            }
        }

        const fetchBranding = async () => {
            try {
                const res = await fetch('/api/branding')
                const data = await res.json()
                setBrandingFields(data)
            } catch (err) {
                console.error("Failed to fetch branding:", err)
            }
        }

        const fetchPresets = async () => {
            try {
                const res = await fetch('/api/presets')
                const data = await res.json()
                if (Array.isArray(data)) setPresets(data)
            } catch (err) {
                console.error("Failed to fetch presets:", err)
            }
        }

        const fetchTelemConfig = async () => {
            try {
                const res = await fetch('/api/telem_config')
                const data = await res.json()
                if (data.active_fields) setActiveTelemFields(data.active_fields)
            } catch (err) {
                console.error("Failed to fetch telem config:", err)
            }
        }

        const fetchCatalogs = async () => {
            try {
                const res = await fetch('/api/catalogs')
                const data = await res.json()
                if (data.cars) setCatalogCars(data.cars)
                if (data.tracks) setCatalogTracks(data.tracks)
            } catch (err) {
                console.error("Failed to fetch catalogs:", err)
            }
        }

        const fetchMapPool = async () => {
            try {
                const res = await fetch('/api/mappool')
                const data = await res.json()
                if (Array.isArray(data)) {
                    setActiveMapPool(data)
                }
            } catch (err) {
                console.error("Failed to fetch map pool:", err)
            }
        }

        fetchRigs()
        fetchCarPool()
        fetchBranding()
        fetchPresets()
        fetchTelemConfig()
        fetchCatalogs()
        fetchMapPool()
        const interval = setInterval(() => {
            fetchRigs()
        }, 2000)
        return () => clearInterval(interval)
    }, [])

    const toggleCarInPool = async (carId: string) => {
        const newPool = activeCarPool.includes(carId)
            ? activeCarPool.filter((id: string) => id !== carId)
            : [...activeCarPool, carId]

        setActiveCarPool(newPool)
        try {
            await fetch('/api/carpool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cars: newPool })
            })
        } catch (err) {
            console.error("Failed to update car pool:", err)
        }
    }

    const toggleMapInPool = async (mapId: string) => {
        const newPool = activeMapPool.includes(mapId)
            ? activeMapPool.filter((id: string) => id !== mapId)
            : [...activeMapPool, mapId]

        setActiveMapPool(newPool)
        try {
            await fetch('/api/mappool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ maps: newPool })
            })
        } catch (err) {
            console.error("Failed to update map pool:", err)
        }
    }

    const handleBrandingPush = async () => {
        try {
            await fetch('/api/branding', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(brandingFields)
            })
            alert("Facility Branding pushed successfully!")
        } catch (err) {
            console.error("Failed to push branding:", err)
        }
    }

    const sendCommand = async (rigId: string, action: string, preferredCar?: string | null) => {
        try {
            // Use rig's selected car if available, otherwise global selection
            const carToLaunch = preferredCar || selectedCar;

            await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rig_id: rigId,
                    action,
                    track: raceSettings.selected_track,
                    car: carToLaunch,
                    weather: raceSettings.selected_weather,
                    practice_time: raceSettings.practice_time,
                    qualy_time: raceSettings.qualy_time,
                    race_laps: raceSettings.race_laps,
                    race_time: raceSettings.race_time,
                    allow_drs: raceSettings.allow_drs,
                    server_ip: "192.168.1.10"
                })
            })
        } catch (err) {
            console.error("Failed to send command:", err)
        }
    }

    const toggleTelemField = async (fieldId: string) => {
        const newFields = activeTelemFields.includes(fieldId)
            ? activeTelemFields.filter(f => f !== fieldId)
            : [...activeTelemFields, fieldId]

        setActiveTelemFields(newFields)
        try {
            await fetch('/api/telem_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active_fields: newFields })
            })
        } catch (err) {
            console.error("Failed to update telem config:", err)
        }
    }

    const saveCurrentAsPreset = async (name: string) => {
        const newPreset = {
            id: Date.now().toString(),
            name,
            track: raceSettings.selected_track,
            weather: raceSettings.selected_weather,
            practice_time: raceSettings.practice_time,
            qualy_time: raceSettings.qualy_time,
            race_laps: raceSettings.race_laps,
            race_time: raceSettings.race_time,
            allow_drs: raceSettings.allow_drs,
            selected_car: selectedCar,
            car_pool: activeCarPool
        }
        const newPresets = [...presets, newPreset]
        setPresets(newPresets)
        try {
            await fetch('/api/presets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newPresets)
            })
        } catch (err) {
            console.error("Failed to save preset:", err)
        }
    }

    const applyPreset = (preset: any) => {
        setRaceSettings({
            ...raceSettings,
            selected_track: preset.track,
            selected_weather: preset.weather,
            practice_time: preset.practice_time,
            qualy_time: preset.qualy_time,
            race_laps: preset.race_laps,
            race_time: preset.race_time,
            allow_drs: preset.allow_drs
        })
        if (preset.selected_car) setSelectedCar(preset.selected_car)
        if (preset.car_pool) {
            setActiveCarPool(preset.car_pool)
            // Sync car pool to backend
            fetch('/api/carpool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cars: preset.car_pool })
            }).catch(console.error)
        }
    }

    const deletePreset = async (id: string) => {
        const newPresets = presets.filter(p => p.id !== id)
        setPresets(newPresets)
        try {
            await fetch('/api/presets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newPresets)
            })
        } catch (err) {
            console.error("Failed to delete preset:", err)
        }
    }

    const sendGlobalCommand = async (action: string) => {
        try {
            await fetch('/api/command/global', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rig_id: 'ALL',
                    action,
                    track: raceSettings.selected_track,
                    weather: raceSettings.selected_weather,
                    practice_time: raceSettings.practice_time,
                    qualy_time: raceSettings.qualy_time,
                    race_laps: raceSettings.race_laps,
                    race_time: raceSettings.race_time,
                    allow_drs: raceSettings.allow_drs,
                    use_server: raceSettings.useMultiplayer
                })
            })

            if (action === "LAUNCH_RACE" && raceSettings.useMultiplayer) {
                setServerStatus('online')
            }
        } catch (err) {
            console.error("Global command failed:", err)
        }
    }




    return (
        <div className="flex min-h-screen bg-ridge-dark text-white overflow-hidden">
            {/* Sidebar */}
            <aside className="w-24 border-r border-white/10 flex flex-col items-center py-8 z-50 bg-[#0a0a0a]">
                <div className="mb-12">
                    <div className="w-12 h-12 bg-ridge-brand rounded-xl rotate-45 flex items-center justify-center shadow-lg shadow-ridge-brand/40">
                        <Zap className="-rotate-45 text-white" size={24} />
                    </div>
                </div>

                <div className="flex-1 w-full space-y-4">
                    <SidebarItem id="groups" activeTab={activeTab} setActiveTab={setActiveTab} icon={Users} label="Groups" />
                    <SidebarItem id="sims" activeTab={activeTab} setActiveTab={setActiveTab} icon={LayoutGrid} label="Sims" />
                    <SidebarItem id="monitor" activeTab={activeTab} setActiveTab={setActiveTab} icon={Activity} label="Monitor" />
                    <SidebarItem id="leaderboard" activeTab={activeTab} setActiveTab={setActiveTab} icon={Flag} label="Standings" />
                    <SidebarItem id="cars" activeTab={activeTab} setActiveTab={setActiveTab} icon={Car} label="Cars" />
                    <SidebarItem id="maps" activeTab={activeTab} setActiveTab={setActiveTab} icon={MapPin} label="Maps" />
                    <SidebarItem id="settings" activeTab={activeTab} setActiveTab={setActiveTab} icon={Wrench} label="Settings" />
                </div>

                <div className="mt-auto">
                    <button onClick={async () => {
                        if (!confirm('Stop ALL rigs and servers?')) return
                        await Promise.all([
                            sendGlobalCommand('KILL_RACE'),
                            fetch('/api/server/stop-all', { method: 'POST' }),
                        ])
                    }} className="p-4 text-red-500 hover:bg-red-500/10 rounded-full transition-all" title="Emergency Kill All">
                        <Power size={24} />
                    </button>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 overflow-y-auto relative">
                <SessionTimerBar />
                <header className="sticky top-0 z-40 bg-ridge-dark/80 backdrop-blur-xl px-8 py-5 flex justify-between items-center border-b border-white/5">
                    <div>
                        <h1 className="text-2xl font-black italic tracking-tighter uppercase flex items-center gap-2">
                            <span className="text-ridge-brand">Ridge</span>
                            <span>{
                                activeTab === 'sims' ? 'Sim Manager' :
                                    activeTab === 'cars' ? 'Fleet Authorization' :
                                        activeTab === 'maps' ? 'Track Authorization' :
                                            activeTab === 'monitor' ? 'Telemetry Feed' :
                                                activeTab === 'leaderboard' ? 'Facility Standings' :
                                                    activeTab === 'groups' ? 'Race Groups' :
                                                        activeTab === 'settings' ? 'Settings' :
                                                            'Ridge-Link'
                            }</span>
                        </h1>
                        <p className="text-white/30 font-mono text-[10px] uppercase tracking-widest leading-none mt-1">
                            {rigs.length} rigs online // {rigs.filter(r => r.status === 'racing').length} racing
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button onClick={async () => { try { await fetch('/api/sync', { method: 'POST' }); alert('Sync command sent to all rigs!') } catch { alert('Sync failed') } }} className="bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-xl font-black uppercase text-[10px] tracking-widest flex items-center gap-2 transition-all">
                            <RotateCcw size={14} /> Sync
                        </button>
                    </div>
                </header>

                <div className="p-8 pb-32">
                    {/* SIM MANAGEMENT VIEW */}
                    {activeTab === 'sims' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                            {rigs.map((rig: Rig) => (
                                <div key={rig.rig_id} className={`glass rounded-2xl p-6 transition-all duration-500 overflow-hidden relative border ${rig.status === 'racing' ? 'status-glow-racing border-ridge-brand/50 bg-ridge-brand/5' :
                                    rig.status === 'ready' ? 'status-glow-online border-green-500/50 bg-green-500/5' :
                                        rig.status === 'setup' ? 'status-glow-online border-blue-500/50 bg-blue-500/5' :
                                            'border-white/10'
                                    }`}>
                                    <div className="flex justify-between items-start mb-6">
                                        <div>
                                            <h3 className="text-2xl font-black italic tracking-tighter line-height-none">{rig.rig_id}</h3>
                                            <code className="text-[10px] text-white/30 font-mono">{rig.ip}</code>
                                        </div>
                                        <div className={`px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest ${rig.status === 'racing' ? 'bg-ridge-brand text-white' :
                                            rig.status === 'ready' ? 'bg-green-500 text-black shadow-lg shadow-green-500/20' :
                                                rig.status === 'setup' ? 'bg-blue-500 text-white' :
                                                    'bg-zinc-800 text-white'
                                            }`}>
                                            {rig.status}
                                        </div>
                                    </div>

                                    {/* Driver Name */}
                                    <div className="mb-4">
                                        <label className="flex items-center gap-1.5 text-[8px] uppercase font-black text-white/30 tracking-widest mb-1">
                                            <Users size={8} /> Driver Name
                                        </label>
                                        <input
                                            type="text"
                                            placeholder="Enter name..."
                                            defaultValue={rig.driver_name || ''}
                                            onBlur={async (e) => {
                                                const name = e.target.value.trim()
                                                await fetch(`/api/rigs/${rig.rig_id}/driver_name`, {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ driver_name: name })
                                                })
                                            }}
                                            onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }}
                                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs font-bold outline-none focus:border-ridge-brand transition-all placeholder:text-white/15"
                                        />
                                    </div>

                                    <div className="space-y-4 mb-8">
                                        <div className="flex items-center justify-between text-[10px] uppercase font-bold tracking-widest">
                                            <div className="flex items-center gap-2 text-white/40">
                                                <Cpu size={14} /> Internal Temp
                                            </div>
                                            <div className={rig.cpu_temp > 80 ? 'text-red-500' : 'text-white'}>{rig.cpu_temp}°C</div>
                                        </div>
                                        {rig.selected_car && (
                                            <div className={`p-3 rounded-xl border ${rig.selected_car !== selectedCar ? 'bg-ridge-brand/10 border-ridge-brand/30' : 'bg-white/5 border-white/10'}`}>
                                                <div className="flex items-center gap-2 font-black uppercase text-[9px] text-white/40 mb-1">
                                                    <Zap size={12} className={rig.selected_car !== selectedCar ? 'text-ridge-brand' : ''} /> Selection
                                                </div>
                                                <div className="font-black italic text-xs truncate overflow-hidden">
                                                    {rig.selected_car.split('_').slice(1).join(' ').toUpperCase()}
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    <div className="grid grid-cols-3 gap-2">
                                        <button onClick={() => sendCommand(rig.rig_id, 'LAUNCH_RACE', rig.selected_car)} className="bg-white/5 hover:bg-ridge-brand/20 hover:text-ridge-brand p-3 rounded-xl flex items-center justify-center transition-all border border-transparent hover:border-ridge-brand/30" title="Launch Race">
                                            <Zap size={20} />
                                        </button>
                                        <button onClick={() => sendCommand(rig.rig_id, 'KILL_RACE')} className="bg-white/5 hover:bg-red-500/20 hover:text-red-500 p-3 rounded-xl flex items-center justify-center transition-all border border-transparent hover:border-red-500/30" title="Kill Race">
                                            <Power size={20} />
                                        </button>
                                        <button
                                            onClick={async () => {
                                                const newMode = (rig.mode || 'lockout') === 'lockout' ? 'freeuse' : 'lockout'
                                                await fetch(`/api/rigs/${rig.rig_id}/mode`, {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ mode: newMode })
                                                })
                                            }}
                                            className={`p-3 rounded-xl flex items-center justify-center transition-all border border-transparent ${
                                                (rig.mode || 'lockout') === 'lockout'
                                                    ? 'bg-white/5 hover:bg-amber-500/20 hover:text-amber-500 hover:border-amber-500/30'
                                                    : 'bg-green-500/10 text-green-400 hover:bg-red-500/20 hover:text-red-400 border-green-500/20 hover:border-red-500/30'
                                            }`}
                                            title={(rig.mode || 'lockout') === 'lockout' ? 'Unlock (Freeuse)' : 'Lock (Lockout)'}
                                        >
                                            {(rig.mode || 'lockout') === 'lockout' ? <Lock size={20} /> : <Unlock size={20} />}
                                        </button>
                                    </div>
                                </div>
                            ))}
                            {rigs.length === 0 && (
                                <div className="col-span-full py-24 flex flex-col items-center justify-center border-2 border-dashed border-white/5 rounded-3xl">
                                    <Activity size={48} className="mb-4 text-white/10 animate-pulse" />
                                    <p className="text-xl font-black italic tracking-tighter uppercase opacity-20 text-center">No Active Signals Detected<br /><span className="text-xs font-mono normal-case tracking-normal">Listening for UDP heartbeats on 5001...</span></p>
                                </div>
                            )}
                        </div>
                    )}

                    {/* GROUPS MANAGER VIEW */}
                    {activeTab === 'groups' && (
                        <GroupManager rigs={rigs} activeCarPool={activeCarPool} activeMapPool={activeMapPool} />
                    )}



                    {/* CAR POOL VIEW — globally available cars for all groups */}
                    {activeTab === 'cars' && (
                        <div className="max-w-5xl">
                            <div className="flex items-center justify-between mb-8">
                                <div>
                                    <h2 className="text-xl font-black italic uppercase">Fleet Authorization</h2>
                                    <p className="text-xs text-white/40 uppercase tracking-widest font-bold">Enable or disable cars available across all groups</p>
                                </div>
                                <div className="flex items-center gap-4">
                                    <button
                                        onClick={async () => {
                                            const allIds = (catalogCars.length > 0 ? catalogCars : ALL_CARS).map(c => c.id)
                                            const allSelected = allIds.every(id => activeCarPool.includes(id))
                                            const newPool = allSelected ? [] : allIds
                                            setActiveCarPool(newPool)
                                            try {
                                                await fetch('/api/carpool', {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ cars: newPool })
                                                })
                                            } catch {}
                                        }}
                                        className="px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border bg-white/5 border-white/10 text-white/50 hover:border-ridge-brand/50 hover:text-ridge-brand"
                                    >
                                        {((catalogCars.length > 0 ? catalogCars : ALL_CARS).map(c => c.id)).every(id => activeCarPool.includes(id)) ? 'Deselect All' : 'Select All'}
                                    </button>
                                    <div className="text-right">
                                        <p className="text-xs font-black uppercase text-white/40">Authorized</p>
                                        <p className="text-2xl font-black italic text-ridge-brand">{activeCarPool.length} / {catalogCars.length || ALL_CARS.length}</p>
                                    </div>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                {(catalogCars.length > 0 ? catalogCars : ALL_CARS.map(c => ({...c, brand: '', car_class: ''}))).map((car) => (
                                    <button
                                        key={car.id}
                                        onClick={() => toggleCarInPool(car.id)}
                                        className={`group text-left p-4 rounded-2xl border transition-all relative overflow-hidden flex flex-col justify-between h-32 ${activeCarPool.includes(car.id)
                                            ? 'bg-ridge-brand/10 border-ridge-brand/50 text-white'
                                            : 'bg-white/5 border-white/5 text-white/20'
                                            }`}
                                    >
                                        <div className="flex justify-between items-start">
                                            <Car size={32} className={`transition-all ${activeCarPool.includes(car.id) ? 'text-ridge-brand' : 'opacity-20'}`} />
                                            {activeCarPool.includes(car.id) ? <Check className="text-ridge-brand" size={16} /> : <Zap size={16} className="opacity-10" />}
                                        </div>
                                        <div>
                                            {car.brand && <span className="text-[8px] font-bold uppercase text-white/30 block">{car.brand}</span>}
                                            <span className={`font-black italic uppercase text-xs tracking-tighter ${activeCarPool.includes(car.id) ? 'text-white' : 'group-hover:text-white/40 transition-colors'}`}>{car.name}</span>
                                        </div>
                                        {activeCarPool.includes(car.id) && <div className="absolute -right-2 -bottom-2 w-12 h-12 bg-ridge-brand/20 blur-xl rounded-full" />}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* MAP POOL VIEW — globally available tracks for all groups */}
                    {activeTab === 'maps' && (
                        <div className="max-w-5xl">
                            <div className="flex items-center justify-between mb-8">
                                <div>
                                    <h2 className="text-xl font-black italic uppercase">Track Authorization</h2>
                                    <p className="text-xs text-white/40 uppercase tracking-widest font-bold">Enable or disable tracks available across all groups</p>
                                </div>
                                <div className="flex items-center gap-4">
                                    <button
                                        onClick={async () => {
                                            const allIds = catalogTracks.map(t => t.id)
                                            const allSelected = allIds.every(id => activeMapPool.includes(id))
                                            const newPool = allSelected ? [] : allIds
                                            setActiveMapPool(newPool)
                                            try {
                                                await fetch('/api/mappool', {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ maps: newPool })
                                                })
                                            } catch {}
                                        }}
                                        className="px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border bg-white/5 border-white/10 text-white/50 hover:border-ridge-brand/50 hover:text-ridge-brand"
                                    >
                                        {catalogTracks.map(t => t.id).every(id => activeMapPool.includes(id)) ? 'Deselect All' : 'Select All'}
                                    </button>
                                    <div className="text-right">
                                        <p className="text-xs font-black uppercase text-white/40">Authorized</p>
                                        <p className="text-2xl font-black italic text-ridge-brand">{activeMapPool.length} / {catalogTracks.length}</p>
                                    </div>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                {catalogTracks.map((track) => (
                                    <button
                                        key={track.id}
                                        onClick={() => toggleMapInPool(track.id)}
                                        className={`group text-left p-4 rounded-2xl border transition-all relative overflow-hidden flex flex-col justify-between h-32 ${activeMapPool.includes(track.id)
                                            ? 'bg-ridge-brand/10 border-ridge-brand/50 text-white'
                                            : 'bg-white/5 border-white/5 text-white/20'
                                            }`}
                                    >
                                        <div className="flex justify-between items-start">
                                            <MapPin size={32} className={`transition-all ${activeMapPool.includes(track.id) ? 'text-ridge-brand' : 'opacity-20'}`} />
                                            {activeMapPool.includes(track.id) ? <Check className="text-ridge-brand" size={16} /> : <Zap size={16} className="opacity-10" />}
                                        </div>
                                        <div>
                                            <span className={`font-black italic uppercase text-xs tracking-tighter ${activeMapPool.includes(track.id) ? 'text-white' : 'group-hover:text-white/40 transition-colors'}`}>{track.name}</span>
                                            <span className="text-[8px] font-mono text-white/20 block mt-0.5">{track.id}</span>
                                        </div>
                                        {activeMapPool.includes(track.id) && <div className="absolute -right-2 -bottom-2 w-12 h-12 bg-ridge-brand/20 blur-xl rounded-full" />}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* LIVE MONITOR VIEW */}
                    {activeTab === 'monitor' && (() => {
                        const t = (rig: Rig, key: string, fallback: any = 0) => rig.telemetry?.[key] ?? fallback
                        const has = (id: string) => activeTelemFields.includes(id)

                        // 2x2 corner grid helper
                        const CornerGrid = ({ label, fl, fr, rl, rr, unit, color }: { label: string, fl: number, fr: number, rl: number, rr: number, unit: string, color?: string }) => (
                            <div className="bg-black/30 p-2.5 rounded-xl">
                                <p className="text-[8px] font-black uppercase text-white/40 mb-1.5">{label}</p>
                                <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] font-bold tabular-nums">
                                    <span className={color || 'text-white/60'}>FL {fl}{unit}</span>
                                    <span className={color || 'text-white/60'}>FR {fr}{unit}</span>
                                    <span className={color || 'text-white/60'}>RL {rl}{unit}</span>
                                    <span className={color || 'text-white/60'}>RR {rr}{unit}</span>
                                </div>
                            </div>
                        )

                        return (
                        <div className="space-y-6">
                            {/* Channel Selector — categorized columns */}
                            <div className="glass rounded-2xl p-5 border border-white/10">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-white/50">Data Channels</h3>
                                    <div className="flex gap-2">
                                        <button onClick={() => setActiveTelemFields(TELEM_CATEGORIES.flatMap(c => c.fields.map(f => f.id)))}
                                            className="text-[9px] font-black uppercase tracking-widest text-ridge-brand/70 hover:text-ridge-brand px-2 py-0.5 rounded border border-ridge-brand/20 hover:border-ridge-brand/40 transition-all">All On</button>
                                        <button onClick={() => setActiveTelemFields([])}
                                            className="text-[9px] font-black uppercase tracking-widest text-white/30 hover:text-white/50 px-2 py-0.5 rounded border border-white/10 hover:border-white/20 transition-all">All Off</button>
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-4">
                                    {TELEM_CATEGORIES.map(cat => (
                                        <div key={cat.category}>
                                            <div className="flex items-center gap-1.5 mb-2">
                                                <cat.icon size={10} className="text-white/40" />
                                                <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{cat.category}</span>
                                            </div>
                                            <div className="space-y-1">
                                                {cat.fields.map(field => (
                                                    <button
                                                        key={field.id}
                                                        onClick={() => toggleTelemField(field.id)}
                                                        className={`w-full text-left px-2 py-1 rounded text-[9px] font-bold transition-all ${
                                                            activeTelemFields.includes(field.id)
                                                                ? 'bg-ridge-brand/15 text-ridge-brand'
                                                                : 'text-white/20 hover:text-white/40 hover:bg-white/5'
                                                        }`}
                                                    >
                                                        {field.name}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Rig Telemetry Cards */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
                                {rigs.map((rig: Rig) => (
                                    <div key={rig.rig_id} className={`rounded-2xl p-5 relative overflow-hidden border transition-all ${rig.status === 'racing' ? 'bg-white/5 border-ridge-brand/30' : 'bg-white/[0.02] border-white/5'}`}>
                                        {/* Header */}
                                        <div className="flex justify-between items-center mb-4">
                                            <div>
                                                <h3 className="text-base font-black italic uppercase tracking-tight">{rig.driver_name || rig.rig_id}</h3>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    {rig.driver_name && <span className="text-[9px] font-mono text-white/30">{rig.rig_id}</span>}
                                                    {rig.telemetry?.car_model && <span className="text-[9px] font-bold text-white/25 uppercase">{rig.telemetry.car_model}</span>}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {rig.status === 'racing' && (
                                                    <button
                                                        onClick={async () => {
                                                            await fetch('/api/command', {
                                                                method: 'POST',
                                                                headers: { 'Content-Type': 'application/json' },
                                                                body: JSON.stringify({ rig_id: rig.rig_id, action: 'KILL_RACE' })
                                                            })
                                                        }}
                                                        className="bg-red-500/10 hover:bg-red-500/20 text-red-400 p-1.5 rounded-lg transition-all"
                                                        title="Stop race for this rig"
                                                    >
                                                        <Square size={12} />
                                                    </button>
                                                )}
                                                <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${rig.status === 'racing' ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-white/30'}`}>
                                                    {rig.status === 'racing' ? 'LIVE' : rig.status.toUpperCase()}
                                                </span>
                                            </div>
                                        </div>

                                        {rig.status === 'racing' && rig.telemetry ? (
                                            <div className="space-y-3">
                                                {/* Speed + RPM Hero */}
                                                {(has('velocity') || has('rpms')) && (
                                                    <div className="flex gap-3">
                                                        {has('velocity') && (
                                                            <div className="flex-1 bg-black/30 p-3 rounded-xl">
                                                                <p className="text-[8px] font-black uppercase text-white/40 mb-0.5">Speed</p>
                                                                <div className="flex items-baseline gap-1">
                                                                    <span className="text-3xl font-black italic tabular-nums leading-none">{Math.round(t(rig, 'velocity', [0])?.[0] ?? 0)}</span>
                                                                    <span className="text-[9px] font-bold text-ridge-brand">km/h</span>
                                                                </div>
                                                            </div>
                                                        )}
                                                        {has('rpms') && (
                                                            <div className="flex-1 bg-black/30 p-3 rounded-xl">
                                                                <p className="text-[8px] font-black uppercase text-white/40 mb-0.5">RPM</p>
                                                                <span className="text-3xl font-black italic tabular-nums leading-none">{Number(t(rig, 'rpms')).toLocaleString()}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                {/* Compact stats row */}
                                                {(() => {
                                                    const cells: JSX.Element[] = []
                                                    if (has('gear')) cells.push(<div key="gear" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Gear</p><span className="text-lg font-black italic">{t(rig,'gear') === -1 ? 'R' : t(rig,'gear') === 0 ? 'N' : t(rig,'gear')}</span></div>)
                                                    if (has('completed_laps')) cells.push(<div key="laps" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Laps</p><span className="text-lg font-black italic">{t(rig,'completed_laps')}/{t(rig,'total_laps','-')}</span></div>)
                                                    if (has('position')) cells.push(<div key="pos" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Pos</p><span className="text-lg font-black italic text-amber-400">P{t(rig,'position')}</span></div>)
                                                    if (has('remaining_laps')) cells.push(<div key="rem" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Left</p><span className="text-lg font-black italic">{t(rig,'remaining_laps')}</span></div>)
                                                    if (has('gforce')) cells.push(<div key="gf" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">G-Lat</p><span className="text-lg font-black italic text-blue-400">{Number(t(rig,'gforce',[0,0,0])?.[0] ?? 0).toFixed(1)}</span></div>)
                                                    if (has('max_speed')) cells.push(<div key="maxspd" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Top</p><span className="text-lg font-black italic">{t(rig,'max_speed')}</span></div>)
                                                    if (has('engine_torque')) cells.push(<div key="torq" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Nm</p><span className="text-lg font-black italic">{Math.round(t(rig,'engine_torque'))}</span></div>)
                                                    if (has('clutch')) cells.push(<div key="clutch" className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Clutch</p><span className="text-lg font-black italic">{Math.round(t(rig,'clutch') * 100)}%</span></div>)
                                                    if (cells.length === 0) return null
                                                    return <div className={`grid gap-2`} style={{ gridTemplateColumns: `repeat(${Math.min(cells.length, 4)}, 1fr)` }}>{cells}</div>
                                                })()}

                                                {/* Lap times */}
                                                {(has('current_lap_time') || has('last_lap_time') || has('best_lap_time')) && (
                                                    <div className="grid grid-cols-3 gap-2">
                                                        {has('current_lap_time') && <div className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Current</p><span className="text-[11px] font-black tabular-nums text-white/70">{t(rig,'current_lap_time','--:--')}</span></div>}
                                                        {has('last_lap_time') && <div className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Last</p><span className="text-[11px] font-black tabular-nums text-white/70">{t(rig,'last_lap_time','--:--')}</span></div>}
                                                        {has('best_lap_time') && <div className="bg-black/30 p-2 rounded-xl text-center"><p className="text-[8px] font-black uppercase text-white/40">Best</p><span className="text-[11px] font-black tabular-nums text-purple-400">{t(rig,'best_lap_time','--:--')}</span></div>}
                                                    </div>
                                                )}

                                                {/* Throttle + Brake bars */}
                                                {(has('gas') || has('brake')) && (
                                                    <div className="grid grid-cols-2 gap-2">
                                                        {has('gas') && (
                                                            <div>
                                                                <div className="flex justify-between text-[8px] font-black uppercase text-white/40 mb-1"><span>Throttle</span><span className="text-green-400">{Math.round(t(rig,'gas') * 100)}%</span></div>
                                                                <div className="h-2 bg-black/40 rounded-full overflow-hidden"><div className="h-full bg-green-500 transition-all duration-75 rounded-full" style={{ width: `${t(rig,'gas') * 100}%` }} /></div>
                                                            </div>
                                                        )}
                                                        {has('brake') && (
                                                            <div>
                                                                <div className="flex justify-between text-[8px] font-black uppercase text-white/40 mb-1"><span>Brake</span><span className="text-red-400">{Math.round(t(rig,'brake') * 100)}%</span></div>
                                                                <div className="h-2 bg-black/40 rounded-full overflow-hidden"><div className="h-full bg-red-500 transition-all duration-75 rounded-full" style={{ width: `${t(rig,'brake') * 100}%` }} /></div>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                {/* Circuit Progress */}
                                                {has('normalized_pos') && (
                                                    <div>
                                                        <div className="flex justify-between text-[8px] font-black uppercase text-white/40 mb-1"><span>Track Progress</span><span>{Math.round(t(rig,'normalized_pos') * 100)}%</span></div>
                                                        <div className="h-1 bg-black/40 rounded-full overflow-hidden"><div className="h-full bg-ridge-brand transition-all duration-300 rounded-full" style={{ width: `${t(rig,'normalized_pos') * 100}%` }} /></div>
                                                    </div>
                                                )}

                                                {/* Fuel */}
                                                {(has('fuel_percent') || has('fuel')) && (
                                                    <div className="flex gap-3">
                                                        {has('fuel_percent') && (
                                                            <div className="flex-1">
                                                                <div className="flex justify-between text-[8px] font-black uppercase text-white/40 mb-1"><span>Fuel</span><span className="text-amber-400">{t(rig,'fuel_percent')}%</span></div>
                                                                <div className="h-2 bg-black/40 rounded-full overflow-hidden"><div className="h-full bg-amber-500 transition-all duration-300 rounded-full" style={{ width: `${t(rig,'fuel_percent')}%` }} /></div>
                                                            </div>
                                                        )}
                                                        {has('fuel') && <div className="bg-black/30 px-3 py-1.5 rounded-xl text-center shrink-0"><p className="text-[8px] font-black uppercase text-white/40">L</p><span className="text-sm font-black italic tabular-nums">{t(rig,'fuel')}</span></div>}
                                                    </div>
                                                )}

                                                {/* Tyres */}
                                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                                    {has('tyre_temps') && <CornerGrid label="Tyre Temp °C" fl={t(rig,'tyre_temp_fl')} fr={t(rig,'tyre_temp_fr')} rl={t(rig,'tyre_temp_rl')} rr={t(rig,'tyre_temp_rr')} unit="°" />}
                                                    {has('tyre_wear') && <CornerGrid label="Tyre Wear %" fl={t(rig,'tyre_wear_fl')} fr={t(rig,'tyre_wear_fr')} rl={t(rig,'tyre_wear_rl')} rr={t(rig,'tyre_wear_rr')} unit="%" color="text-green-400/70" />}
                                                    {has('tyre_psi') && <CornerGrid label="Tyre PSI" fl={t(rig,'tyre_psi_fl')} fr={t(rig,'tyre_psi_fr')} rl={t(rig,'tyre_psi_rl')} rr={t(rig,'tyre_psi_rr')} unit="" />}
                                                </div>

                                                {/* Brakes */}
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                    {has('brake_temps') && <CornerGrid label="Brake Temp °C" fl={t(rig,'brake_temp_fl')} fr={t(rig,'brake_temp_fr')} rl={t(rig,'brake_temp_rl')} rr={t(rig,'brake_temp_rr')} unit="°" color="text-orange-400/70" />}
                                                    {has('brake_bias') && <div className="bg-black/30 p-2.5 rounded-xl"><p className="text-[8px] font-black uppercase text-white/40 mb-1">Brake Bias</p><span className="text-lg font-black italic">{t(rig,'brake_bias')}%</span><span className="text-[8px] text-white/20 ml-1">front</span></div>}
                                                </div>

                                                {/* Electronics */}
                                                {(has('abs') || has('tc') || has('drs')) && (
                                                    <div className="flex gap-2 flex-wrap">
                                                        {has('abs') && <div className={`px-2.5 py-1 rounded-lg text-[8px] font-black uppercase tracking-widest border ${t(rig,'abs_active') ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' : 'bg-white/5 text-white/20 border-white/5'}`}>ABS {t(rig,'abs_level')}</div>}
                                                        {has('tc') && <div className={`px-2.5 py-1 rounded-lg text-[8px] font-black uppercase tracking-widest border ${t(rig,'tc_active') ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' : 'bg-white/5 text-white/20 border-white/5'}`}>TC {t(rig,'tc_level')}</div>}
                                                        {has('drs') && <div className={`px-2.5 py-1 rounded-lg text-[8px] font-black uppercase tracking-widest border ${t(rig,'drs_enabled') ? 'bg-green-500/20 text-green-400 border-green-500/30' : t(rig,'drs_available') ? 'bg-yellow-500/10 text-yellow-400/60 border-yellow-500/20' : 'bg-white/5 text-white/20 border-white/5'}`}>{t(rig,'drs_enabled') ? 'DRS ON' : t(rig,'drs_available') ? 'DRS RDY' : 'DRS'}</div>}
                                                        {has('is_lap_valid') && <div className={`px-2.5 py-1 rounded-lg text-[8px] font-black uppercase tracking-widest border ${t(rig,'is_lap_valid') ? 'bg-green-500/10 text-green-400/60 border-green-500/20' : 'bg-red-500/20 text-red-400 border-red-500/30'}`}>{t(rig,'is_lap_valid') ? 'VALID' : 'INVALID'}</div>}
                                                    </div>
                                                )}

                                                {/* Conditions */}
                                                {(has('air_temp') || has('road_temp')) && (
                                                    <div className="flex gap-3">
                                                        {has('air_temp') && <div className="bg-black/30 p-2 rounded-xl text-center flex-1"><p className="text-[8px] font-black uppercase text-white/40">Air</p><span className="text-sm font-black italic">{t(rig,'air_temp')}°C</span></div>}
                                                        {has('road_temp') && <div className="bg-black/30 p-2 rounded-xl text-center flex-1"><p className="text-[8px] font-black uppercase text-white/40">Track</p><span className="text-sm font-black italic">{t(rig,'road_temp')}°C</span></div>}
                                                    </div>
                                                )}

                                                {/* Damage */}
                                                {has('damage') && t(rig,'damage_avg') > 0 && (
                                                    <div className="bg-red-500/10 border border-red-500/20 p-2.5 rounded-xl">
                                                        <p className="text-[7px] font-black uppercase text-red-400/60 mb-1">Damage</p>
                                                        <div className="grid grid-cols-4 gap-2 text-[10px] font-bold tabular-nums text-red-400/80">
                                                            <span>F: {t(rig,'damage_front')}</span><span>R: {t(rig,'damage_rear')}</span>
                                                            <span>L: {t(rig,'damage_left')}</span><span>R: {t(rig,'damage_right')}</span>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="py-10 text-center">
                                                <Monitor size={24} className="mx-auto mb-2 text-white/10" />
                                                <p className="text-[9px] uppercase font-black tracking-widest text-white/15">Waiting for race to start</p>
                                                <p className="text-[8px] text-white/10 mt-1">{rig.status === 'idle' ? 'Rig idle' : rig.status === 'ready' ? 'Rig ready' : rig.status}</p>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                        )
                    })()}

                    {/* LEADERBOARD VIEW */}
                    {activeTab === 'leaderboard' && (() => {
                        // Build query URL with filters
                        const fetchFilteredLeaderboard = async () => {
                            try {
                                const params = new URLSearchParams()
                                if (leaderboardFilter === 'recent') params.set('view', 'recent')
                                if (leaderboardTrack) params.set('track', leaderboardTrack)
                                const res = await fetch(`/api/leaderboard?${params.toString()}`)
                                const data = await res.json()
                                if (Array.isArray(data)) setLeaderboard(data)
                            } catch { /* offline */ }
                        }

                        // Available tracks from leaderboard data
                        const tracks = [...new Set(leaderboard.map((e: any) => e.track).filter(Boolean))]
                        const filtered = leaderboard
                            .sort((a: any, b: any) => b.lap - a.lap)
                            .slice(0, 50)

                        const formatCarName = (id: string) => id ? id.split('_').slice(1).join(' ').toUpperCase() : '—'
                        const formatTrack = (id: string) => id ? id.charAt(0).toUpperCase() + id.slice(1).replace(/_/g, ' ') : '—'

                        return (
                        <div className="max-w-6xl">
                            <div className="flex justify-between items-start mb-8">
                                <div>
                                    <h2 className="text-4xl font-black italic uppercase tracking-tighter mb-2">Hall of Fame</h2>
                                    <p className="text-sm text-white/40 uppercase tracking-[0.4em] font-bold">Race Results // Facility Leaderboard</p>
                                </div>
                                <div className="p-4 bg-ridge-brand rounded-2xl rotate-3 shadow-2xl shadow-ridge-brand/40">
                                    <Flag size={32} />
                                </div>
                            </div>

                            {/* Filters */}
                            <div className="flex items-center gap-3 mb-6">
                                <button
                                    onClick={() => { setLeaderboardFilter('all'); setLeaderboardTrack('') }}
                                    className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border ${
                                        leaderboardFilter === 'all' && !leaderboardTrack
                                            ? 'bg-ridge-brand/20 border-ridge-brand/50 text-ridge-brand'
                                            : 'bg-white/5 border-white/10 text-white/30 hover:border-white/20'
                                    }`}
                                >All Time</button>
                                <button
                                    onClick={async () => {
                                        setLeaderboardFilter('recent')
                                        setLeaderboardTrack('')
                                        try {
                                            const res = await fetch('/api/leaderboard?view=recent')
                                            const data = await res.json()
                                            if (Array.isArray(data)) setLeaderboard(data)
                                        } catch {}
                                    }}
                                    className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border ${
                                        leaderboardFilter === 'recent'
                                            ? 'bg-amber-500/20 border-amber-500/50 text-amber-400'
                                            : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                                    }`}
                                >Recent Session</button>

                                {tracks.length > 0 && (
                                    <div className="relative">
                                        <select
                                            value={leaderboardTrack}
                                            onChange={async (e) => {
                                                setLeaderboardTrack(e.target.value)
                                                setLeaderboardFilter('all')
                                                try {
                                                    const params = e.target.value ? `?track=${e.target.value}` : ''
                                                    const res = await fetch(`/api/leaderboard${params}`)
                                                    const data = await res.json()
                                                    if (Array.isArray(data)) setLeaderboard(data)
                                                } catch {}
                                            }}
                                            className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 pr-7 text-[10px] font-black uppercase tracking-widest outline-none cursor-pointer appearance-none"
                                        >
                                            <option value="">All Tracks</option>
                                            {tracks.map(t => <option key={t} value={t}>{formatTrack(t)}</option>)}
                                        </select>
                                        <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
                                    </div>
                                )}

                                <span className="ml-auto text-[10px] text-white/30 font-bold uppercase">{filtered.length} records</span>
                            </div>

                            {/* Grid */}
                            <div className="glass rounded-2xl border border-white/10 overflow-hidden">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-white/10">
                                            <th className="text-left px-5 py-4 text-[10px] font-black uppercase tracking-widest text-white/50 w-16">#</th>
                                            <th className="text-left px-5 py-4 text-[10px] font-black uppercase tracking-widest text-white/50">Driver</th>
                                            <th className="text-left px-5 py-4 text-[10px] font-black uppercase tracking-widest text-white/50">Car</th>
                                            <th className="text-left px-5 py-4 text-[10px] font-black uppercase tracking-widest text-white/50">Track</th>
                                            <th className="text-right px-5 py-4 text-[10px] font-black uppercase tracking-widest text-white/50">Laps</th>
                                            <th className="text-right px-5 py-4 text-[10px] font-black uppercase tracking-widest text-white/50">Time</th>
                                            <th className="text-right px-5 py-4 text-[10px] font-black uppercase tracking-widest text-white/50">Date</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filtered.length > 0 ? filtered.map((entry: any, idx: number) => (
                                            <tr key={idx} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                                <td className="px-5 py-3.5">
                                                    <span className={`text-lg font-black italic tabular-nums ${idx < 3 ? 'text-ridge-brand' : 'text-white/30'}`}>{idx + 1}</span>
                                                </td>
                                                <td className="px-5 py-3.5">
                                                    <div>
                                                        <span className="text-sm font-black italic uppercase tracking-tight">{entry.driver_name || entry.rig_id}</span>
                                                        {entry.driver_name && (
                                                            <span className="block text-[9px] font-mono text-white/30">{entry.rig_id}</span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="px-5 py-3.5">
                                                    <span className="text-[11px] font-bold uppercase text-white/60">{formatCarName(entry.car || '')}</span>
                                                </td>
                                                <td className="px-5 py-3.5">
                                                    <span className="text-[11px] font-bold uppercase text-white/60">{formatTrack(entry.track || '')}</span>
                                                </td>
                                                <td className="px-5 py-3.5 text-right">
                                                    <span className="text-sm font-black italic tabular-nums">{entry.lap}</span>
                                                </td>
                                                <td className="px-5 py-3.5 text-right">
                                                    <span className="text-[11px] font-bold text-white/50 tabular-nums">
                                                        {entry.lap_time_ms ? (() => {
                                                            const totalMs = entry.lap_time_ms
                                                            const mins = Math.floor(totalMs / 60000)
                                                            const secs = Math.floor((totalMs % 60000) / 1000)
                                                            const ms = totalMs % 1000
                                                            return `${mins}:${String(secs).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
                                                        })() : '—'}
                                                    </span>
                                                </td>
                                                <td className="px-5 py-3.5 text-right">
                                                    <span className="text-[10px] font-bold text-white/40 tabular-nums">
                                                        {entry.timestamp ? new Date(entry.timestamp * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                                                    </span>
                                                </td>
                                            </tr>
                                        )) : (
                                            <tr>
                                                <td colSpan={7} className="px-5 py-16 text-center">
                                                    <p className="text-sm font-black italic uppercase opacity-20 tracking-tighter">No race results recorded yet</p>
                                                    <p className="text-[11px] text-white/25 font-bold uppercase mt-2">Results will appear as rigs complete laps</p>
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )})()}

                    {/* SETTINGS VIEW — includes branding + system config + presets */}
                    {activeTab === 'settings' && (
                        <div className="max-w-3xl space-y-6">
                            {/* Brand Identity (merged from Media) */}
                            <div className="glass rounded-3xl p-8 border border-white/10">
                                <h2 className="text-lg font-black italic uppercase mb-6 flex items-center gap-2"><Image className="text-ridge-brand" size={20} /> Brand Identity</h2>
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-[10px] uppercase font-black text-white/40 mb-2">Corporate Logo URL (PNG/SVG)</label>
                                        <input
                                            type="text"
                                            value={brandingFields.logo_url}
                                            onChange={(e) => setBrandingFields({ ...brandingFields, logo_url: e.target.value })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 font-mono text-xs focus:ring-1 focus:ring-ridge-brand outline-none transition-all"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-[10px] uppercase font-black text-white/40 mb-1">Cinematic Loop (MP4)</label>
                                        <p className="text-[9px] text-white/20 uppercase font-black mb-2 tracking-widest italic">Displayed during rig idle state</p>
                                        <input
                                            type="text"
                                            value={brandingFields.video_url}
                                            onChange={(e) => setBrandingFields({ ...brandingFields, video_url: e.target.value })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 font-mono text-xs focus:ring-1 focus:ring-ridge-brand outline-none transition-all"
                                        />
                                    </div>
                                    <button
                                        onClick={handleBrandingPush}
                                        className="w-full bg-ridge-brand hover:bg-orange-600 py-3 rounded-xl font-black tracking-tighter italic uppercase text-xs transition-all shadow-lg shadow-ridge-brand/20"
                                    >
                                        Deploy Branding to Network
                                    </button>
                                </div>
                            </div>

                            {/* System Configuration */}
                            <div className="glass rounded-3xl p-8 border border-white/10">
                                <h2 className="text-lg font-black italic uppercase mb-6 flex items-center gap-2"><Wrench className="text-ridge-brand" size={20} /> System Configuration</h2>
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-[10px] uppercase font-black text-white/40 mb-2">Assetto Corsa Install Path</label>
                                        <input
                                            type="text"
                                            value={raceSettings.content_folder}
                                            onChange={(e) => setRaceSettings({ ...raceSettings, content_folder: e.target.value })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 font-mono text-xs focus:ring-1 focus:ring-ridge-brand outline-none transition-all"
                                            placeholder="C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"
                                        />
                                    </div>
                                    <button
                                        onClick={async () => {
                                            try {
                                                await fetch('/api/settings', {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify(raceSettings)
                                                })
                                                alert('Settings saved!')
                                            } catch { alert('Failed to save settings') }
                                        }}
                                        className="bg-ridge-brand hover:bg-orange-600 px-8 py-3 rounded-xl font-black italic uppercase text-xs transition-all shadow-lg shadow-ridge-brand/20"
                                    >
                                        Save Settings
                                    </button>
                                </div>
                            </div>

                            {/* Presets */}
                            <div className="glass rounded-3xl p-8 border border-white/10">
                                <h2 className="text-lg font-black italic uppercase mb-6 flex items-center gap-2"><ShieldCheck className="text-ridge-brand" size={20} /> Configuration Presets</h2>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {presets.map(preset => (
                                        <div key={preset.id} className="bg-black/20 border border-white/5 p-4 rounded-2xl group relative">
                                            <div className="flex justify-between items-center mb-3">
                                                <h4 className="font-black italic uppercase text-sm text-ridge-brand">{preset.name}</h4>
                                                <div className="flex gap-2">
                                                    <button onClick={() => applyPreset(preset)} className="text-green-500 hover:scale-110 transition-transform"><Check size={16} /></button>
                                                    <button onClick={() => deletePreset(preset.id)} className="text-red-500 hover:scale-110 transition-transform opacity-0 group-hover:opacity-100"><Power size={14} /></button>
                                                </div>
                                            </div>
                                            <div className="text-[8px] font-bold uppercase tracking-widest text-white/30 space-y-1">
                                                <p>{preset.track.toUpperCase()} // ENV {preset.weather.split('_').slice(1).join(' ')}</p>
                                                <p>{preset.race_laps} Laps | {preset.qualy_time}m Qualify | DRS: {preset.allow_drs ? 'ON' : 'OFF'}</p>
                                            </div>
                                        </div>
                                    ))}
                                    {presets.length === 0 && (
                                        <div className="col-span-full py-8 text-center text-white/10 italic text-[10px] uppercase font-black tracking-widest px-4 border border-dashed border-white/5 rounded-2xl">
                                            No saved presets found
                                        </div>
                                    )}
                                </div>
                                <button
                                    onClick={() => {
                                        const name = prompt('Enter a name for this preset:');
                                        if (name) saveCurrentAsPreset(name);
                                    }}
                                    className="mt-4 bg-white/10 hover:bg-white/20 px-6 py-2 rounded-full text-[10px] font-black uppercase tracking-widest transition-all"
                                >
                                    Save Current as Preset
                                </button>
                            </div>

                            {/* Full System Update */}
                            <div className="glass rounded-3xl p-8 border border-red-500/20 bg-red-500/[0.02]">
                                <h2 className="text-lg font-black italic uppercase mb-2 flex items-center gap-2"><RotateCcw className="text-red-400" size={20} /> Full System Update</h2>
                                <p className="text-xs text-white/40 mb-4 leading-relaxed">
                                    Stops all active races and servers, pulls the latest code on all rigs and the admin PC,
                                    then restarts everything. All console windows will be closed and reopened.
                                </p>
                                <div className="flex items-center gap-4">
                                    <button
                                        onClick={async () => {
                                            if (!confirm('⚠️ FULL SYSTEM UPDATE\n\nThis will:\n• Stop ALL active races\n• Stop ALL servers\n• Pull latest code on ALL rigs\n• Pull latest code on this admin PC\n• Restart the entire system\n\nAll players will be disconnected.\n\nContinue?')) return
                                            try {
                                                const res = await fetch('/api/update', { method: 'POST' })
                                                const data = await res.json()
                                                alert(`Update initiated!\n\n${data.message}\n\nThe dashboard will go offline briefly while the system restarts.`)
                                            } catch (err) {
                                                alert('Failed to initiate update. Check the console.')
                                                console.error(err)
                                            }
                                        }}
                                        className="bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 hover:border-red-500/50 px-8 py-3 rounded-xl font-black italic uppercase text-xs transition-all"
                                    >
                                        Deploy Full Update
                                    </button>
                                    <span className="text-[9px] text-white/25 font-bold uppercase tracking-widest">Requires network access to Git</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>





            </main>

            {/* Right Rig Status Panel */}
            {showRigPanel && (
                <aside className="w-80 border-l border-white/5 bg-[#0a0a0a] flex flex-col overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
                        <span className="text-[11px] font-black uppercase tracking-[0.2em] text-white/60">Rig Status</span>
                        <button onClick={() => setShowRigPanel(false)} className="text-white/30 hover:text-white/60 transition-colors p-1 hover:bg-white/5 rounded" title="Hide panel">
                            <ChevronRight size={16} />
                        </button>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {rigs.length === 0 && (
                            <div className="px-5 py-16 text-center">
                                <Activity size={20} className="mx-auto mb-2 text-white/10" />
                                <p className="text-[11px] text-white/30 font-black uppercase tracking-widest">No rigs connected</p>
                            </div>
                        )}
                        {rigs.map((rig: Rig) => {
                            const statusColor = rig.status === 'racing' ? 'bg-ridge-brand' :
                                rig.status === 'ready' ? 'bg-green-500' :
                                rig.status === 'setup' ? 'bg-blue-500' :
                                rig.status === 'offline' ? 'bg-red-500' : 'bg-zinc-600'
                            const laps = rig.telemetry?.completed_laps ?? 0
                            return (
                                <div key={rig.rig_id} className="px-5 py-3.5 border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                                    {/* Row 1: Name + status */}
                                    <div className="flex items-center justify-between mb-1.5">
                                        <div className="flex items-center gap-2.5 min-w-0">
                                            <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${statusColor}`} />
                                            <span className="text-[13px] font-black italic uppercase tracking-tight truncate">
                                                {rig.driver_name || rig.rig_id}
                                            </span>
                                        </div>
                                        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded shrink-0 ${
                                            rig.status === 'racing' ? 'bg-ridge-brand/20 text-ridge-brand' :
                                            rig.status === 'ready' ? 'bg-green-500/20 text-green-400' :
                                            rig.status === 'setup' ? 'bg-blue-500/20 text-blue-400' :
                                            'bg-white/5 text-white/40'
                                        }`}>{rig.status}</span>
                                    </div>

                                    {/* Row 2: Rig ID + meta + lock */}
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2.5">
                                            {rig.driver_name && (
                                                <span className="text-[10px] font-mono text-white/35">{rig.rig_id}</span>
                                            )}
                                            {rig.status === 'racing' && (
                                                <span className="text-[10px] font-black text-white/50 flex items-center gap-0.5">
                                                    <Flag size={9} /> Lap {laps}
                                                </span>
                                            )}
                                            {rig.selected_car && (
                                                <span className="text-[9px] font-bold text-white/30 uppercase truncate max-w-28">
                                                    {rig.selected_car.split('_').slice(1, 3).join(' ')}
                                                </span>
                                            )}
                                        </div>

                                        {/* Lock/Unlock */}
                                        <button
                                            onClick={async () => {
                                                const newMode = (rig.mode || 'lockout') === 'lockout' ? 'freeuse' : 'lockout'
                                                await fetch(`/api/rigs/${rig.rig_id}/mode`, {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ mode: newMode })
                                                })
                                            }}
                                            className={`p-1.5 rounded-md transition-all ${
                                                (rig.mode || 'lockout') === 'lockout'
                                                    ? 'text-white/35 hover:text-amber-400 hover:bg-amber-500/10'
                                                    : 'text-green-400 hover:text-red-400 hover:bg-red-500/10 bg-green-500/10'
                                            }`}
                                            title={(rig.mode || 'lockout') === 'lockout' ? 'Unlock' : 'Lock'}
                                        >
                                            {(rig.mode || 'lockout') === 'lockout' ? <Lock size={14} /> : <Unlock size={14} />}
                                        </button>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </aside>
            )}

            {/* Toggle button when panel is hidden */}
            {!showRigPanel && (
                <button
                    onClick={() => setShowRigPanel(true)}
                    className="fixed top-1/2 right-0 -translate-y-1/2 z-50 bg-[#0a0a0a] border border-white/10 border-r-0 rounded-l-lg px-1.5 py-4 text-white/25 hover:text-white/60 transition-colors"
                    title="Show rig panel"
                >
                    <ChevronLeft size={14} />
                </button>
            )}
        </div>
    )
}

export default App
