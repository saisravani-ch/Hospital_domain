import { getConfig } from './config'

export const SERVERS = [
    { key: 'kb', name: '🧠 Knowledge Base' },
    { key: 'workflows', name: '📋 Workflows' },
    { key: 'agent', name: '🤖 Agent (Orchestrator)' },
]

/** GET /health for a service base URL. Returns { ok, status, data?, error? }. */
export async function checkHealth(baseUrl) {
    try {
        const response = await fetch(`${baseUrl}/health`)
        if (!response.ok) {
            return { ok: false, status: response.status }
        }
        const data = await response.json()
        return { ok: data && data.status === 'ok', status: response.status, data }
    } catch (err) {
        return { ok: false, error: err.message }
    }
}

/** Raw GET against any service for the "Raw API Test" panel. */
export async function rawGet(baseUrl, path) {
    try {
        const response = await fetch(`${baseUrl}${path}`)
        const text = await response.text()
        let data = text
        try {
            data = JSON.parse(text)
        } catch (e) {
            /* keep raw text */
        }
        return { ok: response.ok, status: response.status, data }
    } catch (err) {
        return { ok: false, error: err.message }
    }
}

/** Return the live base URL for a server key. */
export function serverUrl(key) {
    return getConfig()[key]
}
