# Generated by Django 4.2.20 on 2025-05-08 02:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestor', '0006_remove_venta_precio_venta_total'),
    ]

    operations = [
        migrations.AlterField(
            model_name='venta',
            name='tipoentrega',
            field=models.CharField(choices=[('S', 'Saco'), ('U', 'Unidad'), ('MS', 'Medio saco'), ('C', 'Caja'), ('MC', 'Media caja')], max_length=2, verbose_name='Tipo de entrega'),
        ),
    ]
