import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Spinner from './Spinner.jsx'
import ErrorBanner from './ErrorBanner.jsx'
import { getAnalyzerExamples, pickRandomItems } from '../questionBank.js'

export default function AnalyzerTab({ lang, t }) {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [presetCaseId, setPresetCaseId] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [randomExamples, setRandomExamples] = useState(() => pickRandomItems(getAnalyzerExamples(lang), 5))

  useEffect(() => {
    setRandomExamples(pickRandomItems(getAnalyzerExamples(lang), 5))
  }, [lang])

  async function handleAnalyze() {
    if (!text.trim()) return
    setLoading(true)
    setResults(null)
    setError('')
    setStatus(t.statusSearch)
    try {
      setStatus(t.statusAI)
      const data = await api.analyze({
        title,
        text,
        top_k: 2,
        lang,
        preset_case: Boolean(presetCaseId),
        preset_case_id: presetCaseId || undefined,
      })
      setResults(data)
    } catch (e) {
      setError(e.message)
    }
    setStatus('')
    setLoading(false)
  }

  const canAnalyze = !loading && !!text.trim()

  function refreshExamples() {
    setRandomExamples(pickRandomItems(getAnalyzerExamples(lang), 5))
  }

  return (
    <div className="analyzer">
      <section className="card">
        <h2 className="section-title">{t.newLaw}</h2>
        <p className="section-subtitle">{t.newLawSub}</p>

        <div className="field">
          <label className="label">{t.titleLabel}</label>
          <input
            value={title}
            onChange={e => { setTitle(e.target.value); setPresetCaseId('') }}
            placeholder={t.titlePH}
            className="input"
          />
        </div>

        <div className="field">
          <label className="label">{t.textLabel}</label>
          <textarea
            value={text}
            onChange={e => { setText(e.target.value); setPresetCaseId('') }}
            rows={10}
            placeholder={t.textPH}
            className="input input--textarea"
          />
        </div>

        <button
          onClick={handleAnalyze}
          disabled={loading || !text.trim()}
          className={canAnalyze ? 'btn btn--active btn--block btn--lg' : 'btn btn--block btn--lg'}
        >
          {loading ? (
            <span className="btn__content">
              <Spinner />
              {status || t.analyzing}
            </span>
          ) : (
            t.analyzeBtn
          )}
        </button>

        {loading && (
          <div className="progress">
            <div className="progress__bar" />
          </div>
        )}

        <div className="examples">
          <div className="examples__head">
            <div className="label label--spaced">{t.examplesTitle}</div>
            <button type="button" onClick={refreshExamples} className="text-btn">
              {t.refreshRandom}
            </button>
          </div>
          {randomExamples.map((ex, i) => (
            <button
              key={i}
              onClick={() => { setTitle(ex.title); setText(ex.text); setPresetCaseId(ex.id || '') }}
              className="example-btn"
            >
              📄 {ex.title}
            </button>
          ))}
        </div>
      </section>

      <section>
        <ErrorBanner msg={error} onClose={() => setError('')} />
        {!results && !loading && (
          <div className="card empty-card">
            <div className="empty-card__icon">⚖️</div>
            <div className="empty-card__title">{t.noResult}</div>
            <div className="empty-card__subtitle">{t.noResultHint}</div>
          </div>
        )}
        {loading && (
          <div className="card loading-card">
            <Spinner size={36} />
            <div className="loading-card__status">{status}</div>
            <div className="loading-card__note">{t.checkingDB}</div>
          </div>
        )}
        {results && <AnalysisResults data={results} t={t} />}
      </section>
    </div>
  )
}

function AnalysisResults({ data, t }) {
  const { analysis, laws_checked, candidates } = data
  const riskColor = t.riskColor[analysis.risk_level] || 'orange'
  const riskLabel = t.riskMap[analysis.risk_level] || analysis.risk_level

  return (
    <div className="results">
      <section className="card">
        <div className="summary__header">
          <div className="summary__label">{t.summaryLabel}</div>
          <div className="summary__meta">
            <span className={`tag tag--${riskColor}`}>{t.riskLabel}: {riskLabel}</span>
            <span className="summary__checked">{t.checkedLabel}: {laws_checked} {t.lawsUnit}</span>
          </div>
        </div>
        <p className="summary__text">{analysis.summary}</p>
      </section>

      <section className="stat-grid">
        <div className="stat-card stat-card--red">
          <div className="stat-card__value">{analysis.contradictions?.length || 0}</div>
          <div className="stat-card__label">{t.contraLabel}</div>
        </div>
        <div className="stat-card stat-card--green">
          <div className="stat-card__value">{analysis.supports?.length || 0}</div>
          <div className="stat-card__label">{t.supLabel}</div>
        </div>
      </section>

      {analysis.contradictions?.length > 0 && (
        <section className="card card--danger">
          <div className="section-kicker section-kicker--red">
            {t.contraLabel} ({analysis.contradictions.length})
          </div>
          {analysis.contradictions.map((c, i) => {
            const sc = t.sevColor[c.severity] || 'red'
            const sl = t.sevMap[c.severity] || c.severity
            return (
              <div key={i} className={`issue issue--${sc}`}>
                <div className="issue__header">
                  <div className="issue__title">{c.law_title}</div>
                  <div className="issue__meta">
                    <span className="pill pill--code">{c.law_code}</span>
                    <span className={`tag tag--${sc} tag--sm`}>{sl}</span>
                  </div>
                </div>
                {c.article && <div className="issue__article">{c.article}</div>}
                <div className="issue__text">{c.explanation}</div>
              </div>
            )
          })}
        </section>
      )}

      {analysis.supports?.length > 0 && (
        <section className="card card--success">
          <div className="section-kicker section-kicker--green">
            {t.supLabel} ({analysis.supports.length})
          </div>
          {analysis.supports.map((sup, i) => (
            <div key={i} className="issue issue--green">
              <div className="issue__header">
                <div className="issue__title">{sup.law_title}</div>
                <span className="pill pill--code">{sup.law_code}</span>
              </div>
              {sup.article && <div className="issue__article">{sup.article}</div>}
              <div className="issue__text">{sup.explanation}</div>
            </div>
          ))}
        </section>
      )}

      {analysis.recommendations?.length > 0 && (
        <section className="card card--info">
          <div className="section-kicker section-kicker--blue">{t.recsLabel}</div>
          {analysis.recommendations.map((r, i) => (
            <div key={i} className="rec-item">
              <div className="rec-item__index">{i + 1}</div>
              <div className="rec-item__text">{r}</div>
            </div>
          ))}
        </section>
      )}

      <section className="card card--compact">
        <div className="section-kicker section-kicker--muted">{t.checkedLawsLabel}</div>
        <div className="pill-grid">
          {candidates.map(c => (
            <span key={c.code} className="pill">{c.code}</span>
          ))}
        </div>
      </section>
    </div>
  )
}
