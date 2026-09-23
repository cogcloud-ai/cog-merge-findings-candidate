"""Pure deterministic consolidation; no filesystem reads or external effects."""
from copy import deepcopy
from jsonschema import Draft202012Validator


def _object(properties, required=None, extra=False):
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required,
            'additionalProperties': extra}


def _array(items, minimum=0):
    return {'type': 'array', 'items': items, 'minItems': minimum}


_STRING = {'type': 'string', 'minLength': 1}
_TEXT = {'type': ['string', 'null']}
_BOOL = {'type': 'boolean'}
_CITATION = _object({'item_id': _STRING, 'passage': _STRING})
_OVERLAP = _object({'finding_id': _STRING, 'item_ids': _array(_STRING, 2),
                    'relationship': {'enum': ['duplicate', 'overlap'], 'type': 'string'},
                    'rationale': _STRING, 'citations': _array(_CITATION, 2)})
_DEPENDENCY = _object({'finding_id': _STRING, 'blocking_item_id': _STRING,
                       'blocked_item_id': _STRING, 'basis': {'enum': ['stated', 'inferred']},
                       'citation': _TEXT, 'inference_rationale': _TEXT})
DETECTOR_SCHEMAS = {
    kind: _object({'abstained': _BOOL, 'findings': _array(finding)})
    for kind, finding in [('overlap', _OVERLAP), ('dependency', _DEPENDENCY)]
}
_INPUT = _object({
    'kind': {'enum': ['overlap', 'dependency']},
    'batches': _array(_object({
        'batch_id': _STRING, 'item_ids': _array(_STRING),
        'cuts': _array(_object({'item_id': _STRING, 'field': _STRING}, extra=True))
    }, ['batch_id', 'item_ids'], True)),
    'results': _array(_array({'type': ['object', 'null']}))
})
_OCCURRENCE = _object({'batch_id': _STRING, 'repeat': {'type': 'integer', 'minimum': 0}})
_SOURCE = _object(dict(_OCCURRENCE['properties'], source_finding_id=_STRING))
_PROVENANCE = _object({
    'finding_id': {'type': 'string', 'pattern': '^m-[1-9][0-9]*$'},
    'support': {'type': 'integer', 'minimum': 1},
    'of': {'type': 'integer', 'minimum': 0},
    'occurrences': _array(_OCCURRENCE, 1),
    'source_finding_ids': dict(_array(_SOURCE, 1), uniqueItems=True),
    'cut_item_ids': dict(_array(_STRING), uniqueItems=True),
    'also_inferred': _object({
        'count': {'type': 'integer', 'minimum': 1},
        'rationale': {'type': 'string'},
        'sources': dict(_array(_SOURCE, 1), uniqueItems=True)
    })
}, ['finding_id', 'support', 'of', 'occurrences', 'source_finding_ids', 'cut_item_ids'])
_OUTPUT = _object({'abstained': _BOOL, 'findings': _array({'type': 'object'}),
                   'provenance': _array(_PROVENANCE), 'authority_use': _array({'type': 'object'})})
_INPUT_VALIDATOR = Draft202012Validator(_INPUT)
_OUTPUT_VALIDATOR = Draft202012Validator(_OUTPUT)
_DETECTORS = {k: Draft202012Validator(s) for k, s in DETECTOR_SCHEMAS.items()}


def _shape_problems(validator, value, check):
    import cog_core
    return [cog_core.problem(check, str(error)) for error in validator.iter_errors(value)]


def check_input(bundle):
    import cog_core
    problems = _shape_problems(_INPUT_VALIDATOR, bundle, 'input-shape')
    if problems:
        return problems
    if len(bundle['batches']) != len(bundle['results']):
        problems.append(cog_core.problem('batch-results-length', 'batches and results must align'))
    ids = [b['batch_id'] for b in bundle['batches']]
    if len(set(ids)) != len(ids):
        problems.append(cog_core.problem('duplicate-batch-id', 'batch_id must be unique'))
    return problems


def _key(kind, finding):
    if kind == 'overlap':
        return (tuple(sorted(set(finding['item_ids']))), finding['relationship'])
    return ((finding['blocking_item_id'], finding['blocked_item_id']), finding['basis'])


def _quality(kind, finding):
    if kind == 'overlap':
        passages = [c['passage'] for c in finding['citations']]
    else:
        passages = [finding['citation']] if finding['citation'] is not None else []
    return (len(passages), max(map(len, passages), default=0))


def _refs(records, batches):
    triples = sorted({(batches[i]['batch_id'], r, f['finding_id']) for i, r, f in records})
    return [{'batch_id': b, 'repeat': r, 'source_finding_id': f} for b, r, f in triples]


def _positions(records):
    return list(dict.fromkeys((i, r) for i, r, _ in records))


def _merge(bundle):
    import cog_core
    kind, batches = bundle['kind'], bundle['batches']
    members = [set(b['item_ids']) for b in batches]
    groups, accepted, problems = {}, [], []
    for i, repeats in enumerate(bundle['results']):
        for r, result in enumerate(repeats):
            if result is None:
                continue
            if not _DETECTORS[kind].is_valid(result):
                problems.append(cog_core.problem('result-shape',
                    'batch %r repeat %d is not a valid %s payload' % (batches[i]['batch_id'], r, kind)))
                continue
            accepted.append((i, r, result['abstained']))
            for finding in result['findings']:
                key = _key(kind, finding)
                if not set(key[0]).issubset(members[i]):
                    problems.append(cog_core.problem('finding-outside-batch',
                        'batch %r repeat %d finding %r names an item outside its batch' %
                        (batches[i]['batch_id'], r, finding['finding_id'])))
                    continue
                groups.setdefault(key, []).append((i, r, finding))
    if not accepted:
        problems.append(cog_core.problem('no-results', 'No accepted detector answers', severity='warn'))
    folded = {}
    if kind == 'dependency':
        for key in list(groups):
            inferred = (key[0], 'inferred')
            if key[1] == 'stated' and inferred in groups:
                folded[key] = groups.pop(inferred)
    values = {}
    for relationship, value in groups:
        values.setdefault(relationship, set()).add(value)
    for relationship in sorted(values):
        if len(values[relationship]) > 1:
            problems.append(cog_core.problem('findings-disagree',
                'Relationship %r has values %r' % (relationship, sorted(values[relationship])), severity='warn'))
    output = {'abstained': all(a for _, _, a in accepted), 'findings': [],
              'provenance': [], 'authority_use': []}
    for number, key in enumerate(sorted(groups), 1):
        records = groups[key]
        # max is stable: records were collected in batch/repeat/finding order.
        kept = max(records, key=lambda record: _quality(kind, record[2]))[2]
        finding = deepcopy(kept)
        finding['finding_id'] = 'm-%d' % number
        positions = _positions(records)
        cuts = {cut['item_id'] for i, _ in positions for cut in batches[i].get('cuts', [])}
        inferred = folded.get(key, [])
        provenance = {
            'finding_id': finding['finding_id'], 'support': len(positions),
            'of': sum(set(key[0]).issubset(members[i]) for i, _, _ in accepted),
            'occurrences': [{'batch_id': batches[i]['batch_id'], 'repeat': r} for i, r in positions],
            'source_finding_ids': _refs(records + inferred, batches),
            'cut_item_ids': sorted(set(key[0]) & cuts)
        }
        if inferred:
            best = max(inferred, key=lambda record: len(record[2]['inference_rationale'] or ''))[2]
            provenance['also_inferred'] = {
                'count': len(_positions(inferred)), 'rationale': best['inference_rationale'] or '',
                'sources': _refs(inferred, batches)
            }
        output['findings'].append(finding)
        output['provenance'].append(provenance)
    return output, problems


def run(bundle, grant, journal):
    problems = check_input(bundle)
    if problems:
        return {'abstained': True, 'findings': [], 'provenance': [], 'authority_use': []}, problems
    return _merge(bundle)


def check_output(payload, bundle):
    import cog_core
    problems = _shape_problems(_OUTPUT_VALIDATOR, payload, 'output-shape')
    input_problems = check_input(bundle)
    if input_problems:
        problems.append(cog_core.problem('output-input', 'Cannot ground output against invalid input'))
        return problems
    if not isinstance(payload, dict):
        return problems
    problems.extend(_shape_problems(_DETECTORS[bundle['kind']],
        {'abstained': payload.get('abstained'), 'findings': payload.get('findings')}, 'detector-output-shape'))
    if problems:
        return problems
    expected, _ = _merge(bundle)
    # Structural comparison also verifies actual source existence and exact text,
    # not merely plausibility of provenance. No supplied text is interpreted.
    for field in ('abstained', 'findings', 'provenance', 'authority_use'):
        if payload[field] != expected[field]:
            problems.append(cog_core.problem('output-contract',
                '%s differs from the grounded deterministic merge' % field))
    return problems
