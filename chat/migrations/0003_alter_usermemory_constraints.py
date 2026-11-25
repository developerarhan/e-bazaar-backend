from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_embeddingdocument'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='usermemory',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='usermemory',
            constraint=models.UniqueConstraint(
                condition=models.Q(('user__isnull', False)),
                fields=('user', 'key'),
                name='unique_user_memory_key',
            ),
        ),
        migrations.AddConstraint(
            model_name='usermemory',
            constraint=models.UniqueConstraint(
                condition=models.Q(('user__isnull', True)),
                fields=('session_key', 'key'),
                name='unique_session_memory_key',
            ),
        ),
    ]
