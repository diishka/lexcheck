"""
LexCheck UZ — FastAPI backend
Supports: Anthropic Claude API or local Ollama
"""

import json
import time
import hashlib
import re
import uuid
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional


def _detect_lang(text: str) -> str:
    """Detect language from character distribution: ru / uz / en."""
    normalized = (text or "").lower()
    cyrillic = len(re.findall(r'[а-яёА-ЯЁ]', text))
    latin    = len(re.findall(r'[a-zA-Z]', text))
    uzbek    = len(re.findall(r'[ʻʼoOgG][ʻʼ]|[oO]ʻ|[gG]ʻ', text))
    uzbek_words = len(re.findall(
        r"\b(qanday|qaysi|uchun|bilan|qonun|modda|hujjat|javob|haqida|bo'yicha|mavjud|kerak|mumkin|emas|bor|yo'q|shaxs|fuqaro|davlat|tadbirkorlik)\b",
        normalized,
    ))
    if cyrillic > latin * 0.3 and cyrillic > 3:
        return "ru"
    if uzbek > 0 or uzbek_words >= 2:
        return "uz"
    if latin > cyrillic * 2 and latin > 3:
        return "en"
    return "uz"  # default

from dotenv import load_dotenv
load_dotenv()  # Must run before importing db/llm so they see .env values

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
import llm
import cache_store

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/lexai")
CHAT_TOP_K = int(os.getenv("CHAT_TOP_K", "3"))
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", "6"))
CHAT_CONTEXT_SUMMARY_CHARS = int(os.getenv("CHAT_CONTEXT_SUMMARY_CHARS", "120"))
CHAT_CONTEXT_ARTICLE_CHARS = int(os.getenv("CHAT_CONTEXT_ARTICLE_CHARS", "180"))
CHAT_CONTEXT_ARTICLES_PER_LAW = int(os.getenv("CHAT_CONTEXT_ARTICLES_PER_LAW", "2"))
CHAT_LAW_CONTEXT_MAX_CHARS = int(os.getenv("CHAT_LAW_CONTEXT_MAX_CHARS", "900"))
CHAT_REPLY_CACHE_TTL = int(os.getenv("CHAT_REPLY_CACHE_TTL", "120"))
CHAT_REPLY_CACHE_MAX = int(os.getenv("CHAT_REPLY_CACHE_MAX", "200"))
ANALYZE_REPLY_CACHE_TTL = int(os.getenv("ANALYZE_REPLY_CACHE_TTL", "300"))
ANALYZE_REPLY_CACHE_MAX = int(os.getenv("ANALYZE_REPLY_CACHE_MAX", "100"))
PERSISTENT_CHAT_CACHE_TTL = int(os.getenv("PERSISTENT_CHAT_CACHE_TTL", "43200"))
PERSISTENT_ANALYZE_CACHE_TTL = int(os.getenv("PERSISTENT_ANALYZE_CACHE_TTL", "43200"))
LAW_CONTEXT_TITLE_CHARS = int(os.getenv("LAW_CONTEXT_TITLE_CHARS", "180"))
ANALYZE_TOP_K = int(os.getenv("ANALYZE_TOP_K", "3"))
CHAT_CACHE_VERSION = os.getenv("CHAT_CACHE_VERSION", "3")
ANALYZE_CACHE_VERSION = os.getenv("ANALYZE_CACHE_VERSION", "3")
_chat_reply_cache: dict[str, tuple[float, str, str]] = {}
_analyze_reply_cache: dict[str, tuple[float, dict]] = {}


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect(DB_URL)
    cache_store.init()
    asyncio.create_task(llm.warmup())
    print(
        f"✅ DB connected | LLM: {llm.PROVIDER} | "
        f"Chat: {llm.ACTIVE_CHAT_MODEL} | Analyze: {llm.ACTIVE_ANALYZE_MODEL}"
    )
    yield
    await db.disconnect()


app = FastAPI(title="LexCheck UZ API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    title: str = ""
    text: str
    top_k: Optional[int] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    law_context: Optional[str] = None
    top_k: Optional[int] = None
    dataset: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_provider": llm.PROVIDER,
        "chat_model": llm.ACTIVE_CHAT_MODEL,
        "analyze_model": llm.ACTIVE_ANALYZE_MODEL,
    }


@app.get("/categories")
async def categories():
    return await db.get_categories()


@app.get("/categories/stats")
async def category_stats():
    return await db.get_category_stats()


@app.get("/laws")
async def laws(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    include_articles: bool = False,
):
    items, total = await db.list_laws_page(
        category=category,
        search=search,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
        include_articles=include_articles,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/laws/{code}")
async def law_detail(code: str):
    law = await db.get_law(code)
    if not law:
        raise HTTPException(404, "Law not found")
    return law


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if not req.text.strip():
        raise HTTPException(400, "Law text is required")

    top_k = max(1, min(req.top_k or ANALYZE_TOP_K, 8))
    candidates = await db.get_candidate_laws(req.text + " " + req.title, top_k)
    if not candidates:
        raise HTTPException(404, "No laws found in database")
    candidate_signature = _make_candidate_signature(candidates)
    cache_key = _make_analyze_cache_key(req.title, req.text, top_k, candidate_signature)
    cached = _analyze_reply_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < ANALYZE_REPLY_CACHE_TTL:
        return cached[1]

    persistent_cached = cache_store.get("analyze", cache_key)
    if persistent_cached:
        result = persistent_cached["value"]
        if len(_analyze_reply_cache) > ANALYZE_REPLY_CACHE_MAX:
            _analyze_reply_cache.clear()
        _analyze_reply_cache[cache_key] = (time.time(), result)
        return result

    input_lang = _detect_lang(req.title + " " + req.text)
    input_lang_name = {"uz": "Uzbek", "ru": "Russian", "en": "English"}[input_lang]
    system = (
        "You analyze draft laws for Uzbekistan legislation. "
        "Return only valid JSON, no markdown. "
        "Use only retrieved law codes, titles, and articles from context. "
        "If context is weak, say so instead of inventing citations. "
        f"Write every text field in {input_lang_name} only."
    )
    prompt = _build_analyze_prompt(
        req.title,
        req.text,
        _build_law_context(
            candidates,
            query_text=req.title + " " + req.text,
        ),
    )
    try:
        raw = await llm.chat(system, [{"role": "user", "content": prompt}], task="analyze")
        analysis = _parse_json(raw)
        analysis_from_llm = True
    except HTTPException:
        analysis = _build_analyze_fallback(candidates, input_lang)
        analysis_from_llm = False

    result = {
        "analysis": analysis,
        "laws_checked": len(candidates),
        "candidates": [
            {"code": c["code"], "title_ru": c["title_ru"], "category": c["category"]}
            for c in candidates
        ],
    }
    if len(_analyze_reply_cache) > ANALYZE_REPLY_CACHE_MAX:
        _analyze_reply_cache.clear()
    _analyze_reply_cache[cache_key] = (time.time(), result)
    if analysis_from_llm:
        cache_store.set(
            "analyze",
            cache_key,
            result,
            PERSISTENT_ANALYZE_CACHE_TTL,
            meta={"model": llm.ACTIVE_ANALYZE_MODEL},
        )
    return result


@app.post("/chat/session")
async def create_session():
    session_id = str(uuid.uuid4())
    await db.create_session(session_id, "Новая сессия")
    return {"session_id": session_id}


@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    if not req.session_id:
        await db.create_session(session_id, req.message[:50])

    await db.save_message(session_id, "user", req.message)
    dataset = db.normalize_assistant_dataset(req.dataset)
    top_k = max(1, min(req.top_k or CHAT_TOP_K, 8))
    if dataset == db.ASSISTANT_DATASET_SCHEMA:
        top_k = 12
    history, candidates = await asyncio.gather(
        db.get_history(session_id, limit=CHAT_HISTORY_LIMIT),
        db.get_candidate_laws(req.message + " " + (req.law_context or ""), top_k, dataset=dataset),
    )
    candidate_signature = _make_candidate_signature(candidates)
    laws_context = _build_law_context(
        candidates,
        query_text=req.message + " " + (req.law_context or ""),
        summary_chars=CHAT_CONTEXT_SUMMARY_CHARS,
        article_chars=CHAT_CONTEXT_ARTICLE_CHARS,
        articles_per_law=CHAT_CONTEXT_ARTICLES_PER_LAW,
    ) if candidates else ""

    law_block = (
        f"\n\nCURRENT DRAFT LAW:\n{req.law_context[:CHAT_LAW_CONTEXT_MAX_CHARS]}"
        if req.law_context
        else ""
    )
    lang = _detect_lang(req.message)
    lang_name = {"uz": "Uzbek", "ru": "Russian", "en": "English"}[lang]
    detailed_matches_label = {
        "ru": "Точные совпадения",
        "uz": "Aniq mos kelgan normalar",
        "en": "Exact matching rules",
    }[lang]
    dataset_instruction = (
        "Use only the 12 laws from the schema12 dataset. Ignore the larger lexai corpus.\n\n"
        if dataset == db.ASSISTANT_DATASET_SCHEMA
        else "Use only the main lexai dataset. Ignore schema12 demo laws.\n\n"
    )
    has_exact_article_context = _has_exact_article_context(
        candidates,
        req.message + " " + (req.law_context or ""),
    )
    missing_article_instruction = {
        "ru": (
            "Within the retrieved documents for this query, no real article breakdown is available. "
            "State this clearly and refer to document codes and titles only."
        ),
        "uz": (
            "Ushbu so'rov uchun tanlangan hujjatlar orasida haqiqiy modda bo'linishi topilmadi. "
            "Buni aniq ayting va faqat hujjat kodlari hamda sarlavhalariga tayaning."
        ),
        "en": (
            "Within the retrieved documents for this query, no real article breakdown is available. "
            "State this clearly and refer to document codes and titles only."
        ),
    }[lang]
    extra_instruction = (
        "Exact article citations are available in the context, so prefer them.\n\n"
        if has_exact_article_context
        else f"{missing_article_instruction}\n\n"
    )
    system = (
        f"You are LexCheck UZ, a legal assistant for Uzbekistan legislation.\n"
        f"Answer in {lang_name} only.\n"
        f"Use only law codes and article identifiers that appear in the retrieved context.\n"
        f"If context is insufficient, say so instead of inventing citations.\n"
        f"Keep the answer compact and informative.\n"
        f"Group multiple articles of the same code into one line.\n\n"
        f"{dataset_instruction}"
        f"Format:\n"
        f"1. Short answer in 2-4 sentences.\n"
        f"2. {detailed_matches_label}:\n"
        f"- CODE | Category | Article(s) | short explanation\n"
        f"3. Brief conclusion in 1-2 sentences.\n\n"
        f"{extra_instruction}"
        f"Retrieved laws:\n{laws_context}{law_block}"
    )

    cache_key = _make_chat_cache_key(history, req.law_context, top_k, dataset, candidate_signature)
    cached = _chat_reply_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CHAT_REPLY_CACHE_TTL:
        reply = _append_exact_sources(cached[1], candidates, req.message, lang)
        model_used = cached[2]
    else:
        persistent_cached = cache_store.get("chat", cache_key)
        if persistent_cached:
            cached_value = persistent_cached["value"]
            reply = _append_exact_sources(cached_value["reply"], candidates, req.message, lang)
            model_used = cached_value.get("model") or persistent_cached["meta"].get("model") or "cache"
        else:
            if not req.law_context and _is_fast_lookup_query(req.message):
                reply = _build_fast_lookup_reply(req.message, candidates, lang)
                model_used = "database-fastpath"
            else:
                try:
                    llm_result = await llm.chat_with_meta(
                        system,
                        [{"role": m["role"], "content": m["content"]} for m in history],
                        task="chat",
                    )
                    reply = llm_result["content"]
                    model_used = llm_result["model"]
                    reply = await _ensure_reply_language(reply, lang)
                    reply = _append_exact_sources(reply, candidates, req.message, lang)
                    cache_store.set(
                        "chat",
                        cache_key,
                        {"reply": reply, "model": model_used},
                        PERSISTENT_CHAT_CACHE_TTL,
                        meta={"model": model_used},
                    )
                except HTTPException:
                    reply = _build_chat_fallback(req.message, candidates, lang)
                    model_used = "database-fallback"
        if len(_chat_reply_cache) > CHAT_REPLY_CACHE_MAX:
            _chat_reply_cache.clear()
        _chat_reply_cache[cache_key] = (time.time(), reply, model_used)

    await db.save_message_meta(session_id, "assistant", reply, model=model_used)

    return {"session_id": session_id, "reply": reply, "model": model_used, "dataset": dataset}


@app.get("/chat/{session_id}/history")
async def history(session_id: str):
    return {"messages": await db.get_history(session_id, limit=50)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_law_context(
    candidates: list[dict],
    query_text: str = "",
    summary_chars: int = 100,
    article_chars: int = 120,
    articles_per_law: int = 2,
) -> str:
    parts = []
    for law in candidates:
        title = _compact_text(_pick_field(law, "title"), LAW_CONTEXT_TITLE_CHARS)
        summary = _compact_text(_pick_field(law, "summary"), summary_chars)
        selected_articles = _select_articles_for_query(law, query_text, articles_per_law)
        articles = "\n".join(
            f"  - {a['article_num']}: {_compact_text(a.get('content_uz') or a.get('content_ru') or '', article_chars)}"
            for a in selected_articles
        )
        parts.append(
            f"[{law['code']}] {title} ({law['year']})\n"
            f"Category/Section: {law.get('category') or 'Unknown'}\n"
            f"Summary: {summary}\n"
            f"Relevant articles from database:\n{articles or '  - No exact article text available'}"
    )
    return "\n\n---\n\n".join(parts)


def _pick_field(law: dict, field_base: str) -> str:
    return (law.get(f"{field_base}_uz") or law.get(f"{field_base}_ru") or "")


def _compact_text(text: str, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokenize_query(text: str) -> list[str]:
    stop_words = {
        "как", "что", "это", "для", "при", "или", "если", "когда", "где", "его", "ее",
        "они", "она", "оно", "есть", "про", "под", "над", "без", "the", "and", "with",
        "qanday", "qaysi", "uchun", "bilan", "yoki", "ham", "shu", "bu", "bir", "bor",
    }
    tokens = re.findall(r"[0-9A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʼʻ-]+", (text or "").lower())
    return [token for token in tokens if len(token) >= 2 and token not in stop_words]


def _score_article_for_query(article: dict, query_text: str) -> int:
    query_norm = _normalize_text(query_text)
    query_tokens = list(dict.fromkeys(_tokenize_query(query_text)))
    article_num = article.get("article_num") or ""
    haystack = _normalize_text(" ".join([
        article_num,
        " ".join(article.get("keywords") or []),
        article.get("content_uz") or "",
        article.get("content_ru") or "",
    ]))
    score = 0

    if query_norm and len(query_norm) > 8 and query_norm in haystack:
        score += 20
    if article_num and _normalize_text(article_num) in query_norm:
        score += 12
    for token in query_tokens:
        if token in haystack:
            score += 4 if len(token) >= 6 else 2

    return score


def _select_articles_for_query(law: dict, query_text: str, limit: int) -> list[dict]:
    articles = list(law.get("articles") or [])
    if not articles or limit <= 0:
        return []

    real_articles = [
        article
        for article in articles
        if not _is_placeholder_article_num(article.get("article_num"))
    ]
    placeholder_articles = [
        article
        for article in articles
        if _is_placeholder_article_num(article.get("article_num"))
    ]
    candidate_articles = real_articles or placeholder_articles

    scored: list[tuple[int, int, dict]] = []
    for idx, article in enumerate(candidate_articles):
        scored.append((_score_article_for_query(article, query_text), idx, article))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [article for score, _, article in scored if score > 0][:limit]

    if len(selected) < limit:
        seen = {id(article) for article in selected}
        for article in candidate_articles:
            if id(article) in seen:
                continue
            selected.append(article)
            if len(selected) >= limit:
                break

    return selected


def _lookup_requests_articles(query_text: str) -> bool:
    normalized = _normalize_text(query_text)
    return any(
        token in normalized
        for token in (
            "modda", "moddalar", "статья", "статьи", "статей",
            "article", "articles", "норма", "нормы", "норм",
        )
    )


def _is_fast_lookup_query(query_text: str) -> bool:
    normalized = _normalize_text(query_text)
    starters = ("qaysi", "qanday", "какие", "какой", "какая", "какое", "which", "what", "покажи", "show")
    nouns = (
        "modda", "moddalar", "hujjat", "hujjatlar", "normalar",
        "стат", "документ", "норм", "article", "articles", "document", "documents", "law", "laws",
    )
    return any(normalized.startswith(prefix) for prefix in starters) and any(noun in normalized for noun in nouns)


def _build_exact_sources(query_text: str, candidates: list[dict], lang: str, max_items: int = 8) -> list[str]:
    lines: list[str] = []
    no_breakdown_label = {
        "ru": "без разбивки на статьи",
        "uz": "moddalarga ajratilmagan",
        "en": "without article breakdown",
    }

    ranked: list[tuple[int, int, dict, dict]] = []
    for law_idx, law in enumerate(candidates):
        selected = _select_articles_for_query(law, query_text, max_items)
        for article_idx, article in enumerate(selected):
            ranked.append((_score_article_for_query(article, query_text), law_idx * 100 + article_idx, law, article))

    ranked.sort(key=lambda item: (-item[0], item[1]))

    grouped: dict[str, dict] = {}
    no_breakdown_codes: list[str] = []
    for _, _, law, article in ranked:
        code = law["code"]
        group = grouped.setdefault(code, {
            "code": code,
            "articles": [],
        })

        article_num = article.get("article_num") or "-"
        if _is_placeholder_article_num(article_num):
            if code not in no_breakdown_codes:
                no_breakdown_codes.append(code)
            continue
        if article_num not in group["articles"]:
            group["articles"].append(article_num)

    real_article_groups = [group for group in grouped.values() if group["articles"]]
    for group in real_article_groups[:max_items]:
        article_list = ", ".join(group["articles"])
        lines.append(f"- {group['code']}: {article_list}")

    if no_breakdown_codes and not lines:
        limited_codes = ", ".join(no_breakdown_codes[:max_items])
        if len(no_breakdown_codes) > max_items:
            limited_codes += ", ..."
        lines.append(f"- {no_breakdown_label[lang]}: {limited_codes}")

    return lines


def _has_exact_article_context(candidates: list[dict], query_text: str) -> bool:
    for law in candidates:
        for article in _select_articles_for_query(law, query_text, CHAT_CONTEXT_ARTICLES_PER_LAW):
            if not _is_placeholder_article_num(article.get("article_num")):
                return True
    return False


def _append_exact_sources(reply: str, candidates: list[dict], query_text: str, lang: str) -> str:
    section_titles = {
        "ru": "Источники",
        "uz": "Manbalar",
        "en": "Sources",
    }
    no_sources = {
        "ru": "Точные статьи не найдены.",
        "uz": "Aniq moddalar topilmadi.",
        "en": "Exact articles not found.",
    }

    if section_titles[lang] in (reply or ""):
        return reply

    lines = _build_exact_sources(query_text, candidates, lang)
    block = "\n".join(lines) if lines else f"- {no_sources[lang]}"
    return f"{reply.rstrip()}\n\n{section_titles[lang]}:\n{block}"


def _build_fast_lookup_reply(query_text: str, candidates: list[dict], lang: str) -> str:
    if not candidates:
        return {
            "ru": "По базе не найдено релевантных документов для этого запроса.",
            "uz": "Bazadan ushbu so'rov uchun mos hujjatlar topilmadi.",
            "en": "No relevant documents were found in the database for this query.",
        }[lang]

    article_mode = _lookup_requests_articles(query_text)
    relevant = candidates[:4]
    section_title = {
        "ru": "Найдено по базе",
        "uz": "Bazadan topildi",
        "en": "Found in database",
    }[lang]
    exact_intro = {
        "ru": "По этому запросу найдены точные совпадения в базе.",
        "uz": "Ushbu so'rov bo'yicha bazada aniq mos keladigan normalar topildi.",
        "en": "Exact matches were found in the database for this query.",
    }[lang]
    no_article_intro = {
        "ru": "По этому запросу найдены подходящие документы, но среди выбранных совпадений нет точной разбивки на статьи.",
        "uz": "Ushbu so'rov bo'yicha mos hujjatlar topildi, ammo tanlangan mosliklarda aniq modda raqamlari yo'q.",
        "en": "Relevant documents were found for this query, but the selected matches do not contain exact article breakdowns.",
    }[lang]

    lines = []
    has_real_articles = False
    for law in relevant:
        title = _compact_text(_pick_field(law, "title"), 120)
        category = law.get("category") or {
            "ru": "Без категории",
            "uz": "Bo'lim ko'rsatilmagan",
            "en": "No category",
        }[lang]
        article_nums = [
            article.get("article_num") or "-"
            for article in _select_articles_for_query(law, query_text, 4)
            if not _is_placeholder_article_num(article.get("article_num"))
        ]
        unique_articles = list(dict.fromkeys(article_nums))
        if unique_articles:
            has_real_articles = True
            lines.append(f"- {law['code']} | {category} | {', '.join(unique_articles)}")
        elif not article_mode:
            lines.append(f"- {law['code']} | {category} | {title}")
        else:
            lines.append(f"- {law['code']} | {category} | {title}")

    sources = _build_exact_sources(query_text, candidates, lang)
    sources_title = {
        "ru": "Источники",
        "uz": "Manbalar",
        "en": "Sources",
    }[lang]

    intro = exact_intro if (has_real_articles or not article_mode) else no_article_intro
    return (
        f"{intro}\n\n"
        f"{section_title}:\n" + "\n".join(lines[:4]) +
        f"\n\n{sources_title}:\n" + ("\n".join(sources) if sources else "-")
    )


def _build_chat_fallback(query_text: str, candidates: list[dict], lang: str) -> str:
    intro = {
        "ru": "LLM временно недоступна, поэтому ответ собран напрямую из базы.",
        "uz": "LLM vaqtincha ishlamayapti, shuning uchun javob to'g'ridan-to'g'ri bazadan yig'ildi.",
        "en": "The LLM is temporarily unavailable, so this answer was assembled directly from the database.",
    }[lang]
    no_matches = {
        "ru": "По базе не нашлось релевантных документов для этого запроса.",
        "uz": "Bazadan ushbu so'rov uchun mos hujjatlar topilmadi.",
        "en": "No relevant documents were found in the database for this query.",
    }[lang]
    conclusion = {
        "ru": "Проверьте коды и формулировку запроса или повторите позже.",
        "uz": "Kodlar va so'rov matnini tekshirib ko'ring yoki keyinroq qayta urinib ko'ring.",
        "en": "Check the law code and wording of the query or try again later.",
    }[lang]

    if not candidates:
        return f"{intro}\n\n{no_matches}\n\n{conclusion}"

    lines = []
    for law in candidates[:4]:
        title = _compact_text(_pick_field(law, "title"), 120)
        summary = _compact_text(_pick_field(law, "summary"), 120)
        category = law.get("category") or "Unknown"
        article_nums = [
            article.get("article_num") or "-"
            for article in _select_articles_for_query(law, query_text, 3)
            if not _is_placeholder_article_num(article.get("article_num"))
        ]
        article_list = ", ".join(dict.fromkeys(article_nums)) if article_nums else {
            "ru": "без разбивки на статьи",
            "uz": "moddalarga ajratilmagan",
            "en": "no article breakdown",
        }[lang]
        lines.append(
            f"- {law['code']} | {category} | {article_list} | {summary or title}"
        )

    sources = _build_exact_sources(query_text, candidates, lang)
    section_title = {
        "ru": "Найдено по базе",
        "uz": "Bazadan topildi",
        "en": "Found in database",
    }[lang]
    sources_title = {
        "ru": "Источники",
        "uz": "Manbalar",
        "en": "Sources",
    }[lang]
    return (
        f"{intro}\n\n"
        f"{section_title}:\n" + "\n".join(lines) +
        f"\n\n{sources_title}:\n" + ("\n".join(sources) if sources else "-")
    )


def _build_analyze_fallback(candidates: list[dict], lang: str) -> dict:
    summary_map = {
        "ru": "LLM временно недоступна. Ниже показаны ближайшие документы из базы, которые стоит проверить вручную.",
        "uz": "LLM vaqtincha ishlamayapti. Quyida bazadan qo'lda tekshirish uchun eng yaqin hujjatlar ko'rsatilgan.",
        "en": "The LLM is temporarily unavailable. The closest documents from the database are shown below for manual review.",
    }
    support_map = {
        "ru": "Документ найден по базе и может быть релевантен для ручной проверки.",
        "uz": "Hujjat bazadan topildi va qo'lda tekshirish uchun relevant bo'lishi mumkin.",
        "en": "This document was found in the database and may be relevant for manual review.",
    }
    recs_map = {
        "ru": [
            "Проверьте найденные документы и статьи вручную.",
            "Повторите анализ позже, когда LLM снова будет доступна.",
            "Если нужен быстрый ответ, уменьшите объем текста законопроекта.",
        ],
        "uz": [
            "Topilgan hujjatlar va moddalarni qo'lda tekshirib chiqing.",
            "LLM qayta ishlaganda tahlilni keyinroq yana ishga tushiring.",
            "Tezroq javob kerak bo'lsa, qonun loyihasi matnini qisqartiring.",
        ],
        "en": [
            "Review the retrieved documents and articles manually.",
            "Retry the analysis later when the LLM is available again.",
            "If you need a faster answer, shorten the draft law text.",
        ],
    }

    supports = []
    for law in candidates[:4]:
        article_nums = [
            article.get("article_num") or "-"
            for article in _select_articles_for_query(law, "", 2)
            if not _is_placeholder_article_num(article.get("article_num"))
        ]
        supports.append({
            "law_code": law["code"],
            "law_title": law.get("title_ru") or law.get("title_uz") or law["code"],
            "article": ", ".join(dict.fromkeys(article_nums)) if article_nums else None,
            "explanation": support_map[lang],
        })

    return {
        "summary": summary_map[lang],
        "risk_level": "medium",
        "contradictions": [],
        "supports": supports,
        "recommendations": recs_map[lang],
    }


async def _ensure_reply_language(reply: str, target_lang: str) -> str:
    if not reply.strip():
        return reply

    current_lang = _detect_lang(_strip_sources_block(reply))
    if current_lang == target_lang:
        return reply

    target_lang_name = {"ru": "Russian", "uz": "Uzbek", "en": "English"}[target_lang]
    system = (
        "You are a legal text translator.\n"
        f"Translate the answer to {target_lang_name} only.\n"
        "Preserve law codes, article numbers, bullet structure, and legal citations exactly.\n"
        "Do not add new facts. Do not omit any legal references.\n"
        "Return only the translated answer text."
    )
    try:
        return await llm.chat(
            system,
            [{"role": "user", "content": reply}],
            task="chat",
        )
    except HTTPException:
        return reply


def _strip_sources_block(reply: str) -> str:
    text = reply or ""
    for marker in ("\n\nИсточники:", "\n\nManbalar:", "\n\nSources:"):
        if marker in text:
            return text.split(marker, 1)[0]
    return text


def _make_chat_cache_key(
    history: list[dict],
    law_context: Optional[str],
    top_k: int,
    dataset: str,
    candidate_signature: str,
) -> str:
    payload = {
        "version": CHAT_CACHE_VERSION,
        "model": llm.ACTIVE_CHAT_MODEL,
        "history": history,
        "law_context": (law_context or "")[:CHAT_LAW_CONTEXT_MAX_CHARS],
        "top_k": top_k,
        "dataset": dataset,
        "candidate_signature": candidate_signature,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _make_analyze_cache_key(title: str, text: str, top_k: int, candidate_signature: str) -> str:
    payload = {
        "version": ANALYZE_CACHE_VERSION,
        "model": llm.ACTIVE_ANALYZE_MODEL,
        "title": title or "",
        "text": text or "",
        "top_k": top_k,
        "candidate_signature": candidate_signature,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _make_candidate_signature(candidates: list[dict]) -> str:
    payload = []
    for law in candidates[:8]:
        articles = law.get("articles") or []
        payload.append({
            "code": law.get("code"),
            "year": law.get("year"),
            "articles": [
                (article.get("article_num") or "").strip()
                for article in articles[:4]
            ],
        })
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_placeholder_article_num(article_num: Optional[str]) -> bool:
    value = (article_num or "").strip().lower()
    return value in {"", "-", "full_text", "full text", "document_text", "document text"}


def _build_analyze_prompt(title: str, text: str, context: str) -> str:
    return f"""Analyze the draft law:

TITLE: {title or "(untitled)"}
TEXT: {text}

APPLICABLE LAWS:
{context}

For risk_level use ONLY: high, medium, low.
For severity use ONLY: high, medium, low.

Return ONLY valid JSON:
{{
  "summary": "2-3 sentences",
  "risk_level": "high|medium|low",
  "contradictions": [
    {{"law_code": "...", "law_title": "...", "article": "...", "severity": "high|medium|low", "explanation": "1-2 sentences"}}
  ],
  "supports": [
    {{"law_code": "...", "law_title": "...", "article": "...", "explanation": "1-2 sentences"}}
  ],
  "recommendations": ["recommendation 1", "recommendation 2"]
}}"""


def _parse_json(raw: str) -> dict:
    try:
        clean = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            clean = match.group(0)
        return json.loads(clean)
    except Exception:
        return {
            "summary": "AI javobi tahlil qilinmadi. Iltimos qayta urinib ko'ring.",
            "risk_level": "medium",
            "contradictions": [],
            "supports": [],
            "recommendations": ["AI javobi to'g'ri formatda kelmadi. Iltimos qayta urinib ko'ring."],
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
