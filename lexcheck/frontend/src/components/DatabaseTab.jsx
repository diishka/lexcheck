import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api.js'
import { buildCivilCatalog, findCatalogPath } from '../civilCatalog.js'
import Spinner from './Spinner.jsx'
import ErrorBanner from './ErrorBanner.jsx'

const PAGE_SIZE = 36
const PLACEHOLDER_ARTICLE_RE = /^(?:full_text|text|document_text)$/i

function isPlaceholderArticleNum(value) {
  return PLACEHOLDER_ARTICLE_RE.test((value || '').trim())
}

export default function DatabaseTab({ lang, t }) {
  const [searchInput, setSearchInput] = useState('')
  const [activeSection, setActiveSection] = useState('')
  const [activeCategory, setActiveCategory] = useState('')
  const [expandedSections, setExpandedSections] = useState({})
  const [categoryStats, setCategoryStats] = useState([])
  const [laws, setLaws] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [selectedCode, setSelectedCode] = useState(null)
  const [selectedLaw, setSelectedLaw] = useState(null)
  const [loadingLaw, setLoadingLaw] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef(null)
  const detailRef = useRef(null)

  const searchQuery = searchInput.trim()
  const locale = lang === 'uz' ? 'uz-UZ' : 'ru-RU'
  const catalog = useMemo(() => buildCivilCatalog(categoryStats), [categoryStats])
  const shouldFetchLaws = Boolean(searchQuery || activeCategory)
  const activeSectionData = catalog.find(section => section.id === activeSection) || null
  const activePath = activeCategory
    ? findCatalogPath(catalog, activeCategory)
    : { section: activeSectionData, child: null }
  const selectedLawPath = selectedLaw
    ? findCatalogPath(catalog, selectedLaw.category)
    : { section: null, child: null }

  function formatNumber(value) {
    return Number(value || 0).toLocaleString(locale)
  }

  function getSectionTitle(section) {
    if (!section) return ''
    return lang === 'uz' ? (section.title_uz || section.title_ru) : section.title_ru
  }

  function getCategoryLabel(category) {
    return t.catMap[category] || category
  }

  function getLawTitle(law) {
    return lang === 'uz' ? (law.title_uz || law.title_ru) : law.title_ru
  }

  function getLawSummary(law) {
    return lang === 'uz' ? (law.summary_uz || law.summary_ru) : law.summary_ru
  }

  function formatPath(parts) {
    return parts.filter(Boolean).join(' / ')
  }

  useEffect(() => {
    api.getCategoryStats().then(setCategoryStats).catch(() => {})
  }, [])

  useEffect(() => {
    if (!activeCategory) return
    const path = findCatalogPath(catalog, activeCategory)
    if (!path.section) return
    setActiveSection(path.section.id)
    setExpandedSections(prev => ({ ...prev, [path.section.id]: true }))
  }, [activeCategory, catalog])

  useEffect(() => {
    let cancelled = false
    setError('')
    setSelectedLaw(null)
    setSelectedCode(null)
    setOffset(0)

    if (!shouldFetchLaws) {
      setLaws([])
      setTotal(0)
      setLoadingList(false)
      return () => { cancelled = true }
    }

    setLoadingList(true)
    api.getLaws({
      category: activeCategory || undefined,
      search: searchQuery || undefined,
      limit: PAGE_SIZE,
      offset: 0,
    })
      .then(data => {
        if (cancelled) return
        setLaws(data.items)
        setTotal(data.total)
        setOffset(0)
        setSelectedCode(data.items[0]?.code || null)
      })
      .catch(e => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoadingList(false)
      })

    return () => { cancelled = true }
  }, [activeCategory, searchQuery, shouldFetchLaws])

  useEffect(() => {
    if (!selectedCode) return
    let cancelled = false
    setLoadingLaw(true)
    api.getLaw(selectedCode)
      .then(data => {
        if (!cancelled) setSelectedLaw(data)
      })
      .catch(e => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoadingLaw(false)
      })
    return () => { cancelled = true }
  }, [selectedCode])

  useEffect(() => {
    if (!loadingList && shouldFetchLaws && window.innerWidth <= 1100) {
      listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [loadingList, shouldFetchLaws])

  useEffect(() => {
    if (!loadingLaw && selectedLaw && window.innerWidth <= 1100) {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [loadingLaw, selectedLaw])

  async function loadMore() {
    const nextOffset = offset + PAGE_SIZE
    setLoadingMore(true)
    setError('')
    try {
      const data = await api.getLaws({
        category: activeCategory || undefined,
        search: searchQuery || undefined,
        limit: PAGE_SIZE,
        offset: nextOffset,
      })
      setLaws(prev => [...prev, ...data.items])
      setOffset(nextOffset)
      setTotal(data.total)
    } catch (e) {
      setError(e.message)
    }
    setLoadingMore(false)
  }

  function resetCatalog() {
    setSearchInput('')
    setActiveSection('')
    setActiveCategory('')
    setSelectedLaw(null)
    setSelectedCode(null)
  }

  function toggleSection(section) {
    setSearchInput('')
    setActiveSection(section.id)
    setExpandedSections(prev => ({
      ...prev,
      [section.id]: !(prev[section.id] ?? false),
    }))

    if (section.children.length === 1) {
      setActiveCategory(section.children[0].category)
      return
    }

    setActiveCategory('')
    setSelectedLaw(null)
    setSelectedCode(null)
  }

  function selectLeaf(section, leaf) {
    setSearchInput('')
    setActiveSection(section.id)
    setActiveCategory(leaf.category)
    setExpandedSections(prev => ({ ...prev, [section.id]: true }))
  }

  const overallStats = useMemo(
    () => ({
      laws: catalog.reduce((sum, section) => sum + Number(section.laws_count || 0), 0),
      articles: catalog.reduce((sum, section) => sum + Number(section.articles_count || 0), 0),
      sections: catalog.length,
      subsections: catalog.reduce((sum, section) => sum + (section.children?.length || 0), 0),
    }),
    [catalog],
  )

  const listTitle = searchQuery
    ? t.dbSearchResults
    : activePath.child
      ? getCategoryLabel(activePath.child.label)
      : activePath.section
        ? getSectionTitle(activePath.section)
        : t.dbIndustryTitle

  const listPath = searchQuery
    ? formatPath([t.dbIndustryTitle, t.dbSearchResults])
    : formatPath([
        t.dbIndustryTitle,
        activePath.section ? getSectionTitle(activePath.section) : '',
        activePath.child ? getCategoryLabel(activePath.child.label) : '',
      ])

  const listOverviewMeta = searchQuery
    ? [t.dbDocsStat(formatNumber(total))]
    : activePath.child
      ? [
          t.dbDocsStat(formatNumber(activePath.child.laws_count)),
          t.dbArticlesStat(formatNumber(activePath.child.articles_count)),
          activePath.child.min_year && activePath.child.max_year
            ? t.yearsRange(activePath.child.min_year, activePath.child.max_year)
            : '',
        ]
      : activePath.section
        ? [
            t.dbDocsStat(formatNumber(activePath.section.laws_count)),
            t.dbArticlesStat(formatNumber(activePath.section.articles_count)),
            t.dbSubsectionsStat(formatNumber(activePath.section.children.length)),
          ]
        : [
            t.dbDocsStat(formatNumber(overallStats.laws)),
            t.dbArticlesStat(formatNumber(overallStats.articles)),
            t.dbSectionsStat(formatNumber(overallStats.sections)),
          ]

  const sectionCards = useMemo(() => {
    if (activeSectionData && !activeCategory && !searchQuery) {
      return activeSectionData.children.map(item => ({
        id: item.category,
        title: getCategoryLabel(item.label),
        path: formatPath([t.dbIndustryTitle, getSectionTitle(activeSectionData)]),
        docs: item.laws_count,
        articles: item.articles_count,
        years: item.min_year && item.max_year ? t.yearsRange(item.min_year, item.max_year) : '',
        onClick: () => selectLeaf(activeSectionData, item),
      }))
    }

    if (!activeCategory && !searchQuery) {
      return catalog.map(section => ({
        id: section.id,
        title: getSectionTitle(section),
        path: t.dbCatalogRoot,
        docs: section.laws_count,
        articles: section.articles_count,
        years: section.min_year && section.max_year ? t.yearsRange(section.min_year, section.max_year) : '',
        onClick: () => toggleSection(section),
        subtitle: t.dbSubsectionsStat(formatNumber(section.children.length)),
      }))
    }

    return []
  }, [activeSectionData, activeCategory, searchQuery, catalog, lang, t])

  const detailArticles = useMemo(() => {
    const lawCode = selectedLaw?.code || 'law'
    return (selectedLaw?.articles || []).map((article, index) => ({
      ...article,
      anchorId: `article-${lawCode}-${index}`,
      displayNum: isPlaceholderArticleNum(article.article_num)
        ? t.dbDocumentTextLabel
        : (article.article_num || t.dbDocumentTextLabel),
      isPlaceholder: isPlaceholderArticleNum(article.article_num),
      content: lang === 'uz' ? (article.content_uz || article.content_ru) : article.content_ru,
    }))
  }, [selectedLaw, lang, t])

  const articleNav = useMemo(() => {
    const seen = new Set()
    return detailArticles.filter(article => {
      const key = article.displayNum
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [detailArticles])

  const hasMore = laws.length < total
  const selectedTitle = selectedLaw ? getLawTitle(selectedLaw) : ''
  const selectedSectionTitle = selectedLawPath.section ? getSectionTitle(selectedLawPath.section) : ''
  const selectedCategoryLabel = selectedLawPath.child
    ? getCategoryLabel(selectedLawPath.child.label)
    : (selectedLaw ? getCategoryLabel(selectedLaw.category) : '')

  return (
    <div className="db-page">
      <ErrorBanner msg={error} onClose={() => setError('')} />
      <div className="db-shell">
        <aside className="card db-sidebar">
          <div className="db-sidebar__head">
            <div>
              <div className="db-panel__kicker">{t.dbCatalogRoot}</div>
              <h2 className="db-title">{t.dbTitle}</h2>
              <p className="db-count">{t.dbIndustrySubtitle}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={resetCatalog}
            className={!activeSection && !activeCategory && !searchQuery ? 'db-root db-root--active' : 'db-root'}
          >
            <span className="db-root__title">{t.dbIndustryTitle}</span>
            <span className="db-root__meta">
              <span>{t.dbSectionsStat(formatNumber(overallStats.sections))}</span>
              <span>{t.dbSubsectionsStat(formatNumber(overallStats.subsections))}</span>
            </span>
          </button>

          <input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            placeholder={t.searchPH}
            className="input input--search db-search"
          />
          {!!searchInput && (
            <button type="button" onClick={() => setSearchInput('')} className="link-btn">
              {t.resetSearch}
            </button>
          )}

          <div className="db-sidebar__section">
            <div className="db-sidebar__label">{t.sectionsLabel}</div>
            <div className="db-group-list">
              {catalog.map(section => {
                const expanded = expandedSections[section.id] ?? false
                const isActiveSection = activeSection === section.id
                return (
                  <div
                    key={section.id}
                    className={isActiveSection ? 'db-tree db-tree--active' : 'db-tree'}
                  >
                    <button
                      type="button"
                      onClick={() => toggleSection(section)}
                      className="db-tree__head"
                    >
                      <span className="db-tree__main">
                        <span className="db-tree__title">{getSectionTitle(section)}</span>
                        <span className="db-tree__stats">
                          <span>{t.dbDocsStat(formatNumber(section.laws_count))}</span>
                          <span>{t.dbSubsectionsStat(formatNumber(section.children.length))}</span>
                        </span>
                      </span>
                      <span className="db-tree__toggle" aria-hidden>
                        {section.children.length > 1 ? (expanded ? '−' : '+') : '→'}
                      </span>
                    </button>

                    {expanded && (
                      <div className="db-tree__children">
                        {section.children.map(item => (
                          <button
                            key={item.category}
                            type="button"
                            onClick={() => selectLeaf(section, item)}
                            className={activeCategory === item.category ? 'db-leaf db-leaf--active' : 'db-leaf'}
                          >
                            <span className="db-leaf__main">
                              <span className="db-leaf__title">{getCategoryLabel(item.label)}</span>
                              <span className="db-leaf__years">
                                {item.min_year && item.max_year ? t.yearsRange(item.min_year, item.max_year) : ''}
                              </span>
                            </span>
                            <span className="db-leaf__count">{formatNumber(item.laws_count)}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </aside>

        <section ref={listRef} className="card db-list-card">
          <div className="db-panel__head">
            <div>
              <div className="db-panel__kicker">{searchQuery ? t.dbSearchResults : t.docsLabel}</div>
              <div className="db-item__title">{listTitle}</div>
              <div className="db-panel__meta">
                {shouldFetchLaws ? t.resultCount(laws.length, total) : listPath}
              </div>
            </div>
          </div>

          <div className="db-overview-card">
            <div className="db-breadcrumb">{listPath || t.dbCatalogRoot}</div>
            <div className="db-overview-card__title">{listTitle}</div>
            <div className="db-overview-card__meta">
              {listOverviewMeta.filter(Boolean).map(item => (
                <span key={item} className="pill pill--soft">{item}</span>
              ))}
            </div>
            {!!searchQuery && (
              <div className="db-overview-card__hint">{t.dbSearchInfo(searchQuery)}</div>
            )}
            {!searchQuery && !activeCategory && activeSectionData && (
              <div className="db-overview-card__hint">{t.dbChooseSubsectionHint}</div>
            )}
            {!searchQuery && !activeSectionData && (
              <div className="db-overview-card__hint">{t.dbChooseSectionHint}</div>
            )}
          </div>

          {!shouldFetchLaws ? (
            <div className="db-branch-grid">
              {sectionCards.map(card => (
                <button
                  key={card.id}
                  type="button"
                  onClick={card.onClick}
                  className="db-branch-card"
                >
                  <div className="db-branch-card__path">{card.path}</div>
                  <div className="db-branch-card__title">{card.title}</div>
                  {card.subtitle && <div className="db-branch-card__subtitle">{card.subtitle}</div>}
                  <div className="db-branch-card__meta">
                    <span className="pill pill--soft">{t.dbDocsStat(formatNumber(card.docs))}</span>
                    <span className="pill pill--soft">{t.dbArticlesStat(formatNumber(card.articles))}</span>
                    {card.years && <span className="pill pill--soft">{card.years}</span>}
                  </div>
                </button>
              ))}
            </div>
          ) : loadingList ? (
            <div className="loading-center">
              <Spinner size={28} />
            </div>
          ) : laws.length === 0 ? (
            <div className="db-empty">
              <div className="db-empty__title">{t.noDocs}</div>
              <div className="db-empty__subtitle">{t.noDocsHint}</div>
            </div>
          ) : (
            <>
              <div className="db-list">
                {laws.map(law => {
                  const lawPath = findCatalogPath(catalog, law.category)
                  return (
                    <button
                      key={law.code}
                      type="button"
                      onClick={() => setSelectedCode(law.code)}
                      className={selectedCode === law.code ? 'db-item db-item--active' : 'db-item'}
                    >
                      <div className="db-item__path">
                        {formatPath([
                          lawPath.section ? getSectionTitle(lawPath.section) : '',
                          lawPath.child ? getCategoryLabel(lawPath.child.label) : getCategoryLabel(law.category),
                        ])}
                      </div>
                      <div className="db-item__top">
                        <span className="tag tag--blue">{lawPath.child ? getCategoryLabel(lawPath.child.label) : getCategoryLabel(law.category)}</span>
                        <div className="db-item__badges">
                          <span className="pill">{law.code}</span>
                          <span className="pill pill--soft">{t.dbArticleCountShort(formatNumber(law.article_count))}</span>
                        </div>
                      </div>
                      <div className="db-item__title">{getLawTitle(law)}</div>
                      <div className="db-item__summary">{getLawSummary(law)}</div>
                      <div className="db-item__footer">
                        <span>{law.year}</span>
                        <span>{t.articleCount(formatNumber(law.article_count))}</span>
                      </div>
                    </button>
                  )
                })}
              </div>

              {hasMore && (
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={loadingMore}
                  className={loadingMore ? 'btn btn--block' : 'btn btn--active btn--block'}
                >
                  {loadingMore ? t.analyzing : t.loadMore}
                </button>
              )}
            </>
          )}
        </section>

        <section ref={detailRef} className="card db-detail-card">
          {!selectedCode ? (
            <div className="db-empty db-empty--detail">
              <div className="db-empty__title">
                {activeSectionData && !activeCategory ? t.dbChooseSubsection : t.pickLaw}
              </div>
              <div className="db-empty__subtitle">
                {activeSectionData && !activeCategory ? t.dbChooseSubsectionHint : t.pickLawHint}
              </div>
            </div>
          ) : loadingLaw || !selectedLaw ? (
            <div className="loading-center">
              <Spinner size={28} />
            </div>
          ) : (
            <div className="db-detail">
              <div className="db-panel__head">
                <div>
                  <div className="db-panel__kicker">{t.selectedLaw}</div>
                  <div className="db-panel__meta">
                    {formatPath([t.dbIndustryTitle, selectedSectionTitle, selectedCategoryLabel])}
                  </div>
                </div>
              </div>

              <h3 className="db-detail__title">{selectedTitle}</h3>
              <div className="db-detail__meta">
                <span className="pill">{selectedLaw.code}</span>
                <span className="pill pill--soft">{selectedLaw.year}</span>
                <span className="pill pill--soft">{t.articleCount(formatNumber(selectedLaw.article_count || detailArticles.length))}</span>
                <span className="tag tag--blue">{selectedCategoryLabel}</span>
              </div>

              {!!articleNav.length && (
                <div className="db-detail__nav-wrap">
                  <div className="db-detail__nav-title">{t.dbDocumentStructure}</div>
                  <div className="db-detail__nav">
                    {articleNav.map(article => (
                      <button
                        key={article.anchorId}
                        type="button"
                        onClick={() => {
                          document.getElementById(article.anchorId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                        }}
                        className="db-detail__nav-chip"
                      >
                        {article.displayNum}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {detailArticles.length ? (
                <div className="db-articles">
                  {detailArticles.map((article, index) => (
                    <article key={`${article.article_num}-${index}`} id={article.anchorId} className="db-article">
                      <div className="db-article__num">{article.displayNum}</div>
                      <div className="db-article__text">{article.content}</div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="db-empty db-empty--inline">
                  <div className="db-empty__title">{t.dbNoArticles}</div>
                  <div className="db-empty__subtitle">{t.dbNoArticlesHint}</div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
