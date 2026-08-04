// Client for the workflows monitoring/dashboard endpoint.

import { getConfig } from './config'

// Fetch the full monitoring dashboard payload for a client (hospital group).
// Returns parsed JSON or throws on a non-OK response.
export async function getDashboard(clientId) {
    const base = getConfig().workflows
    const params = new URLSearchParams({ client_id: clientId || 'gleneagles_001' })
    const res = await fetch(`${base}/appointments/dashboard?${params}`)
    if (!res.ok) {
        let detail = `HTTP ${res.status}`
        try {
            const body = await res.json()
            if (body.detail) {
                detail =
                    typeof body.detail === 'string'
                        ? body.detail
                        : JSON.stringify(body.detail)
            }
        } catch (e) {
            /* ignore */
        }
        throw new Error(detail)
    }
    const data = await res.json()
    return data
}