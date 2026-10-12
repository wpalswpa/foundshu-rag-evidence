"""Offline scope-first retrieval. Synthetic corpus; no payout decisions or LLM."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

STOP_BIGRAMS = {"보험", "험금", "실비", "실손", "수술", "술비", "되나", "나요", "돼?", "받을", "을수", "수있", "있어", "청구"}
BUNDLE_ROLES = {"definition", "exclusion", "reduction", "period", "event"}


def canonical(value):
    return re.sub(r"\s+", "", str(value)).casefold()


def bigrams(text):
    text = re.sub(r"\s+", "", text)
    return [text[i:i + 2] for i in range(len(text) - 1)
            if text[i:i + 2] not in STOP_BIGRAMS]


def valid_citation(chunk, documents):
    """The source text, hash and offsets must agree; no generated quotation."""
    if not isinstance(chunk, dict) or not isinstance(chunk.get("document_id"), str):
        return False
    # A repeated source ID is ambiguous even if the first copy has a matching hash.
    # Never choose a source by list order when its identity cannot be established.
    matches = [d for d in documents if isinstance(d, dict) and d.get("id") == chunk["document_id"]]
    if len(matches) != 1:
        return False
    doc = matches[0]
    raw, quote = doc.get("text"), chunk.get("quote")
    if not isinstance(raw, str) or not isinstance(quote, str):
        return False
    start, end = chunk.get("start"), chunk.get("end")
    return (type(start) is int and type(end) is int and 0 <= start < end <= len(raw)
            and hashlib.sha256(raw.encode()).hexdigest() == doc.get("sha256") == chunk.get("sha256")
            and quote == raw[start:end])


def rank(query, chunks, limit=5):
    """BM25 adapted from TermsIndex.search; corpus statistics follow filtering."""
    # Recompute document frequency inside the selected contract scope. The score
    # ranks lexical matches; it is neither a probability nor a coverage decision.
    vectors = [Counter(bigrams(c["quote"] + " " + c["article"])) for c in chunks]
    df = Counter(t for vector in vectors for t in vector)
    average = sum(sum(v.values()) for v in vectors) / max(len(vectors), 1)
    ranked = []
    for chunk, vector in zip(chunks, vectors):
        score = 0.0
        for term in set(bigrams(query)):
            count = vector[term]
            if count:
                score += math.log(1 + (len(vectors) - df[term] + .5) / (df[term] + .5)) * count * 2.2 / (
                    count + 1.2 * (.25 + .75 * sum(vector.values()) / max(average, 1)))
        if score > 0:
            ranked.append(dict(chunk, score=round(score, 5)))
    return sorted(ranked, key=lambda c: (-c["score"], c["id"]))[:limit]


def retrieve(corpus, query, contract, *, scoped=True, bundle=False, limit=5):
    """Return source clauses for review, or hold. Contract applicability is external."""
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive integer")
    held = {"status": "hold", "generation_used": False, "citations": []}
    if not isinstance(query, str) or not query.strip():
        return held
    documents = corpus["documents"]
    candidates = corpus["chunks"]
    if scoped:
        if not isinstance(contract, dict) or any(not isinstance(contract.get(k), str) or not contract[k].strip()
               for k in ("company", "product", "version", "rider")):
            return held
        matches = [d for d in documents if all(canonical(d[k]) == canonical(contract[k])
                    for k in ("company", "product", "version"))]
        if len(matches) != 1:
            return held
        candidates = [c for c in candidates if isinstance(c, dict) and c.get("document_id") == matches[0]["id"]
                      and canonical(contract["rider"]) in {canonical(r) for r in c["riders"]}]
    candidates = [c for c in candidates if valid_citation(c, documents)]
    hits = rank(query, candidates, limit)
    if not hits:
        return held
    if bundle:
        if not scoped:
            raise ValueError("bundle requires a verified scope")
        seen = {c["id"] for c in hits}
        # Add low-ranked exclusions only after a query hit in the verified scope.
        # These companions have no ranking score and can exceed the top-k limit.
        hits += [dict(c, score=None) for c in candidates
                 if c["id"] not in seen and BUNDLE_ROLES.intersection(c["roles"])]
    return {"status": "evidence_for_review", "generation_used": False, "citations": hits}


def load_example():
    return json.loads((Path(__file__).parent / "examples/corpus.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    corpus = load_example()
    for name, options in (("unscoped", {"scoped": False}), ("scoped", {}), ("bundle", {"bundle": True})):
        result = retrieve(corpus, corpus["query"], corpus["contract"], limit=1, **options)
        print(name, result["status"], [c["id"] for c in result["citations"]])
