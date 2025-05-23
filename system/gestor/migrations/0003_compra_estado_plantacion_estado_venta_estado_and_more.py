# Generated by Django 4.2.20 on 2025-05-05 23:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestor', '0002_remove_cliente_tipocompra_remove_compra_cosecha_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='compra',
            name='estado',
            field=models.BooleanField(default=True, verbose_name='Estado'),
        ),
        migrations.AddField(
            model_name='plantacion',
            name='estado',
            field=models.CharField(choices=[('S', 'Sembrado'), ('F', 'Finalizado')], default='S', max_length=1, verbose_name='Estado'),
        ),
        migrations.AddField(
            model_name='venta',
            name='estado',
            field=models.BooleanField(default=True, verbose_name='Estado'),
        ),
        migrations.AddField(
            model_name='venta',
            name='tipoventa',
            field=models.CharField(choices=[('C', 'Contado'), ('D', 'Credito')], default=1, max_length=1, verbose_name='Tipo venta'),
            preserve_default=False,
        ),
    ]
