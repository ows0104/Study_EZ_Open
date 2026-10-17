"""Conservative first-pass dependencies from authored links and recall directions.

Direct recall is a proxy for a concept's entry connection, not a claim that every
short answer is foundational. Explicit prerequisites always take precedence. No
question text, medical answer, bank JSON or learner record is rewritten here.
"""
from functools import lru_cache

from .ordering import question_slide


@lru_cache(maxsize=128)
def _dependencies(signature: tuple) -> dict[str, frozenset[str]]:
    ids = {qid for qid, *_ in signature}
    explicit = {qid: set(prereqs) & ids for qid, _, _, prereqs in signature}

    def ancestors(qid, graph):
        found, pending = set(), list(graph[qid])
        while pending:
            parent = pending.pop()
            if parent not in found:
                found.add(parent)
                pending.extend(graph[parent] - found)
        return found

    direct = {}
    for qid, concept, direction, _ in signature:
        if direction == 'direct':
            direct.setdefault(concept, set()).add(qid)
    roots = {concept: {qid for qid in members if not (ancestors(qid, explicit) & members)}
             for concept, members in direct.items()}
    graph = {qid: set(parents) for qid, parents in explicit.items()}
    for qid, concept, direction, _ in signature:
        if direction == 'direct':
            continue
        for root in sorted(roots.get(concept, ())):
            # An authored mechanism-before-direct link overrides the heuristic.
            # Check the evolving graph as cross-concept links can form cycles too.
            if qid not in ancestors(root, graph):
                graph[qid].add(root)
    return {qid: frozenset(parents) for qid, parents in graph.items()}


def connection_order(bank: dict, unlearned: set[str], pages: dict | None = None) -> tuple[dict, dict]:
    signature = tuple((q['question_id'], q['concept_id'], q['retrieval_direction'],
                       tuple(q.get('prerequisites', ()))) for q in bank['questions'])
    dependencies = _dependencies(signature)
    anchors = {q['question_id']: (question_slide(q, pages), index)
               for index, q in enumerate(bank['questions'])}
    # A needed root inherits the earliest unlearned descendant's slide position.
    # Once rated, that root no longer moves or blocks the next new connections.
    for qid in unlearned:
        pending, visited = list(dependencies[qid] & unlearned), {qid}
        while pending:
            parent = pending.pop()
            if parent in visited:
                continue
            visited.add(parent)
            anchors[parent] = min(anchors[parent], anchors[qid])
            pending.extend(dependencies[parent] & (unlearned - visited))
    return dependencies, anchors
