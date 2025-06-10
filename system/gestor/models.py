from django.db import models
from django.db.models import Sum

# Create your models here.
class Parcela(models.Model):
    idparcela = models.AutoField(primary_key=True)
    nombre = models.CharField('Nombre', max_length=300)
    Opciones = (("A", "Campo abierto"), ("M", "Malla"))
    tipoparcela =  models.CharField('Tipo', max_length=1, choices=Opciones, blank=False, null=False)
    estado = models.BooleanField('Estado', default=False)
    def __str__(self):
        return f"{self.nombre}"

class Cultivo(models.Model):
    idcultivo = models.AutoField(primary_key=True)
    nombre = models.CharField('Nombre', max_length=300)
    variedad = models.CharField('Variedad', max_length=300)
    
    def __str__(self):
        return f"{self.nombre}, {self.variedad}"
    
class Plantacion(models.Model):
    idplantacion = models.AutoField(primary_key=True)
    parcela = models.ForeignKey(Parcela, on_delete=models.CASCADE, verbose_name="Parcela")
    cultivo = models.ForeignKey(Cultivo, on_delete=models.CASCADE, verbose_name="Cultivo")
    fecha = models.DateField('Fecha de plantacion', auto_now_add=True)
    cantidad = models.IntegerField('Cantidad de plantas', blank=False, null=False)
    estado = models.BooleanField('Estado', default=False)  # False=Activa por defecto

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            # Al crear una nueva plantación, marcar la parcela como ocupada
            self.parcela.estado = True
            self.parcela.save()

    def __str__(self):
        return f"{self.parcela}, {self.cultivo.nombre}, {self.fecha}"


class Cosecha(models.Model):
    idcosecha = models.AutoField(primary_key=True)
    plantacion = models.ForeignKey(Plantacion, on_delete=models.CASCADE, verbose_name="Plantación")
    fecha = models.DateField('Fecha de cosecha', auto_now_add=True)
    primera = models.IntegerField('Primera calidad', blank=False, null=False)
    segunda = models.IntegerField('Segunda calidad', blank=False, null=False)
    tercera = models.IntegerField('Tercera calidad', blank=False, null=False)
    estado = models.BooleanField('Finalizado', default=False)
    Opciones = (("S", "Saco"), ("U", "Unidad"), ("MS", "Medio saco"), ("C", "Caja"), ("MC", "Media caja"),("Lb", "Libras"))
    tipocosecha = models.CharField('Tipo de corte', max_length=2, choices=Opciones, blank=False, null=False)
    

    def __str__(self):
        return f"#{self.idcosecha}, {self.plantacion.parcela.nombre}, {self.fecha}"
    
class Cliente(models.Model):
    idcliente = models.AutoField(primary_key=True)
    nombre = models.CharField('Nombre', max_length=300)
    telefono = models.CharField('Teléfono', max_length=300)
    opcliente = (("C", "Comprador"), ("P", "Proveedor"))
    tipocliente =  models.CharField('Tipo cliente', max_length=1, choices=opcliente, blank=False, null=False)
    
    def __str__(self):
        return f"{self.nombre}"


class Venta(models.Model):
    idventa = models.AutoField(primary_key=True)
    cosecha = models.ForeignKey('Cosecha', on_delete=models.CASCADE, verbose_name="Cosecha")
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, verbose_name="Cliente")
    fecha = models.DateField('Fecha de venta', auto_now_add=True)
    opciones = (("C", "Contado"), ("D", "Credito"))
    tipoventa = models.CharField('Tipo venta', max_length=1, choices=opciones, blank=False, null=False)
    primera = models.IntegerField('Primera', blank=False, null=False, default=0)
    segunda = models.IntegerField('Segunda', blank=False, null=False, default=0)
    tercera = models.IntegerField('Tercera', blank=False, null=False, default=0)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, blank=False, null=False)
    estado = models.BooleanField('Pagado', default=False)

    def save(self, *args, **kwargs):
        if self._state.adding:  # Solo al crear la venta
            self.estado = True if self.tipoventa == 'C' else False
        super().save(*args, **kwargs)
        self.actualizar_estado_cosecha(self.cosecha)


    def delete(self, *args, **kwargs):
        cosecha = self.cosecha  # Guardamos la referencia antes de eliminar
        super().delete(*args, **kwargs)
        self.actualizar_estado_cosecha(cosecha)

    def actualizar_estado_cosecha(self, cosecha):
        ventas = Venta.objects.filter(cosecha=cosecha).aggregate(
            total_primera=Sum('primera'),
            total_segunda=Sum('segunda'),
            total_tercera=Sum('tercera')
        )

        vendida_primera = ventas['total_primera'] or 0
        vendida_segunda = ventas['total_segunda'] or 0
        vendida_tercera = ventas['total_tercera'] or 0

        if (vendida_primera >= cosecha.primera and
            vendida_segunda >= cosecha.segunda and
            vendida_tercera >= cosecha.tercera):
            if not cosecha.estado:
                cosecha.estado = True
                cosecha.save()
        else:
            if cosecha.estado:
                cosecha.estado = False
                cosecha.save()

    def __str__(self):
        return f"Venta #{self.idventa} - Cosecha #{self.cosecha.idcosecha}"

class Compra(models.Model):
    idcompra = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    producto = models.CharField('Producto', max_length=300)
    fecha = models.DateField('Fecha de compra', auto_now_add=True)
    opciones = (("C", "Contado"), ("D", "Credito"))
    tipocompra =  models.CharField('Tipo compra', max_length=1, choices=opciones, blank=False, null=False)
    cantidad = models.IntegerField('Cantidad comprada', blank=False, null=False)
    precio = models.DecimalField('Precio', max_digits=10, decimal_places=2, blank=False, null=False)
    estado = models.BooleanField('Estado', default=True)

    def __str__(self):
        return f"{self.idcompra} {self.fecha}"