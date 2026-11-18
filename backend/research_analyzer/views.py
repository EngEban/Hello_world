import json
import math

import pandas as pd
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from usage import services as usage
from accounts.security import rate_limit

from . import session_store

from .services.data_service import (
    apply_preparation,
    build_preview,
    dataset_summary,
    detect_all_variables,
    parse_uploaded_file,
)

# ``stats_service`` imports the scientific plotting stack through Pingouin.
# Keep that work at request time: Django imports this module while resolving
# URL routes during Gunicorn boot, and loading plotting/font machinery there
# can delay Render long enough for its port check to time out.
def run_test(*args, **kwargs):
    from .services.stats_service import run_test as implementation
    return implementation(*args, **kwargs)


def build_analysis_plan(*args, **kwargs):
    from .services.stats_service import build_analysis_plan as implementation
    return implementation(*args, **kwargs)


def run_analysis_plan(*args, **kwargs):
    from .services.stats_service import run_analysis_plan as implementation
    return implementation(*args, **kwargs)


FEATURE_CODE = 'research_analyzer'
# Bounded per-session history (adopted from the cache-based version).
MAX_SAVED_RESULTS = 20


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return None


def _bad(message, status=400, code=None):
    payload = {'success': False, 'error': message}
    if code:
        payload['code'] = code
    return JsonResponse(payload, status=status)


def _json_safe(value):
    """Convert pandas/numpy scalar values from statistical libraries into JSON-safe primitives."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return value.isoformat() if isinstance(value, pd.Timestamp) else str(value)
    if hasattr(value, 'item'):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _json_response(data, status=200):
    return JsonResponse(_json_safe(data), status=status)


def _require_access(request):
    # Same Free/Premium rules as every other tool: visitors count as Free, so
    # the analyzer is open to them whenever Free access is switched on.
    denied = usage.access_denial(usage.subject_for(request), FEATURE_CODE)
    if denied is not None:
        return _bad(denied.message, denied.status, denied.code)
    return None


def _consume_usage(request, metadata):
    """Charge one analyzer action through the central usage engine.

    Returns the JSON 429 (with limit / remaining / reset time) when the
    allowance is used up, else None. Access was already checked.
    """
    metadata = dict(metadata)
    action = metadata.pop('action')
    return usage.gate(request, FEATURE_CODE, action, metadata=metadata, check_access=False)


def _load(session_id, request):
    """(session, DataFrame) for the caller's live session, else (None, None)."""
    user, visitor_key = session_store.owner_for(request)
    session = session_store.get_session(session_id, user, visitor_key)
    if session is None:
        return None, None
    df = session_store.load_dataframe(session)
    if df is None:
        return None, None
    return session, df


def _expired():
    return _bad('Invalid or expired analyzer session.', 404)


@require_POST
def upload_file(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    if not rate_limit(request, 'research-analyzer-upload', limit=40, window=3600):
        return _bad('Too many uploads. Please wait before trying again.', 429)
    uploaded_file = request.FILES.get('file')
    if uploaded_file is None:
        return _bad("No file provided. Send a multipart/form-data request with key 'file'.")
    try:
        df = parse_uploaded_file(uploaded_file, uploaded_file.name)
    except ValueError as exc:
        return _bad(str(exc))

    session_store.cleanup_expired(limit=20)
    owner, visitor_key = session_store.owner_for(request)
    session = session_store.create_session(owner, uploaded_file.name, df, _json_safe(detect_all_variables(df)), visitor_key=visitor_key)
    return _json_response({
        'success': True,
        'session_id': str(session.pk),
        'filename': session.filename,
        'summary': dataset_summary(df),
        'preview': build_preview(df, n_rows=10),
        'variables': session.variables,
    })


@require_POST
def update_variables(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    payload = _json_body(request)
    if payload is None:
        return _bad('Invalid request payload.')
    variables = payload.get('variables', [])
    session, df = _load(payload.get('session_id'), request)
    if df is None:
        return _expired()
    if not isinstance(variables, list):
        return _bad('Variables must be a list.')

    valid_columns = set(df.columns)
    allowed_types = {'numeric', 'categorical', 'ordinal', 'likert', 'id', 'text', 'date'}
    allowed_roles = {
        'unspecified', 'identifier', 'outcome', 'predictor', 'grouping', 'time',
        'pre_measure', 'post_measure', 'scale_item', 'covariate', 'ignore',
    }
    normalized = []
    for variable in variables:
        if not isinstance(variable, dict):
            return _bad('Each variable must be an object.')
        name = variable.get('name')
        variable_type = variable.get('type')
        role = variable.get('role', 'unspecified')
        if name not in valid_columns:
            return _bad(f'Unknown variable: {name!r}')
        if variable_type not in allowed_types:
            return _bad(f'Unsupported variable type for {name!r}.')
        if role not in allowed_roles:
            return _bad(f'Unsupported research role for {name!r}.')
        normalized.append({**variable, 'name': name, 'type': variable_type, 'role': role})

    session.variables = _json_safe(normalized)
    session_store.save(session, 'variables')
    return _json_response({'success': True, 'status': 'ok', 'variables': normalized})


@require_POST
def prepare_data(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    payload = _json_body(request)
    if payload is None:
        return _bad('Invalid request payload.')
    session, df = _load(payload.get('session_id'), request)
    if df is None:
        return _expired()

    options = payload.get('options', {})
    cleaned_df, change_log, prep_warnings = apply_preparation(df, options if isinstance(options, dict) else {})
    variables = detect_all_variables(cleaned_df)
    session_store.save_dataframe(session, cleaned_df)
    session.variables = _json_safe(variables)
    session_store.save(session, 'variables', 'checksum', 'row_count', 'column_count')
    return _json_response({
        'success': True,
        'summary': dataset_summary(cleaned_df),
        'preview': build_preview(cleaned_df, n_rows=10),
        'change_log': change_log,
        'warnings': prep_warnings,
        'variables': variables,
    })


@require_POST
def run_analysis(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    if not rate_limit(request, 'research-analyzer-test', limit=60, window=3600):
        return _bad('Too many analyses. Please wait before trying again.', 429)
    payload = _json_body(request)
    if payload is None:
        return _bad('Invalid request payload.')
    test = str(payload.get('test', '') or '').strip()
    params = payload.get('params', {})
    if not test:
        return _bad('Analysis test is required.')
    if not isinstance(params, dict):
        return _bad('Analysis parameters must be an object.')
    session, df = _load(payload.get('session_id'), request)
    if df is None:
        return _expired()

    # Each attempt is charged before the (possibly expensive) computation, so a
    # stream of failing requests cannot run unmetered work.
    blocked = _consume_usage(request, {'action': 'run_analysis', 'test': test})
    if blocked:
        return blocked
    variable_map = {item['name']: item for item in session.variables}
    params['_variable_map'] = variable_map

    result = run_test(test, df, params)
    if 'error' in result:
        return _json_response(result, status=422)


    session.results = [*session.results[-(MAX_SAVED_RESULTS - 1):], _json_safe({
        'test': test,
        'params': {key: value for key, value in params.items() if key != '_variable_map'},
        'variables': _result_variables(test, result, params),
        'purpose': _test_purpose(test),
        'decision': 'Selected and run by the researcher.',
        'result': result,
        'source': 'selected',
    })]
    session_store.save(session, 'results')
    return _json_response(result)


@require_GET
def analysis_plan(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    session, df = _load(request.GET.get('session_id', ''), request)
    if df is None:
        return _expired()
    return _json_response(build_analysis_plan(df, session.variables))


@require_POST
def generate_master_analysis(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    # Keyed by account, or by IP alone for visitors (who all share user.id None).
    identity = str(request.user.id) if request.user.is_authenticated else ''
    if not rate_limit(request, 'research-analyzer-master-analysis', identity, limit=5, window=3600):
        return _bad('Too many master-analysis requests. Please try again later.', 429)
    payload = _json_body(request)
    if payload is None:
        return _bad('Invalid request payload.')
    session, df = _load(payload.get('session_id'), request)
    if df is None:
        return _expired()
    blocked = _consume_usage(request, {'action': 'generate_master_report'})
    if blocked:
        return blocked
    plan, executed = run_analysis_plan(df, session.variables)
    session.analysis_plan = _json_safe(plan)
    session.auto_results = _json_safe(executed[-MAX_SAVED_RESULTS:])
    session_store.save(session, 'analysis_plan', 'auto_results')
    return _json_response({'success': True, 'plan': plan, 'analyses': executed})


@require_GET
def master_report(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    session, df = _load(request.GET.get('session_id', ''), request)
    if df is None:
        return _expired()
    results = _merge_report_results(df, session.variables, session.results, session.auto_results)
    return _json_response(_build_master_report(results, session.variables, session.filename, session.analysis_plan))


@require_POST
def clear_session(request, session_id):
    blocked = _require_access(request)
    if blocked:
        return blocked
    user, visitor_key = session_store.owner_for(request)
    session = session_store.get_session(session_id, user, visitor_key)
    if session is not None:
        session_store.delete_session(session)
        return _json_response({'success': True, 'status': 'cleared'})
    return _bad('Session not found.', 404)


def _reportable_variables(variables):
    return [
        {'name': variable['name'], 'type': variable.get('type', 'numeric')}
        for variable in variables
        if variable.get('role') not in {'identifier', 'ignore'} and variable.get('type') not in {'id', 'text', 'date'}
    ]


def _test_purpose(test):
    return {
        'descriptive': 'Describe the dataset, missingness, and core variable summaries before inference.',
        'demographic': 'Create a sample-characteristics table with counts, percentages, and numeric summaries.',
        'pearson': 'Assess a linear association between two numeric variables.',
        'spearman': 'Assess a rank-based association when data are ordinal, skewed, or monotonic.',
        'kendall': 'Assess rank agreement, especially with small samples or many ties.',
        'ttest': 'Compare a numeric outcome between two independent groups.',
        'welch': 'Compare two independent group means when equal variances are doubtful.',
        'mann_whitney': 'Compare two independent groups with a rank-based method.',
        'anova': 'Compare a numeric outcome across three or more independent groups.',
        'welch_anova': 'Compare multiple group means when variances differ.',
        'kruskal': 'Compare three or more groups with a rank-based method.',
        'paired_ttest': 'Estimate average paired change between before and after measurements.',
        'wilcoxon': 'Assess paired change with a rank-based method.',
        'mcnemar': 'Assess paired change in a binary categorical response.',
        'chi_square': 'Assess whether two categorical variables are associated.',
        'cronbach': 'Assess internal consistency for selected questionnaire items.',
        'linear_regression': 'Model a continuous outcome using selected predictors.',
        'logistic_regression': 'Model a binary outcome using selected predictors.',
    }.get(test) or _registry_purpose(test)


def _registry_purpose(test):
    from .engine.registry import label_for
    label = label_for(test)
    return f'{label} selected by the researcher.' if label != test else 'Researcher-selected statistical analysis.'


def _result_variables(test, result, params):
    if isinstance(result, dict):
        if result.get('variables'):
            return result['variables']
        if result.get('items'):
            return result['items']
        if result.get('outcome'):
            return [result['outcome'], *result.get('predictors', [])]
        if result.get('pre') and result.get('post'):
            return [result['pre'], result['post']]
    if test in {'ttest', 'welch', 'mann_whitney', 'anova', 'welch_anova', 'kruskal'}:
        return [params.get('outcome'), params.get('group')]
    if test in {'paired_ttest', 'wilcoxon', 'mcnemar'}:
        return [params.get('pre'), params.get('post')]
    if test in {'pearson', 'spearman', 'kendall', 'chi_square'}:
        return [params.get('var1'), params.get('var2')]
    if test == 'cronbach':
        return params.get('items', [])
    if test in {'linear_regression', 'logistic_regression'}:
        return [params.get('outcome'), *params.get('predictors', [])]
    if test in {'descriptive', 'demographic'}:
        return [item.get('name') for item in params.get('variables', [])]
    return []


def _result_key(entry):
    result = entry.get('result', {})
    variables = entry.get('variables') or _result_variables(entry.get('test'), result, entry.get('params', {}))
    clean_variables = tuple(sorted(str(item) for item in variables if item))
    if entry.get('test') in {'descriptive', 'demographic'}:
        return (entry.get('test'), 'summary')
    return (entry.get('test'), clean_variables)


def _merge_report_results(df, variables, manual_results, auto_results):
    reportable = _reportable_variables(variables)
    merged = []
    if reportable:
        descriptive = run_test('descriptive', df, {'variables': reportable})
        merged.append({
            'id': 'descriptive_current_dataset',
            'test': 'descriptive',
            'purpose': _test_purpose('descriptive'),
            'variables': [item['name'] for item in reportable],
            'decision': 'Automatically included so the Master Report always starts with descriptive statistics.',
            'alternatives': [],
            'status': 'completed' if 'error' not in descriptive else 'not_run',
            'result': descriptive,
            'source': 'required',
        })

    seen = {_result_key(item) for item in merged}
    for source, entries in (('selected', manual_results), ('automatic', auto_results)):
        for entry in entries:
            normalized = {**entry}
            normalized.setdefault('purpose', _test_purpose(entry.get('test')))
            normalized.setdefault('variables', _result_variables(entry.get('test'), entry.get('result', {}), entry.get('params', {})))
            normalized.setdefault('status', 'completed' if 'error' not in normalized.get('result', {}) else 'not_run')
            normalized.setdefault('source', source)
            key = _result_key(normalized)
            if key not in seen:
                merged.append(normalized)
                seen.add(key)
    return merged


def _build_master_report(results, variables, filename, analysis_plan=None):
    desc_results = [item for item in results if item['test'] in ('descriptive', 'demographic')]
    stat_results = [item for item in results if item['test'] not in ('descriptive', 'demographic')]
    apa_en_parts = []
    apa_ar_parts = []
    for item in results:
        result = item.get('result', item)
        if 'apa_en' in result:
            apa_en_parts.append(result['apa_en'])
        if 'apa_ar' in result:
            apa_ar_parts.append(result['apa_ar'])
    return {
        'success': True,
        'filename': filename,
        'n_analyses': len(results),
        'variables_analyzed': [item['name'] for item in variables if item.get('role') not in {'identifier', 'ignore'}],
        'analysis_plan': analysis_plan,
        'sections': {'descriptive': desc_results, 'statistical': stat_results},
        'findings': [
            {
                'test': item['test'],
                'purpose': item.get('purpose', 'Researcher-selected statistical analysis.'),
                'variables': item.get('variables', []),
                'decision': item.get('decision'),
                'alternatives': item.get('alternatives', []),
                'status': item.get('status', 'completed'),
                'source': item.get('source', 'selected'),
                'result': item.get('result', item),
            }
            for item in stat_results
        ],
        'apa_report': {
            'english': '\n\n'.join(apa_en_parts) or 'No analyses run yet.',
            'arabic': '\n\n'.join(apa_ar_parts) or 'لم يتم إجراء أي تحليلات بعد.',
        },
    }


@require_GET
def method_catalog(request):
    """Families, methods (basic / advanced) and their inputs, for the method library and forms."""
    blocked = _require_access(request)
    if blocked:
        return blocked
    from .engine.registry import public_catalog
    return _json_response(public_catalog())


@require_POST
def recommend_method(request):
    """Recommend a method for a plain-language question; nothing is computed or charged yet."""
    blocked = _require_access(request)
    if blocked:
        return blocked
    if not rate_limit(request, 'research-analyzer-recommend', limit=300, window=3600):
        return _bad('Too many requests. Please wait a moment.', 429)
    payload = _json_body(request)
    if payload is None:
        return _bad('Invalid request payload.')
    fields = payload.get('fields', {})
    if not isinstance(fields, dict):
        return _bad('Question fields must be an object.')
    session, df = _load(payload.get('session_id'), request)
    if df is None:
        return _expired()
    from .engine.selection import SelectionError, recommend
    try:
        recommendation = recommend(df, session.variables, str(payload.get('question', '')), fields)
    except SelectionError as exc:
        return _bad(str(exc), 422, 'selection')
    return _json_response({'success': True, **recommendation})


@require_GET
def variable_levels(request):
    """The observed categories of one variable (for event, reference and positive-value choices)."""
    blocked = _require_access(request)
    if blocked:
        return blocked
    session, df = _load(request.GET.get('session_id', ''), request)
    if df is None:
        return _expired()
    name = request.GET.get('variable', '')
    if name not in df.columns:
        return _bad(f'Unknown variable: {name!r}', 404)
    counts = df[name].dropna().astype(str).value_counts()
    if len(counts) > 50:
        return _json_response({'success': True, 'variable': name, 'levels': [], 'too_many': True})
    levels = [{'value': value, 'count': int(count)} for value, count in sorted(counts.items(), key=lambda item: item[0])]
    return _json_response({'success': True, 'variable': name, 'levels': levels, 'missing': int(df[name].isna().sum())})


@require_POST
def export_docx(request):
    """Turn the report the researcher assembled into a Word document."""
    blocked = _require_access(request)
    if blocked:
        return blocked
    if not rate_limit(request, 'research-analyzer-export', limit=30, window=3600):
        return _bad('Too many exports. Please wait before trying again.', 429)
    if len(request.body) > 2 * 1024 * 1024:
        return _bad('The report is too large to export.', 413)
    payload = _json_body(request)
    if payload is None or not isinstance(payload.get('report'), dict):
        return _bad('Invalid report payload.')
    session, _ = _load(payload.get('session_id'), request)
    if session is None:
        return _expired()
    from .engine.report_docx import build
    content = build(payload['report'])
    stem = ''.join(ch for ch in (session.filename or 'analysis').rsplit('.', 1)[0] if ch.isalnum() or ch in '-_')[:60] or 'analysis'
    response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="{stem}-report.docx"'
    return response
