"""List helpers shared by dashboard endpoints."""

from django.core.paginator import Paginator
from django.db.models import Q

from .payload import parse_int

MAX_PER_PAGE = 100


def paginate(queryset, request, serializer, per_page=20):
    requested = parse_int(request.GET.get('per_page'), per_page) or per_page
    paginator = Paginator(queryset, min(max(requested, 1), MAX_PER_PAGE))
    page = paginator.get_page(request.GET.get('page'))
    return {
        'results': [serializer(item) for item in page.object_list],
        'pagination': {
            'current_page': page.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
        },
    }


def apply_common_filters(queryset, request, search_fields=(), allowed_sort=(), default_sort='-created_at'):
    q = request.GET.get('q', '').strip()
    if q and search_fields:
        query = Q()
        for field in search_fields:
            query |= Q(**{f'{field}__icontains': q})
        queryset = queryset.filter(query)
    sort = request.GET.get('sort', default_sort)
    if sort.lstrip('-') in {item.lstrip('-') for item in allowed_sort} or sort == default_sort:
        queryset = queryset.order_by(sort)
    return queryset
