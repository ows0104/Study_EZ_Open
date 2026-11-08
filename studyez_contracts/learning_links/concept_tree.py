"""Concept-map /3 hierarchy checks: the Map's parent_id tree and its preservation.

concept-map-extract/3 adds `parent_id` to every Map concept so the lecture's structure
(central topic → branches → details) survives into the study document. Two pure checks:

- `tree_findings(map)`: the Map itself — known parents, no cycles, 1–8 top-level
  concepts, at least one concept two levels deep.
- `hierarchy_findings(brief, map_text)`: a learning-brief/2 written from that Map keeps
  each Map concept and lists its Map parent in `parent_ids` (extra parents are allowed:
  the tree need not be strict). Returns [] for /2 or absent Maps (old packets unchanged).

No model, DB or server use. Findings are plain strings for repair reasons.
"""
import json

VERSION = 'concept-map-extract/3'
MAX_ROOTS = 8


def parse(map_text):
    """The /3 Map from a packet's conceptMap string (or dict); None for other inputs."""
    if isinstance(map_text, dict):
        value = map_text
    elif isinstance(map_text, str) and map_text.strip():
        try:
            value = json.loads(map_text)
        except ValueError:
            return None
    else:
        return None
    return value if isinstance(value, dict) and value.get('schema_version') == VERSION else None


def depth_of(concepts):
    """{concept_id: depth} with roots at 0; concepts on a cycle or under an unknown parent are absent."""
    parent = {c['concept_id']: c.get('parent_id') for c in concepts}
    depth = {}
    for start in parent:
        path, node = [], start
        while node is not None and node in parent and node not in depth and node not in path:
            path.append(node)
            node = parent[node]
        if node is None:
            base = -1
        elif node in depth:
            base = depth[node]
        else:  # cycle or unknown parent: leave the whole path undefined
            continue
        for offset, item in enumerate(reversed(path), 1):
            depth[item] = base + offset
    return depth


def tree_findings(value):
    concepts = value.get('concepts', [])
    ids = [c['concept_id'] for c in concepts]
    known = set(ids)
    errors = []
    for c in concepts:
        parent = c.get('parent_id')
        if parent == c['concept_id']:
            errors.append(f"Map {c['concept_id']}: parent_id points to itself")
        elif parent is not None and parent not in known:
            errors.append(f"Map {c['concept_id']}: unknown parent_id {parent}")
    depth = depth_of(concepts)
    looped = [i for i in ids if i not in depth and not any(e.startswith(f'Map {i}:') for e in errors)]
    if looped:
        errors.append('Map parent_id cycle or broken chain: ' + ', '.join(looped))
    if concepts:
        roots = [i for i in ids if depth.get(i) == 0]
        if not 1 <= len(roots) <= MAX_ROOTS:
            errors.append(f'Map top-level concepts: {len(roots)} (expected 1–{MAX_ROOTS})')
        if not any(d >= 2 for d in depth.values()):
            errors.append('Map has no concept two levels below a top-level concept')
    return errors


def hierarchy_findings(brief, map_text):
    value = parse(map_text)
    if value is None:
        return []
    concepts = {c['concept_id']: c for c in brief.get('concepts', [])}
    errors = []
    for c in value['concepts']:
        mine = concepts.get(c['concept_id'])
        if mine is None:
            errors.append(f"Concept map hierarchy: Map concept {c['concept_id']} ({c['title']}) is missing from the brief; keep the Map concept ID.")
            continue
        parent = c.get('parent_id')
        if parent is not None and parent not in mine.get('parent_ids', []):
            errors.append(f"Concept map hierarchy: {c['concept_id']} ({c['title']}) must keep its Map parent {parent} in parent_ids.")
    return errors
