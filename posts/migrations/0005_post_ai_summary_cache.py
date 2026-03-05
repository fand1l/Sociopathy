from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0004_post_reposted_post'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='ai_summary',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='post',
            name='ai_summary_source_hash',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
