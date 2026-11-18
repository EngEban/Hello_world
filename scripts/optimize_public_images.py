"""Build local WebP derivatives without modifying any database content.

Run with backend's Python environment from the repository root. Network access
is limited to the known public image hosts below; originals are never deleted.
"""
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'frontend/public/optimized-images'
MANIFEST = ROOT / 'frontend/src/config/optimizedImages.json'
HOSTS = {'resref.com', 'www.resref.com', 'cdn.dal.ca'}
OLD_BANNER = 'hand-medical-glove-pointing-virtual-screen-medical-technology-1.jpg'
Image.MAX_IMAGE_PIXELS = 36_000_000


def canonical(url):
    url = unescape(url).replace('http://resres.local/', 'https://resref.com/').replace('https://resres.local/', 'https://resref.com/').replace('http://resref.local/', 'https://resref.com/').replace('https://resref.local/', 'https://resref.com/')
    parts = urlsplit(url)
    if parts.hostname not in HOSTS or parts.username or parts.password or parts.port not in (None, 80, 443):
        return ''
    if not parts.path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) or parts.path.endswith(OLD_BANNER):
        return ''
    encoded_path = quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    return urlunsplit(('https', parts.hostname.replace('www.resref.com', 'resref.com'), encoded_path, '', ''))


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not canonical(newurl):
            raise ValueError('Redirect outside approved public image hosts')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class ImageSources(HTMLParser):
    def __init__(self, urls):
        super().__init__(convert_charrefs=True)
        self.urls = urls

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            attrs = dict(attrs)
            for key in ('src', 'data-src'):
                if attrs.get(key):
                    self.urls.add(attrs[key])


def collect_sources():
    sys.path.insert(0, str(ROOT / 'backend'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resref.settings')
    import django
    django.setup()
    from blog.models import Post, Author
    from dashboard.models import SiteSettings
    from django.utils import timezone
    urls = set()
    for post in Post.objects.filter(status='publish', published_at__lte=timezone.now()).iterator():
        urls.add(post.featured_image)
        ImageSources(urls).feed(post.content)
    urls.update(Author.objects.filter(is_active=True).values_list('avatar', flat=True))
    urls.update(SiteSettings.objects.filter(key__icontains='image').values_list('value', flat=True))
    urls.update(SiteSettings.objects.filter(key__icontains='logo').values_list('value', flat=True))
    urls.update(re.findall(r"https://[^'\"\s]+", (ROOT / 'frontend/src/siteData.js').read_text(encoding='utf-8')))
    return sorted({valid for url in urls if (valid := canonical(url))})


def encode(image, destination, width, quality=82):
    resized = image.copy()
    resized.thumbnail((width, width), Image.Resampling.LANCZOS)
    resized.save(destination, 'WEBP', quality=quality, method=6)
    return resized.size


def convert(url):
    name = hashlib.sha256(url.encode()).hexdigest()[:20]
    path = OUTPUT / f'{name}.webp'
    small = OUTPUT / f'{name}-640.webp'
    with build_opener(SafeRedirect()).open(Request(url, headers={'User-Agent': 'ResRef-image-optimization/1.0'}), timeout=20) as response:
        data = response.read(12 * 1024 * 1024 + 1)
    if len(data) > 12 * 1024 * 1024:
        raise ValueError('Image exceeds offline conversion size limit')
    with Image.open(io.BytesIO(data)) as original:
        if getattr(original, 'is_animated', False):
            raise ValueError('Animated source retained to avoid losing animation')
        image = ImageOps.exif_transpose(original).convert('RGBA' if 'A' in original.getbands() or original.info.get('transparency') is not None else 'RGB')
        width, height = encode(image, path, 1920)
        encode(image, small, 640)
    return {'file': path.name, 'small': small.name, 'width': width, 'height': height,
            'source_bytes': len(data), 'bytes': path.stat().st_size, 'small_bytes': small.stat().st_size}


def optimize_heroes():
    totals = [0, 0]
    for path in (ROOT / 'frontend/public/hero-images').glob('*.webp'):
        if path.stem.endswith('-mobile'):
            continue
        totals[0] += path.stat().st_size
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original).convert('RGB')
            encode(image, path.with_stem(path.stem + '-mobile'), 768, 72)
            # CSS already centre-crops wide banners. Store that desktop crop
            # instead of transmitting the invisible top/bottom of tall photos.
            desktop = ImageOps.fit(image, (1600, 900), Image.Resampling.LANCZOS)
            desktop.save(path, 'WEBP', quality=72, method=6)
        totals[1] += path.stat().st_size
    print('Hero bytes before/after:', totals, flush=True)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    urls = collect_sources()
    previous = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {}
    results = dict(previous)
    failed = []
    pending = [url for url in urls if url not in results or not (OUTPUT / results[url]['file']).exists()]
    print(f'Public image sources: {len(urls)}; pending: {len(pending)}', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(convert, url): url for url in pending}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception as error:
                failed.append((url, str(error)))
            if index % 20 == 0:
                print(f'Processed {index}/{len(pending)}; unavailable: {len(failed)}', flush=True)
    MANIFEST.write_text(json.dumps(results, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Unavailable originals (kept unchanged):', json.dumps(failed), flush=True)
    print('Image totals:', len(results), 'original bytes:', sum(x['source_bytes'] for x in results.values()),
          'WebP bytes:', sum(x['bytes'] for x in results.values()), flush=True)
    if '--heroes' in sys.argv:
        optimize_heroes()


def optimize_local_assets():
    for source in (ROOT / 'frontend/public').glob('resref-logo*.png'):
        with Image.open(source) as image:
            image.save(source.with_suffix('.webp'), 'WEBP', lossless=True, method=6)
    source = ROOT / 'frontend/src/assets/homepage/global-research-atlas-hero-4k.webp'
    with Image.open(source) as image:
        for width in (640, 1280, 1920):
            encode(image, source.with_name(f'global-research-atlas-hero-{width}.webp'), width)


if __name__ == '__main__':
    main()
    optimize_local_assets()
