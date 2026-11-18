"""WebP delivery derivatives; original dashboard uploads remain untouched."""
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def webp_derivative(uploaded):
    uploaded.seek(0)
    output = BytesIO()
    try:
        with Image.open(uploaded) as source:
            if getattr(source, 'is_animated', False):
                # Do not silently flatten animations or decode unbounded frames.
                return None
            image = ImageOps.exif_transpose(source)
            image = image.convert('RGBA' if 'A' in image.getbands() or image.info.get('transparency') is not None else 'RGB')
            image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            image.save(output, 'WEBP', quality=82, method=6)
        return ContentFile(output.getvalue(), name=f'{Path(uploaded.name).stem}.webp')
    finally:
        uploaded.seek(0)
