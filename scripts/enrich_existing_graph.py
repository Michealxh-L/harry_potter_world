#!/usr/bin/env python3
"""Add graph-only metrics to an existing extraction without fabricating sentiment."""
import argparse
import json
from pathlib import Path

from extract_graph import add_graph_metrics

parser = argparse.ArgumentParser()
parser.add_argument("graph", type=Path, nargs="?", default=Path("app/data/graph.json"))
args = parser.parse_args()
data = json.loads(args.graph.read_text(encoding="utf-8"))
add_graph_metrics(data["nodes"], data["edges"])
data["meta"]["communityCount"] = len({node["community"] for node in data["nodes"]})
for edge in data["edges"]:
    edge.setdefault("sentiment", {
        "score": None, "label": "not calculated", "samples": 0,
        "method": "requires source evidence paragraphs",
    })
args.graph.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Added degree and {data['meta']['communityCount']} communities; sentiment awaits source corpus.")
