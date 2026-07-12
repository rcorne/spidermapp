from __future__ import annotations

import re
import unicodedata
from collections import Counter

# On-page keyword extraction: which terms is each URL actually optimized for?
# This reads the page the way a search engine's first pass does (title, H1,
# meta description weigh more than body copy). It is NOT Google Search Console
# data — once the GSC connector is configured, real query data can replace it.

_WORD_RE = re.compile(r"[a-záéíóúüñàèìòù0-9]{3,}", re.IGNORECASE)

_STOPWORDS = {
    # Spanish
    "las", "los", "una", "unas", "unos", "del", "con", "por", "para", "que", "qué",
    "como", "cómo", "más", "mas", "sus", "este", "esta", "estos", "estas", "ese",
    "esa", "esos", "esas", "aquí", "allí", "ser", "son", "está", "están", "estás",
    "hay", "fue", "muy", "sin", "sobre", "también", "tambien", "hasta", "desde",
    "entre", "cuando", "donde", "dónde", "quien", "quién", "nos", "les", "nuestro",
    "nuestra", "nuestros", "nuestras", "tus", "mis", "sí", "no", "pero", "porque",
    "todo", "toda", "todos", "todas", "otro", "otra", "otros", "otras", "ver",
    "puede", "pueden", "hacer", "tiene", "tienen", "años", "año", "día", "días",
    # English
    "the", "and", "for", "with", "that", "this", "you", "your", "are", "was",
    "have", "has", "not", "but", "all", "can", "our", "from", "más", "how",
    "what", "when", "where", "why", "who", "will", "more", "one", "two", "new",
    "get", "use", "about", "into", "out", "them", "their", "they", "its",
    # Web boilerplate
    "inicio", "home", "menú", "menu", "buscar", "cuenta", "carrito", "login",
    "cookies", "aceptar", "política", "privacidad", "términos", "condiciones",
    "contacto", "copyright", "reservados", "derechos", "página", "web", "sitio",
    "online", "aquí", "click", "clic", "leer", "email", "newsletter",
}

TITLE_WEIGHT = 4
H1_WEIGHT = 3
DESC_WEIGHT = 2
BODY_WEIGHT = 1
BODY_SAMPLE_CHARS = 4000
TOP_N = 5


def _strip_accents_for_compare(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def _content_words(text: str) -> list[str]:
    return [
        w for w in _tokens(text)
        if w not in _STOPWORDS and _strip_accents_for_compare(w) not in _STOPWORDS and not w.isdigit()
    ]


def extract_keywords(
    title: str,
    h1_list: list[str],
    meta_description: str,
    visible_text: str,
    top_n: int = TOP_N,
) -> list[str]:
    """Weighted term + bigram frequency across the page's strongest SEO signals."""
    counts: Counter = Counter()

    def add(text: str, weight: int) -> None:
        words = _content_words(text)
        for w in words:
            counts[w] += weight
        for a, b in zip(words, words[1:]):
            counts[f"{a} {b}"] += weight + 1  # bigrams beat their parts when both appear

    add(title, TITLE_WEIGHT)
    for h1 in h1_list:
        add(h1, H1_WEIGHT)
    add(meta_description, DESC_WEIGHT)
    add(visible_text[:BODY_SAMPLE_CHARS], BODY_WEIGHT)

    if not counts:
        return []

    ranked = [term for term, _ in counts.most_common(top_n * 3)]
    result: list[str] = []
    for term in ranked:
        # skip single words fully contained in an already-picked bigram
        if " " not in term and any(term in chosen.split() for chosen in result if " " in chosen):
            continue
        result.append(term)
        if len(result) >= top_n:
            break
    return result
