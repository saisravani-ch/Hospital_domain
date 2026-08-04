import React, { useState, useEffect, useCallback } from 'react'
import { SERVERS, checkHealth, rawGet, serverUrl } from '../../api/health'

export default function HealthView() {
    const [statuses, setStatuses] = useState({})
    const [checking, setChecking] = useState(false)

    const runChecks = useCallback(async () => {
        setChecking(true)
        const results = {}
        await Promise.all(
            SERVERS.map(async (s) => {
                results[s.key] = await checkHealth(serverUrl(s.key))
            })
        )
        setStatuses(results)
        setChecking(false)
    }, [])

    useEffect(() => {
        runChecks()
    }, [runChecks])

    return (
        <div className="tool-view">
            <div className="tool-view-header">
                <h2>❤️ Server Health Check</h2>
                <button className="btn" onClick={runChecks} disabled={checking}>
                    {checking ? 'Checking...' : '🔄 Refresh'}
                </button>
            </div>

            <div className="health-grid">
                {SERVERS.map((s) => {
                    const st = statuses[s.key]
                    const ok = st && st.ok
                    return (
                        <div key={s.key} className={`health-card ${ok ? 'ok' : 'down'}`}>
                            <h4>{s.name}</h4>
                            {st ? (
                                ok ? (
                                    <span className="status ok">✅ Online</span>
                                ) : (
                                    <span className="status down">
                                        ❌ Offline — {st.error || `HTTP ${st.status}`}
                                    </span>
                                )
                            ) : (
                                <span className="status">… checking</span>
                            )}
                            <code className="muted">{serverUrl(s.key)}</code>
                        </div>
                    )
                })}
            </div>

            <RawApiTest />
        </div>
    )
}

function RawApiTest() {
    const [server, setServer] = useState('kb')
    const [path, setPath] = useState('/')
    const [loading, setLoading] = useState(false)
    const [output, setOutput] = useState(null)
    const [error, setError] = useState('')

    async function run() {
        setLoading(true)
        setError('')
        setOutput(null)
        try {
            const result = await rawGet(serverUrl(server), path)
            setOutput(result)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card">
            <h3>Raw API Test</h3>
            <div className="search-row">
                <div className="field narrow">
                    <span>Server</span>
                    <select value={server} onChange={(e) => setServer(e.target.value)}>
                        {SERVERS.map((s) => (
                            <option key={s.key} value={s.key}>
                                {s.name}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="field grow">
                    <span>Endpoint path</span>
                    <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/" />
                </div>
                <div className="field auto">
                    <button className="btn" onClick={run} disabled={loading}>
                        {loading ? 'Sending...' : 'Send Request'}
                    </button>
                </div>
            </div>
            {error && <div className="alert-error">{error}</div>}
            {output && (
                <div className="result-box">
                    <p className="muted">
                        GET {serverUrl(server)}
                        {path} — HTTP {output.status}
                    </p>
                    <pre className="json-block">
                        {typeof output.data === 'string'
                            ? output.data
                            : JSON.stringify(output.data, null, 2)}
                    </pre>
                </div>
            )}
        </div>
    )
}
