"""Local passage ranking without an additional model call or external index."""
from collections import Counter
import math
import re
import unicodedata

STOP_WORDS = set("le la les un une des de du et ou en dans sur pour par avec au aux ce ces cet cette est sont que qui quoi comment pourquoi peux peut tu vous je nous il elle ils elles mon ma mes ton ta tes son sa ses moi me se ne pas plus tres the a an of to in and is are it this that explique expliquer donne document documents support supports cours reponds francais".split())


def tokens(text: str) -> list[str]:
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    return [word for word in re.findall(r'[a-z0-9]+', text) if word not in STOP_WORDS and len(word) >= 2]


def rank_scores(passages: list[str], query: str) -> list[float]:
    """BM25 scores whole tokens, discounts repetition and rewards rare terms."""
    counts = [Counter(tokens(passage)) for passage in passages]
    terms = set(tokens(query))
    average = sum(sum(count.values()) for count in counts) / max(1, len(counts)) or 1
    frequencies = {term: sum(term in count for count in counts) for term in terms}
    scores = []
    for count in counts:
        length = sum(count.values())
        score = 0.0
        for term in terms:
            frequency = count[term]
            if frequency:
                rarity = math.log(1 + (len(counts) - frequencies[term] + .5) / (frequencies[term] + .5))
                score += rarity * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * length / average))
        scores.append(score)
    return scores


def retrieval_query(message: str, history) -> str:
    """Resolve short follow-ups from recent user turns, never assistant guesses."""
    words = set(tokens(message))
    # Only reference-only turns inherit a topic. A new subject introduced with
    # "explique encore ..." must not drag an unrelated earlier subject into search.
    references = set('cela ca suite continue detaille davantage exemple autre encore oui ok accord simplement simplifie developpe donne deuxieme second premiere premier dernier derniere partie point cas compris comprends rien complique simple enfant bref resume essentiel seulement exactement fonctionne va loin techniquement ai sais comprends comprendre c est n l'.split())
    followup = not (words - references)
    if not followup:
        return message
    previous = []
    for item in reversed(history[-12:]):
        if item.role != 'user':
            continue
        previous.insert(0, item.content[:1500])
        if set(tokens(item.content)) - references:
            break
    return '\n'.join([*previous, message])


def overview_requested(query: str) -> bool:
    """Only broad summaries need sampling across the entire document."""
    words = set(tokens(query))
    requests = {'resume', 'resumer', 'synthese', 'synthetise', 'summarize', 'summary'}
    fillers = {'fais', 'faire', 'moi', 'tout', 'complet', 'complete', 'global', 'globale', 'general', 'generale', 'ensemble', 'ces', 'mes', 'ce', 's', 'il', 'te', 'plait'}
    return bool(words & requests) and not (words - requests - fillers)


def spread_order(count: int) -> list[int]:
    """Start, end, then split remaining intervals to cover long supports."""
    if count <= 1:
        return list(range(count))
    result = [0, count - 1]
    intervals = [(0, count - 1)]
    while intervals:
        left, right = intervals.pop(0)
        if right - left > 1:
            middle = (left + right) // 2
            result.append(middle)
            intervals.extend([(left, middle), (middle, right)])
    return result
