import React from 'react'
import doubleCheck from '../assets/done_all.svg'
import Avatar from './Avatar'

export default function ContactBox({ contact, setContactSelected, messages }) {
    const lastMsg = messages.length
        ? messages.reduce((a, b) => (a.date.getTime() > b.date.getTime() ? a : b))
        : null

    function truncate(text, length) {
        return text.length > length ? `${text.substring(0, length)} ...` : text
    }
    return (
        <div className="contact-box" onClick={() => setContactSelected(contact)}>
            <Avatar user={contact} />
            <div className="right-section">
                <div className="contact-box-header">
                    <h3 className="avatar-title">{contact.name}</h3>
                    {lastMsg && <span className="time-mark">{lastMsg.date.toLocaleDateString()}</span>}
                </div>
                <span className="contact-phone muted">{contact.phone}</span>
                <div className="last-msg">
                    {lastMsg ? (
                        <>
                            <img src={doubleCheck} alt="" className="icon-small" />
                            <span className="text">{truncate(lastMsg.msg, 30)}</span>
                        </>
                    ) : (
                        <span className="text">Start a conversation</span>
                    )}
                </div>
            </div>
        </div>
    )
}
