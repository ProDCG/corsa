import { useState, useEffect } from 'react'
import { Activity, Cpu, Monitor, Zap, Power, RotateCcw, Play, Check } from 'lucide-react'
import Kiosk from './Kiosk'

interface Rig {
    rig_id: string
    ip: string
    status: 'idle' | 'racing' | 'offline' | 'setup' | 'ready'
    selected_car?: string | null
    cpu_temp: number
    mod_version: string
    last_seen: number
}

interface Branding {
    logo_url: string
    video_url: string
}

function App() {
    const isKiosk = window.location.pathname === '/kiosk'

    if (isKiosk) {
        return <Kiosk />
    }

    const [rigs, setRigs] = useState<Rig[]>([])
    const [selectedTrack, setSelectedTrack] = useState('monza')
    const [selectedCar, setSelectedCar] = useState('ks_ferrari_488_gt3')
    const [activeCarPool, setActiveCarPool] = useState<string[]>([])
    const [brandingFields, setBrandingFields] = useState<Branding>({
        logo_url: '/assets/ridge_logo.png',
        video_url: '/assets/idle_race.mp4'
    })

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

        fetchRigs()
        fetchCarPool()
        fetchBranding()
        const interval = setInterval(() => {
            fetchRigs()
        }, 2000)
        return () => clearInterval(interval)
    }, [])

    const toggleCarInPool = async (carId: string) => {
        const newPool = activeCarPool.includes(carId)
            ? activeCarPool.filter(id => id !== carId)
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
                    track: selectedTrack,
                    car: carToLaunch,
                    session_time: 20,
                    server_ip: "192.168.1.10"
                })
            })
        } catch (err) {
            console.error("Failed to send command:", err)
        }
    }

    const sendGlobalCommand = (action: string) => {
        rigs.forEach(rig => sendCommand(rig.rig_id, action, rig.selected_car))
    }

    return (
        <div className="min-h-screen p-8">
            {/* Header */}
            <header className="flex justify-between items-center mb-12">
                <div>
                    <h1 className="text-4xl font-black tracking-tighter uppercase italic flex items-center gap-2">
                        <span className="text-ridge-brand">Ridge</span>
                        <span>Link</span>
                    </h1>
                    <p className="text-white/40 font-mono text-sm">Facility Orchestration System v1.0</p>
                </div>

                <div className="flex gap-4">
                    <button
                        onClick={() => sendGlobalCommand('KILL_RACE')}
                        className="flex items-center gap-2 bg-zinc-800 hover:bg-zinc-700 px-6 py-2 rounded-full font-bold transition-all border border-white/10"
                    >
                        <RotateCcw size={18} /> Global Reset
                    </button>
                    <button
                        onClick={() => sendGlobalCommand('SETUP_MODE')}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-full font-bold transition-all shadow-lg shadow-blue-500/20"
                    >
                        <Monitor size={18} /> Prepare Rigs
                    </button>
                    <button
                        onClick={() => sendGlobalCommand('LAUNCH_RACE')}
                        className="flex items-center gap-2 bg-ridge-brand hover:bg-orange-600 px-6 py-2 rounded-full font-bold transition-all shadow-lg shadow-ridge-brand/20"
                    >
                        <Play size={18} /> Start All
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
                {/* Main Grid */}
                <div className="xl:col-span-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {rigs.map((rig) => (
                        <div key={rig.rig_id} className={`glass rounded-2xl p-6 transition-all duration-500 overflow-hidden relative ${rig.status === 'racing' ? 'status-glow-racing border-ridge-brand/50' :
                            rig.status === 'ready' ? 'status-glow-online border-green-500/50' :
                                rig.status === 'setup' ? 'status-glow-online border-blue-500/50' :
                                    'status-glow-online border-green-500/30'
                            }`}>
                            <div className="flex justify-between items-start mb-6">
                                <div>
                                    <h3 className="text-2xl font-black italic">{rig.rig_id}</h3>
                                    <code className="text-xs text-white/30">{rig.ip}</code>
                                </div>
                                <div className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest ${rig.status === 'racing' ? 'bg-ridge-brand text-white' :
                                    rig.status === 'ready' ? 'bg-green-500 text-black shadow-lg shadow-green-500/20' :
                                        rig.status === 'setup' ? 'bg-blue-500 text-white' :
                                            'bg-zinc-800 text-white'
                                    }`}>
                                    {rig.status}
                                </div>
                            </div>

                            <div className="space-y-4 mb-8">
                                <div className="flex items-center justify-between text-sm">
                                    <div className="flex items-center gap-2 text-white/60">
                                        <Cpu size={16} /> CPU Temp
                                    </div>
                                    <div className="font-mono font-bold">{rig.cpu_temp}°C</div>
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                    <div className="flex items-center gap-2 text-white/60">
                                        <Activity size={16} /> Mod Version
                                    </div>
                                    <div className="font-mono">{rig.mod_version}</div>
                                </div>
                                {rig.selected_car && (
                                    <div className={`flex items-center justify-between text-sm p-2 rounded-lg border ${rig.selected_car !== selectedCar ? 'bg-ridge-brand/10 border-ridge-brand/20' : 'bg-white/5 border-white/10'}`}>
                                        <div className={`flex items-center gap-2 font-bold uppercase text-[10px] ${rig.selected_car !== selectedCar ? 'text-ridge-brand' : 'text-white/60'}`}>
                                            <Zap size={14} /> Selected Car
                                        </div>
                                        <div className="font-bold text-white truncate max-w-[120px]">{rig.selected_car.split('_').slice(1).join(' ').toUpperCase()}</div>
                                    </div>
                                )}
                            </div>

                            <div className="grid grid-cols-2 gap-2 mt-auto">
                                <button
                                    onClick={() => sendCommand(rig.rig_id, 'LAUNCH_RACE', rig.selected_car)}
                                    className="bg-white/5 hover:bg-white/10 p-3 rounded-xl flex items-center justify-center transition-colors group"
                                >
                                    <Zap className="group-hover:text-ridge-brand transition-colors" size={20} />
                                </button>
                                <button
                                    onClick={() => sendCommand(rig.rig_id, 'KILL_RACE')}
                                    className="bg-white/5 hover:bg-white/10 p-3 rounded-xl flex items-center justify-center transition-colors group"
                                >
                                    <Power className="group-hover:text-ridge-brand transition-colors" size={20} />
                                </button>
                            </div>
                        </div>
                    ))}

                    {/* Placeholder for no rigs */}
                    {rigs.length === 0 && (
                        <div className="col-span-full py-24 flex flex-col items-center justify-center glass rounded-3xl opacity-50">
                            <Monitor size={64} className="mb-4 text-white/20 animate-pulse" />
                            <p className="text-xl font-bold italic tracking-tighter uppercase">Waiting for heartbeats...</p>
                            <p className="text-sm text-white/30 font-mono">Ensure Rig Sleds are broadcasting on UDP :5001</p>
                        </div>
                    )}
                </div>
                <aside className="space-y-8">
                    {/* Facility Branding Manager */}
                    <div className="glass rounded-2xl p-6 border border-white/10">
                        <div className="flex items-center gap-2 mb-6">
                            <Monitor className="text-ridge-brand" size={24} />
                            <h2 className="text-xl font-bold uppercase italic">Facility Branding</h2>
                        </div>
                        <div className="space-y-4 text-sm">
                            <div>
                                <label className="block text-white/40 mb-1 uppercase font-bold text-[10px]">Logo URL</label>
                                <input
                                    type="text"
                                    value={brandingFields.logo_url}
                                    onChange={(e) => setBrandingFields({ ...brandingFields, logo_url: e.target.value })}
                                    className="w-full bg-zinc-900 border border-white/10 rounded px-3 py-2 font-mono text-xs focus:ring-1 focus:ring-ridge-brand outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-white/40 mb-1 uppercase font-bold text-[10px]">Idle Video (MP4)</label>
                                <input
                                    type="text"
                                    value={brandingFields.video_url}
                                    onChange={(e) => setBrandingFields({ ...brandingFields, video_url: e.target.value })}
                                    className="w-full bg-zinc-900 border border-white/10 rounded px-3 py-2 font-mono text-xs focus:ring-1 focus:ring-ridge-brand outline-none"
                                />
                            </div>
                            <button
                                onClick={handleBrandingPush}
                                className="w-full bg-zinc-800 hover:bg-zinc-700 py-2 rounded font-bold transition-all text-xs uppercase tracking-widest"
                            >
                                Push Global Branding
                            </button>
                        </div>
                    </div>

                    {/* Car Pool Manager */}
                    <div className="glass rounded-2xl p-6 border border-white/10">
                        <h2 className="text-xl font-black uppercase italic mb-6 flex items-center gap-2">
                            <Monitor className="text-ridge-brand" size={20} />
                            Car Pool Manager
                        </h2>
                        <div className="space-y-3">
                            {ALL_CARS.map(car => (
                                <button
                                    key={car.id}
                                    onClick={() => toggleCarInPool(car.id)}
                                    className={`w-full text-left p-4 rounded-xl border transition-all flex justify-between items-center ${activeCarPool.includes(car.id)
                                        ? 'bg-ridge-brand/10 border-ridge-brand/50 text-white'
                                        : 'bg-white/5 border-white/10 text-white/40 grayscale shadow-inner'
                                        }`}
                                >
                                    <span className="font-bold italic uppercase text-xs">{car.name}</span>
                                    {activeCarPool.includes(car.id) && <Zap size={14} className="text-ridge-brand" />}
                                </button>
                            ))}
                        </div>
                        <div className="mt-8 p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl">
                            <p className="text-[10px] text-blue-400 font-bold uppercase mb-2">Facility Info</p>
                            <p className="text-xs text-blue-200/60 leading-relaxed">
                                Selected cars here will be mirrored in the **User Side Kiosk** for selection.
                            </p>
                        </div>
                    </div>
                </aside>
            </div>

            {/* Mission Packet Setup */}
            <footer className="fixed bottom-0 left-0 right-0 p-8 pt-24 bg-gradient-to-t from-ridge-dark to-transparent pointer-events-none">
                <div className="max-w-5xl mx-auto glass p-6 rounded-3xl border-white/5 pointer-events-auto flex items-center gap-8 shadow-2xl">
                    <div className="flex-1">
                        <label className="block text-[10px] uppercase tracking-widest font-black text-white/40 mb-2">Target Circuit</label>
                        <select
                            value={selectedTrack}
                            onChange={(e) => setSelectedTrack(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 outline-none focus:border-ridge-brand transition-colors appearance-none font-bold italic text-sm"
                        >
                            <option value="monza">Monza - Grand Prix</option>
                            <option value="spa">Spa-Francorchamps</option>
                            <option value="nordschleife">Nürburgring Nordschleife</option>
                        </select>
                    </div>
                    <div className="flex-1">
                        <label className="block text-[10px] uppercase tracking-widest font-black text-white/40 mb-2">Default Class</label>
                        <select
                            value={selectedCar}
                            onChange={(e) => setSelectedCar(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 outline-none focus:border-ridge-brand transition-colors appearance-none font-bold italic text-sm"
                        >
                            {ALL_CARS.filter(c => activeCarPool.includes(c.id)).map(car => (
                                <option key={car.id} value={car.id}>{car.name}</option>
                            ))}
                        </select>
                    </div>
                    <div className="w-px h-12 bg-white/10" />
                    <div className="flex flex-col items-end">
                        <p className="text-[10px] uppercase tracking-widest font-black text-white/40">Active Rigs</p>
                        <p className="text-3xl font-black italic">{rigs.length}</p>
                    </div>
                </div>
            </footer>
        </div>
    )
}

export default App
