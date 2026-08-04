import React, { useState } from 'react'
import {
    graphSearch,
    semanticSearch,
    bySpecialization,
    doctorProfile,
} from '../../api/kb'
import { getConfig } from '../../api/config'

const MODES = [
    { key: 'graphrag', label: 'GraphRAG (vector + graph)' },
    { key: 'semantic', label: 'Semantic (vector only)' },
    { key: 'specialization', label: 'By Specialization' },
    { key: 'profile', label: 'Doctor Profile' },
]

const PLACEHOLDERS = {
    graphrag: 'e.g. heart specialist Tamil speaking',
    semantic: 'e.g. heart specialist Tamil speaking',
    specialization: 'e.g. Cardiology',
    profile: 'e.g. dr-j-ajith-kumar-chn',
}

export default function DoctorsView() {
    const [mode, setMode] = useState('graphrag')
    const [query, setQuery] = useState('')
    const [n, setN] = useState(6)
    const [tenant, setTenant] = useState(() => getConfig().tenantId)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [result, setResult] = useState(null)

    async function runSearch() {
        if (!query.trim()) return
        setLoading(true)
        setError('')
        setResult(null)
        try {
            let data
            switch (mode) {
                case 'graphrag':
                    data = await graphSearch(query, n, tenant)
                    break
                case 'semantic':
                    data = await semanticSearch(query, n)
                    break
                case 'specialization':
                    data = await bySpecialization(query, n)
                    break
                case 'profile':
                    data = await doctorProfile(query)
                    break
                default:
                    data = null
            }
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter') runSearch()
    }

    return (
        <div className="tool-view">
            <div className="tool-view-header">
                <h2>🔍 Doctor Knowledge Base Search</h2>
            </div>

            <div className="card">
                <div className="mode-pills">
                    {MODES.map((m) => (
                        <button
                            key={m.key}
                            className={`pill ${mode === m.key ? 'active' : ''}`}
                            onClick={() => {
                                setMode(m.key)
                                setResult(null)
                                setError('')
                            }}
                        >
                            {m.label}
                        </button>
                    ))}
                </div>

                <div className="search-row">
                    <div className="field grow">
                        <span>{mode === 'profile' ? 'Doctor ID' : 'Search query'}</span>
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={PLACEHOLDERS[mode]}
                        />
                    </div>
                    <div className="field narrow">
                        <span>Max results</span>
                        <input
                            type="number"
                            min="1"
                            max="20"
                            value={n}
                            onChange={(e) => setN(Number(e.target.value) || 6)}
                        />
                    </div>
                    {mode === 'graphrag' && (
                        <div className="field narrow">
                            <span>Tenant ID (optional)</span>
                            <input
                                value={tenant}
                                onChange={(e) => setTenant(e.target.value)}
                                placeholder="e.g. glh-chn"
                            />
                        </div>
                    )}
                    <div className="field auto">
                        <button
                            className="btn"
                            onClick={runSearch}
                            disabled={loading || !query.trim()}
                        >
                            {loading ? 'Searching...' : '🔍 Search'}
                        </button>
                    </div>
                </div>
            </div>

            {loading && <p className="muted">Searching…</p>}
            {error && <div className="alert-error">Search failed: {error}</div>}

            {result && mode === 'graphrag' && <GraphRagResults data={result} />}
            {result && mode === 'semantic' && <SemanticResults data={result} />}
            {result && mode === 'specialization' && <DoctorListResults data={result} />}
            {result && mode === 'profile' && <ProfileResult data={result} />}
        </div>
    )
}

function GraphRagResults({ data }) {
    const doctors = data.doctors || []
    return (
        <>
            <div className="result-summary">
                Found {doctors.length} doctors
                {data.intent ? ` (intent: ${data.intent})` : ''}
            </div>
            {data.ai_response && <div className="alert-info">{data.ai_response}</div>}
            {doctors.map((doc, i) => (
                <DoctorCard key={doc.doctor_id || i} doc={doc} bookingLinks={data.booking_links || []} />
            ))}
        </>
    )
}

function DoctorListResults({ data }) {
    const doctors = data.doctors || []
    return (
        <>
            <div className="result-summary">Found {doctors.length} doctors</div>
            {doctors.map((doc, i) => (
                <DoctorCard key={doc.doctor_id || i} doc={doc} />
            ))}
        </>
    )
}

function DoctorCard({ doc, bookingLinks }) {
    const link = bookingLinks && bookingLinks.length ? bookingLinks[0].booking_url : null
    return (
        <details className="result-card" open>
            <summary>
                <strong>{doc.name || 'Unknown'}</strong>
                {doc.designation && <span className="sub"> — {doc.designation}</span>}
            </summary>
            <div className="card-grid">
                <div>
                    <div><span className="k">Specializations:</span> {doc.specializations || 'N/A'}</div>
                    <div><span className="k">Experience:</span> {doc.experience_years ?? 'N/A'} years</div>
                    <div><span className="k">Fee:</span> ₹{doc.consultation_fee ?? 'N/A'}</div>
                </div>
                <div>
                    <div><span className="k">Languages:</span> {doc.languages || 'N/A'}</div>
                    <div><span className="k">Hospital:</span> {doc.hospitals?.length ? doc.hospitals.join(', ') : doc.hospital_ids?.join(', ') || 'N/A'}</div>
                    {doc.qualifications && (
                        <div><span className="k">Qualifications:</span> {doc.qualifications}</div>
                    )}
                </div>
            </div>
            {link && (
                <a className="book-link" href={link} target="_blank" rel="noreferrer">
                    🔗 Book an appointment
                </a>
            )}
        </details>
    )
}

function SemanticResults({ data }) {
    const results = data.results || []
    return (
        <>
            <div className="result-summary">Found {results.length} results</div>
            {results.map((r, i) => (
                <details className="result-card" key={r.id || i}>
                    <summary>
                        <strong>{r.metadata?.name || r.id || 'Unknown'}</strong>
                        {typeof r.score === 'number' && (
                            <span className="sub"> — score {r.score.toFixed(3)}</span>
                        )}
                    </summary>
                    {r.text && <p className="muted">{String(r.text).slice(0, 500)}</p>}
                    {r.metadata && <pre className="json-block">{JSON.stringify(r.metadata, null, 2)}</pre>}
                </details>
            ))}
        </>
    )
}

function ProfileResult({ data }) {
    return (
        <details className="result-card" open>
            <summary>
                <strong>{data.name || data.doctor_id || 'Doctor'}</strong>
                {data.designation && <span className="sub"> — {data.designation}</span>}
            </summary>
            <pre className="json-block">{JSON.stringify(data, null, 2)}</pre>
        </details>
    )
}
