from .common import *
from ..models import FAQCategory, FAQItem
from ..serializers import faq_category_to_dict, faq_item_to_dict


@require_GET
@api_permission_required('faq.view')
def faq_categories_api(request):
    qs = FAQCategory.objects.prefetch_related('items')
    if request.GET.get('q'):
        qs = qs.filter(name__icontains=request.GET.get('q').strip())
    results = []
    for item in qs:
        data = faq_category_to_dict(item, include_counts=True)
        data['hidden_count'] = data['item_count'] - data['published_count']
        results.append(data)
    return JsonResponse({'results': results})


@require_POST
@api_save_permission_required('faq')
def save_faq_category_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(FAQCategory, pk=pk) if pk else FAQCategory()
    item.name = text_field(data, 'name', item.name)
    item.slug = text_field(data, 'slug', item.slug) or item.slug
    item.sort_order = parse_int(data.get('sort_order'), item.sort_order) or 0
    if not item.name:
        return error_response('FAQ category name is required.')
    if item.slug and FAQCategory.objects.exclude(pk=item.pk).filter(slug=item.slug).exists():
        return error_response('This FAQ category slug is already used.')
    item.save()
    log_activity(request, 'faq', 'update' if pk else 'create', f'Saved FAQ category: {item.name}', item)
    return JsonResponse({'success': True, 'category': faq_category_to_dict(item, include_counts=True)})


@require_POST
@api_permission_required('faq.delete')
def delete_faq_category_api(request, pk):
    item = get_object_or_404(FAQCategory, pk=pk)
    if item.items.exists():
        return error_response('Move or hide FAQ items before deleting this category.')
    name = item.name
    item.delete()
    log_activity(request, 'faq', 'delete', f'Deleted FAQ category: {name}', metadata={'id': pk})
    return JsonResponse({'success': True})


@require_GET
@api_permission_required('faq.view')
def faq_items_api(request):
    qs = FAQItem.objects.select_related('category')
    if request.GET.get('category'):
        qs = qs.filter(category_id=parse_int(request.GET.get('category')))
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET.get('status'))
    qs = apply_common_filters(qs, request, ['question', 'answer', 'category__name'], ['status', 'sort_order', 'updated_at'], 'sort_order')
    return JsonResponse(paginate(qs, request, faq_item_to_dict, 50))


@require_POST
@api_save_permission_required('faq')
def save_faq_item_api(request, pk=None):
    data = get_payload(request)
    item = get_object_or_404(FAQItem, pk=pk) if pk else FAQItem()
    if 'category' in data or not item.pk:
        category_id = id_field(data.get('category'), 'category')
        item.category = FAQCategory.objects.filter(pk=category_id).first() if category_id else None
    item.question = text_field(data, 'question', item.question)
    item.answer = text_field(data, 'answer', item.answer)
    item.status = data.get('status', item.status or 'published')
    item.sort_order = parse_int(data.get('sort_order'), item.sort_order) or 0
    # category_id, not category: reading an unset non-null FK raises.
    if not item.category_id:
        return error_response('FAQ category is required.')
    if not item.question:
        return error_response('FAQ question is required.')
    if not item.answer:
        return error_response('FAQ answer is required.')
    if item.status not in dict(FAQItem.STATUS):
        return error_response('Unknown FAQ status.')
    item.save()
    log_activity(request, 'faq', 'update' if pk else 'create', f'Saved FAQ item: {item.question}', item)
    return JsonResponse({'success': True, 'item': faq_item_to_dict(item)})


@require_POST
@api_permission_required('faq.delete')
def hide_faq_item_api(request, pk):
    item = get_object_or_404(FAQItem, pk=pk)
    item.status = 'hidden'
    item.save(update_fields=['status', 'updated_at'])
    log_activity(request, 'faq', 'status', f'Hidden FAQ item: {item.question}', item)
    return JsonResponse({'success': True, 'item': faq_item_to_dict(item)})
