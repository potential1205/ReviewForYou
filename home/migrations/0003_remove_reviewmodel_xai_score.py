# Generated by Django 3.2.8 on 2021-11-01 08:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0002_reviewmodel_xai_score'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reviewmodel',
            name='xai_score',
        ),
    ]