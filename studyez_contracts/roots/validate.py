import copy
import hashlib
import re
from datetime import date
from studyez_contracts.learning_links.validate import (
    canonical_json, validate_review, require, index_by, refs_exist, question_hash, acyclic,
)


def document_hash(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def direction_hash(doc, direction_id):
    """Conservative identity: source, relation, answer scope and all tested questions."""
    target = next(t for t in doc['review']['targets'] if any(d['direction_id'] == direction_id for d in t['directions']))
    direction = next(d for d in target['directions'] if d['direction_id'] == direction_id)
    questions = index_by(doc['bank_snapshot']['questions'], 'question_id')
    return document_hash({
        'direction': {k: v for k, v in direction.items() if k != 'direction_id'},
        'relations': [r for r in doc['review']['relations'] if r['relation_id'] in direction['relation_ids']],
        'sources': doc['review']['sources'],
        'questions': [questions[t['question_id']] for t in doc['tasks'] if t['direction_id'] == direction_id],
    })


FINGERPRINT_POLICY = 'question-content/1'


def question_fingerprint(question):
    """The question's own content: everything the learner reads and answers, without the bank context
    (`question_hash` includes concepts, plans and build metadata, so any change elsewhere would reset every
    question) and without tier/importance, which are computed from the importance basis, not content."""
    return document_hash({'policy': FINGERPRINT_POLICY,
                          'question': {k: v for k, v in question.items() if k not in ('tier', 'importance')}})


def task_fingerprints(doc):
    """task_id -> content fingerprint of its question. root-generation/4 carries learning history between
    revisions per question by it instead of `direction_hash` (docs/changes/2026-11-10-importance-at-authoring R8):
    the same content carries over, a changed question starts fresh, an ID alone never carries anything."""
    questions = index_by(doc['bank_snapshot']['questions'], 'question_id')
    return {t['task_id']: question_fingerprint(questions[t['question_id']]) for t in doc['tasks']}


def validate_prerequisites(targets,relations,edges,adopted,*,reviewed=True):
    """Draft graphs need valid references; adopted graphs also need review evidence."""
    require(type(edges)is list,'roots: explicit prerequisites array required')
    for edge in edges:
        require(type(edge)is dict and set(edge)=={'before_target','after_target','relation_id'},'roots: invalid prerequisite')
        before,after=edge['before_target'],edge['after_target']
        require(before in adopted and after in adopted and before!=after,'roots: unknown prerequisite target')
        relation=relations.get(edge['relation_id'],{})
        require(relation.get('kind')=='prerequisite'and(not reviewed or relation.get('review_status')=='reviewed')
                and relation.get('from_id')in targets[before]['concept_ids']and relation.get('to_id')in targets[after]['concept_ids'],
                'roots: prerequisite needs a matching reviewed relation'if reviewed else'roots: prerequisite needs matching prerequisite endpoints')
    acyclic([(e['before_target'],e['after_target'])for e in edges],'roots prerequisites')


def replaced_files(doc):
    """notes-update/1 (docs/changes/2026-11-16-replace-updated-notes): optional `replaced_sources` — the earlier files of
    the same pages a corrected notes source replaces. Only figures cropped from them may still name them."""
    rows = doc.get('replaced_sources')
    if rows is None:
        return {}
    current = {s['source_id']: s['sha256'] for s in doc['review']['sources']}
    require(type(rows) is list and rows and all(type(r) is dict and set(r) == {'source_id', 'sha256'} and r['source_id'] in current
            and type(r['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', r['sha256']) and r['sha256'] != current[r['source_id']]
            for r in rows) and len({(r['source_id'], r['sha256']) for r in rows}) == len(rows), 'roots: invalid replaced sources')
    out = {}
    for r in rows:
        out.setdefault(r['source_id'], []).append(r['sha256'])
    return out


def validate_document(doc):
    require(type(doc) is dict and set(doc)-{'generation_policy', 'replaced_sources'} == {
        'schema_version', 'revision', 'title', 'review', 'bank_snapshot', 'bank_source',
        'bank_build_id', 'adopted_target_ids', 'tasks', 'exam_date', 'equivalences', 'prerequisites'}, 'roots: missing or unknown fields')
    require(doc['schema_version'] == 'roots/1', 'roots: unsupported schema')
    replaced = replaced_files(doc)
    if 'generation_policy'in doc:
        require(doc['generation_policy']in('root-generation/2','root-generation/4')and doc['review']['schema_version']=='learning-links/2','roots: invalid generation policy')
        from .media import validate_images
        validate_images(doc['bank_snapshot'],doc['review']['sources'],replaced=replaced)
        from .generation_v2 import graph_order
        graph_order(doc['bank_snapshot'])
    require(type(doc['revision']) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', doc['revision']), 'roots: invalid revision')
    require(type(doc['title']) is str and 0 < len(doc['title'].strip()) <= 300, 'roots: title required')
    require(doc['bank_source'] in ('standalone', 'quizbank'), 'roots: unknown bank source')
    require(doc['bank_build_id'] is None or type(doc['bank_build_id']) is str, 'roots: invalid bank build')
    require(doc['bank_source'] != 'quizbank' or doc['bank_build_id'], 'roots: quizbank build required')
    if doc['exam_date'] is not None:
        require(type(doc['exam_date']) is str, 'roots: invalid exam date')
        date.fromisoformat(doc['exam_date'])
    review, bank = doc['review'], doc['bank_snapshot']
    if any(q.get('stimuli')for q in bank.get('questions',[])):
        from .media import validate_images, photo_import
        validate_images(bank,review['sources'],photo=photo_import(doc),replaced=replaced)
    require(type(review) is dict and type(review.get('sources')) is list, 'roots: review required')
    validate_review(review, bank, bank_sha256=document_hash(bank),
                    source_hashes={s['source_id']: s['sha256'] for s in review['sources']})
    targets = index_by(review['targets'], 'target_id')
    adopted = doc['adopted_target_ids']
    require(type(adopted) is list and adopted and all(type(t) is str for t in adopted), 'roots: adopted targets required')
    require(len(set(adopted)) == len(adopted), 'roots: duplicate adopted targets')
    refs_exist(adopted, targets, 'roots adopted targets')
    relations = index_by(review['relations'], 'relation_id')
    validate_prerequisites(targets,relations,doc['prerequisites'],adopted)
    directions = {d['direction_id']: d for tid in adopted for d in targets[tid]['directions']}
    require(type(doc['tasks']) is list, 'roots: tasks array required')
    tasks = index_by(doc['tasks'], 'task_id')
    questions = index_by(bank['questions'], 'question_id')
    for task_id, task in tasks.items():
        require(set(task) == {'task_id', 'question_id', 'direction_id'}, 'roots: invalid task fields')
        require(type(task_id) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', task_id), 'roots: invalid task ID')
        qid, did = task['question_id'], task['direction_id']
        require(qid in questions and did in directions, 'roots: unknown task reference')
        if doc.get('generation_policy') == 'root-generation/4':
            require(sum(1 for t in doc['tasks'] if t['question_id'] == qid) == 1, 'roots: a question is one task')
        q = questions[qid]
        require(q.get('format', 'basic') in ('basic', 'list', 'cloze', 'ox', 'mcq', 'multi_select'),
                'roots: compound task needs separate direction-level assessment')
        mappings = [m for m in review['mappings'] if m['question_id'] == qid and m['direction_id'] == did]
        if doc.get('generation_policy') == 'root-generation/4':
            # docs/changes/2026-11-10-importance-at-authoring R5/R8: a goal may be asked across several questions;
            # each task tests some of its relations (answers some of its components).
            require(len(mappings) == 1 and mappings[0]['tested_relation_ids']
                    and set(mappings[0]['tested_relation_ids']) <= set(directions[did]['relation_ids']),
                    'roots: task must directly test part of its direction')
        else:
            require(len(mappings) == 1 and set(directions[did]['relation_ids']) <= set(mappings[0]['tested_relation_ids']),
                    'roots: task must directly test the entire direction')
        require(mappings[0]['question_sha256'] == question_hash(q, bank), 'roots: stale task')
    if doc.get('generation_policy')in('root-generation/2','root-generation/4'):
        prepared={t['question_id']for t in tasks.values()}
        require(all(set(questions[q].get('prerequisites',[]))<=prepared for q in prepared),'roots: prerequisite has no prepared task')
        from .generation_v2 import order_plan
        require(order_plan(doc,doc['tasks'],set(tasks),set())==doc['tasks'],'roots: prerequisite order mismatch')
    require(type(doc['equivalences']) is list, 'roots: equivalences array required')
    # One link per (earlier revision, new direction) and per (earlier revision, old direction). A new direction may
    # continue several earlier revisions (docs/changes/2026-11-15-replace-carry-records R3): replay merges their
    # events in time order.
    destinations, sources = set(), set()
    for link in doc['equivalences']:
        require(type(link) is dict and set(link) == {'revision', 'from_direction', 'to_direction', 'reason'}, 'roots: invalid equivalence')
        require(all(type(v) is str and v.strip() for v in link.values()), 'roots: equivalence needs review reason')
        destination, source = (link['revision'], link['to_direction']), (link['revision'], link['from_direction'])
        require(link['to_direction'] in directions and destination not in destinations and source not in sources,
                'roots: ambiguous equivalence')
        require(link['revision'] != doc['revision'], 'roots: self equivalence')
        destinations.add(destination); sources.add(source)
    return copy.deepcopy(doc)
