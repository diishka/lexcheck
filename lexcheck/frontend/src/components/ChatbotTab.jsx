import { useState, useRef, useEffect } from 'react'
import { api } from '../api.js'
import { getAssistantQuestions, pickRandomItems } from '../questionBank.js'

const CHAT_STORAGE_KEY = 'lexcheck_chat_state_v1'

function loadStoredChat() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed
  } catch {
    return null
  }
}

function formatElapsed(ms) {
  const totalMs = Math.max(0, Math.round(ms || 0))
  if (totalMs < 1000) return `${totalMs} ms`

  const totalSeconds = totalMs / 1000
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)} s`

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds - minutes * 60
  return `${minutes}m ${seconds.toFixed(1)}s`
}

export default function ChatbotTab({ lang, t }) {
  const [storedChat] = useState(() => loadStoredChat())
  const [sessionId, setSessionId] = useState(() => storedChat?.sessionId || null)
  const [dataset, setDataset] = useState(() => storedChat?.dataset || 'lexai')
  const [messages, setMessages] = useState(() => {
    if (Array.isArray(storedChat?.messages) && storedChat.messages.length > 0) {
      return storedChat.messages
    }
    return [{ role: 'assistant', content: t.greeting, elapsedMs: null, model: null }]
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [lawCtx, setLawCtx] = useState(() => storedChat?.lawCtx || '')
  const [showCtx, setShowCtx] = useState(() => Boolean(storedChat?.showCtx))
  const [topK, setTopK] = useState(() => Number(storedChat?.topK) || 3)
  const [pendingStartedAt, setPendingStartedAt] = useState(null)
  const [liveElapsedMs, setLiveElapsedMs] = useState(0)
  const [quickQuestions, setQuickQuestions] = useState(() => pickRandomItems(getAssistantQuestions(lang), 5))
  const chatEnd = useRef(null)

  useEffect(() => {
    setMessages(prev =>
      prev.length === 1 && prev[0].role === 'assistant'
        ? [{ role: 'assistant', content: t.greeting, elapsedMs: null, model: null }]
        : prev,
    )
  }, [t.greeting])

  useEffect(() => {
    setQuickQuestions(pickRandomItems(getAssistantQuestions(lang), 5))
  }, [lang])

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    if (!loading || pendingStartedAt === null) {
      setLiveElapsedMs(0)
      return undefined
    }

    setLiveElapsedMs(performance.now() - pendingStartedAt)
    const timer = window.setInterval(() => {
      setLiveElapsedMs(performance.now() - pendingStartedAt)
    }, 100)

    return () => window.clearInterval(timer)
  }, [loading, pendingStartedAt])

  useEffect(() => {
    try {
      localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify({
          sessionId,
          dataset,
          messages: messages.slice(-100),
          lawCtx,
          showCtx,
          topK,
        }),
      )
    } catch {
      // Ignore storage quota / privacy mode errors.
    }
  }, [sessionId, dataset, messages, lawCtx, showCtx, topK])

  function resetConversation(nextDataset = dataset) {
    setSessionId(null)
    setDataset(nextDataset)
    setMessages([{ role: 'assistant', content: t.greeting, elapsedMs: null, model: null }])
    setLoading(false)
    setPendingStartedAt(null)
    setLiveElapsedMs(0)
  }

  async function send() {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    const startedAt = performance.now()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg, elapsedMs: null, model: null }])
    setLoading(true)
    setPendingStartedAt(startedAt)
    try {
      let sid = sessionId
      if (!sid) {
        const r = await api.createSession()
        sid = r.session_id
        setSessionId(sid)
      }
      const data = await api.chat({
        session_id: sid,
        message: userMsg,
        law_context: lawCtx || undefined,
        top_k: topK,
        dataset,
      })
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply,
          elapsedMs: performance.now() - startedAt,
          model: data.model || null,
        },
      ])
    } catch (e) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ ' + e.message,
          elapsedMs: performance.now() - startedAt,
          model: null,
        },
      ])
    }
    setPendingStartedAt(null)
    setLoading(false)
  }

  function refreshQuickQuestions() {
    setQuickQuestions(pickRandomItems(getAssistantQuestions(lang), 5))
  }

  function clearChat() {
    resetConversation(dataset)
    setInput('')
  }

  function switchDataset(nextDataset) {
    if (nextDataset === dataset) return
    resetConversation(nextDataset)
  }

  const canSend = !loading && !!input.trim()

  return (
    <div className="chat-layout">
      <aside className="card sidebar">
        <div className="sidebar__headrow">
          <div className="label label--spaced">{t.quickQTitle}</div>
          <button type="button" onClick={refreshQuickQuestions} className="text-btn">
            {t.refreshRandom}
          </button>
        </div>
        {quickQuestions.map((q, i) => (
          <button key={i} onClick={() => setInput(q)} className="quick-btn">
            {q}
          </button>
        ))}

        <div className="sidebar__section">
          <div className="label label--spaced">{t.datasetLabel}</div>
          <div className="chat__topk">
            {[
              { value: 'lexai', label: t.datasetMainLabel },
              { value: 'schema12', label: t.datasetSchemaLabel },
            ].map(option => (
              <button
                key={option.value}
                onClick={() => switchDataset(option.value)}
                className={dataset === option.value ? 'quick-btn quick-btn--active' : 'quick-btn'}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="hint">{t.datasetHint}</div>
        </div>

        <div className="sidebar__section">
          <button onClick={() => setShowCtx(!showCtx)} className="ctx-toggle">
            {showCtx ? '▼' : '▶'} {t.ctxToggle}
          </button>
          {showCtx && (
            <textarea
              value={lawCtx}
              onChange={e => setLawCtx(e.target.value)}
              rows={6}
              placeholder={t.ctxPH}
              className="input input--textarea input--sm"
            />
          )}
        </div>

        <div className="sidebar__section">
          <div className="label label--spaced">{t.topKLabel || 'Context size'}</div>
          <div className="chat__topk">
            {[3, 5, 8, 12].map(k => (
              <button
                key={k}
                onClick={() => setTopK(k)}
                className={topK === k ? 'quick-btn quick-btn--active' : 'quick-btn'}
                type="button"
              >
                {k}
              </button>
            ))}
          </div>
          <div className="hint">{t.topKHint || 'Higher = more laws, slower response.'}</div>
        </div>

        {sessionId && (
          <div className="sidebar__footer">
            <div className="session-id">{t.sessionLabel}: {sessionId.substring(0, 8)}...</div>
          </div>
        )}
      </aside>

      <section className="card chat">
        <div className="chat__header">
          <div className="chat__header-main">
            <div className="chat__bot-icon" aria-hidden>
              🤖
            </div>
            <div>
              <div className="chat__title">{t.assistantName}</div>
              <div className="chat__status">{t.active}</div>
            </div>
          </div>
          <button type="button" onClick={clearChat} className="text-btn text-btn--danger" disabled={loading}>
            {t.clearChatLabel}
          </button>
        </div>

        <div className="chat__messages">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'message message--user' : 'message message--assistant'}>
              <div className="message__stack">
                <div className="message__bubble">{m.content}</div>
                {m.role === 'assistant' && typeof m.elapsedMs === 'number' && (
                  <div className="message__meta">
                    <span>{t.responseTimeLabel}: {formatElapsed(m.elapsedMs)}</span>
                    {m.model && <span>{t.modelLabel}: {m.model}</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="message message--assistant">
              <div className="message__stack">
                <div className="typing">
                  <span className="typing__dot" />
                  <span className="typing__dot" />
                  <span className="typing__dot" />
                </div>
                <div className="message__meta">
                  {t.responseTimeLabel}: {formatElapsed(liveElapsedMs)}
                </div>
              </div>
            </div>
          )}
          <div ref={chatEnd} />
        </div>

        <div className="chat__input-row">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder={t.chatPH}
            className="input chat__input"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className={canSend ? 'btn btn--active chat__send' : 'btn chat__send'}
            aria-label={t.sendLabel || 'Send'}
          >
            ➤
          </button>
        </div>
      </section>
    </div>
  )
}
