# Generated by Django 4.2.20 on 2025-06-10 22:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestor', '0017_rename_idfruto_cultivo_idcultivo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='parcela',
            name='estado',
            field=models.BooleanField(default=False, verbose_name='Estado'),
        ),
        migrations.AlterField(
            model_name='plantacion',
            name='estado',
            field=models.BooleanField(default=False, verbose_name='Estado'),
        ),
    ]
