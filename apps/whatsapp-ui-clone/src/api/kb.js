import { getConfig } from './config'

async function request(url) {
    const response = await fetch(url)
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`)
    }
    return response.json()
}

/** GraphRAG search (vector + graph) — returns { intent, doctors, booking_links, ai_response }. */
export function graphSearch(query, n = 6, tenantId = '') {
    const cfg = getConfig()
    let url = `${cfg.kb}/search/doctors?q=${encodeURIComponent(query)}&n=${n}`
    if (tenantId) url += `&tenant_id=${encodeURIComponent(tenantId)}`
    return request(url)
}

/** Semantic (vector-only) search — returns { query, results: [{ id, score, text, metadata }] }. */
export function semanticSearch(query, n = 6) {
    const cfg = getConfig()
    return request(
        `${cfg.kb}/search/doctors/semantic?q=${encodeURIComponent(query)}&n=${n}`
    )
}

/** Search by specialization — returns { specialization, doctors }. */
export function bySpecialization(specialization, n = 6) {
    const cfg = getConfig()
    return request(
        `${cfg.kb}/search/doctors/by-specialization?specialization=${encodeURIComponent(
            specialization
        )}&n=${n}`
    )
}

/** Doctor profile — GET /doctors/{id}. */
export function doctorProfile(id) {
    const cfg = getConfig()
    return request(`${cfg.kb}/doctors/${encodeURIComponent(id)}`)
}
