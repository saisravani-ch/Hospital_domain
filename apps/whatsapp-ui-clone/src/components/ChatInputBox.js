import React from 'react'
import emojiIcon from '../assets/tag_faces.svg'
import micIcon from '../assets/mic.svg'
import sendIcon from '../assets/send.svg'

export default function ChatInputBox({ message, setMessage, pushMessage, loading, placeholder }) {
    const disabled = loading
    function handleKeyDown(e) {
        if (e.key === 'Enter' && message && !disabled) {
            pushMessage()
        }
    }
    return (
        <div className="chat-input-box">
            <div className="icon emoji-selector">
                <img src={emojiIcon} alt="" />
            </div>

            <div className="chat-input">
                <input
                    type="text"
                    placeholder={placeholder || (loading ? 'Agent is thinking...' : 'Type a message')}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={disabled}
                />
            </div>

            <div className="icon send" onClick={disabled ? undefined : pushMessage}>
                <img src={message ? sendIcon : micIcon} alt="" />
            </div>
        </div>
    )
}
