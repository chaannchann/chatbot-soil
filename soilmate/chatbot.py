"""Retrieval-based agricultural chatbot (fully local, no APIs).

How it works
------------
Every intent in ``data/knowledge_base.json`` carries a list of example
phrasings ("patterns"). At startup we build TF-IDF vectors for those
phrasings. A user message is tokenized the same way and compared with
cosine similarity, so the bot picks the closest *intent* instead of
matching hardcoded keywords.

A small keyword bonus helps very short questions ("ph", "compost") and
per-session state lets follow-up questions resolve pronouns.

Nothing here calls the network or an external model.
"""

import json
import math
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "knowledge_base.json")
TL_KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "knowledge_base_tl.json")

DEFAULT_SUGGESTIONS = [
    "What can I plant this month?",
    "How do I test soil pH?",
    "How do I make compost?",
]
EMPTY_REPLY = "Ask me anything about soil, compost, fertilizers, or what to plant in the Philippines."

STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "have", "has", "had", "having",
    "i", "me", "my", "mine", "we", "our", "you", "your", "it", "its",
    "this", "that", "these", "those", "there", "here",
    "to", "of", "in", "on", "at", "for", "with", "about", "from", "by",
    "and", "or", "but", "if", "so", "than", "then", "as", "into", "up", "out",
    "can", "could", "should", "would", "will", "shall", "may", "might", "must",
    "what", "when", "where", "which", "who", "why", "how",
    "not", "no", "yes", "very", "too", "much", "many", "more", "most",
    "some", "any", "all", "just", "also", "please", "help", "need", "want",
    "give", "get", "make", "tell", "know", "like", "recipe", "cook", "cooking", "dish",
    "ang", "ng", "mga", "sa", "na", "po", "ba", "ko", "ako", "akin", "mo", "iyo",
    "yung", "yun", "yon", "yong", "ito", "iyan", "iyon", "si", "ni", "kay",
    "para", "lang", "ano", "paano", "papaano", "saan", "kailan", "bakit",
    "sino", "ilan", "gaano", "magkano", "pwede", "puwede", "gusto",
    "kailangan", "hindi", "wala", "meron", "mayroon", "naman", "din", "rin",
    "daw", "raw", "kasi", "pero", "kung", "kapag", "dapat", "maaari",
    "maging", "dito", "doon", "tayo", "kami", "kayo", "sila", "namin",
    "natin", "ninyo", "niyo", "nila", "niya", "siya", "ka", "oo", "opo",
}

FILIPINO_MARKERS = {
    "ang", "ng", "mga", "sa", "na", "po", "ba", "ako", "ko", "mo", "siya",
    "niya", "namin", "natin", "ninyo", "niyo", "nila", "ito", "iyan", "iyon",
    "yung", "yun", "yon", "ano", "paano", "papaano", "saan", "kailan",
    "bakit", "sino", "ilan", "gaano", "magkano", "pwede", "puwede", "gusto",
    "kailangan", "hindi", "wala", "meron", "mayroon", "salamat", "mabuhay",
    "kumusta", "kamusta", "musta", "naman", "lang", "din", "rin", "daw",
    "raw", "kasi", "pero", "kung", "kapag", "dapat", "maaari", "maging",
    "tulong", "magandang", "umaga", "tanghali", "hapon", "gabi",
    "gawin", "tanim", "magtanim", "itanim", "taniman", "pataba", "abono",
    "lupa", "tubig", "dilig", "dahon", "peste", "sakit", "panahon", "ulan",
    "araw", "init", "bukid", "hardin", "halaman", "gulay", "ani", "anihin",
    "punla", "punlaan", "bunga", "ugat", "buhangin", "buhanging", "malagkit",
    "mabuhangin", "itim", "pula", "dilaw", "paso", "sobra", "kulang", "sapat",
    "maputla", "naninilaw", "nalalanta", "tumutubo",
}

GENERIC_TERMS = {
    "fix", "improve", "correct", "adjust", "increase", "decrease", "apply", "use",
    "add", "grow", "plant", "need", "make", "get", "know", "want", "help", "cause",
    "stop", "prevent", "avoid", "best", "good", "bad", "work", "happen", "start",
    "begin", "keep", "put", "mix", "control", "kill", "problem", "issue", "way",
    "time", "soil", "thing", "lot", "kind", "type", "level",
    "lupa", "halaman", "gulay", "tanim", "magtanim", "itanim", "gawin",
    "paraan", "paggawa", "uri", "klase", "mapapabuti", "pagbutihin",
    "marami", "kaunti", "sobra", "kulang", "sapat",
}

WEAK_SOIL_WORDS = {"black", "dark", "red", "yellow", "itim", "pula", "dilaw"}

MONTH_MAP = {
    "january": 1, "jan": 1, "enero": 1,
    "february": 2, "feb": 2, "pebrero": 2,
    "march": 3, "mar": 3, "marso": 3,
    "april": 4, "apr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "june": 6, "jun": 6, "hunyo": 6,
    "july": 7, "jul": 7, "hulyo": 7,
    "august": 8, "aug": 8, "agosto": 8,
    "september": 9, "sep": 9, "sept": 9, "setyembre": 9,
    "october": 10, "oct": 10, "oktubre": 10,
    "november": 11, "nov": 11, "nobyembre": 11,
    "december": 12, "dec": 12, "disyembre": 12,
}


def normalize(text):
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_language(text):
    tokens = normalize(text).split()
    return "tl" if any(tok in FILIPINO_MARKERS for tok in tokens) else "en"


def stem(token):
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text):
    return [
        stem(tok)
        for tok in normalize(text).split()
        if tok and tok not in STOPWORDS and (len(tok) > 1 or tok.isdigit())
    ]


def detect_planting_target_month(text):
    """Detect if the message asks for 'next month', 'this month', or a named month."""
    norm = normalize(text)
    now = datetime.now(timezone(timedelta(hours=8)))

    # Next month triggers (English & Filipino)
    if any(p in norm for p in ["next month", "following month", "susunod na buwan", "sunod na buwan"]):
        if now.month == 12:
            return 1, now.year + 1
        return now.month + 1, now.year

    # This month triggers
    if any(p in norm for p in ["this month", "current month", "ngayong buwan", "kasalukuyang buwan"]):
        return now.month, now.year

    # Check for specific month names (e.g. "December", "Enero")
    tokens = norm.split()
    for tok in tokens:
        if tok in MONTH_MAP:
            target_m = MONTH_MAP[tok]
            target_y = now.year + 1 if target_m < now.month else now.year
            return target_m, target_y

    return None, None


class ChatBot:
    def __init__(self, kb_path=KB_PATH, threshold=0.16, max_sessions=2000):
        self.kb_path = kb_path
        self.threshold = threshold
        self.max_sessions = max_sessions

        with open(kb_path, "r", encoding="utf-8") as fh:
            self.kb = json.load(fh)

        self.intents = self.kb["intents"]
        self.fallback_text = self.kb.get("fallback", "Sorry, I didn't understand that.")
        self.soil_aliases = {name: list(values) for name, values in self.kb.get("soil_aliases", {}).items()}
        self.soil_to_intent = self.kb.get("soil_to_intent", {})

        self.fallback_tl = self.fallback_text
        self.fallback_suggestions_tl = list(DEFAULT_SUGGESTIONS)
        self.empty_tl = {"reply": EMPTY_REPLY, "suggestions": list(DEFAULT_SUGGESTIONS)}

        self._sessions = {}

        self._load_translations()
        self._build_index()

    def _load_translations(self):
        if not os.path.exists(TL_KB_PATH):
            return

        with open(TL_KB_PATH, "r", encoding="utf-8") as fh:
            tl = json.load(fh)

        self.fallback_tl = tl.get("fallback", self.fallback_text)
        self.fallback_suggestions_tl = tl.get("fallback_suggestions", list(DEFAULT_SUGGESTIONS))
        empty = tl.get("empty")
        if empty:
            self.empty_tl = {
                "reply": empty.get("reply", EMPTY_REPLY),
                "suggestions": empty.get("suggestions", list(DEFAULT_SUGGESTIONS)),
            }

        field_map = {
            "title": "title_tl",
            "patterns": "patterns_tl",
            "keywords": "keywords_tl",
            "answer": "answer_tl",
            "answer_by_soil": "answer_by_soil_tl",
            "follow_ups": "follow_ups_tl",
        }
        translations = tl.get("intents", {})
        for intent in self.intents:
            data = translations.get(intent["id"])
            if not data:
                continue
            for source, target in field_map.items():
                if source in data:
                    intent[target] = data[source]

        for canonical, aliases in tl.get("soil_aliases", {}).items():
            target = self.soil_aliases.setdefault(canonical, [])
            for alias in aliases:
                if alias not in target:
                    target.append(alias)

    def _build_index(self):
        self.documents = []
        self.idf = {}

        raw_docs = []
        for intent in self.intents:
            patterns = list(dict.fromkeys(intent.get("patterns", []) + intent.get("patterns_tl", [])))
            for pattern in patterns:
                tokens = tokenize(pattern)
                if tokens:
                    raw_docs.append((intent, tokens))

        total_docs = len(raw_docs) or 1
        df = {}
        for _, tokens in raw_docs:
            for tok in set(tokens):
                df[tok] = df.get(tok, 0) + 1

        self.idf = {tok: math.log((total_docs + 1) / (count + 1)) + 1 for tok, count in df.items()}

        for intent, tokens in raw_docs:
            vector = self._vectorize(tokens)
            self.documents.append((intent, set(tokens), vector))

        self.intent_keywords = {}
        for intent in self.intents:
            keywords = list(dict.fromkeys(
                intent.get("keywords", []) + intent.get("keywords_tl", [])
            ))
            self.intent_keywords[intent["id"]] = [tokenize(kw) for kw in keywords]

    def _vectorize(self, tokens):
        if not tokens:
            return {}
        tf = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1
        vec = {tok: count * self.idf.get(tok, 0.0) for tok, count in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {tok: v / norm for tok, v in vec.items()}

    @staticmethod
    def _cosine(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(weight * b.get(tok, 0.0) for tok, weight in a.items())

    def detect_soil(self, text):
        norm_text = normalize(text)
        tokens = norm_text.split()
        if not tokens:
            return None
        padded = f" {' '.join(tokens)} "

        best = None
        for canonical, aliases in self.soil_aliases.items():
            for alias in aliases:
                a = normalize(alias)
                if not a:
                    continue
                if len(a.split()) == 1 and a in WEAK_SOIL_WORDS:
                    matched = (
                        norm_text == a
                        or f" {a} soil " in padded
                        or f" {a} lupa " in padded
                    )
                else:
                    matched = f" {a} " in padded
                if matched and (best is None or len(a) > best[1]):
                    best = (canonical, len(a))
        return best[0] if best else None

    def _soil_shortcut(self, tokens, soil):
        if not soil or not tokens:
            return None
        intent_id = self.soil_to_intent.get(soil)
        if not intent_id:
            return None
        allowed = {"soil"}
        for alias in self.soil_aliases.get(soil, []):
            allowed.update(tokenize(alias))
        if not tokens.issubset(allowed):
            return None
        return next((i for i in self.intents if i["id"] == intent_id), None)

    def rank(self, message, top_n=5):
        query_tokens = tokenize(message)
        if not query_tokens:
            query_tokens = [stem(tok) for tok in normalize(message).split() if len(tok) > 1]
        if not query_tokens:
            return []

        query_vec = self._vectorize(query_tokens)
        query_set = set(query_tokens)

        scores = {}
        for intent, doc_tokens, doc_vec in self.documents:
            shared = query_set & doc_tokens
            if not shared:
                continue
            if len(shared) == 1 and next(iter(shared)) in GENERIC_TERMS:
                continue
            score = self._cosine(query_vec, doc_vec)
            if score <= 0:
                continue
            intent_id = intent["id"]
            if score > scores.get(intent_id, (0.0, ""))[0]:
                scores[intent_id] = (score, "cosine")

        for intent in self.intents:
            intent_id = intent["id"]
            hits = 0
            for keyword_tokens in self.intent_keywords.get(intent_id, []):
                if keyword_tokens and set(keyword_tokens).issubset(query_set):
                    hits += 1
            if hits:
                bonus = min(0.24, 0.08 * hits)
                current = scores.get(intent_id, (0.0, "keyword"))
                scores[intent_id] = (current[0] + bonus, "keyword")

        ranked = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
        by_id = {intent["id"]: intent for intent in self.intents}
        results = [(by_id[i], score, source) for i, (score, source) in ranked[:top_n]]

        if not results:
            fuzzy = self._fuzzy_match(message)
            if fuzzy:
                results = [fuzzy]
        return results

    def _fuzzy_match(self, message, min_ratio=0.82):
        target = normalize(message)
        if not target:
            return None
        best = None
        for intent in self.intents:
            patterns = intent.get("patterns", []) + intent.get("patterns_tl", [])
            for pattern in patterns:
                ratio = SequenceMatcher(None, target, normalize(pattern)).ratio()
                if ratio >= min_ratio and (best is None or ratio > best[1]):
                    best = (intent, ratio)
        if not best:
            return None
        return (best[0], best[1], "fuzzy")

    def _resolve_answer(self, intent, soil, language="en"):
        if language == "tl":
            by_soil = intent.get("answer_by_soil_tl")
            if by_soil and soil and soil in by_soil:
                return by_soil[soil]
            answer = intent.get("answer_tl")
            if answer:
                return answer

        by_soil = intent.get("answer_by_soil")
        if by_soil and soil and soil in by_soil:
            return by_soil[soil]
        return intent.get("answer", "")

    def _session(self, session_id):
        if not session_id:
            return {}
        if len(self._sessions) > self.max_sessions:
            self._sessions.clear()
        return self._sessions.setdefault(session_id, {})

    def respond(self, message, session_id=None, known_soil=None, preferred_language=None):
        """Produce a reply dict for one user message."""
        message = (message or "").strip()
        session = self._session(session_id)

        language = detect_language(message)
        if language != "tl" and preferred_language in {"en", "tl"}:
            language = preferred_language

        soil_in_text = self.detect_soil(message)
        if soil_in_text:
            session["last_soil"] = soil_in_text
        elif known_soil:
            session.setdefault("last_soil", known_soil)
        soil = session.get("last_soil")

        if not message:
            empty = self.empty_tl if language == "tl" else {"reply": EMPTY_REPLY, "suggestions": list(DEFAULT_SUGGESTIONS)}
            return {
                "reply": empty.get("reply", EMPTY_REPLY),
                "intent": "empty",
                "confidence": 0.0,
                "suggestions": empty.get("suggestions", list(DEFAULT_SUGGESTIONS)),
                "soil_type": soil,
                "action": None,
                "language": language,
            }

        ranked = self.rank(message)
        best_intent, best_score, _source = ranked[0] if ranked else (None, 0.0, "none")

        shortcut = self._soil_shortcut(set(tokenize(message)), soil_in_text)
        if shortcut is not None:
            matched = next((s for i, s, _ in ranked if i["id"] == shortcut["id"]), None)
            best_intent = shortcut
            best_score = matched if matched is not None else max(best_score, 0.9)

        if best_intent is None or best_score < self.threshold:
            fallback = self.fallback_tl if language == "tl" else self.fallback_text
            suggestions = self.fallback_suggestions_tl if language == "tl" else list(DEFAULT_SUGGESTIONS)
            return {
                "reply": fallback,
                "intent": "fallback",
                "confidence": round(float(best_score), 3),
                "suggestions": list(suggestions),
                "soil_type": soil,
                "action": None,
                "language": language,
            }

        # Check if user asked for next month or specific month
        target_m, target_y = detect_planting_target_month(message)
        action = best_intent.get("action")

        planting_words = {"plant", "grow", "itanim", "tanim", "pananim", "crops", "gulay", "sow", "harvest", "ani"}
        if target_m is not None and (action == "plant_now" or any(w in message.lower() for w in planting_words)):
            action = "plant_now"

        # Dynamic follow-up chips
        suggestions = best_intent.get("follow_ups_tl" if language == "tl" else "follow_ups", [])
        if action == "plant_now":
            now_m = datetime.now(timezone(timedelta(hours=8))).month
            if target_m == now_m or target_m is None:
                suggestions = (
                    ["Ano ang puwedeng itanim sa susunod na buwan?", "Paano ihanda ang lupa?", "Iskedyul ng pagdidilig"]
                    if language == "tl" else
                    ["What can I plant next month?", "How do I prepare the soil?", "Watering schedule"]
                )
            else:
                suggestions = (
                    ["Ano ang puwedeng itanim ngayong buwan?", "Paano gumawa ng compost?", "Ano ang tamang pH?"]
                    if language == "tl" else
                    ["What can I plant this month?", "How do I make compost?", "What is the ideal soil pH?"]
                )

        session["last_intent"] = best_intent["id"]

        return {
            "reply": self._resolve_answer(best_intent, soil, language),
            "intent": best_intent["id"],
            "title": best_intent.get("title_tl" if language == "tl" else "title", ""),
            "confidence": round(float(min(best_score, 1.0)), 3),
            "suggestions": suggestions[:3],
            "soil_type": soil,
            "action": action,
            "target_month": target_m,
            "target_year": target_y,
            "language": language,
        }