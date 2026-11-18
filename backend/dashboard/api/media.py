from .common import *
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError
from blog.image_optimization import webp_derivative

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}
IMAGE_FORMAT_BY_EXTENSION = {
    'jpg': 'JPEG',
    'jpeg': 'JPEG',
    'png': 'PNG',
    'webp': 'WEBP',
    'gif': 'GIF',
}
MAX_IMAGE_UPLOAD_SIZE = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 36_000_000


def unsafe_upload_filename(filename):
    """Reject path-like and control-character names before storage sees them."""
    if not filename or any(ord(character) < 32 or ord(character) == 127 for character in filename):
        return True
    normalized = filename.replace('\\', '/')
    path = PurePosixPath(normalized)
    return normalized.startswith('/') or '\\' in filename or any(part in {'.', '..'} for part in path.parts)


def validate_uploaded_image(uploaded_file):
    if uploaded_file.size > MAX_IMAGE_UPLOAD_SIZE:
        return 'Image uploads must be smaller than 8 MB.'
    if unsafe_upload_filename(uploaded_file.name):
        return 'Image filenames cannot contain paths or control characters.'
    extension = Path(uploaded_file.name or '').suffix.lower().lstrip('.')
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return 'Upload a JPG, PNG, WEBP, or GIF image.'
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()
            if image.format not in ALLOWED_IMAGE_FORMATS or image.format != IMAGE_FORMAT_BY_EXTENSION[extension]:
                return 'Upload a JPG, PNG, WEBP, or GIF image.'
    except (UnidentifiedImageError, OSError, ValueError):
        return 'The uploaded image could not be validated.'
    finally:
        uploaded_file.seek(0)
    return ''

MEDIA_SORTS = {'newest': ('-created_at', '-id'), 'oldest': ('created_at', 'id'), 'title': ('title', 'id')}


def media_usage(asset):
    """Where an asset is referenced, so editors see the impact before deleting it."""
    from blog.models import Author, Category, Post
    needles = [value for value in (
        asset.file.name if asset.file else '',
        asset.optimized_file.name if asset.optimized_file else '',
        asset.url,
    ) if value]
    if not needles:
        return {'total': 0, 'posts': [], 'authors': 0, 'categories': 0}
    post_query, category_query = Q(), Q()
    for needle in needles:
        post_query |= Q(featured_image__icontains=needle) | Q(content__icontains=needle)
        category_query |= Q(hero_image__icontains=needle)
    posts = Post.objects.exclude(status='trash').filter(post_query).distinct()
    author_query = Q(profile_media=asset)
    for needle in needles:
        author_query |= Q(avatar__icontains=needle)
    authors = Author.objects.filter(author_query).distinct().count()
    categories = Category.objects.filter(category_query).count()
    post_count = posts.count()
    team_members = asset.team_page_members.count()
    return {
        'total': post_count + authors + categories + team_members,
        'post_count': post_count,
        'posts': [{'id': post.id, 'title': post.title, 'post_type': post.post_type} for post in posts.only('id', 'title', 'post_type')[:6]],
        'authors': authors,
        'categories': categories,
        'team_members': team_members,
    }


def media_source(asset):
    if asset.file:
        return 'upload'
    return 'wordpress' if asset.wordpress_id else 'external'


def media_item(asset, request):
    data = media_to_dict(asset, request)
    data['source'] = media_source(asset)
    return data


@require_GET
@api_permission_required('media.view')
def media_api(request):
    assets = MediaAsset.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        assets = assets.filter(Q(title__icontains=q) | Q(alt_text__icontains=q) | Q(caption__icontains=q) | Q(url__icontains=q) | Q(file__icontains=q))
    if request.GET.get('id'):
        assets = assets.filter(pk=parse_int(request.GET.get('id')) or 0)
    summary = {'total': MediaAsset.objects.count(), 'missing_alt': MediaAsset.objects.filter(alt_text='').count()}
    if request.GET.get('missing_alt') in {'1', 'true'}:
        assets = assets.filter(alt_text='')
    source = request.GET.get('source')
    if source == 'upload':
        assets = assets.exclude(file='').exclude(file__isnull=True)
    elif source in {'external', 'wordpress'}:
        assets = assets.filter(Q(file='') | Q(file__isnull=True)).filter(wordpress_id__isnull=source == 'external')
    assets = assets.order_by(*MEDIA_SORTS.get(request.GET.get('sort'), MEDIA_SORTS['newest']))
    data = paginate(assets, request, lambda asset: media_item(asset, request), 48)
    data['summary'] = summary
    if request.GET.get('id') and request.GET.get('usage') in {'1', 'true'} and data['results']:
        data['results'][0]['usage'] = media_usage(assets.first())
    return JsonResponse(data)

@require_POST
@api_save_permission_required('media')
def save_media_api(request, pk=None):
    asset = get_object_or_404(MediaAsset, pk=pk) if pk else MediaAsset()
    uploaded_file = request.FILES.get('file')
    if uploaded_file:
        upload_error = validate_uploaded_image(uploaded_file)
        if upload_error:
            return error_response(upload_error)
        asset.file = uploaded_file
        try:
            derivative = webp_derivative(uploaded_file)
        except (OSError, ValueError):
            return error_response('The uploaded image could not be optimized.')
        asset.optimized_file = derivative
    asset.title = request.POST.get('title', asset.title).strip()
    asset.alt_text = request.POST.get('alt_text', asset.alt_text).strip()
    asset.caption = request.POST.get('caption', asset.caption).strip()
    asset.url = request.POST.get('url', asset.url).strip()
    if asset.url and not asset.url.startswith('https://'):
        return error_response('External image URLs must start with https://.')
    if not asset.file and not asset.url:
        return error_response('Choose an image file or enter an image URL.')
    asset.save()
    log_activity(request, 'content', 'update' if pk else 'create', f'Saved media: {asset}', asset)
    return JsonResponse({'success': True, 'media': media_item(asset, request)})

@require_POST
@api_permission_required('media.delete')
def delete_media_api(request, pk):
    asset = get_object_or_404(MediaAsset, pk=pk)
    label = str(asset)
    if asset.file:
        asset.file.delete(save=False)
    if asset.optimized_file:
        asset.optimized_file.delete(save=False)
    asset.delete()
    log_activity(request, 'content', 'delete', f'Deleted media: {label}', metadata={'id': pk})
    return JsonResponse({'success': True})
