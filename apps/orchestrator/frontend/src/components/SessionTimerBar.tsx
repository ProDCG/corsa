import { useState, useEffect } from 'react'
import { Clock, Users } from 'lucide-react'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface RigGroup {
    id: string
    name: string
    mode: string
    rig_ids: string[]
    session_duration_min: number
}

interface ActiveTimer {
    groupId: string
    groupName: string
    startedAt: number  // timestamp
    durationMin: number
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function SessionTimerBar() {
    const [groups, setGroups] = useState<RigGroup[]>([])
    const [activeTimers, setActiveTimers] = useState<ActiveTimer[]>([])
    const [, setTick] = useState(0) // Force re-render every second

    // Poll groups for racing status
    useEffect(() => {
        const fetchGroups = async () => {
            try {
                const res = await fetch('/api/groups/')
                const data = await res.json()
                if (Array.isArray(data)) setGroups(data)
            } catch { /* offline */ }
        }
        fetchGroups()
        const interval = setInterval(fetchGroups, 3000)
        return () => clearInterval(interval)
    }, [])

    // Check for racing rigs and start timers
    useEffect(() => {
        const fetchRigs = async () => {
            try {
                const res = await fetch('/api/rigs')
                const rigs = await res.json()
                if (!Array.isArray(rigs)) return

                const racingRigIds = new Set(
                    rigs.filter((r: any) => r.status === 'racing').map((r: any) => r.rig_id)
                )

                // For each group, check if any of its rigs are racing
                setActiveTimers(prev => {
                    const next: ActiveTimer[] = []
                    for (const group of groups) {
                        const hasRacing = group.rig_ids.some(rid => racingRigIds.has(rid))
                        const existing = prev.find(t => t.groupId === group.id)
                        if (hasRacing) {
                            if (existing) {
                                next.push(existing) // Keep existing timer
                            } else {
                                next.push({
                                    groupId: group.id,
                                    groupName: group.name,
                                    startedAt: Date.now(),
                                    durationMin: group.session_duration_min || 30,
                                })
                            }
                        }
                        // If not racing, timer is removed
                    }
                    // Only update if changed
                    const nj = JSON.stringify(next.map(t => t.groupId))
                    const pj = JSON.stringify(prev.map(t => t.groupId))
                    return nj !== pj ? next : prev
                })
            } catch { /* offline */ }
        }
        fetchRigs()
        const interval = setInterval(fetchRigs, 3000)
        return () => clearInterval(interval)
    }, [groups])

    // Tick every second for countdown
    useEffect(() => {
        if (activeTimers.length === 0) return
        const interval = setInterval(() => setTick(t => t + 1), 1000)
        return () => clearInterval(interval)
    }, [activeTimers.length])

    if (activeTimers.length === 0) return null

    return (
        <div className="bg-black/40 border-b border-white/5 px-8 py-2 flex items-center gap-6">
            <div className="flex items-center gap-1.5 text-[9px] text-white/30 font-black uppercase tracking-widest">
                <Clock size={10} /> Active Sessions
            </div>
            {activeTimers.map(timer => {
                const elapsed = (Date.now() - timer.startedAt) / 1000
                const totalSec = timer.durationMin * 60
                const remaining = Math.max(0, totalSec - elapsed)
                const mins = Math.floor(remaining / 60)
                const secs = Math.floor(remaining % 60)
                const hours = Math.floor(mins / 60)
                const displayMins = mins % 60

                let color = 'text-white'
                if (remaining < 300) color = 'text-red-400 animate-pulse'
                else if (remaining < 900) color = 'text-amber-400'

                const timeStr = hours > 0
                    ? `${hours}:${String(displayMins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
                    : `${String(displayMins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`

                return (
                    <div key={timer.groupId} className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-1.5">
                        <Users size={10} className="text-white/30" />
                        <span className="text-[10px] font-black uppercase text-white/50">{timer.groupName}</span>
                        <span className={`text-sm font-black tabular-nums ${color}`}>{timeStr}</span>
                        {remaining <= 0 && (
                            <span className="text-[8px] font-black uppercase text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">EXPIRED</span>
                        )}
                    </div>
                )
            })}
        </div>
    )
}
