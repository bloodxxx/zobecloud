from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_userprofile_last_seen'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchQuery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(db_index=True, max_length=200, verbose_name='Поисковый запрос')),
                ('count', models.PositiveIntegerField(default=1, verbose_name='Количество поисков')),
                ('last_searched', models.DateTimeField(auto_now=True, verbose_name='Последний поиск')),
            ],
            options={
                'verbose_name': 'Поисковый запрос',
                'verbose_name_plural': 'Поисковые запросы',
                'ordering': ['-count'],
            },
        ),
    ]
