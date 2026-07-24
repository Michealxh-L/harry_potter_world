#!/usr/bin/env python3
"""Extract a typed, evidence-backed knowledge graph from a user-supplied corpus."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

BOOK_MARKERS = [
    ("Philosopher's Stone", r"(?:Sorcerer|Philosopher)'s Stone"),
    ("Chamber of Secrets", r"Chamber of Secrets"),
    ("Prisoner of Azkaban", r"Prisoner of Azkaban"),
    ("Goblet of Fire", r"Goblet of Fire"),
    ("Order of the Phoenix", r"Order of the Phoenix"),
    ("Half-Blood Prince", r"Half[- ]Blood Prince"),
    ("Deathly Hallows", r"Deathly Hallows"),
]

# Small, auditable gazetteer. Aliases are longest-first to avoid partial matches.
ENTITIES = {
    "character": {
        "Harry Potter": ["Harry Potter", "Harry"],
        "Hermione Granger": ["Hermione Granger", "Hermione"],
        "Ron Weasley": ["Ron Weasley", "Ron"],
        "Albus Dumbledore": ["Albus Dumbledore", "Professor Dumbledore", "Dumbledore"],
        "Lord Voldemort": ["Lord Voldemort", "Voldemort", "You-Know-Who", "Dark Lord"],
        "Severus Snape": ["Severus Snape", "Professor Snape", "Snape"],
        "Rubeus Hagrid": ["Rubeus Hagrid", "Hagrid"],
        "Draco Malfoy": ["Draco Malfoy", "Malfoy"],
        "Sirius Black": ["Sirius Black", "Sirius"],
        "Remus Lupin": ["Remus Lupin", "Professor Lupin", "Lupin"],
        "Minerva McGonagall": ["Minerva McGonagall", "Professor McGonagall", "McGonagall"],
        "Ginny Weasley": ["Ginny Weasley", "Ginny"],
        "Neville Longbottom": ["Neville Longbottom", "Neville"],
        "Luna Lovegood": ["Luna Lovegood", "Luna"],
        "Dobby": ["Dobby"], "Bellatrix Lestrange": ["Bellatrix Lestrange", "Bellatrix"],
        "Fred Weasley": ["Fred Weasley", "Fred"], "George Weasley": ["George Weasley", "George"],
        "Molly Weasley": ["Molly Weasley", "Mrs. Weasley", "Molly"],
        "Arthur Weasley": ["Arthur Weasley", "Mr. Weasley", "Arthur"],
        "Dolores Umbridge": ["Dolores Umbridge", "Professor Umbridge", "Umbridge"],
        "Cedric Diggory": ["Cedric Diggory", "Cedric"],
        "Peter Pettigrew": ["Peter Pettigrew", "Pettigrew", "Wormtail"],
        "Lucius Malfoy": ["Lucius Malfoy", "Lucius"],
    },
    "place": {
        "Hogwarts": ["Hogwarts"], "Gryffindor common room": ["Gryffindor common room"],
        "Forbidden Forest": ["Forbidden Forest"], "Diagon Alley": ["Diagon Alley"],
        "Hogsmeade": ["Hogsmeade"], "Ministry of Magic": ["Ministry of Magic"],
        "Azkaban": ["Azkaban"], "Privet Drive": ["Privet Drive"],
        "The Burrow": ["the Burrow"], "Gringotts": ["Gringotts"],
        "Room of Requirement": ["Room of Requirement"], "Great Hall": ["Great Hall"],
        "Platform Nine and Three-Quarters": ["Platform Nine and Three-Quarters", "platform nine and three-quarters"],
    },
    "spell": {
        "Accio": ["Accio"], "Avada Kedavra": ["Avada Kedavra"],
        "Expecto Patronum": ["Expecto Patronum"], "Expelliarmus": ["Expelliarmus"],
        "Lumos": ["Lumos"], "Nox": ["Nox"], "Stupefy": ["Stupefy"],
        "Petrificus Totalus": ["Petrificus Totalus"], "Riddikulus": ["Riddikulus"],
        "Wingardium Leviosa": ["Wingardium Leviosa"], "Crucio": ["Crucio"],
        "Imperio": ["Imperio"], "Alohomora": ["Alohomora"], "Obliviate": ["Obliviate"],
        "Sectumsempra": ["Sectumsempra"], "Protego": ["Protego"],
    },
    "creature": {
        "Dementor": ["Dementors", "Dementor"], "Basilisk": ["Basilisk"],
        "Dragon": ["dragons", "dragon"], "House-elf": ["house-elves", "house-elf"],
        "Hippogriff": ["Hippogriffs", "Hippogriff"], "Phoenix": ["phoenix"],
        "Goblin": ["goblins", "goblin"], "Werewolf": ["werewolves", "werewolf"],
        "Thestral": ["Thestrals", "Thestral"], "Acromantula": ["Acromantula", "Acromantulas"],
    },
    "object": {
        "Elder Wand": ["Elder Wand"], "Invisibility Cloak": ["Invisibility Cloak"],
        "Marauder's Map": ["Marauder's Map"], "Sorting Hat": ["Sorting Hat"],
        "Philosopher's Stone": ["Philosopher's Stone", "Sorcerer's Stone"],
        "Goblet of Fire": ["Goblet of Fire"], "Horcrux": ["Horcruxes", "Horcrux"],
        "Time-Turner": ["Time-Turner"], "Resurrection Stone": ["Resurrection Stone"],
    },
}

SPELL_EFFECTS = {
    "Accio": "summons an object", "Avada Kedavra": "causes instant death",
    "Expecto Patronum": "conjures a Patronus", "Expelliarmus": "disarms an opponent",
    "Lumos": "creates wand light", "Nox": "extinguishes wand light",
    "Stupefy": "stuns a target", "Petrificus Totalus": "immobilises the body",
    "Riddikulus": "repels a boggart", "Wingardium Leviosa": "levitates an object",
    "Crucio": "inflicts severe pain", "Imperio": "controls another person",
    "Alohomora": "unlocks doors", "Obliviate": "erases memories",
    "Sectumsempra": "causes deep cuts", "Protego": "creates a magical shield",
}

SENTIMENT_ANALYSER = SentimentIntensityAnalyzer()

def clean_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    if text.count("�") > 100:
        text = raw.decode("latin-1", errors="ignore")
    return text.replace("\r", "").replace("ÿ", "").replace("þ", "")

def split_books(text: str) -> list[tuple[str, str]]:
    hits = []
    for title, pattern in BOOK_MARKERS:
        found = list(re.finditer(rf"(?im)^.*Harry Potter and the {pattern}.*$", text))
        if found:
            # Prefer a marker after the previous book; duplicates in contents pages are ignored.
            hits.append((found[-1 if title == "Deathly Hallows" else 0].start(), title))
    hits.sort()
    # If a table of contents creates clustered false markers, choose starts separated by substantial text.
    filtered = []
    for pos, title in hits:
        if filtered and pos - filtered[-1][0] < 2000:
            continue
        filtered.append((pos, title))
    return [(title, text[pos:(filtered[i + 1][0] if i + 1 < len(filtered) else len(text))])
            for i, (pos, title) in enumerate(filtered)]

def pattern_for(aliases: list[str]) -> re.Pattern:
    options = "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{options})(?![\w-])", re.I)

def sentiment_score(text: str) -> float:
    """Return VADER's normalised compound polarity in [-1, 1]."""
    return SENTIMENT_ANALYSER.polarity_scores(text)["compound"]

SPEECH_VERBS = (
    "said|asked|answered|replied|whispered|shouted|yelled|cried|muttered|"
    "murmured|called|added|snapped|exclaimed|remarked|told|suggested"
)

def dialogue_attributions(paragraph: str, aliases: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Return (speaker, quote) pairs supported by a nearby explicit speech tag."""
    alias_to_name = {
        alias.lower().rstrip("."): name for name, values in aliases.items() for alias in values
    }
    alias_pattern = "|".join(
        re.escape(alias) for alias in sorted(alias_to_name, key=len, reverse=True)
    )
    patterns = [
        re.compile(rf"(?:{SPEECH_VERBS})\s+({alias_pattern})", re.I),
        re.compile(rf"({alias_pattern})\s+(?:{SPEECH_VERBS})", re.I),
    ]
    results = []
    for quote_match in re.finditer(r'["“]([^"”\n]{2,600})["”]', paragraph):
        candidates = []
        before = paragraph[max(0, quote_match.start() - 140):quote_match.start()]
        after = paragraph[quote_match.end():quote_match.end() + 140]
        # Prefer a tag after the quote, the dominant pattern in this corpus.
        for priority, window in ((0, after), (1, before)):
            for pattern in patterns:
                for match in pattern.finditer(window):
                    distance = match.start() if priority == 0 else len(window) - match.end()
                    candidates.append((priority, distance, match.group(1)))
        if candidates:
            alias = min(candidates, key=lambda item: (item[0], item[1]))[2].lower().rstrip(".")
            results.append((alias_to_name[alias], quote_match.group(1)))
    return results

def add_graph_metrics(nodes: list[dict], edges: list[dict]) -> None:
    """Add degree metrics and deterministic one-level Louvain communities."""
    adjacency = defaultdict(dict)
    for edge in edges:
        adjacency[edge["source"]][edge["target"]] = edge["weight"]
        adjacency[edge["target"]][edge["source"]] = edge["weight"]
    labels = {node["id"]: node["id"] for node in nodes}
    weighted_degrees = {node_id: sum(neighbours.values()) for node_id, neighbours in adjacency.items()}
    totals = dict(weighted_degrees)
    twice_total_weight = sum(weighted_degrees.values())
    for _ in range(30):
        changed = False
        for node_id in sorted(labels):
            node_degree = weighted_degrees.get(node_id, 0)
            if not node_degree:
                continue
            old_label = labels[node_id]
            totals[old_label] -= node_degree
            weights_by_community = Counter()
            for neighbour, weight in adjacency[node_id].items():
                weights_by_community[labels[neighbour]] += weight
            best_label, best_gain = old_label, 0.0
            for label, internal_weight in sorted(weights_by_community.items()):
                gain = internal_weight - totals.get(label, 0) * node_degree / twice_total_weight
                if gain > best_gain + 1e-12:
                    best_label, best_gain = label, gain
            labels[node_id] = best_label
            totals[best_label] = totals.get(best_label, 0) + node_degree
            changed |= best_label != old_label
        if not changed:
            break
    communities = {
        label: index for index, label in enumerate(
            sorted(set(labels.values()), key=lambda x: (-sum(v == x for v in labels.values()), x)), 1
        )
    }
    for node in nodes:
        node["degree"] = len(adjacency[node["id"]])
        node["weightedDegree"] = sum(adjacency[node["id"]].values())
        node["community"] = communities[labels[node["id"]]]

def extract(text: str) -> dict:
    books = split_books(text)
    if len(books) < 5:
        raise ValueError(f"Expected a multi-book corpus; detected only {len(books)} book(s).")
    patterns = {name: pattern_for(aliases) for group in ENTITIES.values() for name, aliases in group.items()}
    character_aliases = ENTITIES["character"]
    entity_type = {name: kind for kind, group in ENTITIES.items() for name in group}
    mentions, book_counts, first_seen = Counter(), defaultdict(Counter), {}
    edge_counts, edge_books = Counter(), defaultdict(Counter)
    edge_sentiment, edge_sentiment_samples = Counter(), Counter()
    speech_scores, speech_words = defaultdict(list), Counter()

    for book_index, (book, body) in enumerate(books, 1):
        for paragraph in re.split(r"\n\s*\n|\n", body):
            if len(paragraph) < 20:
                continue
            present = []
            for name, pattern in patterns.items():
                count = len(pattern.findall(paragraph))
                if count:
                    present.append(name)
                    mentions[name] += count
                    book_counts[name][book] += count
                    first_seen.setdefault(name, {"book": book, "bookIndex": book_index})
            # paragraph co-occurrence: interpretable, bounded, and symmetric
            present = sorted(set(present))
            paragraph_sentiment = sentiment_score(paragraph)
            for speaker, quote in dialogue_attributions(paragraph, character_aliases):
                speech_scores[speaker].append(sentiment_score(quote))
                speech_words[speaker] += len(re.findall(r"[A-Za-z]+", quote))
            for i, source in enumerate(present):
                for target in present[i + 1:]:
                    key = (source, target)
                    edge_counts[key] += 1
                    edge_books[key][book] += 1
                    edge_sentiment[key] += paragraph_sentiment
                    edge_sentiment_samples[key] += 1

    nodes = []
    for name, count in mentions.most_common():
        node = {"id": name, "type": entity_type[name], "mentions": count,
                "books": dict(book_counts[name]), "firstSeen": first_seen[name]}
        if name in speech_scores:
            mean_speech = sum(speech_scores[name]) / len(speech_scores[name])
            node["speech"] = {
                "quotes": len(speech_scores[name]),
                "words": speech_words[name],
                "meanSentiment": round(mean_speech, 3),
                "kindnessScore": round((mean_speech + 1) * 50, 1),
                "method": "VADER mean over dialogue with explicit nearby speaker tags",
            }
        if name in SPELL_EFFECTS:
            node["effect"] = SPELL_EFFECTS[name]
        nodes.append(node)
    edges = []
    for (a, b), weight in edge_counts.most_common():
        if weight < 2:
            continue
        score = edge_sentiment[(a, b)] / edge_sentiment_samples[(a, b)]
        edges.append({
            "source": a, "target": b, "weight": weight, "relation": "CO_OCCURS",
            "books": dict(edge_books[(a, b)]),
            "confidence": round(min(.99, .55 + .08 * weight), 2),
            "sentiment": {
                "score": round(score, 3),
                "label": "positive" if score >= .05 else "negative" if score <= -.05 else "neutral",
                "samples": edge_sentiment_samples[(a, b)],
                "method": "VADER compound score averaged over evidence paragraphs",
            },
        })
    add_graph_metrics(nodes, edges)
    return {
        "meta": {"books": [b[0] for b in books], "bookCount": len(books),
                 "entityCount": len(nodes), "relationCount": len(edges),
                 "communityCount": len({node["community"] for node in nodes}),
                 "method": "case-insensitive gazetteer matching + paragraph co-occurrence",
                 "sentimentMethod": "VADER 3.3.2 compound score over evidence paragraphs",
                 "speechMethod": "quoted dialogue attributed by nearby explicit speech tags; VADER mean; score=(mean+1)*50",
                 "generatedFrom": "user-supplied local corpus"},
        "nodes": nodes, "edges": edges,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Path to a legally obtained plain-text corpus")
    parser.add_argument("-o", "--output", type=Path, default=Path("app/data/graph.json"))
    args = parser.parse_args()
    graph = extract(clean_text(args.input.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {graph['meta']['entityCount']} entities and {graph['meta']['relationCount']} relations to {args.output}")

if __name__ == "__main__":
    main()
