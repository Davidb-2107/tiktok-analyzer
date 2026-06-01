import { useEffect } from 'react'

export default function Toast({ message, onDismiss }) {
  // NOTE: deps are [message] only — depending on onDismiss would reset the
  // 3s timer on every parent re-render (App polls /status every 500ms, so
  // the toast would never dismiss while a job is active).
  useEffect(() => {
    if (!message) return
    const t = setTimeout(() => onDismiss && onDismiss(), 3000)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message])

  if (!message) return null

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '1.5rem',
        right: '1.5rem',
        padding: '0.7rem 1rem',
        borderRadius: '8px',
        border: '1px solid #2a2a2a',
        background: '#1a1a1a',
        color: '#f0f0f0',
        fontSize: '0.85rem',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
        zIndex: 1000,
        maxWidth: '320px',
      }}
    >
      {message}
    </div>
  )
}
