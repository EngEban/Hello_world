from django.core.validators import FileExtensionValidator
from django.db import migrations, models
import blog.models


class Migration(migrations.Migration):
    dependencies = [('blog', '0009_restore_explicit_article_credits')]
    operations = [migrations.AddField(
        model_name='mediaasset', name='optimized_file',
        field=models.ImageField(blank=True, null=True, upload_to=blog.models.uuid_upload_to,
                                validators=[FileExtensionValidator(allowed_extensions=['webp'])]),
    )]
