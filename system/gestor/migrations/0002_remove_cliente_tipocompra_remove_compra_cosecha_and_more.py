# Generated by Django 4.2.20 on 2025-05-05 22:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestor', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cliente',
            name='tipocompra',
        ),
        migrations.RemoveField(
            model_name='compra',
            name='cosecha',
        ),
        migrations.AddField(
            model_name='compra',
            name='tipocompra',
            field=models.CharField(choices=[('C', 'Contado'), ('D', 'Credito')], default=1, max_length=1, verbose_name='Tipo compra'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='cosecha',
            name='rechazo',
            field=models.IntegerField(default=0, verbose_name='Rechazo'),
        ),
        migrations.AlterField(
            model_name='plantacion',
            name='fecha',
            field=models.DateField(auto_now=True, verbose_name='Fecha de plantacion'),
        ),
    ]
