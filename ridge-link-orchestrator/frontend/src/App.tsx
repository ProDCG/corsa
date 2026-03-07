import { Activity, Cpu, Monitor, Zap, Power, RotateCcw, Play, Check, Image, Car, Settings2, Flag, Clock, ShieldCheck, LayoutGrid } from 'lucide-react'
import Kiosk from './Kiosk'

interface Rig {
    rig_id: string
    ip: string
    status: 'idle' | 'racing' | 'offline' | 'setup' | 'ready'
    selected_car?: string | null
    cpu_temp: number
    mod_version: string
    last_seen: number
    telemetry?: {
        velocity: [number, number, number]
        gforce: [number, number, number]
        normalized_pos: number
        completed_laps: number
        gas: number
        brake: number
        gear: number
    }
}

interface Branding {
    logo_url: string
    video_url: string
}

import { useState, useEffect } from 'react'

function App() {
    const isKiosk = window.location.pathname === '/kiosk'

    if (isKiosk) {
        return <Kiosk />
    }

    const [activeTab, setActiveTab] = useState<'sims' | 'media' | 'cars' | 'race' | 'monitor' | 'leaderboard'>('sims')
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
        useMultiplayer: false
    })
    const [serverStatus, setServerStatus] = useState<'online' | 'offline'>('offline')
    const [selectedCar, setSelectedCar] = useState('ks_ferrari_488_gt3')
    const [activeCarPool, setActiveCarPool] = useState<string[]>([])
    const [brandingFields, setBrandingFields] = useState<Branding>({
        logo_url: '/assets/ridge_logo.png',
        video_url: '/assets/idle_race.mp4'
    })
    const [leaderboard, setLeaderboard] = useState<any[]>([])
    const [presets, setPresets] = useState<any[]>([])
    const [activeTelemFields, setActiveTelemFields] = useState<string[]>(['velocity', 'gforce', 'normalized_pos', 'gear', 'completed_laps', 'gas'])

    const TELEM_FIELDS = [
        { id: 'velocity', name: 'Velocity (KM/H)', icon: Zap },
        { id: 'gforce', name: 'G-Force', icon: Activity },
        { id: 'normalized_pos', name: 'Circuit Progress', icon: LayoutGrid },
        { id: 'gear', name: 'Gear', icon: Settings2 },
        { id: 'completed_laps', name: 'Lap Count', icon: Flag },
        { id: 'gas', name: 'Throttle Input', icon: Power },
        { id: 'brake', name: 'Brake Input', icon: ShieldCheck },
        { id: 'rpms', name: 'Engine RPM', icon: Activity },
        { id: 'status', name: 'Engine Status', icon: Monitor },
    ]

    const ALL_CARS = [
        { id: 'ks_ferrari_488_gt3', name: 'Ferrari 488 GT3' },
        { id: 'ks_lamborghini_huracan_gt3', name: 'Lambo Huracán GT3' },
        { id: 'ks_porsche_911_gt3_r', name: 'Porsche 911 GT3 R' },
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
                    setRigs(data)
                }

                const sRes = await fetch('/api/server/status')
                const sData = await sRes.json()
                setServerStatus(sData.status)

                const lRes = await fetch('/api/leaderboard')
                const lData = await lRes.json()
                setLeaderboard(lData)
            } catch (err) {
                console.error("Failed to fetch rigs:", err)
            }
        }

        const fetchCarPool = async () => {
            try {
                const res = await fetch('/api/carpool')
                const data = await res.json()
                if (Array.isArray(data)) {
                    setActiveCarPool(data)
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

        fetchRigs()
        fetchCarPool()
        fetchBranding()
        fetchPresets()
        fetchTelemConfig()
        const interval = setInterval(() => {
            fetchRigs()
        }, 500)
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


    const SidebarItem = ({ id, icon: Icon, label }: { id: typeof activeTab, icon: any, label: string }) => (
        <button
            onClick={() => setActiveTab(id)}
            className={`w-full flex flex-col items-center gap-2 p-4 transition-all ${activeTab === id ? 'text-ridge-brand bg-white/5 border-r-2 border-ridge-brand' : 'text-white/40 hover:text-white/60 hover:bg-white/5 border-r-2 border-transparent'}`}
        >
            <Icon size={24} />
            <span className="text-[10px] font-black uppercase tracking-widest">{label}</span>
        </button>
    )

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
                    <SidebarItem id="sims" icon={LayoutGrid} label="Sims" />
                    <SidebarItem id="monitor" icon={Activity} label="Live Monitor" />
                    <SidebarItem id="leaderboard" icon={Flag} label="Standings" />
                    <SidebarItem id="cars" icon={Car} label="Cars" />
                    <SidebarItem id="race" icon={Settings2} label="Race Control" />
                    <SidebarItem id="media" icon={Image} label="Media" />
                </div>

                <div className="mt-auto">
                    <button onClick={() => sendGlobalCommand('KILL_RACE')} className="p-4 text-red-500 hover:bg-red-500/10 rounded-full transition-all">
                        <Power size={24} />
                    </button>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 overflow-y-auto relative">
                <header className="sticky top-0 z-40 bg-ridge-dark/80 backdrop-blur-xl p-8 flex justify-between items-center border-b border-white/5">
                    <div>
                        <h1 className="text-3xl font-black italic tracking-tighter uppercase flex items-center gap-2">
                            <span className="text-ridge-brand">Ridge</span>
                            <span>{
                                activeTab === 'sims' ? 'Sim Manager' :
                                    activeTab === 'media' ? 'Media Center' :
                                        activeTab === 'cars' ? 'Car Pool' :
                                            activeTab === 'monitor' ? 'Telemetry Feed' :
                                                activeTab === 'leaderboard' ? 'Facility Standings' :
                                                    'Race Control'
                            }</span>
                        </h1>
                        <p className="text-white/30 font-mono text-[10px] uppercase tracking-widest leading-none mt-1">
                            {rigs.length} Units Online // {raceSettings.selected_track.toUpperCase()} // ENV {raceSettings.selected_weather.split('_').slice(1).join(' ')}
                        </p>
                    </div>

                    <div className="flex gap-4">
                        <button onClick={() => sendGlobalCommand('SETUP_MODE')} className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-full font-black italic uppercase text-xs flex items-center gap-2 transition-all shadow-lg shadow-blue-500/20">
                            <Monitor size={16} /> Prepare Grid
                        </button>
                        <button onClick={() => sendGlobalCommand('LAUNCH_RACE')} className="bg-ridge-brand hover:bg-orange-600 px-8 py-2 rounded-full font-black italic uppercase text-xs flex items-center gap-2 transition-all shadow-lg shadow-ridge-brand/40">
                            <Play size={16} /> Start Session
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

                                    <div className="grid grid-cols-2 gap-2">
                                        <button onClick={() => sendCommand(rig.rig_id, 'LAUNCH_RACE', rig.selected_car)} className="bg-white/5 hover:bg-ridge-brand/20 hover:text-ridge-brand p-3 rounded-xl flex items-center justify-center transition-all border border-transparent hover:border-ridge-brand/30">
                                            <Zap size={20} />
                                        </button>
                                        <button onClick={() => sendCommand(rig.rig_id, 'KILL_RACE')} className="bg-white/5 hover:bg-red-500/20 hover:text-red-500 p-3 rounded-xl flex items-center justify-center transition-all border border-transparent hover:border-red-500/30">
                                            <Power size={20} />
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

                    {/* RACE MANAGER VIEW */}
                    {activeTab === 'race' && (
                        <div className="max-w-4xl space-y-8">
                            <div className="bg-white/5 border border-white/10 rounded-3xl p-8 mb-8">
                                <div className="flex items-center justify-between mb-8">
                                    <div>
                                        <h2 className="text-2xl font-black italic uppercase tracking-tighter">Event Orchestration</h2>
                                        <p className="text-[10px] font-black uppercase tracking-[0.3em] text-white/30">Master Control</p>
                                    </div>
                                    <div className="flex gap-4">
                                        <button
                                            onClick={() => setRaceSettings({ ...raceSettings, useMultiplayer: !raceSettings.useMultiplayer })}
                                            className={`px-6 py-2 rounded-full border-2 text-[10px] font-black uppercase tracking-widest transition-all ${raceSettings.useMultiplayer
                                                ? 'bg-ridge-brand/20 border-ridge-brand text-ridge-brand'
                                                : 'bg-white/5 border-white/10 text-white/30'
                                                }`}
                                        >
                                            {raceSettings.useMultiplayer ? 'MULTIPLAYER ON' : 'LOCAL RACES ONLY'}
                                        </button>
                                        <button
                                            onClick={() => sendGlobalCommand('LAUNCH_RACE')}
                                            className="bg-ridge-brand hover:bg-orange-600 px-8 py-3 rounded-full flex items-center gap-3 transition-all group scale-110 shadow-2xl shadow-ridge-brand/20"
                                        >
                                            <Play className="w-5 h-5 fill-white group-hover:scale-110 transition-transform" />
                                            <span className="font-black italic uppercase tracking-tighter text-sm">Deploy Session</span>
                                        </button>
                                    </div>
                                </div>

                                <div className="grid grid-cols-4 gap-4">
                                    <div className={`p-4 rounded-2xl border transition-all ${serverStatus === 'online' ? 'bg-green-500/10 border-green-500/50' : 'bg-white/5 border-white/5'}`}>
                                        <p className="text-[8px] font-black uppercase opacity-40 mb-1">Server Status</p>
                                        <p className={`font-black uppercase tracking-widest ${serverStatus === 'online' ? 'text-green-500' : 'text-zinc-600'}`}>{serverStatus}</p>
                                    </div>
                                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                                        <p className="text-[8px] font-black uppercase opacity-40 mb-1">Circuit</p>
                                        <p className="font-black uppercase tracking-widest text-ridge-brand">{raceSettings.selected_track}</p>
                                    </div>
                                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                                        <p className="text-[8px] font-black uppercase opacity-40 mb-1">DRS System</p>
                                        <p className={`font-black uppercase tracking-widest ${raceSettings.allow_drs ? 'text-green-500' : 'text-red-500'}`}>{raceSettings.allow_drs ? 'ACTIVE' : 'RESTR'}</p>
                                    </div>
                                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                                        <p className="text-[8px] font-black uppercase opacity-40 mb-1">Cars Prepared</p>
                                        <p className="font-black uppercase tracking-widest">{rigs.filter(r => r.status === 'ready').length} / {rigs.length}</p>
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="glass rounded-3xl p-8 border border-white/10">
                                    <h2 className="text-xl font-black italic uppercase mb-6 flex items-center gap-2"><Flag className="text-ridge-brand" size={20} /> Circuit & Atmosphere</h2>
                                    <div className="space-y-6">
                                        <div>
                                            <label className="block text-[10px] uppercase font-black text-white/40 mb-2">Target Circuit</label>
                                            <select
                                                value={raceSettings.selected_track}
                                                onChange={(e) => setRaceSettings({ ...raceSettings, selected_track: e.target.value })}
                                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 outline-none focus:border-ridge-brand transition-all font-bold italic appearance-none"
                                            >
                                                <option value="monza">Monza - Grand Prix</option>
                                                <option value="spa">Spa-Francorchamps</option>
                                                <option value="nordschleife">Nürburgring Nordschleife</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-[10px] uppercase font-black text-white/40 mb-2">Environment / Weather</label>
                                            <select
                                                value={raceSettings.selected_weather}
                                                onChange={(e) => setRaceSettings({ ...raceSettings, selected_weather: e.target.value })}
                                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 outline-none focus:border-ridge-brand transition-all font-bold italic appearance-none"
                                            >
                                                <option value="0_sun">01 - Clear Sun</option>
                                                <option value="1_nosun">02 - No Sun</option>
                                                <option value="2_clouds">03 - Overcast</option>
                                                <option value="3_clear">04 - Optimum (Clear)</option>
                                                <option value="4_mid_clouds">05 - Mid Clouds</option>
                                                <option value="5_light_clouds">06 - Light Clouds</option>
                                                <option value="6_heavy_clouds">07 - Heavy Clouds</option>
                                            </select>
                                        </div>
                                        <div className="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/10">
                                            <div>
                                                <p className="font-black italic uppercase text-sm">DRS System Availability</p>
                                                <p className="text-[10px] text-white/40 uppercase tracking-widest font-bold">Global Regulation Flag</p>
                                            </div>
                                            <button
                                                onClick={() => setRaceSettings({ ...raceSettings, allow_drs: !raceSettings.allow_drs })}
                                                className={`w-14 h-8 rounded-full relative transition-all ${raceSettings.allow_drs ? 'bg-ridge-brand' : 'bg-zinc-800'}`}
                                            >
                                                <div className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-all ${raceSettings.allow_drs ? 'left-7' : 'left-1'}`} />
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <div className="glass rounded-3xl p-8 border border-white/10">
                                    <h2 className="text-xl font-black italic uppercase mb-6 flex items-center gap-2"><Clock className="text-ridge-brand" size={20} /> Session Timing</h2>
                                    <div className="space-y-6">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-[10px] uppercase font-black text-white/40 mb-2">Practice (Min)</label>
                                                <input
                                                    type="number"
                                                    value={raceSettings.practice_time}
                                                    onChange={(e) => setRaceSettings({ ...raceSettings, practice_time: parseInt(e.target.value) })}
                                                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 outline-none focus:border-ridge-brand transition-all font-bold font-mono"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-[10px] uppercase font-black text-white/40 mb-2">Qualifying (Min)</label>
                                                <input
                                                    type="number"
                                                    value={raceSettings.qualy_time}
                                                    onChange={(e) => setRaceSettings({ ...raceSettings, qualy_time: parseInt(e.target.value) })}
                                                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 outline-none focus:border-ridge-brand transition-all font-bold font-mono"
                                                />
                                            </div>
                                        </div>
                                        <div>
                                            <label className="block text-[10px] uppercase font-black text-white/40 mb-2">Race Length (Laps)</label>
                                            <input
                                                type="number"
                                                value={raceSettings.race_laps}
                                                onChange={(e) => setRaceSettings({ ...raceSettings, race_laps: parseInt(e.target.value) })}
                                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 outline-none focus:border-ridge-brand transition-all font-bold font-mono text-xl"
                                            />
                                        </div>
                                        <div className="bg-ridge-brand/10 border border-ridge-brand/30 p-4 rounded-2xl flex items-start gap-4">
                                            <div className="p-2 bg-ridge-brand rounded-lg"><Flag size={16} /></div>
                                            <div>
                                                <p className="text-[10px] font-black uppercase tracking-widest text-ridge-brand mb-1">Session Summary</p>
                                                <p className="text-xs text-white/70 leading-relaxed font-medium capitalize">
                                                    Race will run {raceSettings.practice_time > 0 ? `${raceSettings.practice_time}m Practice, ` : ''}{raceSettings.qualy_time > 0 ? `${raceSettings.qualy_time}m Qualy, ` : ''}followed by a {raceSettings.race_laps} Lap Grand Prix.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* PRESETS SECTION */}
                            <div className="bg-white/5 border border-white/10 rounded-3xl p-8">
                                <div className="flex justify-between items-center mb-6">
                                    <h2 className="text-xl font-black italic uppercase flex items-center gap-2">
                                        <ShieldCheck className="text-ridge-brand" size={24} /> Configuration Presets
                                    </h2>
                                    <button
                                        onClick={() => {
                                            const name = prompt("Enter a name for this preset:");
                                            if (name) saveCurrentAsPreset(name);
                                        }}
                                        className="bg-white/10 hover:bg-white/20 px-6 py-2 rounded-full text-[10px] font-black uppercase tracking-widest transition-all"
                                    >
                                        Save Current as Preset
                                    </button>
                                </div>
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
                                                <p>{preset.race_laps} Laps | {preset.qualy_time}m Qualy | DRS: {preset.allow_drs ? 'ON' : 'OFF'}</p>
                                            </div>
                                        </div>
                                    ))}
                                    {presets.length === 0 && (
                                        <div className="col-span-full py-8 text-center text-white/10 italic text-[10px] uppercase font-black tracking-widest px-4 border border-dashed border-white/5 rounded-2xl">
                                            No saved presets found. Configure a setup above and click "Save Current"
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* CAR POOL VIEW */}
                    {activeTab === 'cars' && (
                        <div className="max-w-5xl">
                            <div className="flex items-center justify-between mb-8">
                                <div>
                                    <h2 className="text-xl font-black italic uppercase">Fleet Authorization</h2>
                                    <p className="text-xs text-white/40 uppercase tracking-widest font-bold">Manage available vehicle classes for customer selection</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-xs font-black uppercase text-white/40">Authorized</p>
                                    <p className="text-2xl font-black italic text-ridge-brand">{activeCarPool.length} / {ALL_CARS.length}</p>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                {ALL_CARS.map((car: { id: string; name: string }) => (
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
                                        <span className={`font-black italic uppercase text-xs tracking-tighter ${activeCarPool.includes(car.id) ? 'text-white' : 'group-hover:text-white/40 transition-colors'}`}>{car.name}</span>
                                        {activeCarPool.includes(car.id) && <div className="absolute -right-2 -bottom-2 w-12 h-12 bg-ridge-brand/20 blur-xl rounded-full" />}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* LIVE MONITOR VIEW */}
                    {activeTab === 'monitor' && (
                        <div className="space-y-6">
                            {/* Telemetry Master Checklist */}
                            <div className="glass rounded-3xl p-6 border border-white/10 mb-8">
                                <h3 className="text-sm font-black italic uppercase italic tracking-tighter mb-4 flex items-center gap-2">
                                    <Monitor size={16} className="text-ridge-brand" /> Telemetry Data Master Selection
                                </h3>
                                <div className="flex flex-wrap gap-2">
                                    {TELEM_FIELDS.map(field => (
                                        <button
                                            key={field.id}
                                            onClick={() => toggleTelemField(field.id)}
                                            className={`px-4 py-2 rounded-xl border text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-2 ${activeTelemFields.includes(field.id)
                                                ? 'bg-ridge-brand/10 border-ridge-brand text-ridge-brand'
                                                : 'bg-white/5 border-white/10 text-white/30 hover:border-white/20'
                                                }`}
                                        >
                                            <field.icon size={12} />
                                            {field.name}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                                {rigs.map((rig: Rig) => (
                                    <div key={rig.rig_id} className="bg-white/5 border border-white/10 rounded-3xl p-6 relative overflow-hidden group">
                                        <div className="flex justify-between items-start mb-6">
                                            <div>
                                                <h3 className="text-xl font-black italic uppercase italic tracking-tighter">{rig.rig_id}</h3>
                                                <p className="text-[8px] font-black uppercase text-white/30 tracking-widest leading-none mt-1">Status // {rig.status}</p>
                                            </div>
                                            <div className={`px-3 py-1 rounded-full text-[8px] font-bold uppercase tracking-widest ${rig.status === 'racing' ? 'bg-green-500 text-white' : 'bg-white/10 text-white/40'}`}>
                                                {rig.status === 'racing' ? 'Live Telemetry' : 'Standby'}
                                            </div>
                                        </div>

                                        {rig.telemetry ? (
                                            <div className="space-y-6">
                                                {/* DYNAMIC FIELDS GRID */}
                                                <div className="grid grid-cols-2 gap-4">
                                                    {activeTelemFields.includes('velocity') && (
                                                        <div className="bg-black/20 p-4 rounded-2xl border border-white/5">
                                                            <p className="text-[8px] font-black uppercase opacity-40 mb-1">Velocity</p>
                                                            <div className="flex items-baseline gap-2">
                                                                <span className="text-2xl font-black italic tabular-nums">{rig.telemetry.velocity[0]}</span>
                                                                <span className="text-[10px] font-bold text-ridge-brand">KM/H</span>
                                                            </div>
                                                        </div>
                                                    )}
                                                    {activeTelemFields.includes('gforce') && (
                                                        <div className="bg-black/20 p-4 rounded-2xl border border-white/5">
                                                            <p className="text-[8px] font-black uppercase opacity-40 mb-1">Force (G-Lat)</p>
                                                            <div className="flex items-baseline gap-2">
                                                                <span className="text-2xl font-black italic tabular-nums">{rig.telemetry.gforce[0]}</span>
                                                                <span className="text-[10px] font-bold text-blue-400">G</span>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>

                                                {activeTelemFields.includes('normalized_pos') && (
                                                    <div className="space-y-2">
                                                        <div className="flex justify-between text-[8px] font-black uppercase tracking-widest mb-1">
                                                            <span>Circuit Progress</span>
                                                            <span>{Math.round(rig.telemetry.normalized_pos * 100)}%</span>
                                                        </div>
                                                        <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full bg-ridge-brand transition-all duration-300"
                                                                style={{ width: `${rig.telemetry.normalized_pos * 100}%` }}
                                                            />
                                                        </div>
                                                    </div>
                                                )}

                                                <div className="grid grid-cols-3 gap-2">
                                                    {activeTelemFields.includes('gear') && (
                                                        <div className="flex flex-col items-center justify-center p-3 rounded-2xl bg-white/5 border border-white/5">
                                                            <span className="text-[8px] font-black uppercase opacity-30 mb-1">Gear</span>
                                                            <span className="text-xl font-black italic">
                                                                {rig.telemetry.gear === -1 ? 'R' : rig.telemetry.gear === 0 ? 'N' : rig.telemetry.gear}
                                                            </span>
                                                        </div>
                                                    )}
                                                    {activeTelemFields.includes('completed_laps') && (
                                                        <div className="flex flex-col items-center justify-center p-3 rounded-2xl bg-white/5 border border-white/5">
                                                            <span className="text-[8px] font-black uppercase opacity-30 mb-1">Laps</span>
                                                            <span className="text-xl font-black italic">{rig.telemetry.completed_laps}</span>
                                                        </div>
                                                    )}
                                                    {activeTelemFields.includes('gas') && (
                                                        <div className="flex flex-col items-center justify-center p-3 rounded-2xl bg-white/5 border border-white/5">
                                                            <span className="text-[8px] font-black uppercase opacity-30 mb-1">Throttle</span>
                                                            <span className="text-xl font-black italic text-green-500">{Math.round(rig.telemetry.gas * 100)}%</span>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Additional logic if others fields are added later */}
                                                <div className="grid grid-cols-2 gap-2 mt-2">
                                                    {activeTelemFields.includes('brake') && (
                                                        <div className="flex flex-col items-center justify-center p-3 rounded-2xl bg-white/5 border border-white/5">
                                                            <span className="text-[8px] font-black uppercase opacity-30 mb-1">Brake</span>
                                                            <span className="text-xl font-black italic text-red-500">{Math.round(rig.telemetry.brake * 100)}%</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="py-12 text-center opacity-20">
                                                <Activity size={32} className="mx-auto mb-2" />
                                                <p className="text-[10px] uppercase font-black tracking-widest">Waiting for Engine Signal</p>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* LEADERBOARD VIEW */}
                    {activeTab === 'leaderboard' && (
                        <div className="glass rounded-[3rem] p-12 lg:p-16 border border-white/10 relative overflow-hidden max-w-5xl">
                            <div className="flex justify-between items-start mb-12">
                                <div>
                                    <h2 className="text-4xl font-black italic uppercase tracking-tighter mb-2">Hall of Fame</h2>
                                    <p className="text-sm text-white/40 uppercase tracking-[0.4em] font-bold">Fastest Laps // All Time</p>
                                </div>
                                <div className="p-4 bg-ridge-brand rounded-2xl rotate-3 shadow-2xl shadow-ridge-brand/40">
                                    <Flag size={32} />
                                </div>
                            </div>

                            <div className="space-y-4">
                                {leaderboard.length > 0 ? (
                                    leaderboard.sort((a: any, b: any) => b.lap - a.lap).slice(0, 10).map((entry: any, idx: number) => (
                                        <div key={idx} className="bg-white/5 hover:bg-white/10 p-6 rounded-2xl flex items-center gap-8 transition-all border border-white/5 group">
                                            <div className="text-3xl font-black italic opacity-20 group-hover:opacity-100 group-hover:text-ridge-brand transition-all">#{idx + 1}</div>
                                            <div className="flex-1">
                                                <p className="text-2xl font-black italic uppercase tracking-tighter">{entry.rig_id}</p>
                                                <p className="text-[10px] font-bold uppercase text-white/30 tracking-widest">{entry.car?.split('_').slice(1).join(' ').toUpperCase()}</p>
                                            </div>
                                            <div className="text-right">
                                                <p className="text-[10px] font-black uppercase text-ridge-brand mb-1">Lap Completion</p>
                                                <p className="text-3xl font-black italic tabular-nums italic">LAP {entry.lap}</p>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div className="py-32 text-center">
                                        <p className="text-xl font-black italic uppercase opacity-20 tracking-tighter">No Race Results Recorded Yet</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* MEDIA VIEW */}
                    {activeTab === 'media' && (
                        <div className="max-w-2xl space-y-6">
                            <div className="glass rounded-3xl p-8 border border-white/10">
                                <h2 className="text-xl font-black italic uppercase mb-6 flex items-center gap-2"><Image className="text-ridge-brand" size={24} /> Brand Identity</h2>
                                <div className="space-y-6">
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
                                        className="w-full bg-ridge-brand hover:bg-orange-600 py-4 rounded-xl font-black tracking-tighter italic uppercase text-sm transition-all shadow-lg shadow-ridge-brand/20"
                                    >
                                        Deploy Branding to Network
                                    </button>
                                </div>
                            </div>

                            <div className="p-6 border border-zinc-800 rounded-3xl opacity-50">
                                <p className="text-[10px] font-black uppercase text-white/30 mb-2">Preview</p>
                                <div className="aspect-video bg-zinc-900 rounded-2xl flex items-center justify-center border border-white/5">
                                    <Monitor size={32} className="text-white/5" />
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Sub-Footer Contextual Label */}
                <div className="fixed bottom-8 right-8 z-50 pointer-events-none">
                    <div className="glass px-6 py-2 rounded-full border border-white/10 shadow-2xl flex items-center gap-4">
                        <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                            <span className="text-[9px] font-black uppercase tracking-widest">Orchestrator Stable</span>
                        </div>
                        <div className="w-px h-4 bg-white/10" />
                        <span className="text-[9px] font-black font-mono text-ridge-brand uppercase italic tracking-widest">Target: {raceSettings.selected_track.toUpperCase()}</span>
                    </div>
                </div>
            </main>
        </div>
    )
}

export default App
