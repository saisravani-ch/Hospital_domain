import { getConfig } from './config'

async function request(url, options) {
    const response = await fetch(url, options)
    if (!response.ok) {
        let detail = `Request failed: ${response.status}`
        try {
            const data = await response.json()
            if (data && data.detail) {
                detail =
                    typeof data.detail === 'string'
                        ? data.detail
                        : JSON.stringify(data.detail)
            }
        } catch (e) {
            /* not JSON — keep default message */
        }
        throw new Error(detail)
    }
    return response.json()
}

function base() {
    return getConfig().workflows
}

/** Check available slots — GET /appointments/availability. */
export function checkAvailability(doctorId, date, clientId) {
    const cfg = getConfig()
    const params = new URLSearchParams({
        doctor_id: doctorId,
        date,
        client_id: clientId || cfg.clientId,
    })
    return request(`${base()}/appointments/availability?${params}`)
}

/** Book an appointment — POST /appointments/book. */
export function bookAppointment({ client_id, patient_phone, doctor_id, date, time, notes }) {
    const cfg = getConfig()
    return request(`${base()}/appointments/book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            client_id: client_id || cfg.clientId,
            patient_phone,
            doctor_id,
            date,
            time,
            notes: notes || null,
        }),
    })
}

/** Reschedule — POST /appointments/reschedule. */
export function rescheduleAppointment({ appointment_id, new_date, new_time, client_id }) {
    const cfg = getConfig()
    return request(`${base()}/appointments/reschedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            appointment_id,
            new_date,
            new_time,
            client_id: client_id || cfg.clientId,
        }),
    })
}

/** Cancel — POST /appointments/cancel. */
export function cancelAppointment({ appointment_id, client_id }) {
    const cfg = getConfig()
    return request(`${base()}/appointments/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            appointment_id,
            client_id: client_id || cfg.clientId,
        }),
    })
}
