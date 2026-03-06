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
    const [selectedBrand, setSelectedBrand] = useState<string | null>(null)

    const ALL_CARS = [
        { id: 'ks_ferrari_488_gt3', name: '488 GT3', brand: 'Ferrari', class: 'GT3' },
        { id: 'ks_lamborghini_huracan_gt3', name: 'Huracan GT3', brand: 'Lamborghini', class: 'GT3' },
        { id: 'ks_porsche_911_gt3_r', name: '911 GT3 R', brand: 'Porsche', class: 'GT3' },
        { id: 'ks_mclaren_650s_gt3', name: '650S GT3', brand: 'McLaren', class: 'GT3' },
        { id: 'ks_audi_r8_lms', name: 'R8 LMS', brand: 'Audi', class: 'GT3' },
        { id: 'ks_mercedes_amg_gt3', name: 'AMG GT3', brand: 'Mercedes', class: 'GT3' },
        { id: 'ks_bmw_m6_gt3', name: 'M6 GT3', brand: 'BMW', class: 'GT3' },
        { id: 'ks_nissan_gt_r_gt3', name: 'GT-R GT3', brand: 'Nissan', class: 'GT3' },
        { id: 'ks_corvette_c7_r', name: 'C7.R GTE', brand: 'Chevrolet', class: 'GTE' },
        { id: 'ks_ferrari_488_gte', name: '488 GTE', brand: 'Ferrari', class: 'GTE' },
        { id: 'tatuusfa1', name: 'FA.01', brand: 'Tatuus', class: 'FORMULA' },
        { id: 'ks_lotus_exos_125', name: 'Exos 125', brand: 'Lotus', class: 'F1' }
    ]

    const activeCars = (ALL_CARS || []).filter(c => (carPool || []).includes(c.id))
    const brands = Array.from(new Set(activeCars.map(c => c.brand)))

    useEffect(() => {
        const params = new URLSearchParams(window.location.search)
        const id = params.get('rig_id') || 'UNKNOWN'
        setRigId(id)

        const registerKiosk = async () => {
            try {
                // Just check in, don't force a status. This preserves 'setup' if already set by Sled.
                await fetch(`/api/rigs/${id}/status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
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
                    const myRig = rigs.find((r: Rig) => r && r.rig_id === id)
                    if (myRig) {
                        setStatus(myRig.status || 'idle')
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
                    width: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: rgba(255, 255, 255, 0.02);
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: rgba(255, 81, 0, 0.2);
                    border-radius: 10px;
                }
                .locked-pane {
                    height: 500px;
                    width: 900px;
                    background: rgba(0, 0, 0, 0.6);
                    backdrop-blur: 40px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 40px;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
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
                className={`absolute inset-0 w-full h-full object-cover transition-all duration-1000 ${status === 'setup' || status === 'ready' ? 'blur-3xl scale-110 opacity-30 px-20' : 'opacity-80'}`}
            >
                <source src={finalVideoSrc} type="video/mp4" />
            </video>

            {/* Logo Overlay */}
            <div className="absolute top-12 left-12 z-50 pointer-events-none">
                <img
                    src={branding.logo_url || "/assets/ridge_logo.png"}
                    alt="Facility Logo"
                    className="h-16 w-auto object-contain"
                />
            </div>

            {/* Setup Overlay */}
            {(status?.toLowerCase() === 'setup' || status?.toLowerCase() === 'ready') && (
                <div className="absolute inset-0 flex items-center justify-center z-40 bg-black/20 animate-in fade-in duration-700">
                    <div className="flex flex-col items-center">
                        <div className="text-center mb-10">
                            <h1 className="text-5xl font-black uppercase tracking-tighter italic leading-none">
                                {selectedBrand ? selectedBrand.toUpperCase() : 'MISSION PREP'}
                            </h1>
                            <p className="text-ridge-brand font-black tracking-[0.4em] uppercase text-[10px] mt-2">
                                {selectedBrand ? 'Select Your Model' : 'CHOOSE MANUFACTURER'}
                            </p>
                        </div>

                        <div className="locked-pane relative">
                            {selectedBrand && (
                                <button
                                    onClick={() => setSelectedBrand(null)}
                                    className="absolute top-6 left-8 z-50 text-[10px] font-black uppercase tracking-widest text-white/40 hover:text-ridge-brand transition-colors flex items-center gap-2"
                                >
                                    ← BACK TO BRANDS
                                </button>
                            )}

                            <div className="flex-1 overflow-y-auto custom-scrollbar p-12 pt-16">
                                {brands.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full opacity-30 text-center px-12">
                                        <Shield className="w-16 h-16 mb-4" />
                                        <p className="font-black italic uppercase text-lg italic uppercase tracking-tighter">Fleet database unavailable</p>
                                        <p className="text-[10px] font-mono mt-2 tracking-widest leading-relaxed">System status: {status} // Car Pool Size: {carPool?.length || 0}</p>
                                    </div>
                                ) : !selectedBrand ? (
                                    <div className="grid grid-cols-3 gap-6">
                                        {brands.map(brand => (
                                            <button
                                                key={brand}
                                                onClick={() => setSelectedBrand(brand)}
                                                className="aspect-[4/3] rounded-3xl bg-white/5 border border-white/5 hover:border-ridge-brand/50 hover:bg-ridge-brand/5 transition-all flex flex-col items-center justify-center group"
                                            >
                                                <Shield className="w-12 h-12 text-white/10 group-hover:text-ridge-brand transition-all duration-500 mb-4" />
                                                <span className="font-black italic uppercase tracking-tighter text-xl">{brand}</span>
                                            </button>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-2 gap-4">
                                        {activeCars.filter(c => c.brand === selectedBrand).map(car => (
                                            <button
                                                key={car.id}
                                                onClick={() => handleCarSelect(car.id)}
                                                className={`p-6 rounded-3xl border-2 text-left relative transition-all duration-500 overflow-hidden ${selectedCar === car.id
                                                    ? 'bg-ridge-brand/20 border-ridge-brand shadow-[0_0_40px_rgba(255,81,0,0.2)]'
                                                    : 'bg-white/5 border-white/5 hover:border-white/10'
                                                    }`}
                                            >
                                                <div className="relative z-10">
                                                    <p className="text-[10px] font-black opacity-30 uppercase mb-1">{car.class}</p>
                                                    <h3 className="text-2xl font-black tracking-tighter italic uppercase underline-offset-4 decoration-ridge-brand">{car.name}</h3>
                                                </div>
                                                {selectedCar === car.id && (
                                                    <div className="absolute top-4 right-4 text-ridge-brand">
                                                        <Check size={20} />
                                                    </div>
                                                )}
                                                <Shield className={`absolute -right-6 -bottom-6 w-32 h-32 transition-all duration-700 ${selectedCar === car.id ? 'text-ridge-brand/10 scale-125' : 'text-white/5 opacity-0'}`} />
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="p-8 bg-black/20 border-t border-white/5 flex justify-center">
                                <button
                                    onClick={toggleReady}
                                    disabled={!selectedCar}
                                    className={`group px-20 py-4 rounded-full font-black uppercase tracking-[0.2em] text-sm transition-all duration-500 ${ready
                                        ? 'bg-green-500 shadow-[0_0_50px_rgba(34,197,94,0.4)]'
                                        : !selectedCar ? 'bg-zinc-800 text-white/20 cursor-not-allowed' : 'bg-white text-black hover:scale-105 active:scale-95 shadow-xl shadow-white/5'
                                        }`}
                                >
                                    <span className="flex items-center gap-3">
                                        {ready ? <Check className="w-5 h-5" /> : <Zap className="w-5 h-5 shadow-inner shadow-black" />}
                                        {ready ? 'SYSTEM READY' : 'CONFIRM SELECTION'}
                                    </span>
                                </button>
                            </div>
                        </div>

                        <div className="mt-8 flex items-center gap-4 animate-pulse">
                            <div className="w-2 h-2 rounded-full bg-ridge-brand" />
                            <span className="text-[10px] font-black uppercase tracking-[0.4em] text-white/40 italic">Link active: {rigId}</span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
