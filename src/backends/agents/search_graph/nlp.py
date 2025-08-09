from math import log
from typing import Dict, List


STOPWORDS = set(
    (
        "a an the and or but if then else when while for on in at by of to from with without "
        "is are was were be been being this that those these into over under again further more most some such "
        "no nor not only own same so than too very can will just don should now what which who whom whose why how"
    ).split()
)


def tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    word = []
    for ch in (text or "").lower():
        if ch.isalnum():
            word.append(ch)
        else:
            if word:
                tokens.append("".join(word))
                word = []
    if word:
        tokens.append("".join(word))
    # simple stopword filter and short token removal
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def compute_tfidf_scores(query_terms: List[str], documents: List[str]) -> List[float]:
    """
    Lightweight TF-IDF scoring: builds df over documents for query term set only.
    Returns a score for each document.
    """
    if not documents:
        return []
    # Use tokenized doc terms
    doc_tokens: List[List[str]] = [tokenize(doc) for doc in documents]
    # restrict to query term set (tokenized)
    q_terms = [t for t in tokenize(" ".join(query_terms))]
    if not q_terms:
        # fall back to all tokens in user query
        q_terms = tokenize(" ".join(query_terms))

    # document frequency for each q_term
    N = len(documents)
    df: Dict[str, int] = {t: 0 for t in q_terms}
    for tokens in doc_tokens:
        tset = set(tokens)
        for t in q_terms:
            if t in tset:
                df[t] += 1

    idf: Dict[str, float] = {t: log((N + 1) / (df[t] + 1)) + 1.0 for t in q_terms}

    scores: List[float] = []
    for tokens in doc_tokens:
        tf: Dict[str, int] = {}
        for tok in tokens:
            if tok in idf:  # only count query terms
                tf[tok] = tf.get(tok, 0) + 1
        score = 0.0
        for t, tfc in tf.items():
            score += (tfc) * idf.get(t, 0.0)
        scores.append(score)
    return scores


