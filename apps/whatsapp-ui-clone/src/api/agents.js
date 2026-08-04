import { getConfig } from './config'

/**
 * Send a message to the conversation agent.
 * tenant_id / client_id are read from the current config (see config.js) —
 * the same values the Streamlit UI sends from its sidebar.
 */
export async function sendAgentMessage(message, sessionId = null) {
    const cfg = getConfig()
    const response = await fetch(`${cfg.agent}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            session_id: sessionId,
            tenant_id: cfg.tenantId || null,
            client_id: cfg.clientId || null,
            // Mock WhatsApp identity resolution — the agent seeds these into
            // state and never asks the user for phone number or name.
            patient_phone: cfg.senderPhone || null,
            patient_name: cfg.senderName || null,
        }),
    })

    if (!response.ok) {
        throw new Error(`Agent request failed: ${response.status}`)
    }

    return response.json()
}
