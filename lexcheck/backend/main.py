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
    uzbek_stems = (
        "qanday", "qaysi", "uchun", "bilan", "qonun", "modda", "hujjat", "javob",
        "haqida", "boyicha", "bo'yicha", "mavjud", "kerak", "mumkin", "emas", "bor",
        "yoq", "yo'q", "shaxs", "fuqaro", "davlat", "tadbirkor", "asosiy", "muhim",
        "ko'rsat", "korsat", "normalar", "qoidalar", "ichiga", "oladi",
    )
    normalized_ascii = normalized.replace("ʻ", "'").replace("ʼ", "'")
    uzbek_words = sum(1 for stem in uzbek_stems if stem in normalized_ascii)
    if cyrillic > latin * 0.3 and cyrillic > 3:
        return "ru"
    if uzbek > 0 or uzbek_words >= 1:
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
PERSISTENT_TRANSLATE_CACHE_TTL = int(os.getenv("PERSISTENT_TRANSLATE_CACHE_TTL", "2592000"))
LAW_CONTEXT_TITLE_CHARS = int(os.getenv("LAW_CONTEXT_TITLE_CHARS", "180"))
ANALYZE_TOP_K = int(os.getenv("ANALYZE_TOP_K", "3"))
CHAT_CACHE_VERSION = os.getenv("CHAT_CACHE_VERSION", "3")
ANALYZE_CACHE_VERSION = os.getenv("ANALYZE_CACHE_VERSION", "3")
_chat_reply_cache: dict[str, tuple[float, str, str]] = {}
_analyze_reply_cache: dict[str, tuple[float, dict]] = {}
_translation_cache: dict[str, tuple[float, str]] = {}


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
    preset_case: Optional[bool] = False
    preset_case_id: Optional[str] = None
    lang: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    law_context: Optional[str] = None
    top_k: Optional[int] = None
    dataset: Optional[str] = None
    preset_question: Optional[bool] = False


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_provider": llm.PROVIDER,
        "chat_model": llm.ACTIVE_CHAT_MODEL,
        "analyze_model": llm.ACTIVE_ANALYZE_MODEL,
        "active_document_limit": int(os.getenv("ACTIVE_DOCUMENT_LIMIT", "20")),
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
    lang: Optional[str] = None,
):
    items, total = await db.list_laws_page(
        category=category,
        search=search,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
        include_articles=include_articles,
    )
    items = await _localize_laws_payload(items, _normalize_lang(lang), include_articles=False)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/laws/{code}")
async def law_detail(code: str, lang: Optional[str] = None):
    law = await db.get_law(code)
    if not law:
        raise HTTPException(404, "Law not found")
    return await _localize_law_payload(law, _normalize_lang(lang), include_articles=True)


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if not req.text.strip():
        raise HTTPException(400, "Law text is required")

    top_k = max(1, min(req.top_k or ANALYZE_TOP_K, 8))
    input_lang = _normalize_lang(req.lang) if req.lang else _detect_lang(req.title + " " + req.text)
    preset_spec = _get_preset_analyze_spec(req.preset_case_id, req.title, req.text)
    retrieval_query = (req.text + " " + req.title).strip()
    if preset_spec:
        retrieval_query = f"{retrieval_query} {preset_spec['hint']}".strip()
        top_k = max(top_k, 5)

    candidates = await db.get_candidate_laws(retrieval_query, top_k)
    if not candidates:
        raise HTTPException(404, "No laws found in database")
    candidate_signature = _make_candidate_signature(candidates)
    cache_key = _make_analyze_cache_key(
        req.title,
        req.text,
        top_k,
        candidate_signature,
        lang=input_lang,
        preset_case=bool(req.preset_case),
        preset_case_id=(preset_spec or {}).get("id", ""),
    )
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

    input_lang_name = {"uz": "Uzbek", "ru": "Russian", "en": "English"}[input_lang]
    analysis_source = "llm"
    if req.preset_case and preset_spec:
        analysis = _build_preset_analyze_result(preset_spec, candidates, input_lang)
        analysis_source = "database-preset"
    else:
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
                query_text=retrieval_query,
            ),
        )
        try:
            raw = await llm.chat(system, [{"role": "user", "content": prompt}], task="analyze")
            analysis = _parse_json(raw)
        except HTTPException:
            analysis = _build_analyze_fallback(candidates, input_lang)
            analysis_source = "database-fallback"

    result = {
        "analysis": analysis,
        "laws_checked": len(candidates),
        "mode": analysis_source,
        "candidates": [
            {"code": c["code"], "title_ru": c["title_ru"], "category": c["category"]}
            for c in candidates
        ],
    }
    if len(_analyze_reply_cache) > ANALYZE_REPLY_CACHE_MAX:
        _analyze_reply_cache.clear()
    _analyze_reply_cache[cache_key] = (time.time(), result)
    cache_store.set(
        "analyze",
        cache_key,
        result,
        PERSISTENT_ANALYZE_CACHE_TTL,
        meta={"model": llm.ACTIVE_ANALYZE_MODEL if analysis_source == "llm" else analysis_source},
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
    if req.preset_question:
        top_k = max(top_k, 4)
    if dataset == db.ASSISTANT_DATASET_SCHEMA:
        top_k = 12
    preset_hint = _preset_query_hint(req.message)
    retrieval_query = req.message + (" " + preset_hint if preset_hint else "") + " " + (req.law_context or "")
    history, candidates = await asyncio.gather(
        db.get_history(session_id, limit=CHAT_HISTORY_LIMIT),
        db.get_candidate_laws(retrieval_query, top_k, dataset=dataset),
    )
    candidate_signature = _make_candidate_signature(candidates)
    laws_context = _build_law_context(
        candidates,
        query_text=retrieval_query,
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
    dataset_instruction = (
        "Use only the 12 laws from the schema12 dataset. Ignore the larger lexai corpus.\n\n"
        if dataset == db.ASSISTANT_DATASET_SCHEMA
        else "Use only the main lexai dataset. Ignore schema12 demo laws.\n\n"
    )
    has_exact_article_context = _has_exact_article_context(
        candidates,
        retrieval_query,
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
        f"Keep the answer practical, clear, warm, and natural.\n"
        f"Prioritize explanation over citation density.\n"
        f"Mention only the 2-3 most relevant documents in the main answer unless the question clearly requires more.\n"
        f"Explain what they mean for the user in natural prose.\n"
        f"Do not output a separate sources list; it will be appended automatically.\n\n"
        f"{dataset_instruction}"
        f"Format:\n"
        f"1. Main answer in 2-4 short readable paragraphs.\n"
        f"2. Mention relevant law codes and article numbers naturally and sparingly in the text.\n"
        f"3. End with a short practical takeaway in 1-2 sentences.\n\n"
        f"{extra_instruction}"
        f"Retrieved laws:\n{laws_context}{law_block}"
    )

    cache_key = _make_chat_cache_key(
        history,
        req.law_context,
        top_k,
        dataset,
        candidate_signature,
        preset_question=bool(req.preset_question),
    )
    cached = _chat_reply_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CHAT_REPLY_CACHE_TTL:
        reply = _append_exact_sources(cached[1], candidates, req.message, lang)
        model_used = cached[2]
    else:
        persistent_cached = cache_store.get("chat", cache_key)
        if persistent_cached:
            cached_value = persistent_cached["value"]
            reply = _append_exact_sources(cached_value["reply"], candidates, retrieval_query, lang)
            model_used = cached_value.get("model") or persistent_cached["meta"].get("model") or "cache"
        else:
            if req.preset_question and not req.law_context:
                reply = _append_exact_sources(_build_fast_lookup_reply(retrieval_query, candidates, lang), candidates, retrieval_query, lang)
                model_used = "database-preset"
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
                    reply = _append_exact_sources(reply, candidates, retrieval_query, lang)
                    cache_store.set(
                        "chat",
                        cache_key,
                        {"reply": reply, "model": model_used},
                        PERSISTENT_CHAT_CACHE_TTL,
                        meta={"model": model_used},
                    )
                except HTTPException:
                    reply = _build_chat_fallback(retrieval_query, candidates, lang)
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


def _normalize_lang(lang: Optional[str]) -> str:
    value = (lang or "").strip().lower()
    if value in {"uz", "uzbek", "uz-uz"}:
        return "uz"
    if value in {"en", "eng", "en-us", "en-gb"}:
        return "en"
    return "ru"


async def _translate_text_cached(text: str, target_lang: str, kind: str = "legal text") -> str:
    source = (text or "").strip()
    if not source:
        return source
    if target_lang == "ru":
        return source
    if _detect_lang(source) == target_lang:
        return source

    cache_key_raw = json.dumps(
        {
            "model": llm.ACTIVE_CHAT_MODEL,
            "target_lang": target_lang,
            "kind": kind,
            "text": source,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    cache_key = hashlib.sha256(cache_key_raw.encode("utf-8")).hexdigest()
    in_memory = _translation_cache.get(cache_key)
    if in_memory and (time.time() - in_memory[0]) < PERSISTENT_TRANSLATE_CACHE_TTL:
        return in_memory[1]

    cached = cache_store.get("translate", cache_key)
    if cached:
        translated = cached["value"]["text"]
        _translation_cache[cache_key] = (time.time(), translated)
        return translated

    target_lang_name = {"uz": "Uzbek", "en": "English"}[target_lang]
    system = (
        "You are a legal translator.\n"
        f"Translate the text into {target_lang_name} only.\n"
        "Preserve legal meaning, article numbers, document codes, and structure.\n"
        "Do not add commentary. Return only the translated text."
    )
    try:
        translated = await llm.chat(system, [{"role": "user", "content": source}], task="chat")
    except HTTPException:
        translated = source

    _translation_cache[cache_key] = (time.time(), translated)
    cache_store.set(
        "translate",
        cache_key,
        {"text": translated},
        PERSISTENT_TRANSLATE_CACHE_TTL,
        meta={"model": llm.ACTIVE_CHAT_MODEL, "kind": kind, "lang": target_lang},
    )
    return translated


async def _localize_law_payload(law: dict, lang: str, include_articles: bool = False) -> dict:
    if lang != "uz":
        return law

    localized = dict(law)
    if not localized.get("summary_uz") and localized.get("summary_ru"):
        localized["summary_uz"] = await _translate_text_cached(localized["summary_ru"], "uz", kind="law summary")

    if include_articles:
        localized_articles = []
        for article in localized.get("articles") or []:
            localized_article = dict(article)
            if not localized_article.get("content_uz") and localized_article.get("content_ru"):
                localized_article["content_uz"] = await _translate_text_cached(
                    localized_article["content_ru"],
                    "uz",
                    kind=f"law article {localized.get('code') or ''}".strip(),
                )
            localized_articles.append(localized_article)
        localized["articles"] = localized_articles

    return localized


async def _localize_laws_payload(items: list[dict], lang: str, include_articles: bool = False) -> list[dict]:
    if lang != "uz":
        return items
    localized_items = []
    for item in items:
        localized_items.append(await _localize_law_payload(item, lang, include_articles=include_articles))
    return localized_items


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _preset_query_hint(text: str) -> str:
    normalized = _normalize_text(text).replace("ʻ", "'").replace("ʼ", "'")
    rules: list[tuple[tuple[str, ...], str]] = [
        (("ооо", "mchj", "регистрац", "ro'yxat", "royxat"), "регистрация юридического лица учредительные документы создание юридического лица"),
        (("ликвидац", "tugat", "кредитор", "kreditor"), "ликвидация юридического лица прекращение юридического лица уведомление кредиторов"),
        (("несовершеннолет", "voyaga yetmagan", "подписать договор", "shartnomani o'zi imzolamoqchi"), "сделки несовершеннолетних малолетние дееспособность несовершеннолетних"),
        (("подопеч", "опекун", "vasiy", "vasiylik", "mol-mulk"), "опека попечительство распоряжение имуществом подопечного разрешение органа опеки"),
        (("доверен", "представител", "ishonchnoma", "vakil"), "представительство доверенность полномочия представителя совершение сделки через представителя"),
        (("устав", "состав участников", "ta'sischilar", "ishtirokchilar"), "учредительные документы устав участники юридического лица"),
        (("оформить опеку", "vasiylik rasmiy", "назначение опекуна"), "опека попечительство назначение опекуна"),
        (("ограниченно дееспособ", "муomala layoqati cheklangan", "недееспособ"), "ограничение дееспособности признание гражданина недееспособным"),
        (("акт гражданского состояния", "fuqarolik holati"), "регистрация актов гражданского состояния"),
        (("реорганизац", "qayta tashkil"), "реорганизация юридического лица"),
        (("базовые принципы", "основные принципы", "asosiy tamoyil"), "основные начала гражданского законодательства общие положения гражданского права"),
        (("выходит из юридического лица", "выход участника", "ishtirokchi", "tarkibidan chiq"), "выход участника юридического лица доля участника"),
    ]
    extras: list[str] = []
    for triggers, hint in rules:
        if any(trigger in normalized for trigger in triggers):
            extras.append(hint)
    return " ".join(dict.fromkeys(extras))


def _get_preset_analyze_spec(preset_case_id: Optional[str], title: str, text: str) -> Optional[dict]:
    normalized = _normalize_text(f"{title} {text}").replace("ʻ", "'").replace("ʼ", "'")
    specs = [
        {
            "id": "registration_without_address",
            "hint": "регистрация юридического лица учредительные документы юридический адрес сведения об учредителях проверка достоверности документов",
            "triggers": ("manzilsiz", "юридического адреса", "учредителях", "ta'sischilar", "ro'yxatdan", "ro'yxat"),
            "risk": "high",
            "ru": {
                "summary": "Проект снимает базовые требования к созданию и регистрации юридического лица. Это повышает риск фиктивной регистрации, споров о правоспособности и проблем для контрагентов.",
                "contra": "Проект противоречит действующим требованиям к созданию юридического лица и составу обязательных сведений при регистрации.",
                "support": "Если цель проекта состоит в упрощении регистрации, опираться стоит на действующие нормы о юридических лицах и уточнять процедуру без отмены обязательных реквизитов.",
                "recommendations": [
                    "Сохранить обязательность указания адреса и сведений об учредителях.",
                    "Оставить проверку достоверности представленных документов хотя бы в минимальном объеме.",
                    "Если нужно ускорение процедуры, сокращать сроки рассмотрения, а не отменять базовые требования.",
                ],
            },
            "uz": {
                "summary": "Loyiha yuridik shaxsni tashkil etish va ro'yxatdan o'tkazishdagi asosiy talablarni bekor qilmoqda. Bu soxta ro'yxatdan o'tkazish, huquqiy maqom bo'yicha nizolar va kontragentlar uchun xavflarni kuchaytiradi.",
                "contra": "Loyiha yuridik shaxsni tashkil etish va ro'yxatdan o'tkazish bo'yicha amaldagi majburiy talablar bilan zid keladi.",
                "support": "Agar maqsad ro'yxatdan o'tkazishni soddalashtirish bo'lsa, amaldagi normalarga tayangan holda tartibni yengillashtirish mumkin, lekin majburiy ma'lumotlarni bekor qilmaslik kerak.",
                "recommendations": [
                    "Yuridik manzil va ta'sischilar haqidagi ma'lumotlarni majburiy saqlab qoling.",
                    "Taqdim etilgan hujjatlar ishonchliligini tekshirish mexanizmini bekor qilmang.",
                    "Jarayonni tezlashtirish kerak bo'lsa, muddatlarni qisqartiring, lekin asosiy talablarni emas.",
                ],
            },
            "en": {
                "summary": "The draft removes core requirements for establishing and registering a legal entity. That creates risks of fictitious registration, disputes over legal capacity, and problems for counterparties.",
                "contra": "The draft conflicts with the current baseline requirements for forming a legal entity and the mandatory registration data set.",
                "support": "If the goal is to simplify registration, it is safer to streamline procedure while preserving the mandatory information and verification safeguards.",
                "recommendations": [
                    "Keep the legal address and founder information mandatory.",
                    "Retain at least a minimal document authenticity check.",
                    "Speed up deadlines rather than removing baseline registration safeguards.",
                ],
            },
        },
        {
            "id": "liquidation_without_creditors",
            "hint": "ликвидация юридического лица уведомление кредиторов публикация сведений о ликвидации прекращение юридического лица",
            "triggers": ("ликвидир", "tugatil", "кредитор", "kreditor", "публикац", "e'lon"),
            "risk": "high",
            "ru": {
                "summary": "Проект делает ликвидацию юридического лица слишком упрощенной и исключает защиту кредиторов. Это создает высокий риск утраты требований, злоупотреблений и последующих судебных споров.",
                "contra": "Проект конфликтует с действующей логикой ликвидации юридического лица, где уведомление кредиторов и публичность процедуры играют ключевую роль.",
                "support": "Для законной ликвидации лучше опираться на действующие нормы о прекращении юридического лица и сохранять механизм уведомления заинтересованных лиц.",
                "recommendations": [
                    "Оставить уведомление кредиторов обязательным этапом ликвидации.",
                    "Сохранить публикацию сведений о ликвидации и срок для предъявления требований.",
                    "Уточнить порядок расчетов с кредиторами до завершения ликвидации.",
                ],
            },
            "uz": {
                "summary": "Loyiha yuridik shaxsni tugatish tartibini haddan tashqari soddalashtirib, kreditorlar himoyasini amalda yo'qotmoqda. Bu talablarning yo'qolishi, suiiste'mollik va keyingi sud nizolari xavfini oshiradi.",
                "contra": "Loyiha yuridik shaxsni tugatishda kreditorlarni xabardor qilish va jarayonning oshkoraligi bo'yicha amaldagi yondashuvga zid.",
                "support": "Qonuniy tugatish uchun amaldagi tugatish qoidalariga tayangan holda kreditorlarni xabardor qilish mexanizmini saqlab qolish kerak.",
                "recommendations": [
                    "Kreditorlarni xabardor qilishni majburiy bosqich sifatida qoldiring.",
                    "Tugatish haqida e'lon berish va talablar uchun muddatni saqlang.",
                    "Tugatish yakunlanishidan oldin kreditorlar bilan hisob-kitob tartibini aniq yozing.",
                ],
            },
            "en": {
                "summary": "The draft makes liquidation of a legal entity overly simplified and effectively removes creditor protection. That creates a high risk of lost claims, abuse, and later litigation.",
                "contra": "The draft conflicts with the current liquidation framework, where creditor notice and public disclosure are central safeguards.",
                "support": "A lawful liquidation model should rely on existing termination rules and preserve notice to interested parties.",
                "recommendations": [
                    "Keep creditor notification as a mandatory liquidation step.",
                    "Preserve publication of liquidation information and a claims period.",
                    "Clarify creditor settlement rules before liquidation is completed.",
                ],
            },
        },
        {
            "id": "minor_any_transactions",
            "hint": "сделки несовершеннолетних малолетние дееспособность несовершеннолетних согласие родителей отчуждение имущества кредит",
            "triggers": ("несовершеннолет", "voyaga yetmagan", "14 yosh", "14 лет", "ota-on", "родител"),
            "risk": "high",
            "ru": {
                "summary": "Проект чрезмерно расширяет самостоятельную дееспособность несовершеннолетних и снимает защитные барьеры для сделок, кредитов и распоряжения имуществом. Это повышает риск оспаривания сделок и имущественного вреда ребенку.",
                "contra": "Проект расходится с действующим разграничением сделок несовершеннолетних и необходимостью согласия законных представителей.",
                "support": "Если нужно расширить хозяйственную самостоятельность подростков, это лучше делать точечно и с оговорками по видам сделок, суммам и контролю законных представителей.",
                "recommendations": [
                    "Сохранить общее правило о согласии родителей или законных представителей для существенных сделок.",
                    "Отдельно перечислить допустимые самостоятельные сделки, а не разрешать все подряд.",
                    "Исключить возможность свободного кредитования и отчуждения имущества без защитных ограничений.",
                ],
            },
            "uz": {
                "summary": "Loyiha voyaga yetmaganlarning mustaqil muomala layoqatini haddan tashqari kengaytiradi va bitimlar, kreditlar hamda mol-mulkni tasarruf etish bo'yicha himoya cheklovlarini olib tashlaydi. Bu bitimlarning haqiqiyligi bo'yicha nizolar va bolaga mulkiy zarar yetishi xavfini oshiradi.",
                "contra": "Loyiha voyaga yetmaganlarning bitimlari bo'yicha amaldagi cheklovlar va qonuniy vakillar roziligi talabiga zid keladi.",
                "support": "Agar voyaga yetmaganlarning mustaqilligini kengaytirish maqsad qilingan bo'lsa, buni faqat ayrim bitim turlari, summalar va nazorat mexanizmlari bilan amalga oshirish kerak.",
                "recommendations": [
                    "Muhim bitimlar uchun ota-ona yoki qonuniy vakil roziligini saqlab qoling.",
                    "Voyaga yetmagan shaxs mustaqil tuzishi mumkin bo'lgan bitimlarni aniq sanab o'ting.",
                    "Kredit olish va mol-mulkni begonalashtirishni cheklovlarsiz ruxsat etuvchi qoidani olib tashlang.",
                ],
            },
            "en": {
                "summary": "The draft expands the independent legal capacity of minors too far and removes safeguards for transactions, loans, and disposal of property. That increases the risk of voidable transactions and financial harm to the child.",
                "contra": "The draft departs from the current distinction between what minors may do themselves and what requires consent of legal representatives.",
                "support": "If broader autonomy is desired, it should be introduced narrowly with safeguards by transaction type, amount, and parental control.",
                "recommendations": [
                    "Keep the general consent rule for substantial transactions.",
                    "List the transactions minors may perform independently instead of allowing everything.",
                    "Remove the clause allowing unrestricted loans and disposal of property.",
                ],
            },
        },
        {
            "id": "guardian_sell_without_permission",
            "hint": "опека попечительство распоряжение имуществом подопечного разрешение органа опеки продажа имущества подопечного",
            "triggers": ("опекун", "подопеч", "vasiy", "vasiylik", "mol-mulk", "подопечного"),
            "risk": "high",
            "ru": {
                "summary": "Проект снимает один из ключевых защитных механизмов для имущества подопечного. Без предварительного разрешения уполномоченного органа резко возрастает риск злоупотреблений и ущерба интересам подопечного.",
                "contra": "Проект противоречит действующему защитному режиму распоряжения имуществом подопечного, где требуется внешний контроль и разрешительный порядок.",
                "support": "Если нужно упростить процедуру, можно сократить сроки согласования, но не убирать сам контроль за отчуждением имущества подопечного.",
                "recommendations": [
                    "Сохранить предварительное разрешение уполномоченного органа на отчуждение имущества подопечного.",
                    "Разграничить обычное управление имуществом и сделки, которые затрагивают его сохранность.",
                    "Добавить критерии проверки выгодности сделки для подопечного.",
                ],
            },
            "uz": {
                "summary": "Loyiha vasiylik ostidagi shaxs mol-mulkini himoya qiluvchi asosiy mexanizmlardan birini bekor qilmoqda. Vakolatli organning oldindan ruxsatisiz suiiste'mollik va podopetchiy manfaatlariga zarar yetishi xavfi keskin ortadi.",
                "contra": "Loyiha podopetchiy mol-mulkini tasarruf etishda amaldagi nazorat va ruxsat berish tartibiga zid keladi.",
                "support": "Agar maqsad tartibni soddalashtirish bo'lsa, kelishish muddatlarini qisqartirish mumkin, lekin mol-mulkni sotish ustidan nazoratni olib tashlash mumkin emas.",
                "recommendations": [
                    "Podopetchiy mol-mulkini begonalashtirish uchun oldindan ruxsat talabini saqlab qoling.",
                    "Oddiy boshqaruv harakatlari bilan muhim bitimlarni alohida ajrating.",
                    "Bitimning podopetchiy manfaatiga mosligini baholash mezonlarini qo'shing.",
                ],
            },
            "en": {
                "summary": "The draft removes one of the core safeguards protecting the ward’s property. Without prior approval from the competent authority, the risk of abuse and harm to the ward rises sharply.",
                "contra": "The draft conflicts with the current protective regime for disposing of ward property, which relies on external oversight and prior authorization.",
                "support": "If simplification is the goal, approval timelines can be streamlined without removing supervision over disposal of the ward’s assets.",
                "recommendations": [
                    "Keep prior approval for disposal of ward property.",
                    "Differentiate routine management from high-impact transactions.",
                    "Add criteria for assessing whether the deal benefits the ward.",
                ],
            },
        },
        {
            "id": "representative_without_power",
            "hint": "представительство доверенность полномочия представителя письменная доверенность форма доверенности сделка через представителя",
            "triggers": ("доверенн", "ishonchnoma", "представител", "vakil", "yozma", "письменной"),
            "risk": "high",
            "ru": {
                "summary": "Проект фактически убирает письменное подтверждение полномочий представителя и создает неопределенность для третьих лиц. Это повышает риск споров о действительности сделки и превышении полномочий.",
                "contra": "Проект расходится с действующими правилами о представительстве и форме доверенности, которые служат доказательством объема полномочий.",
                "support": "Если задача состоит в упрощении документооборота, разумнее расширять электронную форму доверенности, а не отменять сам письменный источник полномочий.",
                "recommendations": [
                    "Сохранить письменную или равнозначную ей электронную форму доверенности.",
                    "Уточнить пределы полномочий представителя по видам сделок или сумме.",
                    "Не допускать совершение любых сделок без подтверждаемого основания полномочий.",
                ],
            },
            "uz": {
                "summary": "Loyiha vakil vakolatini yozma tasdiqlash talabini amalda yo'qotadi va uchinchi shaxslar uchun noaniqlik tug'diradi. Bu bitimning haqiqiyligi va vakolatdan oshib ketish bo'yicha nizolar xavfini oshiradi.",
                "contra": "Loyiha vakillik va ishonchnoma shakli bo'yicha amaldagi qoidalarga zid, chunki ular vakolat hajmini isbotlash vositasi hisoblanadi.",
                "support": "Agar maqsad hujjat aylanishini soddalashtirish bo'lsa, yozma manbani bekor qilish o'rniga elektron ishonchnoma shaklini rivojlantirish to'g'riroq bo'ladi.",
                "recommendations": [
                    "Ishonchnomaning yozma yoki unga tenglashtirilgan elektron shaklini saqlab qoling.",
                    "Vakil vakolatlari chegarasini bitim turi yoki summasi bo'yicha aniq belgilang.",
                    "Tasdiqlanadigan vakolatsiz har qanday bitim tuzishga ruxsat bermang.",
                ],
            },
            "en": {
                "summary": "The draft effectively removes written proof of the representative’s authority and creates uncertainty for third parties. That increases the risk of disputes over validity and excess of authority.",
                "contra": "The draft departs from the current rules on representation and the form of a power of attorney, which serve as evidence of the scope of authority.",
                "support": "If the goal is simplification, it is safer to expand electronic power-of-attorney formats rather than abolish the written source of authority.",
                "recommendations": [
                    "Keep the written form of the power of attorney or an equivalent electronic form.",
                    "Clarify the limits of the representative’s authority by transaction type or amount.",
                    "Do not allow unrestricted transactions without verifiable authority.",
                ],
            },
        },
    ]

    if preset_case_id:
        for spec in specs:
            if spec["id"] == preset_case_id:
                return spec

    for spec in specs:
        if any(trigger in normalized for trigger in spec["triggers"]):
            return spec
    return None


def _best_law_excerpt(law: dict, query_text: str, max_chars: int = 170) -> str:
    for article in _select_articles_for_query(law, query_text, 2):
        content = (article.get("content_uz") or article.get("content_ru") or "").strip()
        if content:
            return _compact_text(content, max_chars)
    return _compact_text(_pick_field(law, "summary") or _pick_field(law, "title"), max_chars)


def _law_article_label(law: dict, query_text: str, limit: int = 2) -> Optional[str]:
    labels = []
    for article in _select_articles_for_query(law, query_text, limit):
        article_num = article.get("article_num")
        if article_num and not _is_placeholder_article_num(article_num):
            if article_num not in labels:
                labels.append(article_num)
    return ", ".join(labels) if labels else None


def _build_analysis_entry(law: dict, query_text: str, explanation: str, severity: Optional[str] = None) -> dict:
    entry = {
        "law_code": law["code"],
        "law_title": _pick_field(law, "title") or law["code"],
        "article": _law_article_label(law, query_text, 2),
        "explanation": f"{explanation} {_best_law_excerpt(law, query_text)}".strip(),
    }
    if severity:
        entry["severity"] = severity
    return entry


def _build_preset_analyze_result(spec: dict, candidates: list[dict], lang: str) -> dict:
    localized = spec.get(lang) or spec["ru"]
    contradictions_source = candidates[:3]
    supports_source = candidates[3:5] or candidates[:2]

    contradictions = []
    for idx, law in enumerate(contradictions_source):
        contradictions.append(
            _build_analysis_entry(
                law,
                spec["hint"],
                localized["contra"],
                severity="high" if idx == 0 else "medium",
            )
        )

    supports = []
    seen_codes = {item["law_code"] for item in contradictions}
    for law in supports_source:
        if law["code"] in seen_codes and len(candidates) > len(supports_source):
            continue
        supports.append(_build_analysis_entry(law, spec["hint"], localized["support"]))
        if len(supports) >= 2:
            break

    if not supports:
        for law in candidates[:2]:
            if law["code"] in seen_codes:
                continue
            supports.append(_build_analysis_entry(law, spec["hint"], localized["support"]))

    cited_codes = ", ".join(law["code"] for law in contradictions_source[:2])
    summary = localized["summary"]
    if cited_codes:
        summary = f"{summary} {cited_codes} hujjatlari." if lang == "uz" else f"{summary} Основные ориентиры в базе: {cited_codes}."

    return {
        "summary": summary,
        "risk_level": spec["risk"],
        "contradictions": contradictions,
        "supports": supports,
        "recommendations": localized["recommendations"],
    }


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
    for prefix in ("bazadagi ", "bazada ", "в базе ", "по базе ", "in the database ", "in database "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].lstrip()
            break
    starters = ("qaysi", "qanday", "какие", "какой", "какая", "какое", "which", "what", "покажи", "show")
    nouns = (
        "modda", "moddalar", "hujjat", "hujjatlar", "normalar",
        "стат", "документ", "норм", "article", "articles", "document", "documents", "law", "laws",
    )
    scenario_terms = (
        "нужно", "надо", "стоит", "проверить", "посмотреть", "хочу", "хотим", "собира", "перед",
        "регистрац", "ликвидац", "кредитор", "несовершеннолет", "подопеч", "доверен", "представител",
        "kerak", "tekshirish", "ko'rish", "korish", "xohlay", "oldin", "ro'yxat", "royxat",
        "tugat", "kreditor", "voyaga", "bitim", "vasiylik", "mol-mulk", "vakil", "ishonchnoma",
    )
    topic_terms = (
        "ооо", "регистрац", "ликвидац", "кредитор", "договор", "сделк", "несовершеннолет",
        "подопеч", "доверен", "представител", "имуществ", "опекун",
        "mchj", "ro'yxat", "royxat", "tugat", "kreditor", "shartnoma", "bitim",
        "voyaga", "vasiy", "vasiylik", "mol-mulk", "vakil", "ishonchnoma",
    )
    has_starter = any(normalized.startswith(prefix) for prefix in starters)
    has_noun = any(noun in normalized for noun in nouns)
    has_code = bool(db._extract_code_tokens(query_text))
    has_lookup_verb = any(token in normalized for token in ("asosiy", "muhim", "ключев", "основн", "ko'rsat", "korsat"))
    has_scenario = any(term in normalized for term in scenario_terms)
    has_topic = any(term in normalized for term in topic_terms)
    return (
        (has_starter and has_noun)
        or (has_code and (has_noun or has_lookup_verb))
        or (has_noun and has_scenario)
        or (has_scenario and has_topic)
    )


def _build_exact_sources(query_text: str, candidates: list[dict], lang: str, max_items: int = 4) -> list[str]:
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
        "ru": "Использованные документы и статьи",
        "uz": "Foydalanilgan hujjatlar va moddalar",
        "en": "Documents and Articles Used",
    }
    no_sources = {
        "ru": "Точные статьи не найдены.",
        "uz": "Aniq moddalar topilmadi.",
        "en": "Exact articles not found.",
    }

    if any(title in (reply or "") for title in (*section_titles.values(), "Источники", "Manbalar", "Sources")):
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
    article_label = {
        "ru": "статьи",
        "uz": "moddalar",
        "en": "articles",
    }[lang]
    no_article_breakdown = {
        "ru": "без разбивки на статьи",
        "uz": "moddalarga ajratilmagan",
        "en": "without article breakdown",
    }[lang]
    intro_templates = {
        "ru": {
            "with_articles": "По этому вопросу в базе в первую очередь релевантен документ {code} — {title}. Для ответа наиболее полезны {article_word} {articles}.",
            "without_articles": "По этому вопросу в базе в первую очередь релевантен документ {code} — {title}, однако в выбранной выборке он представлен без точной разбивки на статьи.",
            "additional": "Дополнительно стоит учитывать документ {code} — {title}. {explanation}",
            "closing": "Эти документы помогают проверить вопрос с точки зрения гражданско-правовых правил и связанных ограничений.",
        },
        "uz": {
            "with_articles": "Ushbu savol bo'yicha bazada birinchi navbatda {code} — {title} hujjati muhim. Javob uchun ayniqsa {articles} {article_word} foydali.",
            "without_articles": "Ushbu savol bo'yicha bazada birinchi navbatda {code} — {title} hujjati muhim, ammo tanlangan ma'lumotlarda u aniq moddalarga ajratilmagan.",
            "additional": "Bundan tashqari, {code} — {title} hujjatini ham hisobga olish kerak. {explanation}",
            "closing": "Bu hujjatlar masalani fuqarolik-huquqiy qoidalar va bog'liq cheklovlar nuqtai nazaridan tekshirishga yordam beradi.",
        },
        "en": {
            "with_articles": "For this question, the most relevant document in the database is {code} — {title}. The most useful {article_word} for the answer are {articles}.",
            "without_articles": "For this question, the most relevant document in the database is {code} — {title}, but it is not broken down into exact articles in the selected context.",
            "additional": "It is also worth considering {code} — {title}. {explanation}",
            "closing": "Together, these documents help assess the issue from the perspective of civil-law rules and related restrictions.",
        },
    }

    paragraphs: list[str] = []
    for index, law in enumerate(relevant):
        title = _compact_text(_pick_field(law, "title"), 120)
        category = law.get("category") or {
            "ru": "Без категории",
            "uz": "Bo'lim ko'rsatilmagan",
            "en": "No category",
        }[lang]
        selected_articles = _select_articles_for_query(law, query_text, 4)
        article_nums = [
            article.get("article_num") or "-"
            for article in selected_articles
            if not _is_placeholder_article_num(article.get("article_num"))
        ]
        unique_articles = list(dict.fromkeys(article_nums))
        best_explanation = ""
        for article in selected_articles:
            content = article.get("content_uz") or article.get("content_ru") or ""
            if content:
                best_explanation = _compact_text(content, 180)
                break
        if not best_explanation:
            best_explanation = _compact_text(_pick_field(law, "summary") or title, 180)

        if index == 0:
            if unique_articles:
                paragraphs.append(
                    intro_templates[lang]["with_articles"].format(
                        code=law["code"],
                        title=title,
                        article_word=article_label,
                        articles=", ".join(unique_articles),
                    )
                )
            else:
                paragraphs.append(
                    intro_templates[lang]["without_articles"].format(
                        code=law["code"],
                        title=title,
                    )
                )
            paragraphs.append(best_explanation)
        else:
            extra_explanation = best_explanation
            if not unique_articles and article_mode:
                extra_explanation = f"{no_article_breakdown}. {extra_explanation}"
            paragraphs.append(
                intro_templates[lang]["additional"].format(
                    code=law["code"],
                    title=title,
                    explanation=extra_explanation,
                )
            )

    paragraphs.append(intro_templates[lang]["closing"])
    return "\n\n".join(paragraphs)


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
    base_reply = _build_fast_lookup_reply(query_text, candidates, lang)
    base_reply = _append_exact_sources(base_reply, candidates, query_text, lang)
    return f"{intro}\n\n{base_reply}"


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
    for marker in (
        "\n\nИспользованные документы и статьи:",
        "\n\nFoydalanilgan hujjatlar va moddalar:",
        "\n\nDocuments and Articles Used:",
        "\n\nИсточники:",
        "\n\nManbalar:",
        "\n\nSources:",
    ):
        if marker in text:
            return text.split(marker, 1)[0]
    return text


def _make_chat_cache_key(
    history: list[dict],
    law_context: Optional[str],
    top_k: int,
    dataset: str,
    candidate_signature: str,
    preset_question: bool = False,
) -> str:
    payload = {
        "version": CHAT_CACHE_VERSION,
        "model": llm.ACTIVE_CHAT_MODEL,
        "history": history,
        "law_context": (law_context or "")[:CHAT_LAW_CONTEXT_MAX_CHARS],
        "top_k": top_k,
        "dataset": dataset,
        "candidate_signature": candidate_signature,
        "preset_question": preset_question,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _make_analyze_cache_key(
    title: str,
    text: str,
    top_k: int,
    candidate_signature: str,
    lang: str = "ru",
    preset_case: bool = False,
    preset_case_id: str = "",
) -> str:
    payload = {
        "version": ANALYZE_CACHE_VERSION,
        "model": llm.ACTIVE_ANALYZE_MODEL,
        "title": title or "",
        "text": text or "",
        "top_k": top_k,
        "lang": lang,
        "preset_case": preset_case,
        "preset_case_id": preset_case_id,
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
