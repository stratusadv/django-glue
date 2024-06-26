# Generated by Django 5.0.6 on 2024-05-24 19:57

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0002_bigtestmodel_foreign_key_alter_testmodel_birth_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='testmodel',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='testmodel',
            name='personality_type',
            field=models.CharField(choices=[('int', 'Introvert'), ('ext', 'Extrovert')], default='int', max_length=3),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='testmodel',
            name='favorite_number',
            field=models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(999)]),
        ),
    ]
