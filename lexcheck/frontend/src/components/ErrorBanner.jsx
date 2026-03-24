export default function ErrorBanner({ msg, onClose }) {
  if (!msg) return null
  return (
    <div className="error-banner">
      <span>⚠️ {msg}</span>
      {onClose && (
        <button onClick={onClose} className="error-banner__close" aria-label="Dismiss error">
          ✕
        </button>
      )}
    </div>
  )
}
