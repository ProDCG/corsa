import React, { useState, useEffect, useRef } from 'react'
import { Zap, Check, Shield } from 'lucide-react'

interface Branding {
    logo_url: string
    video_url: string
}

interface Rig {
    rig_id: string
    ip: string
    status: string
    selected_car?: string | null
    cpu_temp: number
    mod_version: string
}

export default function Kiosk() {
    const [status, setStatus] = useState('idle') // idle, setup, ready, racing
    const [rigId, setRigId] = useState('UNKNOWN')
    const [ready, setReady] = useState(false)
    const [selectedCar, setSelectedCar] = useState<string | null>(null)
    const [carPool, setCarPool] = useState<string[]>([])
    const [branding, setBranding] = useState<Branding>({
        logo_url: '/assets/ridge_logo.png',
        video_url: '/assets/idle_race.mp4'
    })

    const ALL_CARS = [
        { id: 'ks_ferrari_488_gt3', name: 'Ferrari 488 GT3', class: 'GT3' },
        { id: 'ks_lamborghini_huracan_gt3', name: 'Lamborghini Huracan GT3', class: 'GT3' },
        { id: 'ks_porsche_911_gt3_r', name: 'Porsche 911 GT3 R', class: 'GT3' },
        { id: 'ks_mclaren_650s_gt3', name: 'McLaren 650S GT3', class: 'GT3' },
        { id: 'ks_audi_r8_lms', name: 'Audi R8 LMS', class: 'GT3' },
        { id: 'ks_mercedes_amg_gt3', name: 'Mercedes AMG GT3', class: 'GT3' },
        { id: 'ks_bmw_m6_gt3', name: 'BMW M6 GT3', class: 'GT3' },
        { id: 'ks_nissan_gt_r_gt3', name: 'Nissan GT-R GT3', class: 'GT3' },
        { id: 'ks_corvette_c7_r', name: 'Corvette C7.R', class: 'GTE' },
        { id: 'ks_ferrari_488_gte', name: 'Ferrari 488 GTE', class: 'GTE' },
        { id: 'tatuusfa1', name: 'Tatuus FA.01', class: 'OPEN' },
        { id: 'ks_lotus_exos_125', name: 'Lotus Exos 125', class: 'F1' }
    ]

    useEffect(() => {
        const params = new URLSearchParams(window.location.search)
        const id = params.get('rig_id') || 'UNKNOWN'
        setRigId(id)

        const registerKiosk = async () => {
            try {
                await fetch(`/api/rigs/${id}/status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'idle' })
                })
            } catch (err) { console.error("Initial registration failed", err) }
        }

        const fetchData = async () => {
            try {
                const brandRes = await fetch('/api/branding')
                const brandData = await brandRes.json()
                setBranding(brandData)

                const rigRes = await fetch('/api/rigs')
                const rigs = await rigRes.json()
                if (Array.isArray(rigs)) {
                    const myRig = rigs.find((r: Rig) => r.rig_id === id)
                    if (myRig) {
                        setStatus(myRig.status)
                        if (myRig.status === 'idle') {
                            setReady(false)
                        }
                    }
                }

                const poolRes = await fetch('/api/carpool')
                const poolData = await poolRes.json()
                if (Array.isArray(poolData)) {
                    setCarPool(poolData)
                }
            } catch (err) {
                console.error("Kiosk sync failed:", err)
            }
        }

        registerKiosk().then(fetchData)
        const interval = setInterval(fetchData, 2000)
        return () => clearInterval(interval)
    }, [])

    const syncKioskState = async (newStatus: string, newCar?: string) => {
        try {
            await fetch(`/api/rigs/${rigId}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    status: newStatus,
                    selected_car: newCar || selectedCar
                })
            })
        } catch (err) {
            console.error("Failed to sync kiosk state:", err)
        }
    }

    const toggleReady = () => {
        const newReady = !ready
        setReady(newReady)
        const newStatus = newReady ? 'ready' : 'setup'
        setStatus(newStatus)
        syncKioskState(newStatus)
    }

    const handleCarSelect = (carId: string) => {
        setSelectedCar(carId)
        syncKioskState(status, carId)
    }

    const videoRef = useRef<HTMLVideoElement>(null)

    useEffect(() => {
        const attemptPlay = () => {
            if (videoRef.current) {
                videoRef.current.play().catch(() => {
                    console.log("Autoplay blocked, waiting for interaction")
                })
            }
        }
        attemptPlay()
        window.addEventListener('click', attemptPlay, { once: true })
        return () => window.removeEventListener('click', attemptPlay)
    }, [branding.video_url])

    const videoSrc = branding.video_url || "/assets/idle_race.mp4"
    const finalVideoSrc = videoSrc.startsWith('/') ? videoSrc : `/${videoSrc}`

    return (
        <div className="relative h-screen w-screen bg-black overflow-hidden font-sans text-white">
            <style>
                {`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: rgba(255, 81, 0, 0.3);
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: rgba(255, 81, 0, 0.6);
                }
                `}
            </style>
            {/* Background Video */}
            <video
                ref={videoRef}
                autoPlay
                loop
                muted
                playsInline
                key={branding.video_url}
                poster="/assets/idle_race_temp.jpg"
                className={`absolute inset-0 w-full h-full object-cover transition-all duration-1000 ${status === 'setup' || status === 'ready' ? 'blur-2xl scale-110 opacity-50' : 'opacity-80'}`}
            >
                <source src={finalVideoSrc} type="video/mp4" />
            </video>

            {/* Logo Overlay */}
            <div className="absolute bottom-12 right-12 z-50 pointer-events-none">
                <div className="flex items-center gap-4 glass p-6 rounded-3xl border border-white/10 shadow-2xl transition-all duration-1000">
                    <img
                        src={branding.logo_url || "/assets/ridge_logo.png"}
                        alt="Facility Logo"
                        className="h-24 w-auto object-contain drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]"
                        onError={(e) => {
                            (e.target as HTMLImageElement).src = "/assets/ridge_logo.png";
                        }}
                    />
                </div>
            </div>

            {/* Setup Overlay */}
            {(status === 'setup' || status === 'ready') && (
                <div className="absolute inset-0 flex items-center justify-center z-40 bg-black/40 backdrop-blur-sm animate-in fade-in zoom-in duration-500">
                    <div className="max-w-4xl w-full mx-8">
                        <div className="text-center mb-12">
                            <h1 className="text-6xl font-black uppercase tracking-tighter italic mb-2">Prepare for Mission</h1>
                            <p className="text-ridge-brand font-bold tracking-[0.3em] uppercase text-sm">Select Your Vehicle</p>
                        </div>

                        <div className="max-h-[50vh] overflow-y-auto overflow-x-hidden p-2 mb-12 custom-scrollbar">
                            <div className="grid grid-cols-3 gap-6">
                                {carPool.map(carId => {
                                    const carInfo = ALL_CARS.find(c => c.id === carId) || { id: carId, name: carId.split('_').slice(1).join(' ').toUpperCase() || carId, class: 'CAR' };
                                    return (
                                        <button
                                            key={carId}
                                            onClick={() => handleCarSelect(carId)}
                                            className={`p-6 rounded-3xl border-2 transition-all duration-500 text-left relative overflow-hidden group ${selectedCar === carId
                                                ? 'bg-ridge-brand border-ridge-brand shadow-[0_0_30px_rgba(255,81,0,0.4)]'
                                                : 'bg-white/5 border-white/5 hover:border-white/20'
                                                }`}
                                        >
                                            <div className="relative z-10">
                                                <p className="text-[10px] font-bold opacity-50 uppercase mb-1">{carInfo.class}</p>
                                                <h3 className="text-xl font-bold uppercase italic leading-tight">{carInfo.name}</h3>
                                            </div>
                                            <Shield className={`absolute -right-4 -bottom-4 w-24 h-24 transition-all duration-700 ${selectedCar === carId ? 'text-white/20 scale-110 rotate-12' : 'text-white/5 rotate-45'}`} />
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="flex justify-center">
                            <button
                                onClick={toggleReady}
                                className={`group relative px-16 py-6 rounded-full font-black uppercase tracking-[0.2em] transition-all duration-500 overflow-hidden ${ready
                                    ? 'bg-green-500 shadow-[0_0_50px_rgba(34,197,94,0.4)]'
                                    : 'bg-white text-black hover:scale-105 active:scale-95'
                                    }`}
                            >
                                <span className={`relative z-10 flex items-center gap-3 ${ready ? 'text-white' : ''}`}>
                                    {ready ? <Check className="w-6 h-6" /> : <Zap className="w-6 h-6" />}
                                    {ready ? 'Ready for Launch' : 'Confirm & Ready'}
                                </span>
                                {ready && <div className="absolute inset-0 bg-gradient-to-r from-green-400 to-green-600 animate-pulse" />}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
