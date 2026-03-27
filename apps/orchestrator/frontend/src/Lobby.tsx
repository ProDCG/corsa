import { useState, useEffect } from 'react'
import { Flag, Zap, Activity } from 'lucide-react'

interface LobbyData {
    top_10: Array<{
        rig_id: string
        driver_name?: string | null
        car: string | null
        track: string | null
        timestamp: number
        lap: number
        lap_time_ms?: number | null
    }>
    active_rigs: Array<{
        rig_id: string
        driver_name?: string | null
        status: string
        selected_car: string | null
        telemetry: {
            velocity?: [number, number, number]
            gear?: number
            completed_laps?: number
            normalized_pos?: number
        } | null
    }>
    total_rigs: number
    server_status: string
}

const formatCarName = (id: string) => id ? id.split('_').slice(1).join(' ').toUpperCase() : '—'
const formatTrack = (id: string) => id ? id.charAt(0).toUpperCase() + id.slice(1).replace(/_/g, ' ') : '—'

export default function Lobby() {
    const [data, setData] = useState<LobbyData | null>(null)

    useEffect(() => {
        const fetchLobby = async () => {
            try {
                const res = await fetch('/api/lobby')
                const json = await res.json()
                setData(json)
            } catch (err) {
                console.error('Lobby fetch failed:', err)
            }
        }
        fetchLobby()
        const interval = setInterval(fetchLobby, 1000)
        return () => clearInterval(interval)
    }, [])

    if (!data) {
        return (
            <div className="h-screen w-screen bg-black flex items-center justify-center">
                <div className="animate-pulse text-white/20 font-black italic uppercase text-4xl tracking-tighter">
                    Connecting...
                </div>
            </div>
        )
    }

    return (
        <div className="h-screen w-screen bg-[#050505] text-white overflow-hidden font-sans">
            {/* Header */}
            <div className="flex justify-between items-center px-16 py-8 border-b border-white/5">
                <div>
                    <h1 className="text-5xl font-black italic uppercase tracking-tighter leading-none">
                        <span className="text-ridge-brand">Ridge</span> Racing
                    </h1>
                    <p className="text-[11px] font-black uppercase tracking-[0.5em] text-white/40 mt-1">
                        Live Facility Leaderboard
                    </p>
                </div>
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${data.active_rigs.length > 0 ? 'bg-green-500 animate-pulse' : 'bg-white/20'}`} />
                        <span className="text-[11px] font-black uppercase tracking-widest text-white/50">
                            {data.active_rigs.length} Racing / {data.total_rigs} Online
                        </span>
                    </div>
                </div>
            </div>

            <div className="flex h-[calc(100vh-120px)]">
                {/* Leaderboard */}
                <div className="flex-1 p-12 overflow-y-auto">
                    <div className="space-y-3">
                        {data.top_10.length > 0 ? (
                            data.top_10.map((entry, idx) => (
                                <div
                                    key={idx}
                                    className={`flex items-center gap-8 p-6 rounded-2xl transition-all ${
                                        idx === 0
                                            ? 'bg-ridge-brand/10 border-2 border-ridge-brand/50 shadow-lg shadow-ridge-brand/10'
                                            : idx < 3
                                                ? 'bg-white/5 border border-white/10'
                                                : 'bg-white/[0.02] border border-white/5'
                                    }`}
                                >
                                    <div className={`text-4xl font-black italic w-16 text-center ${
                                        idx === 0 ? 'text-ridge-brand' : idx < 3 ? 'text-white/60' : 'text-white/25'
                                    }`}>
                                        {idx + 1}
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-3xl font-black italic uppercase tracking-tighter">
                                            {entry.driver_name || entry.rig_id}
                                        </p>
                                        <div className="flex items-center gap-3 mt-1">
                                            {entry.driver_name && (
                                                <span className="text-[10px] font-mono text-white/30">{entry.rig_id}</span>
                                            )}
                                            <span className="text-[10px] font-bold uppercase text-white/40 tracking-widest">
                                                {formatCarName(entry.car || '')}
                                            </span>
                                            {entry.track && (
                                                <span className="text-[10px] font-bold uppercase text-white/25 tracking-widest">
                                                    {formatTrack(entry.track)}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[9px] font-black uppercase text-ridge-brand tracking-widest mb-1">Laps</p>
                                        <p className="text-4xl font-black italic tabular-nums">{entry.lap}</p>
                                        {entry.lap_time_ms && (
                                            <p className="text-[10px] font-bold text-white/30 tabular-nums mt-1">
                                                {(entry.lap_time_ms / 1000).toFixed(3)}s
                                            </p>
                                        )}
                                    </div>
                                    <div className="text-right w-24">
                                        <p className="text-[9px] font-bold text-white/30 tabular-nums">
                                            {entry.timestamp ? new Date(entry.timestamp * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                                        </p>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="py-32 text-center">
                                <Flag size={64} className="mx-auto mb-6 text-white/5" />
                                <p className="text-2xl font-black italic uppercase opacity-10 tracking-tighter">
                                    No Race Results Yet
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Live Ticker */}
                <div className="w-96 border-l border-white/5 p-8 overflow-y-auto">
                    <h2 className="text-sm font-black italic uppercase tracking-tighter mb-6 flex items-center gap-2">
                        <Activity size={16} className="text-green-500" /> Live Now
                    </h2>
                    <div className="space-y-4">
                        {data.active_rigs.map(rig => (
                            <div key={rig.rig_id} className="bg-white/5 rounded-2xl p-4 border border-white/5">
                                <div className="flex justify-between items-center mb-3">
                                    <div>
                                        <span className="font-black italic uppercase text-sm">{rig.driver_name || rig.rig_id}</span>
                                        {rig.driver_name && (
                                            <span className="block text-[9px] font-mono text-white/25">{rig.rig_id}</span>
                                        )}
                                    </div>
                                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                                </div>
                                {rig.telemetry && (
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="bg-black/30 p-2 rounded-lg">
                                            <p className="text-[8px] font-black uppercase text-white/40">Speed</p>
                                            <p className="text-lg font-black italic tabular-nums">
                                                {Math.round(rig.telemetry.velocity?.[0] || 0)}
                                                <span className="text-[8px] text-ridge-brand ml-1">KM/H</span>
                                            </p>
                                        </div>
                                        <div className="bg-black/30 p-2 rounded-lg">
                                            <p className="text-[8px] font-black uppercase text-white/40">Gear</p>
                                            <p className="text-lg font-black italic">
                                                {rig.telemetry.gear === -1 ? 'R' : rig.telemetry.gear === 0 ? 'N' : rig.telemetry.gear}
                                            </p>
                                        </div>
                                    </div>
                                )}
                                {rig.selected_car && (
                                    <p className="text-[9px] font-bold uppercase text-white/30 tracking-widest mt-2">
                                        {rig.selected_car.split('_').slice(1).join(' ')}
                                    </p>
                                )}
                            </div>
                        ))}
                        {data.active_rigs.length === 0 && (
                            <div className="py-12 text-center opacity-20">
                                <Zap size={32} className="mx-auto mb-2" />
                                <p className="text-[11px] uppercase font-black tracking-widest">No Active Races</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
