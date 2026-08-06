import React, { useState } from 'react'
import { faker } from '@faker-js/faker'
import HealthView from './health/HealthView'

const TABS = [
    { key: 'chat', label: '💬 Chat' },
    { key: 'dashboard', label: '📊 Dashboard' },
]

export default function TopNav({ active, onChange, config, onSaveConfig, contacts = [] }) {
    const [showSettings, setShowSettings] = useState(false)
    const [showRandomMenu, setShowRandomMenu] = useState(false)
    const [form, setForm] = useState(config)

    function openSettings() {
        setForm(config)
        setShowSettings(true)
    }

    function save() {
        onSaveConfig(form)
        setShowSettings(false)
    }

    function update(field, value) {
        setForm((f) => ({ ...f, [field]: value }))
    }

    function applyRandomContact() {
        const people = contacts
            .map((c) => c.contact || c)
            .filter((c) => c && c.phone)
        if (people.length) {
            const pick = people[Math.floor(Math.random() * people.length)]
            update('senderPhone', pick.phone)
            update('senderName', pick.name || '')
        } else {
            applyRandomDigits()
        }
        setShowRandomMenu(false)
    }

    function applyRandomDigits() {
        // faker v10 ignores format masks in phone.number(), so build it manually.
        update('senderPhone', `+91${faker.string.numeric(10)}`)
        setShowRandomMenu(false)
    }

    return (
        <>
            <nav className="top-nav">
                <div className="top-nav-brand">
                    <span className="brand-dot" />
                    Hospital Assistant
                </div>
                <div className="top-nav-tabs">
                    {TABS.map((t) => (
                        <button
                            key={t.key}
                            className={`nav-tab ${active === t.key ? 'active' : ''}`}
                            onClick={() => onChange(t.key)}
                        >
                            {t.label}
                        </button>
                    ))}
                </div>
                <button
                    className="settings-btn"
                    onClick={openSettings}
                    title="Server & session settings"
                    aria-label="Settings"
                >
                    ⚙️
                </button>
            </nav>

            {showSettings && (
                <div className="modal-backdrop" onClick={() => setShowSettings(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <h3>⚙️ Server & Session Settings</h3>
                        <p className="modal-hint">
                            The same settings the Streamlit UI exposes in its sidebar.
                        </p>

                        <label className="field">
                            <span>Knowledge Base URL</span>
                            <input
                                value={form.kb}
                                onChange={(e) => update('kb', e.target.value)}
                                placeholder="http://localhost:8000"
                            />
                        </label>
                        <label className="field">
                            <span>Workflows URL</span>
                            <input
                                value={form.workflows}
                                onChange={(e) => update('workflows', e.target.value)}
                                placeholder="http://localhost:8001"
                            />
                        </label>
                        <label className="field">
                            <span>Agent URL</span>
                            <input
                                value={form.agent}
                                onChange={(e) => update('agent', e.target.value)}
                                placeholder="http://localhost:8002"
                            />
                        </label>
                        <label className="field">
                            <span>Tenant ID (branch)</span>
                            <input
                                value={form.tenantId}
                                onChange={(e) => update('tenantId', e.target.value)}
                                placeholder="e.g. glh-chn"
                            />
                        </label>
                        <label className="field">
                            <span>Client ID (hospital group)</span>
                            <input
                                value={form.clientId}
                                onChange={(e) => update('clientId', e.target.value)}
                                placeholder="e.g. gleneagles_001"
                            />
                        </label>
                        <label className="field">
                            <span>Sender phone (WhatsApp)</span>
                            <div className="phone-field-row">
                                <input
                                    value={form.senderPhone}
                                    onChange={(e) => update('senderPhone', e.target.value)}
                                    placeholder="+91… sent as patient_phone"
                                />
                                <button
                                    type="button"
                                    className="btn btn-ghost btn-randomize"
                                    onClick={() => setShowRandomMenu((m) => !m)}
                                    title="Randomize sender identity"
                                    aria-label="Randomize sender identity"
                                >
                                    🎲
                                </button>
                            </div>
                            {showRandomMenu && (
                                <div className="randomize-menu">
                                    <button
                                        type="button"
                                        onClick={applyRandomContact}
                                    >
                                        👤 Random contact (name + phone)
                                    </button>
                                    <button
                                        type="button"
                                        onClick={applyRandomDigits}
                                    >
                                        🔢 Random phone digits
                                    </button>
                                </div>
                            )}
                        </label>
                        <label className="field">
                            <span>Sender name (resolved from phone)</span>
                            <input
                                value={form.senderName}
                                onChange={(e) => update('senderName', e.target.value)}
                                placeholder="e.g. Priya Sharma"
                            />
                        </label>

                        <hr style={{ margin: '1rem 0', borderColor: '#30363d' }} />
                        <h4 style={{ marginBottom: '0.75rem' }}>❤️ Server Health</h4>
                        <HealthView />

                        <div className="modal-actions">
                            <button className="btn" onClick={save}>
                                💾 Save
                            </button>
                            <button className="btn btn-ghost" onClick={() => setShowSettings(false)}>
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
