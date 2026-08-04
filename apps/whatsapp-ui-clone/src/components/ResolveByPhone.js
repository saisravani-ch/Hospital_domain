import React, { useState } from 'react'

// Resolves a phone number to a contact name, like WhatsApp does.
// In production this would be an API request; here it searches the local contact list.
export default function ResolveByPhone({ contacts, onSelect }) {
    const [phone, setPhone] = useState('')
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)

    function handleResolve() {
        const cleaned = phone.replace(/[\s\-()]/g, '')
        if (!cleaned) {
            setResult(null)
            return
        }
        setLoading(true)
        // Simulate a network request delay (like WhatsApp resolving a number).
        setTimeout(() => {
            // Items may be contact objects or { contact, messages } entries.
            const found = contacts.find((c) => {
                const entry = c.contact || c
                return (
                    entry.phone === cleaned ||
                    (entry.phone || '').replace(/[\s\-()]/g, '') === cleaned
                )
            })
            setResult(found ? found.contact || found : null)
            setLoading(false)
        }, 150)
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter') {
            handleResolve()
        }
    }

    return (
        <div className="resolve-by-phone">
            <div className="resolve-row">
                <input
                    type="text"
                    className="resolve-input"
                    placeholder="📞 Resolve by phone number"
                    value={phone}
                    onChange={(e) => {
                        setPhone(e.target.value)
                        setResult(null)
                    }}
                    onKeyDown={handleKeyDown}
                />
                <button
                    className="btn btn-resolve"
                    onClick={handleResolve}
                    disabled={loading || !phone.trim()}
                >
                    {loading ? '…' : '🔍'}
                </button>
            </div>
            {result && (
                <div
                    className="resolve-result"
                    onClick={() => onSelect(result)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && onSelect(result)}
                >
                    <span className="resolve-name">{result.name}</span>
                    <span className="resolve-phone muted">{result.phone}</span>
                </div>
            )}
            {phone && !loading && !result && (
                <div className="resolve-no-result muted">No contact found</div>
            )}
        </div>
    )
}