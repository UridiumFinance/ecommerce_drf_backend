# Generated by Django 4.2.16 on 2025-06-10 04:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0001_initial'),
        ('authentication', '0002_remove_useraccount_qr_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='useraccount',
            name='qr_code',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_qr_codes', to='assets.media'),
        ),
    ]
