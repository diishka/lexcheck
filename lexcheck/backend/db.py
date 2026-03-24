"""
Database repository — all SQL lives here, nowhere else.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import asyncpg

pool: Optional[asyncpg.Pool] = None
_laws_summary_cache: Optional[str] = None
_laws_summary_ts: float = 0.0
_candidate_cache: dict[tuple[str, int, str], tuple[float, list[dict]]] = {}
_chat_sessions: dict[str, dict] = {}
CANDIDATE_CACHE_TTL = int(os.getenv("CANDIDATE_CACHE_TTL", "120"))
CANDIDATE_CACHE_MAX = int(os.getenv("CANDIDATE_CACHE_MAX", "500"))
CANDIDATE_ARTICLES_PER_LAW = int(os.getenv("CANDIDATE_ARTICLES_PER_LAW", "6"))
UI_TITLE_MAX_CHARS = int(os.getenv("UI_TITLE_MAX_CHARS", "220"))
UI_SUMMARY_MAX_CHARS = int(os.getenv("UI_SUMMARY_MAX_CHARS", "420"))
CODE_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ]+(?:[-–—][0-9A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ]+)+")
LAW_CODE_NORM_SQL = (
    "regexp_replace("
    "replace(replace(replace(upper(coalesce(l.code, '')), '–', '-'), '—', '-'), '−', '-'), "
    "'\\s+', '', 'g'"
    ")"
)
LAW_FTS_RU_SQL = "to_tsvector('russian', (COALESCE(l.title_ru, ''::text) || ' '::text) || COALESCE(l.summary_ru, ''::text))"
LAW_FTS_UZ_SQL = "to_tsvector('simple', (COALESCE(l.title_uz, ''::text) || ' '::text) || COALESCE(l.summary_uz, ''::text))"
ARTICLE_FTS_RU_SQL = "to_tsvector('russian', a.content_ru)"
ARTICLE_FTS_UZ_SQL = "to_tsvector('simple', COALESCE(a.content_uz, ''::text))"
ASSISTANT_DATASET_MAIN = "lexai"
ASSISTANT_DATASET_SCHEMA = "schema12"


# ── Connection lifecycle ──────────────────────────────────────────────────────

async def connect(url: str) -> None:
    global pool
    pool = await asyncpg.create_pool(url, min_size=1, max_size=10)
    await _ensure_runtime_indexes()
    await _ensure_schema12_seed_data()


async def disconnect() -> None:
    if pool is not None:
        await pool.close()


# ── Laws ──────────────────────────────────────────────────────────────────────

def normalize_assistant_dataset(dataset: str | None) -> str:
    value = (dataset or "").strip().lower()
    if value in {"schema12", "schema-12", "demo", "seed", "uzb"}:
        return ASSISTANT_DATASET_SCHEMA
    return ASSISTANT_DATASET_MAIN


def _dataset_filter_sql(alias: str, dataset: str) -> str:
    if dataset == ASSISTANT_DATASET_SCHEMA:
        return f"{alias}.code LIKE 'UZB-%'"
    return f"{alias}.code NOT LIKE 'UZB-%'"


async def get_candidate_laws(query_text: str, top_k: int = 5, dataset: str | None = None) -> list[dict]:
    """Full-text search across titles, summaries, and article text."""
    dataset_name = normalize_assistant_dataset(dataset)
    cache_key = (query_text.strip().lower(), top_k, dataset_name)
    now = time.time()
    cached = _candidate_cache.get(cache_key)
    if cached and (now - cached[0]) < CANDIDATE_CACHE_TTL:
        return cached[1]

    code_tokens = _extract_code_tokens(query_text)
    law_dataset_filter = _dataset_filter_sql("l", dataset_name)
    article_dataset_filter = _dataset_filter_sql("l", dataset_name)

    ranked_sql = f"""
        WITH query AS (
            SELECT
                nullif(btrim($1), '') AS raw_search,
                '%' || nullif(btrim($1), '') || '%' AS pattern,
                plainto_tsquery('russian', coalesce($1, '')) AS q_ru,
                plainto_tsquery('simple', coalesce($1, '')) AS q_simple,
                $4::text[] AS code_tokens
        ),
        law_hits AS (
            SELECT hits.law_id, max(hits.rank) AS law_rank
            FROM (
                SELECT l.id AS law_id, 60 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {law_dataset_filter}
                  AND {LAW_CODE_NORM_SQL} = ANY(query.code_tokens)

                UNION ALL

                SELECT l.id AS law_id, 22 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {law_dataset_filter}
                  AND l.code ILIKE query.pattern

                UNION ALL

                SELECT l.id AS law_id, 10 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {law_dataset_filter}
                  AND l.category ILIKE query.pattern

                UNION ALL

                SELECT l.id AS law_id, 10 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {law_dataset_filter}
                  AND {LAW_FTS_RU_SQL} @@ query.q_ru

                UNION ALL

                SELECT l.id AS law_id, 10 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {law_dataset_filter}
                  AND {LAW_FTS_UZ_SQL} @@ query.q_simple
            ) hits
            GROUP BY hits.law_id
        ),
        article_hits AS (
            SELECT
                hits.law_id,
                max(hits.rank) AS article_rank
            FROM (
                SELECT a.law_id, 6 AS rank
                FROM law_articles a
                JOIN laws l ON l.id = a.law_id
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {article_dataset_filter}
                  AND a.article_num ILIKE query.pattern

                UNION ALL

                SELECT a.law_id, 4 AS rank
                FROM law_articles a
                JOIN laws l ON l.id = a.law_id
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {article_dataset_filter}
                  AND {ARTICLE_FTS_RU_SQL} @@ query.q_ru

                UNION ALL

                SELECT a.law_id, 4 AS rank
                FROM law_articles a
                JOIN laws l ON l.id = a.law_id
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {article_dataset_filter}
                  AND {ARTICLE_FTS_UZ_SQL} @@ query.q_simple
            ) hits
            GROUP BY hits.law_id
        ),
        matched_hits AS (
            SELECT law_id, max(rank) AS rank
            FROM (
                SELECT law_id, law_rank AS rank FROM law_hits
                UNION ALL
                SELECT law_id, article_rank AS rank FROM article_hits
            ) all_hits
            GROUP BY law_id
        ),
        ranked AS (
            SELECT
                l.id,
                l.code,
                l.title_ru,
                l.title_uz,
                l.category,
                l.year,
                l.summary_ru,
                l.summary_uz,
                matched_hits.rank
            FROM laws l
            JOIN matched_hits ON matched_hits.law_id = l.id
            WHERE {law_dataset_filter}
              AND NOT (l.id = ANY($5::int[]))
            ORDER BY matched_hits.rank DESC, l.year DESC, l.code
            LIMIT $2
        )
        SELECT
            r.*,
            coalesce(art.articles, '[]'::json) AS articles
        FROM ranked r
        CROSS JOIN query
        LEFT JOIN LATERAL (
            SELECT json_agg(
                json_build_object(
                    'article_num', ax.article_num,
                    'content_ru', ax.content_ru,
                    'content_uz', ax.content_uz,
                    'keywords', ax.keywords
                )
                ORDER BY ax.rank DESC, ax.id
            ) AS articles
            FROM (
                SELECT
                    a.id,
                    a.article_num,
                    a.content_ru,
                    a.content_uz,
                    a.keywords,
                    (
                        CASE WHEN query.raw_search IS NOT NULL AND a.article_num ILIKE query.pattern THEN 3 ELSE 0 END +
                        CASE WHEN query.raw_search IS NOT NULL AND to_tsvector('russian', a.content_ru) @@ query.q_ru THEN 2 ELSE 0 END +
                        CASE WHEN query.raw_search IS NOT NULL AND to_tsvector('simple', coalesce(a.content_uz, ''::text)) @@ query.q_simple THEN 2 ELSE 0 END +
                        CASE WHEN query.raw_search IS NOT NULL AND array_to_string(coalesce(a.keywords, ARRAY[]::text[]), ' ') ILIKE query.pattern THEN 1 ELSE 0 END
                    ) AS rank
                FROM law_articles a
                WHERE a.law_id = r.id
                ORDER BY rank DESC, a.id
                LIMIT $3
            ) ax
        ) art ON TRUE
        ORDER BY r.rank DESC, r.year DESC, r.code
    """
    exact_code_sql = """
        SELECT
            l.id,
            l.code,
            l.title_ru,
            l.title_uz,
            l.category,
            l.year,
            l.summary_ru,
            l.summary_uz,
            1000.0 AS rank,
            coalesce(art.articles, '[]'::json) AS articles
        FROM laws l
        LEFT JOIN LATERAL (
            SELECT json_agg(
                json_build_object(
                    'article_num', a.article_num,
                    'content_ru', a.content_ru,
                    'content_uz', a.content_uz,
                    'keywords', a.keywords
                )
                ORDER BY a.id
            ) AS articles
            FROM (
                SELECT id, article_num, content_ru, content_uz, keywords
                FROM law_articles
                WHERE law_id = l.id
                ORDER BY id
                LIMIT $2
            ) a
        ) art ON TRUE
        WHERE regexp_replace(
            replace(replace(replace(upper(coalesce(l.code, '')), '–', '-'), '—', '-'), '−', '-'),
            '\\s+',
            '',
            'g'
        ) = ANY($1::text[])
          AND {dataset_filter}
        ORDER BY l.year DESC, l.code
        LIMIT $3
    """.replace("{dataset_filter}", law_dataset_filter)
    fallback_sql = """
        SELECT
            l.id,
            l.code,
            l.title_ru,
            l.title_uz,
            l.category,
            l.year,
            l.summary_ru,
            l.summary_uz,
            0.0 AS rank,
            coalesce(art.articles, '[]'::json) AS articles
        FROM laws l
        LEFT JOIN LATERAL (
            SELECT json_agg(
                json_build_object(
                    'article_num', a.article_num,
                    'content_ru', a.content_ru,
                    'content_uz', a.content_uz,
                    'keywords', a.keywords
                )
                ORDER BY a.id
            ) AS articles
            FROM (
                SELECT id, article_num, content_ru, content_uz, keywords
                FROM law_articles
                WHERE law_id = l.id
                ORDER BY id
                LIMIT $2
            ) a
        ) art ON TRUE
        WHERE {dataset_filter}
          AND NOT (l.id = ANY($3::int[]))
        ORDER BY l.year DESC, l.code
        LIMIT $1
    """.replace("{dataset_filter}", law_dataset_filter)

    rows = []
    async with pool.acquire() as conn:
        matched_ids: list[int] = []
        if code_tokens:
            exact_rows = await conn.fetch(exact_code_sql, code_tokens, CANDIDATE_ARTICLES_PER_LAW, top_k)
            rows.extend(exact_rows)
            matched_ids.extend([row["id"] for row in exact_rows])

        remaining = max(0, top_k - len(rows))
        if remaining > 0:
            fts_rows = await conn.fetch(
                ranked_sql,
                query_text,
                remaining,
                CANDIDATE_ARTICLES_PER_LAW,
                code_tokens,
                matched_ids,
            )
            rows.extend(fts_rows)
            matched_ids.extend([row["id"] for row in fts_rows])

            if len(fts_rows) < min(4, remaining):
                fallback_rows = await conn.fetch(fallback_sql, remaining, CANDIDATE_ARTICLES_PER_LAW, matched_ids)
                rows.extend(fallback_rows)

    result = [_parse_law(row) for row in rows]
    if len(_candidate_cache) > CANDIDATE_CACHE_MAX:
        _candidate_cache.clear()
    _candidate_cache[cache_key] = (now, result)
    return result


async def get_all_laws(category: str = None, search: str = None) -> list[dict]:
    return await list_laws(category=category, search=search, limit=2000, offset=0, include_articles=True)


async def list_laws_page(
    category: str = None,
    search: str = None,
    limit: int = 30,
    offset: int = 0,
    include_articles: bool = False,
) -> tuple[list[dict], int]:
    search_text = (search or "").strip()
    category_filter = (category or "").strip()
    code_tokens = _extract_code_tokens(search_text)

    if not search_text:
        sql = """
            SELECT
                l.id,
                l.code,
                l.title_ru,
                l.title_uz,
                l.category,
                l.year,
                l.summary_ru,
                l.summary_uz,
                coalesce(ac.article_count, 0) AS article_count,
                count(*) OVER() AS total_count
            FROM laws l
            LEFT JOIN LATERAL (
                SELECT count(*) AS article_count
                FROM law_articles a_count
                WHERE a_count.law_id = l.id
            ) ac ON TRUE
            WHERE ($1 = '' OR l.category = $1)
            ORDER BY l.year DESC, l.code
            LIMIT $2 OFFSET $3
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, category_filter, limit, offset)
    else:
        sql = f"""
        WITH query AS (
            SELECT
                nullif(btrim($1), '') AS raw_search,
                '%' || nullif(btrim($1), '') || '%' AS pattern,
                plainto_tsquery('russian', coalesce($1, '')) AS q_ru,
                plainto_tsquery('simple', coalesce($1, '')) AS q_simple,
                $2::text[] AS code_tokens,
                $3::text AS category_filter
        ),
        law_hits AS (
            SELECT hits.law_id, max(hits.rank) AS law_rank
            FROM (
                SELECT l.id AS law_id, 60 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE {LAW_CODE_NORM_SQL} = ANY(query.code_tokens)

                UNION ALL

                SELECT l.id AS law_id, 22 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE l.code ILIKE query.pattern

                UNION ALL

                SELECT l.id AS law_id, 10 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE l.category ILIKE query.pattern

                UNION ALL

                SELECT l.id AS law_id, 10 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE {LAW_FTS_RU_SQL} @@ query.q_ru

                UNION ALL

                SELECT l.id AS law_id, 10 AS rank
                FROM laws l
                CROSS JOIN query
                WHERE {LAW_FTS_UZ_SQL} @@ query.q_simple
            ) hits
            GROUP BY hits.law_id
        ),
        article_hits AS (
            SELECT
                hits.law_id,
                max(hits.rank) AS article_rank
            FROM (
                SELECT a.law_id, 6 AS rank
                FROM law_articles a
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND a.article_num ILIKE query.pattern

                UNION ALL

                SELECT a.law_id, 4 AS rank
                FROM law_articles a
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {ARTICLE_FTS_RU_SQL} @@ query.q_ru

                UNION ALL

                SELECT a.law_id, 4 AS rank
                FROM law_articles a
                CROSS JOIN query
                WHERE query.raw_search IS NOT NULL
                  AND {ARTICLE_FTS_UZ_SQL} @@ query.q_simple
            ) hits
            GROUP BY hits.law_id
        ),
        matched_hits AS (
            SELECT law_id, max(rank) AS rank
            FROM (
                SELECT law_id, law_rank AS rank FROM law_hits
                UNION ALL
                SELECT law_id, article_rank AS rank FROM article_hits
            ) all_hits
            GROUP BY law_id
        ),
        matched AS (
            SELECT
                l.id,
                l.code,
                l.title_ru,
                l.title_uz,
                l.category,
                l.year,
                l.summary_ru,
                l.summary_uz,
                coalesce(ac.article_count, 0) AS article_count,
                matched_hits.rank AS search_rank
            FROM laws l
            LEFT JOIN LATERAL (
                SELECT count(*) AS article_count
                FROM law_articles a_count
                WHERE a_count.law_id = l.id
            ) ac ON TRUE
            JOIN matched_hits ON matched_hits.law_id = l.id
            WHERE ($3 = '' OR l.category = $3)
        )
        SELECT
            m.id,
            m.code,
            m.title_ru,
            m.title_uz,
            m.category,
            m.year,
            m.summary_ru,
            m.summary_uz,
            m.article_count,
            count(*) OVER() AS total_count
        FROM matched m
        ORDER BY m.search_rank DESC, m.year DESC, m.code
        LIMIT $4 OFFSET $5
    """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, search_text, code_tokens, category_filter, limit, offset)

    total = int(rows[0]["total_count"]) if rows else 0
    laws = [dict(row) for row in rows]
    for law in laws:
        law.pop("total_count", None)

    if not include_articles:
        for law in laws:
            law["articles"] = []
        return ([_parse_law(law) for law in laws], total)

    return (await _attach_articles(laws), total)


async def list_laws(
    category: str = None,
    search: str = None,
    limit: int = 30,
    offset: int = 0,
    include_articles: bool = False,
) -> list[dict]:
    items, _ = await list_laws_page(
        category=category,
        search=search,
        limit=limit,
        offset=offset,
        include_articles=include_articles,
    )
    return items


async def count_laws(category: str = None, search: str = None) -> int:
    _, total = await list_laws_page(
        category=category,
        search=search,
        limit=1,
        offset=0,
        include_articles=False,
    )
    return total


async def get_law(code: str) -> Optional[dict]:
    sql = """
        SELECT id, code, title_ru, title_uz, category, year, summary_ru, summary_uz
        FROM laws
        WHERE code = $1
        LIMIT 1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, code)
    if not row:
        return None
    laws = await _attach_articles([dict(row)])
    return laws[0]


async def get_category_stats() -> list[dict]:
    sql = """
        SELECT
            l.category,
            count(DISTINCT l.id) AS laws_count,
            count(a.id) AS articles_count,
            min(l.year) AS min_year,
            max(l.year) AS max_year
        FROM laws l
        LEFT JOIN law_articles a ON a.law_id = l.id
        GROUP BY l.category
        ORDER BY count(DISTINCT l.id) DESC, count(a.id) DESC, l.category
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
    return [dict(row) for row in rows]


async def get_all_laws_summary() -> str:
    sql = "SELECT code, title_ru, summary_ru FROM laws ORDER BY year DESC, code"
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
    return "\n".join(f"[{r['code']}] {r['title_ru']}: {r['summary_ru']}" for r in rows)


async def get_all_laws_summary_cached(ttl_seconds: int = 300) -> str:
    global _laws_summary_cache, _laws_summary_ts
    now = time.time()
    if _laws_summary_cache and (now - _laws_summary_ts) < ttl_seconds:
        return _laws_summary_cache
    _laws_summary_cache = await get_all_laws_summary()
    _laws_summary_ts = now
    return _laws_summary_cache


async def get_categories() -> list[str]:
    sql = "SELECT DISTINCT category FROM laws ORDER BY category"
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
    return [r["category"] for r in rows]


# ── Chat sessions ─────────────────────────────────────────────────────────────

async def create_session(session_id: str, title: str) -> None:
    _chat_sessions[session_id] = {
        "title": title,
        "messages": [],
        "created_at": time.time(),
    }


async def save_message(session_id: str, role: str, content: str) -> None:
    await save_message_meta(session_id, role, content)


async def save_message_meta(session_id: str, role: str, content: str, model: str | None = None) -> None:
    session = _chat_sessions.setdefault(
        session_id,
        {"title": content[:50], "messages": [], "created_at": time.time()},
    )
    message = {"role": role, "content": content}
    if model:
        message["model"] = model
    session["messages"].append(message)


async def get_history(session_id: str, limit: int = 20) -> list[dict]:
    session = _chat_sessions.get(session_id)
    if not session:
        return []
    return session["messages"][-limit:]


# ── Internal ──────────────────────────────────────────────────────────────────

async def _ensure_runtime_indexes() -> None:
    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "CREATE INDEX IF NOT EXISTS idx_laws_title_ru_trgm ON laws USING gin (title_ru gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS idx_laws_title_uz_trgm ON laws USING gin (title_uz gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS idx_law_articles_article_num_trgm ON law_articles USING gin (article_num gin_trgm_ops)",
    ]
    async with pool.acquire() as conn:
        for statement in statements:
            await conn.execute(statement)


async def _ensure_schema12_seed_data() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    if not schema_path.exists():
        return

    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT count(*) FROM laws WHERE code LIKE 'UZB-%'")
        existing_articles = await conn.fetchval(
            """
            SELECT count(*)
            FROM law_articles a
            JOIN laws l ON l.id = a.law_id
            WHERE l.code LIKE 'UZB-%'
            """
        )
        if int(existing or 0) >= 12 and int(existing_articles or 0) >= 40:
            return

        sql_text = schema_path.read_text(encoding="utf-8")
        if "SEED DATA" not in sql_text:
            return

        seed_sql = sql_text.split("SEED DATA", 1)[1]
        statements = [
            match.group(0).strip()
            for match in re.finditer(
                r"INSERT\s+INTO\s+(?:laws|law_articles)\b.*?;",
                seed_sql,
                flags=re.IGNORECASE | re.DOTALL,
            )
        ]
        if not statements:
            return

        async with conn.transaction():
            await conn.execute("DELETE FROM laws WHERE code LIKE 'UZB-%'")
            for statement in statements:
                await conn.execute(statement)

def _parse_law(row) -> dict:
    d = dict(row)
    d["articles"] = json.loads(d["articles"]) if isinstance(d.get("articles"), str) else (d.get("articles") or [])
    d["article_count"] = int(d.get("article_count") or len(d["articles"]))
    d["title_ru"] = _clean_text(d.get("title_ru"), UI_TITLE_MAX_CHARS)
    d["title_uz"] = _clean_text(d.get("title_uz"), UI_TITLE_MAX_CHARS)
    d["summary_ru"] = _clean_text(d.get("summary_ru"), UI_SUMMARY_MAX_CHARS)
    d["summary_uz"] = _clean_text(d.get("summary_uz"), UI_SUMMARY_MAX_CHARS)
    for article in d["articles"]:
        article["content_ru"] = _clean_text(article.get("content_ru"), 2200)
        article["content_uz"] = _clean_text(article.get("content_uz"), 2200)
        article["keywords"] = article.get("keywords") or []
    return d


async def _attach_articles(laws: list[dict]) -> list[dict]:
    if not laws:
        return []
    law_ids = [law["id"] for law in laws]
    sql = """
        SELECT law_id, article_num, content_ru, content_uz, keywords
        FROM law_articles
        WHERE law_id = ANY($1::int[])
        ORDER BY law_id, id
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, law_ids)

    articles_by_law: dict[int, list[dict]] = {law_id: [] for law_id in law_ids}
    for row in rows:
        articles_by_law[row["law_id"]].append(
            {
                "article_num": row["article_num"],
                "content_ru": row["content_ru"],
                "content_uz": row["content_uz"],
                "keywords": row["keywords"] or [],
            }
        )

    for law in laws:
        law["articles"] = articles_by_law.get(law["id"], [])
    return [_parse_law(law) for law in laws]


def _clean_text(text: Optional[str], max_chars: int | None = None) -> Optional[str]:
    if text is None:
        return None

    cleaned = re.sub(r"\[(?:\s*ОКОЗ:|\s*ТСЗ:).*?\]", " ", text, flags=re.DOTALL)
    cleaned = re.sub(r"Предложения по документу", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Прослушать аудио", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Получить ссылку из элемента документа", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \n\t-")

    if max_chars and len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 1].rstrip() + "…"
    return cleaned


def _extract_code_tokens(text: str) -> list[str]:
    tokens = CODE_TOKEN_RE.findall(text or "")
    normalized = []
    seen = set()
    for token in tokens:
        code = re.sub(r"\s+", "", token.upper())
        code = code.replace("–", "-").replace("—", "-").replace("−", "-")
        if code not in seen:
            seen.add(code)
            normalized.append(code)
    return normalized
