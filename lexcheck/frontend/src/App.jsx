import { useState, useEffect } from 'react'
import { api } from './api.js'
import { LANG } from './lang.js'
import AnalyzerTab from './components/AnalyzerTab.jsx'
import ChatbotTab from './components/ChatbotTab.jsx'
import DatabaseTab from './components/DatabaseTab.jsx'

export default function App() {
  const [tab, setTab] = useState('analyzer')
  const [lang, setLang] = useState(() => localStorage.getItem('lexcheck_lang') || 'uz')
  const [health, setHealth] = useState(null)
  const [backendOk, setBackendOk] = useState(null)

  const t = LANG[lang]

  useEffect(() => {
    localStorage.setItem('lexcheck_lang', lang)
  }, [lang])

  useEffect(() => {
    api.health()
      .then(h => { setHealth(h); setBackendOk(true) })
      .catch(() => setBackendOk(false))
  }, [])

  return (
    <div className="app">
      <Header
        tab={tab}
        lang={lang}
        t={t}
        health={health}
        backendOk={backendOk}
        onTab={setTab}
        onLang={setLang}
      />

      <main className="app__content">
        <section className={tab === 'analyzer' ? 'tab-panel' : 'tab-panel is-hidden'}>
          <AnalyzerTab lang={lang} t={t} />
        </section>
        <section className={tab === 'chatbot' ? 'tab-panel' : 'tab-panel is-hidden'}>
          <ChatbotTab lang={lang} t={t} />
        </section>
        <section className={tab === 'database' ? 'tab-panel' : 'tab-panel is-hidden'}>
          <DatabaseTab lang={lang} t={t} />
        </section>
      </main>
    </div>
  )
}

function Header({ tab, lang, t, health, backendOk, onTab, onLang }) {
  const statusState = backendOk === null ? 'pending' : backendOk ? 'ok' : 'bad'

  return (
    <header className="header">
      <div className="header__inner">
        <div className="header__top">
          <div className="brand">
            <div className="brand__logo" aria-hidden>
              ⚖️
            </div>
            <div className="brand__text">
              <div className="brand__title">
                LexCheck <span className="brand__accent">UZ</span>
              </div>
              <div className="brand__subtitle">{t.subtitle}</div>
            </div>
          </div>

          <div className="controls">
            <div className="lang-toggle" role="group" aria-label={t.langLabel}>
              <button
                type="button"
                onClick={() => onLang('ru')}
                className={lang === 'ru' ? 'lang-toggle__btn lang-toggle__btn--active' : 'lang-toggle__btn'}
              >
                RU
              </button>
              <button
                type="button"
                onClick={() => onLang('uz')}
                className={lang === 'uz' ? 'lang-toggle__btn lang-toggle__btn--active' : 'lang-toggle__btn'}
              >
                UZ
              </button>
            </div>

            <div className={`status status--${statusState}`}>
              <span className="status__dot" aria-hidden />
              {backendOk === null ? t.connecting : backendOk ? t.online : t.offline}
            </div>

            {health && (
              <div className="model-badge">🤖 {health.chat_model || health.analyze_model}</div>
            )}
          </div>
        </div>

        <div className="tabs" role="tablist">
          {t.tabs.map(([k, label]) => (
            <button
              key={k}
              onClick={() => onTab(k)}
              className={tab === k ? 'tab-btn tab-btn--active' : 'tab-btn'}
              role="tab"
              aria-selected={tab === k}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}
