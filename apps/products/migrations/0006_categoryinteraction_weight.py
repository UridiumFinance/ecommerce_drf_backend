# Generated by Django 4.2.16 on 2025-06-29 03:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_alter_product_sub_category_alter_product_topic'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoryinteraction',
            name='weight',
            field=models.FloatField(default=1.0),
        ),
    ]
