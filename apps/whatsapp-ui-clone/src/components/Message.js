import React from 'react'
import doubleCheck from '../assets/done_all.svg'

export default function Message({ message }) {
    const lines = String(message.msg).split('\n')

    return (
        <div className={`message ${message.isMainUser ? 'sent' : 'received'}`}>
            {lines.map((line, i) => (
                <React.Fragment key={i}>
                    {line}
                    {i < lines.length - 1 && <br />}
                </React.Fragment>
            ))}
            <div className="metadata">
                <span className="date">{message.date.toLocaleString()}</span>
                {message.isMainUser && <img src={doubleCheck} alt="" className="icon-small" />}
            </div>
        </div>
    )
}
