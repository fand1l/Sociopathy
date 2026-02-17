from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0003_alter_post_parent_post"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="reposted_post",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reposts",
                to="posts.post",
            ),
        ),
    ]
