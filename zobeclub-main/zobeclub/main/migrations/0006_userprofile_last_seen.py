from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_chat_message_chatmembership'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='last_seen',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Последнее посещение'),
        ),
    ]
