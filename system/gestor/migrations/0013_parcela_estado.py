# Generated by Django 4.2.20 on 2025-05-10 05:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestor', '0012_remove_venta_rechazo'),
    ]

    operations = [
        migrations.AddField(
            model_name='parcela',
            name='estado',
            field=models.BooleanField(default=True, verbose_name='Estado'),
        ),
    ]
