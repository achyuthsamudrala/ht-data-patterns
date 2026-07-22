#!/usr/bin/env python3
"""
Regenerate the Mermaid block in interaction-map.md from src/interactions.yml.
Replaces the content between the first ```mermaid fence and its closing ```.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
INTERACTIONS_YAML = SRC / "interactions.yml"
INTERACTION_MAP = SRC / "interaction-map.md"


def slug_to_node_id(slug: str) -> str:
    return slug.split("/")[-1]


def main() -> int:
    data = yaml.safe_load(INTERACTIONS_YAML.read_text())
    edges = data.get("edges", [])

    lines = ["graph TD"]
    for edge in edges:
        src_id = slug_to_node_id(edge["from"])
        dst_id = slug_to_node_id(edge["to"])
        label = edge.get("label", "")
        src_label = edge["from"].split("/")[-1].replace("-", " ").title()
        dst_label = edge["to"].split("/")[-1].replace("-", " ").title()
        lines.append(
            f'    {src_id}["{src_label}"] -->|"{label}"| {dst_id}["{dst_label}"]'
        )
    generated = "\n".join(lines)

    map_text = INTERACTION_MAP.read_text()
    pattern = re.compile(r'```mermaid\n.*?```', re.DOTALL)
    replacement = f"```mermaid\n{generated}\n```"
    new_text, count = pattern.subn(replacement, map_text, count=1)

    if count == 0:
        print("No ```mermaid block found in interaction-map.md")
        return 1

    INTERACTION_MAP.write_text(new_text)
    print(f"Regenerated Mermaid block with {len(edges)} edges.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
