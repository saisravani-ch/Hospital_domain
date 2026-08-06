import React, { useState, useEffect } from 'react'

import { mainUser, contacts, Message, agentContact } from './generateFakeData'
import Avatar from './components/Avatar'
import ContactBox from './components/ContactBox'
import MessagesBox from './components/MessagesBox'
import ChatInputBox from './components/ChatInputBox'
import Search from './components/Search'
import Welcome from './components/Welcome'
import TopNav from './components/TopNav'
import DashboardView from './components/dashboard/DashboardView'
import ResolveByPhone from './components/ResolveByPhone'
import { sendAgentMessage } from './api/agents'
import { getConfig, saveConfig } from './api/config'

import './App.css'

const AGENT_THREAD_KEY = 'hospital_agent_thread'

const QUICK_QUERIES = [
    'I need a heart doctor in chennai',
    'book an appointment with Dr. Guru Prasad S',
    'Find a Tamil-speaking doctor',
    'Show me available slots for today',
]

function buildContacts() {
    const users = contacts.map((contact) => ({
        contact,
        messages: Array.from({ length: 6 }, (_, i) =>
            i % 2 === 0 ? new Message(true) : new Message(false)
        ),
    }))
    // AI Agent pinned at the top of the contact list.
    return [{ contact: agentContact, messages: [] }, ...users]
}

function loadAgentThread() {
    try {
        const raw = localStorage.getItem(AGENT_THREAD_KEY)
        if (raw) {
            const parsed = JSON.parse(raw)
            return {
                sessionId: parsed.sessionId || null,
                pending: !!parsed.pending,
                messages: (parsed.messages || []).map(
                    (m) => new Message(m.isMainUser, m.msg, new Date(m.date))
                ),
            }
        }
    } catch (e) {
        /* ignore corrupted storage */
    }
    return { sessionId: null, pending: false, messages: [] }
}

function App() {
    const [config, setConfig] = useState(getConfig)
    const [activeView, setActiveView] = useState('chat')
    const [data, setData] = useState(buildContacts)
    const [contactSelected, setContactSelected] = useState(agentContact)
    const [currentMessages, setCurrentMessages] = useState([])
    const [message, setMessage] = useState('')
    const [search, setSearch] = useState('')
    const [filteredContacts, setFilterContacts] = useState([])
    const [agentThread, setAgentThread] = useState(loadAgentThread)
    const [agentLoading, setAgentLoading] = useState(false)
    // When switching away from chat, clear the chat UI state so the dashboard
    // (or any other view) starts with a clean slate.
    useEffect(() => {
        if (activeView !== 'chat') {
            setContactSelected(agentContact)
            setMessage('')
            setSearch('')
        }
    }, [activeView])
    // Persist the agent conversation + session across reloads.
    useEffect(() => {
        localStorage.setItem(
            AGENT_THREAD_KEY,
            JSON.stringify({
                sessionId: agentThread.sessionId,
                pending: agentThread.pending,
                messages: agentThread.messages.map((m) => ({
                    isMainUser: m.isMainUser,
                    msg: m.msg,
                    date: m.date.toISOString(),
                })),
            })
        )
    }, [agentThread])

    useEffect(() => {
        if (contactSelected.id === agentContact.id) {
            setCurrentMessages(agentThread.messages)
        } else {
            const c = data.find((d) => d.contact.id === contactSelected.id)
            setCurrentMessages((c && c.messages) || [])
        }
    }, [contactSelected, data, agentThread])

    useEffect(() => {
        const result = data.filter(({ contact }) =>
            !search || contact.name.toLowerCase().includes(search.toLowerCase())
        )
        setFilterContacts(result)
    }, [data, search])

    function handleSaveConfig(next) {
        saveConfig(next)
        setConfig(getConfig())
    }

    async function pushAgentMessage(text) {
        const content = (text !== undefined ? text : message).trim()
        if (!content) return
        setMessage('')

        const userMsg = new Message(true, content, new Date())

        if (contactSelected.id === agentContact.id) {
            setAgentThread((prev) => ({
                ...prev,
                pending: false,
                messages: [...prev.messages, userMsg],
            }))
            setAgentLoading(true)
            try {
                const result = await sendAgentMessage(content, agentThread.sessionId)
                setAgentThread((prev) => ({
                    sessionId: result.session_id,
                    pending: result.status === 'pending_confirmation',
                    messages: [
                        ...prev.messages,
                        new Message(false, result.response, new Date()),
                    ],
                }))
            } catch (err) {
                setAgentThread((prev) => ({
                    ...prev,
                    messages: [
                        ...prev.messages,
                        new Message(false, 'Sorry, the agent is unavailable.', new Date()),
                    ],
                }))
            } finally {
                setAgentLoading(false)
            }
        } else {
            setData((prevData) =>
                prevData.map((d) =>
                    d.contact.id === contactSelected.id
                        ? { contact: d.contact, messages: [...d.messages, userMsg] }
                        : d
                )
            )
        }
    }

    function confirmBooking(confirm) {
        pushAgentMessage(confirm ? 'yes' : 'no')
    }

    function clearChat() {
        setAgentThread({ sessionId: null, pending: false, messages: [] })
        localStorage.removeItem(AGENT_THREAD_KEY)
    }

    const isAgentChat = contactSelected.id === agentContact.id
    const awaitingConfirmation = isAgentChat && agentThread.pending
    const inputDisabled = agentLoading || awaitingConfirmation

    return (
        <div className="app">
            <TopNav
                active={activeView}
                onChange={setActiveView}
                config={config}
                onSaveConfig={handleSaveConfig}
                contacts={data}
            />

            {activeView === 'chat' && (
                <div className="app-body">
                    <aside>
                        <header>
                            <Avatar user={mainUser} />
                        </header>
                        <Search search={search} setSearch={setSearch} />
                        <ResolveByPhone
                            contacts={data}
                            onSelect={(contact) => setContactSelected(contact)}
                        />
                        <div className="contact-boxes">
                            {filteredContacts.map(({ contact, messages }) => (
                                <ContactBox
                                    contact={contact}
                                    key={contact.id}
                                    setContactSelected={setContactSelected}
                                    messages={messages}
                                />
                            ))}
                        </div>
                    </aside>
                    {contactSelected.id ? (
                        <main>
                            <header>
                                <Avatar user={contactSelected} showName />
                                {isAgentChat && config.senderPhone && (
                                    <span
                                        className="sender-phone-chip"
                                        title="Sending as this WhatsApp number"
                                    >
                                        📞 {config.senderPhone}
                                    </span>
                                )}
                                {awaitingConfirmation && (
                                    <span className="pending-badge">
                                        ⏳ Awaiting confirmation
                                    </span>
                                )}
                                {isAgentChat && agentThread.messages.length > 0 && (
                                    <button
                                        className="btn-ghost btn-clear-chat"
                                        onClick={clearChat}
                                        title="Clear chat history"
                                    >
                                        🗑️ Clear
                                    </button>
                                )}
                            </header>
                            <MessagesBox messages={currentMessages} />
                            {awaitingConfirmation && (
                                <div className="confirmation-bar">
                                    <span className="confirmation-text">
                                        The agent is waiting for your confirmation to book.
                                    </span>
                                    <div className="confirmation-buttons">
                                        <button
                                            className="btn btn-confirm"
                                            onClick={() => confirmBooking(true)}
                                        >
                                            ✅ Yes, confirm booking
                                        </button>
                                        <button
                                            className="btn btn-ghost"
                                            onClick={() => confirmBooking(false)}
                                        >
                                            ❌ No, cancel
                                        </button>
                                    </div>
                                </div>
                            )}
                            <ChatInputBox
                                message={message}
                                setMessage={setMessage}
                                pushMessage={() => pushAgentMessage()}
                                loading={inputDisabled}
                                placeholder={
                                    awaitingConfirmation
                                        ? 'Confirm above to continue...'
                                        : undefined
                                }
                            />
                            {isAgentChat && !awaitingConfirmation && !agentLoading && (
                                <div className="quick-queries">
                                    {QUICK_QUERIES.map((q) => (
                                        <button
                                            key={q}
                                            className="chip"
                                            onClick={() => pushAgentMessage(q)}
                                        >
                                            {q}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </main>
                    ) : (
                        <main className="welcome-wrap">
                            <Welcome />
                        </main>
                    )}
                </div>
            )}

            {activeView === 'dashboard' && <DashboardView config={config} />}
        </div>
    )
}

export default App
