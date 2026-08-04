// Central runtime config for the three backend services, persisted in
// localStorage so it survives reloads. Mirrors the Streamlit sidebar settings.

const DEFAULTS = {
    kb: 'http://localhost:8000',
    workflows: 'http://localhost:8001',
    agent: 'http://localhost:8002',
    tenantId: '',
    clientId: 'gleneagles_001',
    // Mock WhatsApp identity — sent as patient_phone / patient_name with
    // every /chat request so the agent never asks for them.
    senderPhone: '',
    senderName: '',
}

const KEY = 'hospital_config'

export function getConfig() {
    try {
        const raw = localStorage.getItem(KEY)
        if (raw) return { ...DEFAULTS, ...JSON.parse(raw) }
    } catch (e) {
        /* corrupted storage — fall back to defaults */
    }
    return { ...DEFAULTS }
}

export function saveConfig(overrides) {
    const next = { ...getConfig(), ...overrides }
    localStorage.setItem(KEY, JSON.stringify(next))
    return next
}

export function resetConfig() {
    localStorage.removeItem(KEY)
    return { ...DEFAULTS }
}
