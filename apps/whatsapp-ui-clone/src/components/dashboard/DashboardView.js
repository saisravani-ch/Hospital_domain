import React, { useState, useEffect, useCallback } from 'react'
import { getDashboard } from '../../api/dashboard'

// Accent colors (Gleneagles dark theme)
const ACCENT = ['#58a6ff', '#3fb950', '#e3b341', '#d2a8ff', '#f85149', '#f0883e', '#39c5cf', '#bc8cff']

function fmt(n) {
    return (n === null || n === undefined) ? '—' : Number(n).toLocaleString();
}

function statusClass(status) {
    if (status === 'booked') return 'd-status booked'
    if (status === 'cancelled') return 'd-status cancelled'
    if (status === 'rescheduled') return 'd-status rescheduled'
    return 'd-status'
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

export default function DashboardView({ config }) {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const clientId = (config && config.clientId) || 'gleneagles_001'

    const load = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const d = await getDashboard(clientId)
            setData(d)
        } catch (err) {
            setError(err.message || 'Failed to load dashboard')
            setData(null)
        } finally {
            setLoading(false)
        }
    }, [clientId])

    useEffect(() => {
        load()
    }, [load])

    return (
        <div className="dash">
            <div className="dash-hero">
                <div>
                    <h1>📊 Monitoring Dashboard</h1>
                    <p className="dash-sub">
                        {data ? `${data.client_name} · ${data.today}` : 'Operational overview + network analytics'}
                    </p>
                </div>
                <div className="dash-hero-right">
                    {data && data.generated_at && (
                        <span className="dash-last-updated">Updated {fmtTime(data.generated_at)}</span>
                    )}
                    <button className="btn dash-refresh" onClick={load} disabled={loading}>
                        {loading ? 'Loading…' : '🔄 Refresh'}
                    </button>
                </div>
            </div>

            {error && <div className="alert-error dash-error">⚠️ {error}</div>}

            {loading && !data && (
                <div className="dash-loading">Loading dashboard data…</div>
            )}

            {data && (
                <>
                    <ReceptionistOps data={data} />
                    <Analytics data={data} />
                </>
            )}
        </div>
    )
}

/* ────────────────────────── OPS ────────────────────────── */

function ReceptionistOps({ data }) {
    const s = data.summary || {}
    return (
        <section className="dash-section">
            <h2 className="dash-sec-title">🩺 Today &amp; Availability</h2>

            {data.alerts && data.alerts.length > 0 && (
                <div className="dash-alerts">
                    {data.alerts.map((a, i) => (
                        <div
                            key={i}
                            className={`dash-alert ${a.level === 'warn' ? 'warn' : 'info'}`}
                        >
                            {a.level === 'warn' ? '⚠️' : 'ℹ️'} {a.text}
                        </div>
                    ))}
                </div>
            )}

            <div className="dash-kpis">
                <Kpi label="Today · Booked" value={s.today_booked} accent="#3fb950" />
                <Kpi label="Today · Cancelled" value={s.today_cancelled} accent="#f85149" />
                <Kpi label="Upcoming Booked" value={s.upcoming} accent="#58a6ff" />
                <Kpi label="Open Slots Today" value={s.open_slots_today} accent="#e3b341" />
                <Kpi label="Open Slots · 7 Days" value={s.open_slots_7d} accent="#d2a8ff" />
                <Kpi label="Doctors Available" value={s.doctors_with_slots} accent="#39c5cf" />
            </div>

            <div className="dash-cols">
                <div className="dash-card">
                    <h3>📌 Today's Appointments</h3>
                    <ApptList items={data.today_appointments} empty="No appointments scheduled for today." />
                </div>
                <div className="dash-card">
                    <h3>📅 Upcoming Appointments</h3>
                    <ApptList items={data.upcoming_appointments} empty="No upcoming booked appointments." />
                </div>
            </div>

            <div className="dash-card">
                <h3>🩺 Doctors with Most Open Slots</h3>
                {data.doctor_availability && data.doctor_availability.length ? (
                    <table className="dash-table">
                        <thead>
                            <tr>
                                <th>Doctor</th>
                                <th>Speciality</th>
                                <th>Location</th>
                                <th className="num">Open Slots</th>
                                <th>Next Available</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.doctor_availability.map((d) => (
                                <tr key={d.doctor_id}>
                                    <td className="strong">{d.doctor_name}</td>
                                    <td>{d.speciality}</td>
                                    <td>{d.city}</td>
                                    <td className="num slot-num">{d.open_slots}</td>
                                    <td className="muted">{d.next_available || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <p className="dash-empty">No availability data.</p>
                )}
            </div>
        </section>
    )
}

function ApptList({ items, empty }) {
    if (!items || items.length === 0) {
        return <p className="dash-empty">{empty}</p>
    }
    return (
        <ul className="dash-appt-list">
            {items.map((a) => (
                <li key={a.appointment_id} className="dash-appt">
                    <span className="dash-time">{a.time}</span>
                    <span className="dash-appt-body">
                        <span className="strong">{a.doctor_name}</span>
                        <span className="muted">{a.speciality} · {a.patient_phone}</span>
                    </span>
                    <span className={statusClass(a.status)}>{a.status}</span>
                </li>
            ))}
        </ul>
    )
}

/* ────────────────────────── ANALYTICS ────────────────────────── */

function Analytics({ data }) {
    const s = data.summary || {}
    const a = data.analytics || {}
    const maxSpec = Math.max(1, ...(a.top_specializations || []).map((x) => x.count))
    const maxLang = Math.max(1, ...(a.languages || []).map((x) => x.count))

    return (
        <section className="dash-section">
            <h2 className="dash-sec-title">📈 Network Analytics</h2>

            <div className="dash-kpis">
                <Kpi label="Total Doctors" value={s.total_doctors} accent="#58a6ff" />
                <Kpi label="Hospitals" value={s.total_hospitals} accent="#3fb950" />
                <Kpi label="Specialties" value={s.specialties} accent="#e3b341" />
                <Kpi label="Avg Experience" value={s.avg_experience ? `${s.avg_experience}y` : '—'} accent="#d2a8ff" />
                <Kpi label="Total Appointments" value={s.total_appointments} accent="#f0883e" />
                <Kpi label="Lifetime Cancelled" value={s.total_cancelled} accent="#f85149" />
            </div>

            <div className="dash-cols">
                <div className="dash-card">
                    <h3>🏥 Top Specializations</h3>
                    {a.top_specializations && a.top_specializations.length ? (
                        <ul className="dash-bars">
                            {a.top_specializations.map((x, i) => (
                                <li key={i} className="dash-bar-row">
                                    <span className="dash-bar-label">{x.name}</span>
                                    <div className="dash-bar-track">
                                        <div
                                            className="dash-bar-fill"
                                            style={{
                                                width: `${(x.count / maxSpec) * 100}%`,
                                                background: ACCENT[i % ACCENT.length],
                                            }}
                                        />
                                    </div>
                                    <span className="dash-bar-val">{x.count}</span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="dash-empty">No data.</p>
                    )}
                </div>

                <div className="dash-card">
                    <h3>🗣️ Languages Spoken</h3>
                    {a.languages && a.languages.length ? (
                        <ul className="dash-bars">
                            {a.languages.map((x, i) => (
                                <li key={i} className="dash-bar-row">
                                    <span className="dash-bar-label">{x.language}</span>
                                    <div className="dash-bar-track">
                                        <div
                                            className="dash-bar-fill"
                                            style={{
                                                width: `${(x.count / maxLang) * 100}%`,
                                                background: ACCENT[i % ACCENT.length],
                                            }}
                                        />
                                    </div>
                                    <span className="dash-bar-val">{x.count}</span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="dash-empty">No data.</p>
                    )}
                </div>
            </div>

            <div className="dash-cols">
                <div className="dash-card">
                    <h3>📍 Open Slots by City</h3>
                    <CitySlots rows={a.slots_by_city || []} />
                </div>
                <div className="dash-card">
                    <h3>🧑‍⚕️ Designation Mix</h3>
                    <Designations rows={a.designation_mix || []} />
                </div>
            </div>

            <div className="dash-card">
                <h3>🕑 Recent Appointment Activity</h3>
                <Activity rows={data.recent_activity || []} />
            </div>
        </section>
    )
}

function CitySlots({ rows }) {
    if (!rows.length) return <p className="dash-empty">No data.</p>
    const max = Math.max(1, ...rows.map((r) => r.slots))
    return (
        <ul className="dash-bars">
            {rows.map((r, i) => (
                <li key={r.city} className="dash-bar-row">
                    <span className="dash-bar-label">{r.city}</span>
                    <div className="dash-bar-track">
                        <div
                            className="dash-bar-fill"
                            style={{ width: `${(r.slots / max) * 100}%`, background: ACCENT[i % ACCENT.length] }}
                        />
                    </div>
                    <span className="dash-bar-val">{r.slots.toLocaleString()}</span>
                </li>
            ))}
        </ul>
    )
}

function Designations({ rows }) {
    if (!rows.length) return <p className="dash-empty">No data.</p>
    return (
        <ul className="dash-plain">
            {rows.map((r, i) => (
                <li key={i} className="dash-plain-row">
                    <span>{r.designation}</span>
                    <span className="dash-count">{r.count}</span>
                </li>
            ))}
        </ul>
    )
}

function Activity({ rows }) {
    if (!rows.length) return <p className="dash-empty">No recent activity.</p>
    return (
        <table className="dash-table">
            <thead>
                <tr>
                    <th>When</th>
                    <th>Doctor</th>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Patient</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {rows.map((r) => (
                    <tr key={r.appointment_id}>
                        <td className="muted">{fmtTime(r.created_at)}</td>
                        <td className="strong">{r.doctor_name}</td>
                        <td>{r.date}</td>
                        <td>{r.time}</td>
                        <td className="muted">{r.patient_phone}</td>
                        <td><span className={statusClass(r.action)}>{r.action}</span></td>
                    </tr>
                ))}
            </tbody>
        </table>
    )
}

function Kpi({ label, value, accent }) {
    return (
        <div className="dash-kpi">
            <div className="dash-kpi-value" style={{ color: accent }}>{value}</div>
            <div className="dash-kpi-label">{label}</div>
        </div>
    )
}