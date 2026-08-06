import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { getDashboard } from '../../api/dashboard'
import {
    checkInAppointment,
    rescheduleAppointment,
    cancelAppointment,
    getUpcomingSlots,
} from '../../api/workflows'
import './DashboardView.css'
import {
    ResponsiveContainer,
    PieChart, Pie, Cell, Tooltip, Legend,
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    AreaChart, Area
} from 'recharts'
import {
    Activity, Calendar, Clock, Stethoscope, MapPin, TrendingUp,
    AlertTriangle, Info, RefreshCw, UserCheck, UserX, Sparkles,
    Building2, Languages, Award, Search, LayoutDashboard,
    ExternalLink, Filter, Users, Layers, ShieldCheck, X, ClipboardList
} from 'lucide-react'
import { doctorAvatar } from './genderAvatar'

// Curated dark theme color palette matching dashboard.py
const COLORS = [
    '#58a6ff', '#3fb950', '#e3b341', '#d2a8ff',
    '#f85149', '#f0883e', '#39c5cf', '#bc8cff',
    '#79c0ff', '#56d364'
]

const CITY_COLORS = {
    'Chennai': '#58a6ff',
    'Bengaluru': '#3fb950',
    'Mumbai': '#e3b341',
    'Hyderabad': '#d2a8ff',
    'Bangalore': '#3fb950',
}

function fmt(n) {
    if (n === null || n === undefined) return '—'
    if (typeof n === 'string') return n
    const num = Number(n)
    return isNaN(num) ? '—' : num.toLocaleString()
}

function fmtExp(val) {
    if (val === null || val === undefined) return '—'
    const num = Number(val)
    if (isNaN(num) || num <= 0) return '—'
    return `${num.toFixed(1)} yrs`
}

function fmtTime(iso) {
    if (!iso) return ''
    try {
        const d = new Date(iso)
        return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch (e) {
        return iso
    }
}

function initials(name) {
    if (!name) return 'DR'
    const parts = name.trim().split(' ')
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return name.slice(0, 2).toUpperCase()
}

// ── Receptionist helpers ────────────────────────────────────────────────────

const STATUS_META = {
    booked:      { label: 'Booked',      cls: 'blue' },
    checked_in:  { label: 'Checked In',  cls: 'green' },
    completed:   { label: 'Completed',   cls: 'green' },
    cancelled:   { label: 'Cancelled',   cls: 'red' },
    rescheduled: { label: 'Rescheduled', cls: 'amber' },
    pending:     { label: 'Pending',     cls: 'amber' },
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function fmtDate(d) {
    if (!d) return '—'
    try {
        const [y, m, day] = String(d).split('-')
        return `${day} ${MONTHS[Number(m) - 1]} ${y}`
    } catch (e) {
        return String(d)
    }
}

function fmtClock(t) {
    if (!t) return '—'
    try {
        const [h, m] = String(t).split(':')
        const hh = Number(h)
        return `${String(hh % 12 || 12).padStart(2, '0')}:${m} ${hh < 12 ? 'AM' : 'PM'}`
    } catch (e) {
        return String(t)
    }
}

function patientLabel(a) {
    return a.patient_name || a.patient_phone || '—'
}

function StatusPill({ status }) {
    const meta = STATUS_META[status] || { label: status || 'Unknown', cls: 'muted' }
    return <span className={`d-status-pill ${meta.cls}`}>{meta.label}</span>
}

function whatsappReminderUrl(a) {
    const phone = String(a.patient_phone || '').replace(/[^0-9]/g, '')
    const msg =
        `Dear ${a.patient_name || 'Patient'}, this is a reminder for your appointment with ` +
        `${a.doctor_name} at Gleneagles Hospitals on ${fmtDate(a.date)} at ${fmtClock(a.time)}. ` +
        `Appointment ID: ${a.appointment_id}. Please arrive 15 minutes early.`
    return `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`
}

// Custom Tooltip for Recharts
const CustomTooltip = ({ active, payload, label, unit = '' }) => {
    if (active && payload && payload.length) {
        return (
            <div className="custom-tooltip">
                <div className="custom-tooltip-title">{label || payload[0].name}</div>
                {payload.map((entry, index) => (
                    <div key={`item-${index}`} className="custom-tooltip-row" style={{ color: entry.color || '#58a6ff' }}>
                        <span>● {entry.name || 'Count'}:</span>
                        <strong>{fmt(entry.value)} {unit}</strong>
                    </div>
                ))}
            </div>
        )
    }
    return null
}

export default function DashboardView({ config }) {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'hospitals' | 'doctors' | 'analytics' | 'ops'
    const [role, setRole] = useState('receptionist') // 'receptionist' | 'attender' | 'analytics'
    
    // Directory Filters State
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedCity, setSelectedCity] = useState('All')
    const [selectedSpecialty, setSelectedSpecialty] = useState('All')
    const [onlySlotsToggle, setOnlySlotsToggle] = useState(false)
    const [directoryView, setDirectoryView] = useState('cards') // 'cards' | 'table'

    const clientId = (config && config.clientId) || 'gleneagles_001'

    const load = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const d = await getDashboard(clientId)
            setData(d)
        } catch (err) {
            setError(err.message || 'Failed to load monitoring dashboard')
            setData(null)
        } finally {
            setLoading(false)
        }
    }, [clientId])

    useEffect(() => {
        load()
        const pollId = setInterval(load, 30000)
        const onFocus = () => load()
        window.addEventListener('focus', onFocus)
        return () => {
            clearInterval(pollId)
            window.removeEventListener('focus', onFocus)
        }
    }, [load])

    // Cities list derived from SQLite data / hospital network
    const citiesList = useMemo(() => {
        if (data?.cities && data.cities.length > 0) return data.cities
        if (!data || !data.hospital_network) return []
        const set = new Set(data.hospital_network.map((h) => h.city).filter(Boolean))
        return Array.from(set).sort()
    }, [data])

    // Specialties list derived from SQLite data / all doctors
    const specialtiesList = useMemo(() => {
        if (data?.specialties && data.specialties.length > 0) return data.specialties
        if (!data || !data.all_doctors) return []
        const set = new Set(data.all_doctors.map((d) => d.speciality).filter(Boolean))
        return Array.from(set).sort()
    }, [data])

    // Filtered doctor directory based on multi-filter controls
    const filteredDirectory = useMemo(() => {
        const list = (data?.all_doctors && data.all_doctors.length > 0) ? data.all_doctors : (data?.doctor_availability || [])
        return list.filter((d) => {
            if (searchQuery.trim()) {
                const q = searchQuery.toLowerCase().trim()
                const name = (d.name || d.doctor_name || '').toLowerCase()
                const spec = (d.speciality || '').toLowerCase()
                const city = (d.city || '').toLowerCase()
                if (!name.includes(q) && !spec.includes(q) && !city.includes(q)) return false
            }
            if (selectedCity !== 'All' && (d.city || '').toLowerCase() !== selectedCity.toLowerCase()) return false
            if (selectedSpecialty !== 'All' && (d.speciality || '').toLowerCase() !== selectedSpecialty.toLowerCase()) return false
            const slots = d.open_slots ?? d.total_available_slots ?? 0
            if (onlySlotsToggle && slots <= 0) return false
            return true
        })
    }, [data, searchQuery, selectedCity, selectedSpecialty, onlySlotsToggle])

    // Format Status Breakdown for Pie Chart
    const statusPieData = useMemo(() => {
        if (!data || !data.status_breakdown) return []
        return Object.entries(data.status_breakdown).map(([status, count]) => ({
            name: status.charAt(0).toUpperCase() + status.slice(1),
            value: count
        }))
    }, [data])

    const totalStatusCount = useMemo(() => {
        return statusPieData.reduce((acc, curr) => acc + curr.value, 0)
    }, [statusPieData])

    return (
        <div className="dash-container">
            {/* Header / Hero */}
            <div className="dash-hero">
                <div className="dash-title-group">
                    <h1 className="dash-title">
                        <Activity className="dash-title-icon" size={28} />
                        Gleneagles Doctor KB Dashboard
                    </h1>
                    <div className="dash-sub">
                        {data ? (
                            <>
                                <span>{data.client_name}</span>
                                <span className="dash-badge">{data.today}</span>
                                {citiesList.map((c) => (
                                    <span key={c} className="hero-city-tag" style={{ borderLeft: `3px solid ${CITY_COLORS[c] || '#58a6ff'}` }}>
                                        {c}
                                    </span>
                                ))}
                            </>
                        ) : (
                            'Real-time operational overview + doctor network analytics'
                        )}
                    </div>
                </div>

                <div className="dash-hero-actions">
                    {data && data.generated_at && (
                        <div className="dash-updated">
                            <Clock size={14} />
                            Updated {fmtTime(data.generated_at)}
                        </div>
                    )}
                    <button className="dash-btn-refresh" onClick={load} disabled={loading}>
                        <RefreshCw size={15} className={loading ? 'spin-icon' : ''} />
                        {loading ? 'Refreshing…' : 'Refresh Data'}
                    </button>
                </div>
            </div>

            {/* Error Banner */}
            {error && (
                <div className="dash-alert-item warn" style={{ marginBottom: '1rem' }}>
                    <AlertTriangle size={18} />
                    <span>⚠️ {error} — Ensure Workflows service is running on port 8001.</span>
                </div>
            )}

            {/* Role Switcher — Receptionist / Attender / Analytics */}
            <div className="dash-role-switcher">
                <button
                    className={`dash-role-btn ${role === 'receptionist' ? 'active' : ''}`}
                    onClick={() => setRole('receptionist')}
                >
                    <ClipboardList size={16} /> Receptionist
                </button>
                <button
                    className={`dash-role-btn ${role === 'attender' ? 'active' : ''}`}
                    onClick={() => setRole('attender')}
                >
                    <UserCheck size={16} /> Attender
                </button>
                <button
                    className={`dash-role-btn ${role === 'analytics' ? 'active' : ''}`}
                    onClick={() => setRole('analytics')}
                >
                    <TrendingUp size={16} /> Analytics
                </button>
            </div>

            {/* Content Loading State */}
            {loading && !data && (
                <div className="dash-empty-msg">
                    <RefreshCw size={24} className="spin-icon" style={{ marginBottom: '0.5rem' }} />
                    <div>Loading real-time hospital network analytics…</div>
                </div>
            )}

            {/* ═══════════════ RECEPTIONIST ROLE ═══════════════ */}
            {role === 'receptionist' && data && (
                <ReceptionistView data={data} clientId={clientId} onChanged={load} />
            )}

            {/* ═══════════════ ATTENDER ROLE (coming next) ═══════════════ */}
            {role === 'attender' && data && (
                <div className="dash-empty-msg" style={{ padding: '3rem 1rem' }}>
                    <UserCheck size={28} style={{ marginBottom: '0.6rem', color: '#3fb950' }} />
                    <div style={{ fontWeight: 700, color: '#e6edf3', marginBottom: '0.35rem' }}>
                        Attender View
                    </div>
                    <div>Provide the attender requirements and this view will be built here.</div>
                </div>
            )}

            {/* ═══════════════ ANALYTICS ROLE (original dashboard) ═══════════════ */}
            {role === 'analytics' && (
            <>
            {/* View Switcher Tabs matching dashboard.py */}
            <div className="dash-view-tabs">
                <button
                    className={`dash-view-tab ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                >
                    <LayoutDashboard size={16} /> 📊 Overview
                </button>
                <button
                    className={`dash-view-tab ${activeTab === 'hospitals' ? 'active' : ''}`}
                    onClick={() => setActiveTab('hospitals')}
                >
                    <Building2 size={16} /> 🏥 Hospital Network
                </button>
                <button
                    className={`dash-view-tab ${activeTab === 'doctors' ? 'active' : ''}`}
                    onClick={() => setActiveTab('doctors')}
                >
                    <Users size={16} /> 👨‍⚕️ Doctor Directory
                </button>
                <button
                    className={`dash-view-tab ${activeTab === 'analytics' ? 'active' : ''}`}
                    onClick={() => setActiveTab('analytics')}
                >
                    <TrendingUp size={16} /> 📈 Analytics &amp; Graphs
                </button>
                <button
                    className={`dash-view-tab ${activeTab === 'ops' ? 'active' : ''}`}
                    onClick={() => setActiveTab('ops')}
                >
                    <Stethoscope size={16} /> 🩺 Today's Operations
                </button>
            </div>

            {/* Main Content Areas */}
            {data && (
                <>
                    {/* Alert Banners */}
                    {data.alerts && data.alerts.length > 0 && (
                        <div className="dash-alerts-container">
                            {data.alerts.map((a, i) => (
                                <div key={i} className={`dash-alert-item ${a.level === 'warn' ? 'warn' : 'info'}`}>
                                    {a.level === 'warn' ? <AlertTriangle size={16} /> : <Info size={16} />}
                                    <span>{a.text}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* KPI Cards Grid 1 */}
                    <div className="dash-kpis-grid">
                        <KpiCard
                            title="Total Doctors"
                            value={data.summary?.total_doctors}
                            sub="Indexed in network"
                            icon={<Users size={18} color="#58a6ff" />}
                            colorClass="blue"
                        />
                        <KpiCard
                            title="Hospitals"
                            value={data.summary?.total_hospitals}
                            sub="Active branches"
                            icon={<Building2 size={18} color="#3fb950" />}
                            colorClass="green"
                        />
                        <KpiCard
                            title="Specialties"
                            value={data.summary?.specialties}
                            sub="Clinical domains"
                            icon={<Award size={18} color="#e3b341" />}
                            colorClass="yellow"
                        />
                        <KpiCard
                            title="Avg Experience"
                            value={fmtExp(data.summary?.avg_experience)}
                            sub="Seniority index"
                            icon={<TrendingUp size={18} color="#d2a8ff" />}
                            colorClass="purple"
                        />
                        <KpiCard
                            title="Open Slots Today"
                            value={data.summary?.open_slots_today}
                            sub="Immediate availability"
                            icon={<Sparkles size={18} color="#39c5cf" />}
                            colorClass="cyan"
                        />
                        <KpiCard
                            title="Open Slots (7 Days)"
                            value={data.summary?.open_slots_7d}
                            sub="Weekly capacity"
                            icon={<Calendar size={18} color="#f0883e" />}
                            colorClass="orange"
                        />
                    </div>

                    {/* ════════════════════ TAB 1: OVERVIEW ════════════════════ */}
                    {activeTab === 'overview' && (
                        <>
                            {/* Receptionist cockpit */}
                            <ReceptionistCockpit data={data} clientId={clientId} onChanged={load} />

                            {/* Hospital Network Mini Cards */}
                            <div style={{ marginBottom: '1.5rem' }}>
                                <div className="dash-section-label">🏥 Hospital Network Coverage</div>
                                <div className="hosp-mini-grid">
                                    {(data.hospital_network || []).map((h) => {
                                        const maxDocs = Math.max(1, ...(data.hospital_network || []).map((x) => x.doctor_count))
                                        const pct = Math.round((h.doctor_count / maxDocs) * 100)
                                        const cColor = CITY_COLORS[h.city] || '#58a6ff'
                                        return (
                                            <div key={h.id} className="hmini-card" style={{ borderTop: `3px solid ${cColor}` }}>
                                                <div className="hmini-title">{h.name}</div>
                                                <div className="hmini-loc">📍 {h.city} · {h.state}</div>
                                                <div className="hmini-bar">
                                                    <div className="hmini-bar-fill" style={{ width: `${pct}%`, background: cColor }} />
                                                </div>
                                                <div className="hmini-footer">
                                                    <span style={{ color: cColor, fontWeight: 600 }}>{h.doctor_count} doctors</span>
                                                    <span className="muted">{fmt(h.total_slots)} slots</span>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>

                            {/* Graphs Row 1: Specialization Bar Chart & Designation Pie Chart */}
                            <div className="dash-grid-2">
                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <Award size={18} color="#58a6ff" />
                                            Top 15 Specializations
                                        </div>
                                    </div>
                                    <div className="chart-wrapper">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart
                                                data={data.analytics?.top_specializations?.slice(0, 10) || []}
                                                layout="vertical"
                                                margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
                                            >
                                                <CartesianGrid strokeDasharray="3 3" stroke="#21262d" horizontal={false} />
                                                <XAxis type="number" stroke="#8b949e" fontSize={11} />
                                                <YAxis dataKey="name" type="category" stroke="#c9d1d9" fontSize={11} width={110} />
                                                <Tooltip content={<CustomTooltip unit="doctors" />} />
                                                <Bar dataKey="count" fill="#58a6ff" radius={[0, 4, 4, 0]} barSize={14}>
                                                    {(data.analytics?.top_specializations || []).map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                    ))}
                                                </Bar>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <Award size={18} color="#f0883e" />
                                            Designation Mix
                                        </div>
                                    </div>
                                    <div className="chart-wrapper">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={data.analytics?.designation_mix || []}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={50}
                                                    outerRadius={80}
                                                    paddingAngle={3}
                                                    dataKey="count"
                                                    nameKey="designation"
                                                >
                                                    {(data.analytics?.designation_mix || []).map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={COLORS[(index + 2) % COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip content={<CustomTooltip unit="doctors" />} />
                                                <Legend
                                                    formatter={(value) => <span style={{ color: '#c9d1d9', fontSize: 11 }}>{value}</span>}
                                                    layout="horizontal"
                                                    align="center"
                                                    verticalAlign="bottom"
                                                />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </div>

                            {/* Graphs Row 2: Experience Distribution & Languages Bar Chart */}
                            <div className="dash-grid-2">
                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <TrendingUp size={18} color="#d2a8ff" />
                                            Experience Distribution (Years)
                                        </div>
                                    </div>
                                    <div className="chart-wrapper">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={data.analytics?.experience_distribution || []}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#21262d" vertical={false} />
                                                <XAxis dataKey="range" stroke="#8b949e" fontSize={11} />
                                                <YAxis stroke="#8b949e" fontSize={11} />
                                                <Tooltip content={<CustomTooltip unit="doctors" />} />
                                                <Bar dataKey="count" fill="#d2a8ff" radius={[4, 4, 0, 0]} barSize={24} />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <Languages size={18} color="#39c5cf" />
                                            Languages Spoken
                                        </div>
                                    </div>
                                    <div className="chart-wrapper">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={data.analytics?.languages || []}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#21262d" vertical={false} />
                                                <XAxis dataKey="language" stroke="#8b949e" fontSize={11} />
                                                <YAxis stroke="#8b949e" fontSize={11} />
                                                <Tooltip content={<CustomTooltip unit="doctors" />} />
                                                <Bar dataKey="count" fill="#39c5cf" radius={[4, 4, 0, 0]} barSize={24}>
                                                    {(data.analytics?.languages || []).map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                    ))}
                                                </Bar>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}

                    {/* ════════════════════ TAB 2: HOSPITALS ════════════════════ */}
                    {activeTab === 'hospitals' && (
                        <>
                            <div className="dash-section-label">🏥 Hospital Network Details</div>
                            <div className="dash-hospitals-grid">
                                {(data.hospital_network || []).map((h) => {
                                    const cColor = CITY_COLORS[h.city] || '#58a6ff'
                                    const availPct = h.doctor_count > 0 ? Math.round((h.doctors_with_slots / h.doctor_count) * 100) : 0
                                    return (
                                        <div key={h.id} className="hcard-full" style={{ borderLeft: `4px solid ${cColor}` }}>
                                            <div className="hcard-header">
                                                <div>
                                                    <div className="hcard-title">{h.full_name}</div>
                                                    <div className="hcard-sub">
                                                        📍 {h.city}, {h.state} · <code className="muted">{h.id}</code>
                                                    </div>
                                                </div>
                                                <div className="hcard-badges">
                                                    <span className="dash-pill blue">{h.doctor_count} Doctors</span>
                                                    <span className="dash-pill green">{fmt(h.total_slots)} Slots</span>
                                                </div>
                                            </div>

                                            <div className="hcard-progress-section">
                                                <div className="hcard-progress-label">
                                                    <span>Open Slot Capacity</span>
                                                    <span>{availPct}% Doctors Available</span>
                                                </div>
                                                <div className="hcard-progress-track">
                                                    <div className="hcard-progress-fill" style={{ width: `${availPct}%`, background: cColor }} />
                                                </div>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </>
                    )}

                    {/* ════════════════════ TAB 3: DOCTOR DIRECTORY ════════════════════ */}
                    {activeTab === 'doctors' && (
                        <>
                            {/* Directory Filter Bar */}
                            <div className="directory-filter-card">
                                <div className="directory-filter-row">
                                    <div className="field-group grow">
                                        <label><Search size={12} /> Search Doctor Name</label>
                                        <input
                                            type="text"
                                            className="dir-input"
                                            placeholder="Search Dr. Name or specialization..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                        />
                                    </div>
                                    <div className="field-group">
                                        <label>City</label>
                                        <select className="dir-select" value={selectedCity} onChange={(e) => setSelectedCity(e.target.value)}>
                                            <option value="All">All Cities</option>
                                            {citiesList.map((c) => (
                                                <option key={c} value={c}>{c}</option>
                                            ))}
                                        </select>
                                    </div>
                                    <div className="field-group">
                                        <label>Specialization</label>
                                        <select className="dir-select" value={selectedSpecialty} onChange={(e) => setSelectedSpecialty(e.target.value)}>
                                            <option value="All">All Specializations</option>
                                            {specialtiesList.map((s) => (
                                                <option key={s} value={s}>{s}</option>
                                            ))}
                                        </select>
                                    </div>
                                    <div className="field-group flex-row">
                                        <label className="toggle-label">
                                            <input
                                                type="checkbox"
                                                checked={onlySlotsToggle}
                                                onChange={(e) => setOnlySlotsToggle(e.target.checked)}
                                            />
                                            <span>Open Slots Only</span>
                                        </label>
                                    </div>
                                    <div className="field-group">
                                        <div className="view-toggle-btns">
                                            <button
                                                className={`v-btn ${directoryView === 'cards' ? 'active' : ''}`}
                                                onClick={() => setDirectoryView('cards')}
                                            >
                                                🃏 Cards
                                            </button>
                                            <button
                                                className={`v-btn ${directoryView === 'table' ? 'active' : ''}`}
                                                onClick={() => setDirectoryView('table')}
                                            >
                                                📋 Table
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div className="directory-count-line">
                                    <strong>{filteredDirectory.length}</strong> doctors match criteria
                                </div>
                            </div>

                            {/* Directory Display: Cards Grid vs Table */}
                            {directoryView === 'cards' ? (
                                <div className="doctor-cards-grid">
                                    {filteredDirectory.slice(0, 48).map((doc) => {
                                        const cColor = CITY_COLORS[doc.city] || '#58a6ff'
                                        return (
                                            <div key={doc.id} className="dcard-box">
                                                <div className="dcard-top">
                                                    <div className="dcard-avatar" style={{ borderColor: cColor, color: cColor }}>
                                                        {initials(doc.name)}
                                                    </div>
                                                    <div className="dcard-meta">
                                                        <div className="dcard-name" title={doc.name}>{doc.name}</div>
                                                        <div className="dcard-desig">{doc.designation || 'Consultant'}</div>
                                                    </div>
                                                </div>

                                                <div className="dcard-spec">📋 {doc.speciality}</div>

                                                <div className="dcard-badges-row">
                                                    {doc.open_slots > 0 ? (
                                                        <span className="dash-pill green">🟢 {doc.open_slots} slots</span>
                                                    ) : (
                                                        <span className="dash-pill muted">🔴 No slots</span>
                                                    )}
                                                    {doc.experience_years && (
                                                        <span className="dash-pill amber">🕐 {doc.experience_years} yrs exp</span>
                                                    )}
                                                    <span className="dash-pill blue">📍 {doc.city}</span>
                                                </div>

                                                {doc.qualifications && (
                                                    <div className="dcard-sub-line">🎓 {doc.qualifications}</div>
                                                )}
                                                {doc.languages && (
                                                    <div className="dcard-sub-line">🗣️ {doc.languages}</div>
                                                )}

                                                {doc.booking_url && (
                                                    <a className="dcard-book-btn" href={doc.booking_url} target="_blank" rel="noreferrer">
                                                        📅 Book Appointment <ExternalLink size={12} />
                                                    </a>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            ) : (
                                <div className="dash-card">
                                    <DoctorAvailabilityTable doctors={filteredDirectory} />
                                </div>
                            )}
                        </>
                    )}

                    {/* ════════════════════ TAB 4: ANALYTICS & GRAPHS ════════════════════ */}
                    {activeTab === 'analytics' && (
                        <>
                            {/* City Slots & Language Mix */}
                            <div className="dash-grid-2">
                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <MapPin size={18} color="#3fb950" />
                                            Open Slot Capacity by City
                                        </div>
                                    </div>
                                    <div className="chart-wrapper">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <AreaChart
                                                data={data.analytics?.slots_by_city || []}
                                                margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
                                            >
                                                <defs>
                                                    <linearGradient id="colorSlots" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#3fb950" stopOpacity={0.8} />
                                                        <stop offset="95%" stopColor="#3fb950" stopOpacity={0.0} />
                                                    </linearGradient>
                                                </defs>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                                                <XAxis dataKey="city" stroke="#8b949e" fontSize={11} />
                                                <YAxis stroke="#8b949e" fontSize={11} />
                                                <Tooltip content={<CustomTooltip unit="slots" />} />
                                                <Area type="monotone" dataKey="slots" stroke="#3fb950" fillOpacity={1} fill="url(#colorSlots)" />
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <Languages size={18} color="#d2a8ff" />
                                            Languages Spoken Distribution
                                        </div>
                                    </div>
                                    <div className="chart-wrapper">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={data.analytics?.languages || []}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={50}
                                                    outerRadius={80}
                                                    paddingAngle={3}
                                                    dataKey="count"
                                                    nameKey="language"
                                                >
                                                    {(data.analytics?.languages || []).map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip content={<CustomTooltip unit="doctors" />} />
                                                <Legend
                                                    formatter={(value) => <span style={{ color: '#c9d1d9', fontSize: 11 }}>{value}</span>}
                                                    layout="horizontal"
                                                    align="center"
                                                    verticalAlign="bottom"
                                                />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}

                    {/* ════════════════════ TAB 5: TODAY'S OPERATIONS ════════════════════ */}
                    {activeTab === 'ops' && (
                        <>
                            {/* Today's & Upcoming Appointments */}
                            <div className="dash-grid-2">
                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <Clock size={18} color="#e3b341" />
                                            Today's Scheduled Appointments ({data.today_appointments?.length || 0})
                                        </div>
                                    </div>
                                    <AppointmentList items={data.today_appointments} emptyMsg="No appointments scheduled for today." />
                                </div>

                                <div className="dash-card">
                                    <div className="dash-card-header">
                                        <div className="dash-card-title">
                                            <Calendar size={18} color="#58a6ff" />
                                            Upcoming Booked Appointments ({data.upcoming_appointments?.length || 0})
                                        </div>
                                    </div>
                                    <AppointmentList items={data.upcoming_appointments} emptyMsg="No upcoming booked appointments on the horizon." />
                                </div>
                            </div>

                            <div className="dash-card">
                                <div className="dash-card-header">
                                    <div className="dash-card-title">
                                        <Activity size={18} color="#58a6ff" />
                                        Recent Appointment Activity Feed
                                    </div>
                                </div>
                                <RecentActivityTable items={data.recent_activity || []} />
                            </div>
                        </>
                    )}
                </>
            )}
            </>
            )}
        </div>
    )
}

/* ══════════════════════════ RECEPTIONIST VIEW ══════════════════════════ */

function RecKpi({ label, value, color }) {
    return (
        <div className={`rec-kpi ${color}`}>
            <div className="rec-kpi-label">{label}</div>
            <div className="rec-kpi-value">{fmt(value)}</div>
        </div>
    )
}

function ReceptionistView({ data, clientId, onChanged }) {
    const [opsDate, setOpsDate] = useState(data.ops_date || data.today || '')
    const [query, setQuery] = useState('')
    const [selectedId, setSelectedId] = useState(null)
    const [busy, setBusy] = useState('')
    const [notice, setNotice] = useState('')

    const all = data.recent_appointments || []
    const opsDates = (data.ops_dates && data.ops_dates.length) ? data.ops_dates : [opsDate]
    const day = useMemo(() => all.filter((a) => a.date === opsDate), [all, opsDate])

    // Search across appointment id, patient name, and phone. When a query is
    // present we search the full history, not just the selected day.
    const rows = useMemo(() => {
        const q = query.trim().toLowerCase()
        const source = q ? all : day
        return source
            .filter((a) =>
                !q ||
                String(a.appointment_id || '').toLowerCase().includes(q) ||
                (a.patient_name || '').toLowerCase().includes(q) ||
                String(a.patient_phone || '').includes(q)
            )
            .sort((a, b) => (b.date || '').localeCompare(a.date || '') || (a.time || '').localeCompare(b.time || ''))
    }, [all, day, query])

    const count = (status) => day.filter((a) => a.status === status).length
    const kpis = [
        { label: "Today's Appointments",   value: day.length,                                                         color: 'blue' },
        { label: 'Checked-In Patients',    value: count('checked_in'),                                                color: 'green' },
        { label: 'Upcoming Appointments',  value: all.filter((a) => a.date > opsDate && a.status === 'booked').length, color: 'purple' },
        { label: 'Cancelled Appointments', value: count('cancelled'),                                                 color: 'red' },
        { label: 'Doctors Available',      value: (data.doctor_availability || []).length,                            color: 'green' },
        { label: 'Pending Requests',       value: all.filter((a) => a.status === 'pending').length,                   color: 'amber' },
    ]

    const runAction = async (action, successMsg, busyMsg) => {
        setBusy(busyMsg)
        try {
            await action()
            setNotice(successMsg)
            setSelectedId(null)
            onChanged()
        } catch (err) {
            setNotice(`⚠️ ${err.message || 'Action failed'}`)
        } finally {
            setBusy('')
        }
    }

    const selected = all.find((a) => a.appointment_id === selectedId) || null
    const doctors = data.all_doctors && data.all_doctors.length ? data.all_doctors : (data.doctor_availability || [])

    return (
        <div className="rec-view">
            {/* KPI Row — matches operational snapshot */}
            <div className="rec-kpi-grid">
                {kpis.map((k) => (
                    <RecKpi key={k.label} label={k.label} value={k.value} color={k.color} />
                ))}
            </div>

            {notice && (
                <div className="dash-alert-item info" style={{ marginBottom: '0.9rem' }}>
                    <Info size={16} />
                    <span>{notice}</span>
                </div>
            )}

            {/* Search + date controls */}
            <div className="rec-controls">
                <div className="rec-search-wrap">
                    <Search size={15} className="rec-search-icon" />
                    <input
                        type="text"
                        className="rec-search"
                        placeholder="Search by appointment ID, patient name, or phone number…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                    {query && (
                        <button className="rec-search-clear" onClick={() => setQuery('')} aria-label="Clear search">
                            <X size={14} />
                        </button>
                    )}
                </div>
                <div className="rec-date-group">
                    <label className="rec-date-label">Ops date</label>
                    <select
                        className="dir-select"
                        value={opsDate}
                        onChange={(e) => { setOpsDate(e.target.value); setSelectedId(null) }}
                    >
                        {opsDates.map((d) => (
                            <option key={d} value={d}>{fmtDate(d)}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Appointments */}
            <div className="dash-section-label">
                📅 {query.trim() ? `Search Results (${rows.length})` : `Appointments · ${fmtDate(opsDate)} (${rows.length})`}
            </div>
            {rows.length === 0 ? (
                <div className="dash-empty-msg">
                    No appointments found{query.trim() ? ` matching “${query.trim()}”` : ' for this date'}.
                </div>
            ) : (
                <div className="rec-appt-grid">
                    {rows.slice(0, 60).map((a) => (
                        <button
                            key={a.appointment_id}
                            className="rec-appt-card"
                            onClick={() => setSelectedId(a.appointment_id)}
                        >
                            <div className="rec-appt-top">
                                <span className="rec-appt-time">{fmtClock(a.time)}</span>
                                <StatusPill status={a.status} />
                            </div>
                            <div className="rec-appt-patient">{patientLabel(a)}</div>
                            <div className="rec-appt-doc">
                                <Stethoscope size={13} /> {a.doctor_name}
                                <span className="rec-appt-spec"> · {a.speciality}</span>
                            </div>
                            <div className="rec-appt-foot">
                                <span className="rec-appt-id">#{a.appointment_id}</span>
                                <span className="rec-appt-view">View details →</span>
                            </div>
                        </button>
                    ))}
                </div>
            )}

            {/* Doctor profiles */}
            <div className="dash-section-label" style={{ marginTop: '1.5rem' }}>
                🩺 Doctor Profiles ({doctors.length})
            </div>
            <div className="rec-doc-grid">
                {doctors.slice(0, 60).map((d) => {
                    const name = d.name || d.doctor_name || 'Unknown'
                    const av = doctorAvatar(name)
                    const slots = d.open_slots ?? d.total_available_slots ?? 0
                    return (
                        <div key={d.id || d.doctor_id || name} className="rec-doc-card">
                            <div className="rec-doc-head">
                                <div className="rec-doc-avatar" style={{ borderColor: av.color }}>
                                    <span className="rec-doc-emoji">{av.emoji}</span>
                                </div>
                                <div className="rec-doc-meta">
                                    <div className="rec-doc-name" title={name}>{name}</div>
                                    <div className="rec-doc-dept">{d.speciality || 'General'}</div>
                                </div>
                            </div>
                            {d.designation && (
                                <div className="rec-doc-line">🎓 {d.designation}</div>
                            )}
                            <div className="rec-doc-badges">
                                {slots > 0
                                    ? <span className="dash-pill green">🟢 {slots} slots</span>
                                    : <span className="dash-pill muted">🔴 No slots</span>}
                                {d.city && <span className="dash-pill blue">📍 {d.city}</span>}
                            </div>
                            {d.booking_url ? (
                                <a className="rec-doc-book" href={d.booking_url} target="_blank" rel="noreferrer">
                                    📅 Book Appointment <ExternalLink size={12} />
                                </a>
                            ) : (
                                <span className="rec-doc-book disabled">📅 Book Appointment</span>
                            )}
                        </div>
                    )
                })}
            </div>

            {/* Appointment detail modal */}
            {selected && (
                <AppointmentModal
                    appt={selected}
                    clientId={clientId}
                    busy={busy}
                    onAction={runAction}
                    onClose={() => setSelectedId(null)}
                />
            )}
        </div>
    )
}

/* ────────────────────────── SUB COMPONENTS ────────────────────────── */

function KpiCard({ title, value, sub, icon, colorClass }) {
    return (
        <div className={`dash-kpi-card ${colorClass}`}>
            <div className="dash-kpi-header">
                <span className="dash-kpi-title">{title}</span>
                <div className="dash-kpi-icon-wrap">{icon}</div>
            </div>
            <div className="dash-kpi-val">{fmt(value)}</div>
            <div className="dash-kpi-sub">{sub}</div>
        </div>
    )
}

function AppointmentList({ items, emptyMsg }) {
    if (!items || items.length === 0) {
        return <div className="dash-empty-msg">{emptyMsg}</div>
    }
    return (
        <ul className="dash-appt-list">
            {items.map((a) => {
                const isBooked = a.status === 'booked'
                const isCancel = a.status === 'cancelled'
                return (
                    <li key={a.appointment_id} className="dash-appt-item">
                        <div className="dash-appt-left">
                            <span className="dash-appt-time">{a.time}</span>
                            <div className="dash-appt-info">
                                <span className="dash-appt-doc">{a.doctor_name}</span>
                                <span className="dash-appt-sub">
                                    {a.speciality} · {a.patient_phone}
                                </span>
                            </div>
                        </div>
                        <span className={`d-status-pill ${a.status}`}>
                            {a.status}
                        </span>
                    </li>
                )
            })}
        </ul>
    )
}

function DoctorAvailabilityTable({ doctors }) {
    if (!doctors || doctors.length === 0) {
        return <div className="dash-empty-msg">No matching doctor availability records found.</div>
    }
    return (
        <div style={{ overflowX: 'auto' }}>
            <table className="dash-table">
                <thead>
                    <tr>
                        <th>Doctor</th>
                        <th>Speciality</th>
                        <th>Location</th>
                        <th>Experience</th>
                        <th style={{ textAlign: 'right' }}>Open Slots</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {doctors.map((d) => {
                        const name = d.name || d.doctor_name || 'Unknown'
                        const slots = d.open_slots ?? d.total_available_slots ?? 0
                        return (
                            <tr key={d.id || d.doctor_id || name}>
                                <td className="doc-name">{name}</td>
                                <td>{d.speciality || 'General'}</td>
                                <td>
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                        <MapPin size={12} color="#8b949e" />
                                        {d.city || 'Unknown'}
                                    </span>
                                </td>
                                <td>{d.experience_years ? `${d.experience_years} yrs` : '—'}</td>
                                <td style={{ textAlign: 'right' }}>
                                    {slots > 0 ? (
                                        <span className="slot-badge">{slots} slots</span>
                                    ) : (
                                        <span className="dash-pill muted">0 slots</span>
                                    )}
                                </td>
                                <td>
                                    {d.booking_url ? (
                                        <a className="book-link-sm" href={d.booking_url} target="_blank" rel="noreferrer">
                                            Book <ExternalLink size={10} />
                                        </a>
                                    ) : '—'}
                                </td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}

function RecentActivityTable({ items }) {
    if (!items || items.length === 0) {
        return <div className="dash-empty-msg">No recent activity logged.</div>
    }
    return (
        <div style={{ overflowX: 'auto' }}>
            <table className="dash-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Doctor</th>
                        <th>Date &amp; Time</th>
                        <th>Patient Phone</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {items.map((r) => (
                        <tr key={r.appointment_id}>
                            <td style={{ color: '#8b949e' }}>{fmtTime(r.created_at)}</td>
                            <td className="doc-name">{r.doctor_name}</td>
                            <td>{r.date} at {r.time}</td>
                            <td style={{ color: '#8b949e' }}>{r.patient_phone}</td>
                            <td>
                                <span className={`d-status-pill ${r.action}`}>
                                    {r.action}
                                </span>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}

/* ────────────────────────── RECEPTIONIST COCKPIT ────────────────────────── */

function CockpitKpi({ label, value, color }) {
    return (
        <div className={`cockpit-kpi ${color}`}>
            <div className="cockpit-kpi-label">{label}</div>
            <div className="cockpit-kpi-value">{fmt(value)}</div>
        </div>
    )
}

function ReceptionistCockpit({ data, clientId, onChanged }) {
    const [opsDate, setOpsDate] = useState(data.ops_date || data.today || '')
    const [query, setQuery] = useState('')
    const [selectedId, setSelectedId] = useState(null)
    const [busy, setBusy] = useState('')
    const [notice, setNotice] = useState('')

    const all = data.recent_appointments || []
    const opsDates = (data.ops_dates && data.ops_dates.length) ? data.ops_dates : [opsDate]
    const day = useMemo(() => all.filter((a) => a.date === opsDate), [all, opsDate])

    const rows = useMemo(() => {
        const q = query.trim().toLowerCase()
        return day
            .filter((a) =>
                !q ||
                (a.patient_name || '').toLowerCase().includes(q) ||
                String(a.patient_phone || '').includes(q)
            )
            .sort((a, b) => (a.time || '').localeCompare(b.time || ''))
    }, [day, query])

    const count = (status) => day.filter((a) => a.status === status).length
    const summary = [
        { label: 'Appointments Booked', value: count('booked'),      color: 'blue' },
        { label: 'Completed',           value: count('completed'),   color: 'green' },
        { label: 'Checked In',          value: count('checked_in'),  color: 'green' },
        { label: 'Cancelled',           value: count('cancelled'),   color: 'red' },
        { label: 'Rescheduled',         value: count('rescheduled'), color: 'amber' },
        { label: 'Pending',             value: count('pending'),     color: 'amber' },
        { label: 'Walk-in Patients',    value: day.filter((a) => a.booked_through === 'Walk-in').length,  color: 'purple' },
        { label: 'WhatsApp Bookings',   value: day.filter((a) => a.booked_through === 'WhatsApp').length, color: 'green' },
        { label: 'Reception Bookings',  value: day.filter((a) => a.booked_through === 'Reception').length, color: 'blue' },
    ]
    const overview = [
        { label: "Today's Appointments",   value: day.length,                                                        color: 'blue' },
        { label: 'Checked-In Patients',    value: count('checked_in'),                                               color: 'green' },
        { label: 'Upcoming Appointments',  value: all.filter((a) => a.date > opsDate && a.status === 'booked').length, color: 'purple' },
        { label: 'Cancelled Appointments', value: count('cancelled'),                                                color: 'red' },
        { label: 'Doctors Available',      value: (data.doctor_availability || []).length,                           color: 'green' },
        { label: 'Pending Requests',       value: all.filter((a) => a.status === 'pending').length,                  color: 'amber' },
    ]

    const runAction = async (action, successMsg, busyMsg) => {
        setBusy(busyMsg)
        try {
            await action()
            setNotice(successMsg)
            setSelectedId(null)
            onChanged()
        } catch (err) {
            setNotice(`⚠️ ${err.message || 'Action failed'}`)
        } finally {
            setBusy('')
        }
    }

    const selected = all.find((a) => a.appointment_id === selectedId) || null

    return (
        <div className="receptionist-cockpit">
            <div className="dash-section-label">🩺 Receptionist Desk · {fmtDate(opsDate)} <span style={{ fontSize: '.72rem', color: '#8fa3b8', fontWeight: 400 }}>· auto-refreshes every 30s</span></div>
            <div className="ops-date-row">
                <label className="ops-date-label">Operations date</label>
                <select
                    className="dir-select"
                    value={opsDate}
                    onChange={(e) => { setOpsDate(e.target.value); setSelectedId(null) }}
                >
                    {opsDates.map((d) => (
                        <option key={d} value={d}>{fmtDate(d)}</option>
                    ))}
                </select>
            </div>

            {notice && (
                <div className="dash-alert-item info" style={{ marginBottom: '.5rem' }}>
                    <Info size={16} />
                    <span>{notice}</span>
                </div>
            )}

            <div className="dash-section-label">📊 Today's Summary</div>
            <div className="cockpit-kpi-grid">
                {summary.map((k) => (
                    <CockpitKpi key={k.label} label={k.label} value={k.value} color={k.color} />
                ))}
            </div>

            <div className="dash-section-label">Overview</div>
            <div className="cockpit-kpi-grid">
                {overview.map((k) => (
                    <CockpitKpi key={k.label} label={k.label} value={k.value} color={k.color} />
                ))}
            </div>

            <div className="dash-section-label">🔍 Search Patient</div>
            <input
                type="text"
                className="dir-input cockpit-search"
                placeholder="Name or phone number…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
            />

            <div className="dash-section-label">📅 Today's Appointments ({rows.length})</div>
            {rows.length === 0 ? (
                <div className="dash-empty-msg">
                    No appointments found{query.trim() ? ` matching “${query.trim()}”` : ''}.
                </div>
            ) : (
                <div className="cockpit-table-wrap">
                    <table className="dash-table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Patient</th>
                                <th>Doctor</th>
                                <th>Status</th>
                                <th style={{ textAlign: 'right' }}>View</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.slice(0, 50).map((a) => (
                                <tr key={a.appointment_id}>
                                    <td className="cockpit-time">{fmtClock(a.time)}</td>
                                    <td>
                                        <div className="cockpit-name">{patientLabel(a)}</div>
                                        <div className="cockpit-sub">{a.patient_phone}</div>
                                    </td>
                                    <td>
                                        <div className="cockpit-name">{a.doctor_name}</div>
                                        <div className="cockpit-sub">{a.speciality}</div>
                                    </td>
                                    <td><StatusPill status={a.status} /></td>
                                    <td style={{ textAlign: 'right' }}>
                                        <button className="cockpit-view-btn" onClick={() => setSelectedId(a.appointment_id)}>
                                            👁 View
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="dash-section-label">🩺 Doctor Availability</div>
            {(data.doctor_availability || []).length === 0 ? (
                <div className="dash-empty-msg">No open slots from this date onwards.</div>
            ) : (
                <div className="cockpit-table-wrap">
                    <table className="dash-table">
                        <thead>
                            <tr>
                                <th>Doctor</th>
                                <th>Department</th>
                                <th style={{ textAlign: 'right' }}>Slots</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.doctor_availability.map((d) => (
                                <tr key={d.doctor_id || d.doctor_name}>
                                    <td className="doc-name">{d.doctor_name}</td>
                                    <td>{d.speciality || 'General'}</td>
                                    <td style={{ textAlign: 'right' }}>
                                        {d.open_slots > 0
                                            ? <span className="slot-badge">{d.open_slots} slots</span>
                                            : <span className="dash-pill muted">0 slots</span>}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {selected && (
                <AppointmentDetailPanel
                    appt={selected}
                    clientId={clientId}
                    busy={busy}
                    onAction={runAction}
                    onClose={() => setSelectedId(null)}
                />
            )}
        </div>
    )
}

function AppointmentDetailPanel({ appt, clientId, busy, onAction, onClose }) {
    const [rescheduleOpen, setRescheduleOpen] = useState(false)
    const [slots, setSlots] = useState([])
    const [newSlot, setNewSlot] = useState('')
    const [slotError, setSlotError] = useState('')
    const [tokenOpen, setTokenOpen] = useState(false)

    const openReschedule = async () => {
        setSlotError('')
        setSlots([])
        setRescheduleOpen(true)
        try {
            const res = await getUpcomingSlots(appt.doctor_id, clientId)
            setSlots(res.slots || [])
            if (res.slots && res.slots.length) {
                setNewSlot(`${res.slots[0].date}|${res.slots[0].time}`)
            } else {
                setSlotError('No available slots for this doctor in the next 14 days.')
            }
        } catch (err) {
            setSlotError(err.message || 'Failed to load slots')
        }
    }

    const age = appt.age ? String(appt.age) : '—'
    const detailRows = [
        ['Appointment ID', appt.appointment_id],
        ['Patient Name', patientLabel(appt)],
        ['Age', age],
        ['Gender', appt.gender || '—'],
        ['Problem / Reason', appt.notes || '—'],
        ['Mobile', appt.patient_phone || '—'],
        ['City', appt.city || '—'],
        ['Department', appt.speciality || '—'],
        ['Doctor', appt.doctor_name],
        ['Appointment Date', fmtDate(appt.date)],
        ['Time Slot', fmtClock(appt.time)],
        ['Status', STATUS_META[appt.status]?.label || appt.status],
        ['Booked Through', appt.booked_through || '—'],
    ]

    return (
        <div className="appt-detail-panel">
            <div className="appt-detail-header">
                <span className="appt-detail-title">📋 Appointment Details</span>
                <StatusPill status={appt.status} />
            </div>
            <div className="appt-detail-grid">
                {detailRows.map(([k, v]) => (
                    <div className="appt-detail-item" key={k}>
                        <span className="k">{k}</span>
                        <span className="v">{v}</span>
                    </div>
                ))}
            </div>
            <div className="appt-detail-sep" />
            <div className="appt-medical">
                <div className="bk">Medical History</div>
                <div className="bv">{appt.medical_history || '—'}</div>
                <div className="bk">Previous Visit</div>
                <div className="bv">{appt.previous_visit || '—'}</div>
            </div>

            <div className="appt-detail-sep" />
            <div className="appt-actions">
                <button
                    className="cockpit-act-btn green"
                    disabled={!!busy}
                    onClick={() =>
                        onAction(
                            () => checkInAppointment({ appointment_id: appt.appointment_id, client_id: clientId }),
                            'Patient checked in ✅',
                            'Checking in…'
                        )
                    }
                >
                    ✅ Check-In
                </button>
                <button className="cockpit-act-btn amber" disabled={!!busy} onClick={openReschedule}>
                    🔄 Reschedule
                </button>
                <button
                    className="cockpit-act-btn red"
                    disabled={!!busy}
                    onClick={() =>
                        onAction(
                            () => cancelAppointment({ appointment_id: appt.appointment_id, client_id: clientId }),
                            'Appointment cancelled ❌',
                            'Cancelling…'
                        )
                    }
                >
                    ❌ Cancel Appointment
                </button>
                <button className="cockpit-act-btn blue" disabled={!!busy} onClick={() => setTokenOpen(true)}>
                    🖨️ Print Token
                </button>
                <a className="cockpit-act-btn blue" href={whatsappReminderUrl(appt)} target="_blank" rel="noreferrer">
                    💬 WhatsApp Reminder
                </a>
                <button className="cockpit-act-btn muted" disabled={!!busy} onClick={onClose}>
                    ✕ Close
                </button>
            </div>

            {rescheduleOpen && (
                <div className="reschedule-box">
                    <div className="cockpit-name" style={{ marginBottom: '.4rem' }}>Select new slot</div>
                    {slotError ? (
                        <div className="dash-empty-msg">{slotError}</div>
                    ) : (
                        <select className="dir-select" value={newSlot} onChange={(e) => setNewSlot(e.target.value)}>
                            {slots.map((s) => (
                                <option key={`${s.date}|${s.time}`} value={`${s.date}|${s.time}`}>
                                    {fmtDate(s.date)} · {fmtClock(s.time)}
                                </option>
                            ))}
                        </select>
                    )}
                    <div className="reschedule-actions">
                        <button
                            className="cockpit-act-btn green"
                            disabled={!!busy || !newSlot}
                            onClick={() => {
                                const [d, t] = newSlot.split('|')
                                onAction(
                                    () => rescheduleAppointment({ appointment_id: appt.appointment_id, new_date: d, new_time: t, client_id: clientId }),
                                    `Rescheduled to ${fmtDate(d)} ${fmtClock(t)} 🔄`,
                                    'Rescheduling…'
                                )
                            }}
                        >
                            Confirm Reschedule
                        </button>
                        <button className="cockpit-act-btn muted" disabled={!!busy} onClick={() => setRescheduleOpen(false)}>
                            Cancel
                        </button>
                    </div>
                </div>
            )}

            {tokenOpen && <TokenCard appt={appt} onClose={() => setTokenOpen(false)} />}
        </div>
    )
}

function TokenCard({ appt, onClose }) {
    const tokenNo = `TK-${String(appt.appointment_id || '').slice(-6).toUpperCase()}`
    return (
        <div className="token-overlay" onClick={onClose}>
            <div className="token-modal" onClick={(e) => e.stopPropagation()}>
                <div className="token-modal-actions">
                    <button className="cockpit-act-btn green" onClick={() => window.print()}>
                        🖨️ Print Token
                    </button>
                    <button className="cockpit-act-btn muted" onClick={onClose}>✕ Close</button>
                </div>
                <div id="token-print-area" className="token-card">
                    <div className="token-hosp">GLENEAGLES HOSPITALS</div>
                    <div className="token-sub">OPD APPOINTMENT TOKEN</div>
                    <div className="token-no">{tokenNo}</div>
                    <table className="token-table">
                        <tbody>
                            <tr><td>Patient</td><td>{patientLabel(appt)}</td></tr>
                            <tr><td>Doctor</td><td>{appt.doctor_name}</td></tr>
                            <tr><td>Department</td><td>{appt.speciality || '—'}</td></tr>
                            <tr><td>Date</td><td>{fmtDate(appt.date)}</td></tr>
                            <tr><td>Time</td><td>{fmtClock(appt.time)}</td></tr>
                        </tbody>
                    </table>
                    <div className="token-foot">Please arrive 15 minutes early and carry this token</div>
                </div>
            </div>
        </div>
    )
}

/* ── Appointment detail modal (centered overlay wrapper) ── */
function AppointmentModal({ appt, clientId, busy, onAction, onClose }) {
    return (
        <div className="appt-modal-overlay" onClick={onClose}>
            <div className="appt-modal" onClick={(e) => e.stopPropagation()}>
                <button className="appt-modal-close" onClick={onClose} aria-label="Close">
                    <X size={18} />
                </button>
                <AppointmentDetailPanel
                    appt={appt}
                    clientId={clientId}
                    busy={busy}
                    onAction={onAction}
                    onClose={onClose}
                />
            </div>
        </div>
    )
}