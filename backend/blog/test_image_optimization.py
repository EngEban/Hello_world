from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from blog.image_optimization import webp_derivative
from blog.models import MediaAsset


class ImageOptimizationTests(SimpleTestCase):
    def test_real_webp_preserves_transparency_and_original_bytes(self):
        original = BytesIO()
        Image.new('RGBA', (48, 32), (0, 20, 80, 0)).save(original, 'PNG')
        upload = SimpleUploadedFile('transparent.png', original.getvalue(), content_type='image/png')
        result = webp_derivative(upload)
        self.assertEqual(upload.read(), original.getvalue())
        with Image.open(result) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertEqual(image.size, (48, 32))
            self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_large_upload_is_resized_without_cropping(self):
        original = BytesIO()
        Image.new('RGB', (4000, 1000), '#0c2c59').save(original, 'JPEG')
        result = webp_derivative(SimpleUploadedFile('large.jpg', original.getvalue()))
        with Image.open(result) as image:
            self.assertEqual(image.size, (1920, 480))

    def test_animation_is_not_silently_flattened(self):
        original = BytesIO()
        frames = [Image.new('RGB', (8, 8), color) for color in ['red', 'blue']]
        frames[0].save(original, 'GIF', save_all=True, append_images=frames[1:], duration=100, loop=0)
        upload = SimpleUploadedFile('animation.gif', original.getvalue())
        self.assertIsNone(webp_derivative(upload))
        self.assertEqual(upload.read(), original.getvalue())


@override_settings(ALLOWED_HOSTS=['testserver'])
class MediaWebpDeliveryTests(TestCase):
    def test_dashboard_delivers_webp_and_retains_original(self):
        user = User.objects.create_superuser('image-admin', 'image@example.invalid', 'Not-a-real-account-2026!')
        self.client.force_login(user)
        content = BytesIO()
        Image.new('RGB', (48, 32), '#0c2c59').save(content, 'PNG')
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post('/api/dashboard/media/save/', {'file': SimpleUploadedFile('image.png', content.getvalue(), content_type='image/png')})
            self.assertEqual(response.status_code, 200)
            asset = MediaAsset.objects.get(pk=response.json()['media']['id'])
            self.assertTrue(asset.optimized_file.name.endswith('.webp'))
            self.assertTrue(response.json()['media']['url'].endswith('.webp'))
            with asset.file.open('rb') as original:
                self.assertEqual(original.read(), content.getvalue())
            with asset.optimized_file.open('rb') as optimized:
                self.assertEqual(Image.open(optimized).format, 'WEBP')
            delivery = self.client.get(asset.source_url())
            self.assertEqual(delivery.status_code, 200)
            self.assertEqual(delivery['Content-Type'], 'image/webp')
            self.assertEqual(delivery['X-Content-Type-Options'], 'nosniff')
            self.assertTrue(b''.join(delivery.streaming_content).startswith(b'RIFF'))
