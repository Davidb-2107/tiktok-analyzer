const LABELS = {
  pending: 'Queued...',
  downloading: 'Downloading video...',
  extracting: 'Extracting frames...',
  frames_ready: 'Uploading to R2...',
  awaiting_transcription_approval: 'No captions found',
  transcribing: 'Transcribing with Whisper...',
  done: 'Done',
  error: 'Error',
}

const COLORS = {
  pending: '#888',
  downloading: '#f0a500',
  extracting: '#4da6ff',
  frames_ready: '#a78bfa',
  awaiting_transcription_approval: '#f0a500',
  transcribing: '#4da6ff',
  done: '#4caf50',
  error: '#f44336',
}

const TERMINAL = ['done', 'error', 'awaiting_transcription_approval']

export default function StatusIndicator({ status }) {
  const s = status.status
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
      <span style={{
        width: '10px', height: '10px', borderRadius: '50%',
        background: COLORS[s] || '#888',
        boxShadow: !TERMINAL.includes(s) ? `0 0 6px ${COLORS[s]}` : 'none',
      }} />
      <span style={{ color: COLORS[s], fontWeight: 500 }}>{LABELS[s] || s}</span>
      {s === 'error' && status.error && (
        <span style={{ color: '#aaa', fontSize: '0.85rem' }}>— {status.error}</span>
      )}
      {s === 'done' && (
        <span style={{ color: '#888', fontSize: '0.85rem' }}>
          — {status.frames.length} frames
          {status.duration ? `, ${Math.floor(status.duration / 60)}:${String(Math.round(status.duration % 60)).padStart(2, '0')}` : ''}
        </span>
      )}
    </div>
  )
}
