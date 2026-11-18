"""SEO / AEO / GEO health of articles for the dashboard overview and library.

Reports are computed on demand and cached (blog.seo_analysis.cached_reports);
nothing is stored in the database. One request never analyses more than
REFRESH_BATCH uncached articles, so a cold cache fills over a few requests.
"""
from blog.seo_analysis import CHECK_IDS, CHECK_INFO, GROUPS, cached_reports, score_band
from resref.seo import ai_crawler_policy, indexing_allowed

from .common import *

REFRESH_BATCH = 40
LOW_SCORE_NEEDS = {f'{group}_low': group for group in GROUPS}


def content_queryset(post_type):
    return Post.objects.filter(post_type='page' if post_type == 'page' else 'post').exclude(status='trash')


def optimization_summary(report):
    """Compact per-row health for the article library."""
    report = report or {}
    checks = report.get('checks') or {}
    ranked = sorted((check_id for check_id in CHECK_IDS if checks.get(check_id) in {'bad', 'warn'}),
                    key=lambda check_id: (checks[check_id] != 'bad', -CHECK_INFO[check_id][1]))
    return {
        'scores': report.get('scores') or None,
        'problems': sum(1 for status in checks.values() if status == 'bad'),
        'improvements': sum(1 for status in checks.values() if status == 'warn'),
        'issues': ranked[:5],
    }


def is_score_need(need):
    return need in {'keyphrase', 'low_score'} or need in LOW_SCORE_NEEDS or str(need or '').startswith('issue:')


def valid_score_need(need):
    return not str(need).startswith('issue:') or need[6:] in CHECK_INFO


def report_matches(report, need):
    """Whether an analysed article matches a score-based "needs" filter."""
    checks, scores = report.get('checks') or {}, report.get('scores') or {}
    if need == 'keyphrase':
        return checks.get('keyphrase') == 'bad'
    if need == 'low_score':
        return scores.get('overall') is not None and scores['overall'] < 50
    if need in LOW_SCORE_NEEDS:
        value = scores.get(LOW_SCORE_NEEDS[need])
        return value is not None and value < 50
    if need.startswith('issue:'):
        return checks.get(need[6:]) in {'bad', 'warn'}
    return False


@require_GET
@api_permission_required('content.view')
def seo_overview_api(request):
    post_type = request.GET.get('type', 'post')
    queryset = content_queryset(post_type)
    reports, pending = cached_reports(queryset, budget=REFRESH_BATCH)
    titles = {row['id']: row for row in queryset.values('id', 'title', 'slug', 'status', 'post_type')}
    scores = {group: [] for group in (*GROUPS, 'overall')}
    bands = {'good': 0, 'ok': 0, 'poor': 0}
    issues = {check_id: {'id': check_id, 'group': CHECK_INFO[check_id][0], 'bad': 0, 'warn': 0} for check_id in CHECK_IDS}
    faq_articles = cited_articles = 0
    for report in reports.values():
        for group, value in (report.get('scores') or {}).items():
            if value is not None and group in scores:
                scores[group].append(value)
        band = score_band((report.get('scores') or {}).get('overall'))
        if band in bands:
            bands[band] += 1
        for check_id, status in (report.get('checks') or {}).items():
            if check_id in issues and status in {'bad', 'warn'}:
                issues[check_id][status] += 1
        faq_articles += 1 if report.get('faq', 0) >= 2 else 0
        cited_articles += 1 if (report.get('checks') or {}).get('citations') == 'good' else 0
    ranked = sorted((item for item in issues.values() if item['bad'] or item['warn']),
                    key=lambda item: (-(item['bad'] * 2 + item['warn']), -CHECK_INFO[item['id']][1]))
    lowest = sorted((pk for pk, report in reports.items() if (report.get('scores') or {}).get('overall') is not None and pk in titles),
                    key=lambda pk: reports[pk]['scores']['overall'])[:6]
    return JsonResponse({
        'type': 'page' if post_type == 'page' else 'post',
        'total': len(titles), 'analysed': len(reports), 'pending': pending,
        'averages': {group: round(sum(values) / len(values)) if values else None for group, values in scores.items()},
        'bands': bands,
        'issues': ranked[:12],
        'lowest': [{**titles[pk], 'scores': reports[pk]['scores']} for pk in lowest],
        'signals': {
            'faq_articles': faq_articles, 'cited_articles': cited_articles,
            'indexing_allowed': indexing_allowed(), 'ai_crawlers': ai_crawler_policy(),
            'llms_txt': True, 'sitemap': True,
        },
    })


@require_POST
@api_permission_required('content.manage')
def seo_refresh_api(request):
    """Analyse the next batch of articles that have no cached report yet."""
    reports, remaining = cached_reports(Post.objects.exclude(status='trash'), budget=REFRESH_BATCH)
    return JsonResponse({'success': True, 'analysed': len(reports), 'remaining': remaining})
