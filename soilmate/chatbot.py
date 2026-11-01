"""Retrieval-based agricultural chatbot (fully local, no APIs).

How it works
------------
Every intent in ``data/knowledge_base.json`` carries a list of example
phrasings ("patterns"). At startup we build TF-IDF vectors for those
phrasings. A user message is tokenized the same way and compared with
cosine similarity, so the bot picks the closest *intent* instead of
matching hardcoded keywords.

A small keyword bonus helps very short questions ("ph", "compost") and
per-session state lets follow-up questions resolve pronouns, e.g.:

    User: "What is yellow soil?"        -> intent soil_yellow, last_soil=Yellow
    User: "How much compost for this?"   -> intent compost_amount, soil=Yellow

Nothing here calls the network or an external model.
"""

import json
import math
import os
import re
import unicodedata
from difflib import SequenceMatcher

KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "knowledge_base.json")

# Very common English/Filipino filler words that carry no topic signal.
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
    # Filipino particles
    "ang", "ng", "sa", "na", "po", "ba", "ko", "ako", "akin", "mo", "iyo",
    "mga", "yung", "ito", "iyan", "si", "ni", "kay", "para", "lang", "ba",
}

# Words that appear across many intents and therefore must not carry a match
# on their own ("how do i fix my motorcycle" would otherwise hit "fix acidic
# soil"). A hit that shares *only* one of these is rejected.
GENERIC_TERMS = {
    "fix", "improve", "correct", "adjust", "increase", "decrease", "apply", "use",
    "add", "grow", "plant", "need", "make", "get", "know", "want", "help", "cause",
    "stop", "prevent", "avoid", "best", "good", "bad", "work", "happen", "start",
    "begin", "keep", "put", "mix", "control", "kill", "problem", "issue", "way",
    "time", "soil", "thing", "lot", "kind", "type", "level",
}


# Bare colour words are too ambiguous to treat as a soil mention on their own
# ("leaves turning yellow" is a nutrient problem, not Yellow Soil).
WEAK_SOIL_WORDS = {"black", "dark", "red", "yellow"}


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


def stem(token):
    """Extremely light suffix stripping.

    It only needs to be *consistent* between the knowledge base and the
    query, so aggressive linguistic accuracy would be counter-productive.
    """
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text):
    """Turn raw text into a list of meaningful stemmed tokens."""
    return [
        stem(tok)
        for tok in normalize(text).split()
        if tok and tok not in STOPWORDS and (len(tok) > 1 or tok.isdigit())
    ]


class ChatBot:
    def __init__(self, kb_path=KB_PATH, threshold=0.16, max_sessions=2000):
        self.kb_path = kb_path
        self.threshold = threshold
        self.max_sessions = max_sessions

        with open(kb_path, "r", encoding="utf-8") as fh:
            self.kb = json.load(fh)

        self.intents = self.kb["intents"]
        self.fallback_text = self.kb.get("fallback", "Sorry, I didn't understand that.")
        self.soil_aliases = self.kb.get("soil_aliases", {})
        self.soil_to_intent = self.kb.get("soil_to_intent", {})

        # Session state: session_id -> {"last_intent": str, "last_soil": str}
        self._sessions = {}

        self._build_index()

    # ------------------------------------------------------------------ index
    def _build_index(self):
        """Pre-compute TF-IDF vectors for every knowledge-base pattern."""
        self.documents = []          # list of (intent, token_set, vector)
        self.idf = {}

        raw_docs = []
        for intent in self.intents:
            for pattern in intent.get("patterns", []):
                tokens = tokenize(pattern)
                if tokens:
                    raw_docs.append((intent, tokens))
            # The keywords field is searchable metadata, not a document.

        total_docs = len(raw_docs) or 1

        # Document frequency
        df = {}
        for _, tokens in raw_docs:
            for tok in set(tokens):
                df[tok] = df.get(tok, 0) + 1

        # Smoothed IDF
        self.idf = {tok: math.log((total_docs + 1) / (count + 1)) + 1 for tok, count in df.items()}

        for intent, tokens in raw_docs:
            vector = self._vectorize(tokens)
            self.documents.append((intent, set(tokens), vector))

        # Pre-tokenize keyword sets for the short-query bonus.
        self.intent_keywords = {
            intent["id"]: [tokenize(kw) for kw in intent.get("keywords", [])]
            for intent in self.intents
        }

    def _vectorize(self, tokens):
        """Raw-count TF weighted by IDF, L2-normalized."""
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
        # Both vectors are already L2-normalized.
        if len(a) > len(b):
            a, b = b, a
        return sum(weight * b.get(tok, 0.0) for tok, weight in a.items())

    # ------------------------------------------------------------------ soil
    def detect_soil(self, text):
        """Return the canonical soil name explicitly mentioned in the text.

        Colour words are dangerous: "leaves turning yellow" must not be read
        as Yellow Soil. A bare colour only counts when the message is just
        that word, or when it sits directly before "soil"/"lupa".
        """
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
                    # Longer aliases are more specific ("black soil" > "black").
                    best = (canonical, len(a))
        return best[0] if best else None

    def _soil_shortcut(self, tokens, soil):
        """If the user only named a soil ("yellow", "sandy soil"), pick it.

        Without this, a bare word like "yellow" could match the *yellowing
        leaves* intent purely on vocabulary overlap.
        """
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

    # ---------------------------------------------------------------- scoring
    def rank(self, message, top_n=5):
        """Return the best-scoring intents as (intent, score, source) tuples."""
        query_tokens = tokenize(message)
        if not query_tokens:
            # The whole sentence was filler ("what can you do?"). Keep the raw
            # words so it can still match a knowledge-base phrase.
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
            # One shared word is enough only if it is topic-specific.
            if len(shared) == 1 and next(iter(shared)) in GENERIC_TERMS:
                continue
            score = self._cosine(query_vec, doc_vec)
            if score <= 0:
                continue
            intent_id = intent["id"]
            if score > scores.get(intent_id, (0.0, ""))[0]:
                scores[intent_id] = (score, "cosine")

        # Keyword bonus for short, direct questions.
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
        """Character-level fallback for messages made only of filler words.

        Queries like "what can you do" have no indexable tokens at all, so
        cosine similarity cannot see them. Comparing the raw normalized
        strings recovers an exact wording match from the knowledge base.
        """
        target = normalize(message)
        if not target:
            return None
        best = None
        for intent in self.intents:
            for pattern in intent.get("patterns", []):
                ratio = SequenceMatcher(None, target, normalize(pattern)).ratio()
                if ratio >= min_ratio and (best is None or ratio > best[1]):
                    best = (intent, ratio)
        if not best:
            return None
        return (best[0], best[1], "fuzzy")

    # ------------------------------------------------------------- responders
    def _resolve_answer(self, intent, soil):
        """Pick a soil-specific answer variant when one exists."""
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

    def respond(self, message, session_id=None, known_soil=None):
        """Produce a reply dict for one user message.

        Args:
            message: raw user text.
            session_id: stable client-side id, used to remember context.
            known_soil: last soil detected from an uploaded image, if any.
        """
        message = (message or "").strip()
        session = self._session(session_id)

        # A soil mentioned in the text always wins over a stale image result.
        soil_in_text = self.detect_soil(message)
        if soil_in_text:
            session["last_soil"] = soil_in_text
        elif known_soil:
            session.setdefault("last_soil", known_soil)
        soil = session.get("last_soil")

        if not message:
            return {
                "reply": "Ask me anything about soil, compost, fertilizers, or what to plant in the Philippines.",
                "intent": "empty",
                "confidence": 0.0,
                "suggestions": ["What can I plant this month?", "How do I test soil pH?", "How do I make compost?"],
                "soil_type": soil,
                "action": None,
            }

        ranked = self.rank(message)
        best_intent, best_score, _source = ranked[0] if ranked else (None, 0.0, "none")

        shortcut = self._soil_shortcut(set(tokenize(message)), soil_in_text)
        if shortcut is not None:
            # Keep the real similarity score if that intent was already ranked.
            matched = next((s for i, s, _ in ranked if i["id"] == shortcut["id"]), None)
            best_intent = shortcut
            best_score = matched if matched is not None else max(best_score, 0.9)

        if best_intent is None or best_score < self.threshold:
            return {
                "reply": self.fallback_text,
                "intent": "fallback",
                "confidence": round(float(best_score), 3),
                "suggestions": ["What can I plant this month?", "How do I test soil pH?", "How do I make compost?"],
                "soil_type": soil,
                "action": None,
            }

        session["last_intent"] = best_intent["id"]

        return {
            "reply": self._resolve_answer(best_intent, soil),
            "intent": best_intent["id"],
            "title": best_intent.get("title", ""),
            "confidence": round(float(min(best_score, 1.0)), 3),
            "suggestions": best_intent.get("follow_ups", [])[:3],
            "soil_type": soil,
            "action": best_intent.get("action"),
        }
