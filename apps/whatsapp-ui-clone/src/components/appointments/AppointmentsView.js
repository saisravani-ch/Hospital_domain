import React, { useState } from 'react'
import {
    checkAvailability,
    bookAppointment,
    rescheduleAppointment,
    cancelAppointment,
} from '../../api/workflows'
import { getConfig } from '../../api/config'

const SUB_TABS = ['Check Availability', 'Book', 'Reschedule', 'Cancel']

function todayISO() {
    const d = new Date()
    const off = d.getTimezoneOffset()
    return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
}

export default function AppointmentsView() {
    const [tab, setTab] = useState('Check Availability')

    return (
        <div className="tool-view">
            <div className="tool-view-header">
                <h2>📅 Appointment Workflows</h2>
            </div>

            <div className="sub-tabs">
                {SUB_TABS.map((t) => (
                    <button
                        key={t}
                        className={`sub-tab ${tab === t ? 'active' : ''}`}
                        onClick={() => setTab(t)}
                    >
                        {t}
                    </button>
                ))}
            </div>

            {tab === 'Check Availability' && <AvailabilityTab />}
            {tab === 'Book' && <BookTab />}
            {tab === 'Reschedule' && <RescheduleTab />}
            {tab === 'Cancel' && <CancelTab />}
        </div>
    )
}

function ResultBox({ result, error }) {
    if (error) return <div className="alert-error">{error}</div>
    if (!result) return null
    return (
        <div className="result-box">
            <pre className="json-block">{JSON.stringify(result, null, 2)}</pre>
        </div>
    )
}

function AvailabilityTab() {
    const [docId, setDocId] = useState('')
    const [date, setDate] = useState(todayISO())
    const [clientId, setClientId] = useState(() => getConfig().clientId)
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState('')

    async function run() {
        if (!docId.trim()) return
        setLoading(true)
        setError('')
        setResult(null)
        try {
            const data = await checkAvailability(docId, date, clientId)
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card">
            <h3>Check Available Slots</h3>
            <div className="search-row">
                <div className="field grow">
                    <span>Doctor ID</span>
                    <input value={docId} onChange={(e) => setDocId(e.target.value)} placeholder="dr-..." />
                </div>
                <div className="field narrow">
                    <span>Date</span>
                    <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                </div>
                <div className="field narrow">
                    <span>Client ID</span>
                    <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="e.g. gleneagles_001" />
                </div>
                <div className="field auto">
                    <button className="btn" onClick={run} disabled={loading || !docId.trim()}>
                        {loading ? 'Checking...' : '🔍 Check'}
                    </button>
                </div>
            </div>
            <ResultBox result={result} error={error} />
            {result && !result.slots?.length && (
                <div className="alert-info">No slots available on this date.</div>
            )}
            {result && result.slots?.length > 0 && (
                <div className="slot-list">
                    {result.slots.map((s) => (
                        <span key={s.slot_id} className="slot-chip">
                            🕐 {s.time} ({s.period || 'day'}) — {s.slot_id}
                        </span>
                    ))}
                </div>
            )}
        </div>
    )
}

function BookTab() {
    const [form, setForm] = useState({
        doctor_id: '',
        patient_phone: '',
        date: todayISO(),
        time: '',
        client_id: getConfig().clientId,
        notes: '',
    })
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState('')

    function set(field, value) {
        setForm((f) => ({ ...f, [field]: value }))
    }

    async function run() {
        const { doctor_id, patient_phone, date, time } = form
        if (!doctor_id.trim() || !patient_phone.trim() || !time.trim()) return
        setLoading(true)
        setError('')
        setResult(null)
        try {
            const data = await bookAppointment(form)
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const ready = form.doctor_id && form.patient_phone && form.time

    return (
        <div className="card">
            <h3>Book Appointment</h3>
            <div className="grid-2">
                <div className="field">
                    <span>Doctor ID</span>
                    <input value={form.doctor_id} onChange={(e) => set('doctor_id', e.target.value)} placeholder="dr-..." />
                </div>
                <div className="field">
                    <span>Patient Phone</span>
                    <input value={form.patient_phone} onChange={(e) => set('patient_phone', e.target.value)} placeholder="e.g. +919999999999" />
                </div>
                <div className="field">
                    <span>Date</span>
                    <input type="date" value={form.date} onChange={(e) => set('date', e.target.value)} />
                </div>
                <div className="field">
                    <span>Time</span>
                    <input value={form.time} onChange={(e) => set('time', e.target.value)} placeholder="10:30" />
                </div>
                <div className="field">
                    <span>Client ID</span>
                    <input value={form.client_id} onChange={(e) => set('client_id', e.target.value)} placeholder="e.g. gleneagles_001" />
                </div>
                <div className="field">
                    <span>Notes (optional)</span>
                    <input value={form.notes} onChange={(e) => set('notes', e.target.value)} placeholder="Reason for visit" />
                </div>
            </div>
            <button className="btn" onClick={run} disabled={loading || !ready}>
                {loading ? 'Booking...' : '📅 Book Appointment'}
            </button>
            <ResultBox result={result} error={error} />
        </div>
    )
}

function RescheduleTab() {
    const [form, setForm] = useState({
        appointment_id: '',
        new_date: todayISO(),
        new_time: '',
        client_id: getConfig().clientId,
    })
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState('')

    function set(field, value) {
        setForm((f) => ({ ...f, [field]: value }))
    }

    async function run() {
        if (!form.appointment_id.trim() || !form.new_time.trim()) return
        setLoading(true)
        setError('')
        setResult(null)
        try {
            const data = await rescheduleAppointment(form)
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card">
            <h3>Reschedule Appointment</h3>
            <div className="grid-2">
                <div className="field">
                    <span>Appointment ID</span>
                    <input value={form.appointment_id} onChange={(e) => set('appointment_id', e.target.value)} placeholder="apt_..." />
                </div>
                <div className="field">
                    <span>New Date</span>
                    <input type="date" value={form.new_date} onChange={(e) => set('new_date', e.target.value)} />
                </div>
                <div className="field">
                    <span>New Time</span>
                    <input value={form.new_time} onChange={(e) => set('new_time', e.target.value)} placeholder="14:00" />
                </div>
                <div className="field">
                    <span>Client ID</span>
                    <input value={form.client_id} onChange={(e) => set('client_id', e.target.value)} placeholder="e.g. gleneagles_001" />
                </div>
            </div>
            <button className="btn" onClick={run} disabled={loading || !form.appointment_id || !form.new_time}>
                {loading ? 'Rescheduling...' : '🔄 Reschedule'}
            </button>
            <ResultBox result={result} error={error} />
        </div>
    )
}

function CancelTab() {
    const [appointmentId, setAppointmentId] = useState('')
    const [clientId, setClientId] = useState(() => getConfig().clientId)
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState('')

    async function run() {
        if (!appointmentId.trim()) return
        setLoading(true)
        setError('')
        setResult(null)
        try {
            const data = await cancelAppointment({ appointment_id: appointmentId, client_id: clientId })
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card">
            <h3>Cancel Appointment</h3>
            <div className="search-row">
                <div className="field grow">
                    <span>Appointment ID</span>
                    <input value={appointmentId} onChange={(e) => setAppointmentId(e.target.value)} placeholder="apt_..." />
                </div>
                <div className="field narrow">
                    <span>Client ID</span>
                    <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="e.g. gleneagles_001" />
                </div>
                <div className="field auto">
                    <button className="btn" onClick={run} disabled={loading || !appointmentId.trim()}>
                        {loading ? 'Cancelling...' : '❌ Cancel'}
                    </button>
                </div>
            </div>
            <ResultBox result={result} error={error} />
        </div>
    )
}
