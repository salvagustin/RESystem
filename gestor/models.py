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

    class Meta:
        verbose_name = "Cultivo"
        verbose_name_plural = "Cultivos"

class DetalleCultivo(models.Model):
    cultivo = models.ForeignKey(Cultivo, on_delete=models.CASCADE, verbose_name="Cultivo")
    OPCIONES = (
        ("S", "Saco"),
        ("C", "Caja"),
        ("Lb","Libra")
    )
    CATEGORIAS = (
        ('primera', 'Primera'),
        ('segunda', 'Segunda'),
        ('tercera', 'Tercera'),
    )
    categoria = models.CharField('Categoria', max_length=10, choices=CATEGORIAS, blank=False, null=False)
    tipocosecha = models.CharField('Tipo de corte', max_length=2, choices=OPCIONES, blank=False, null=False)
    cantidad = models.IntegerField('Unidades', blank=False, null=False)

    def __str__(self):
        return f"{self.cultivo.nombre} - {self.get_categoria_display()}: {self.cantidad} {self.get_tipocosecha_display()}"

    class Meta:
        verbose_name = "Detalle de Cultivo"
        verbose_name_plural = "Detalles de Cultivo"
        unique_together = ['cultivo', 'categoria', 'tipocosecha']

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
        return f" {self.cultivo.nombre}"

class Cliente(models.Model):
    idcliente = models.AutoField(primary_key=True)
    nombre = models.CharField('Nombre', max_length=300)
    telefono = models.CharField('Teléfono', max_length=300)
    opcliente = (("C", "Comprador"), ("P", "Proveedor"))
    tipocliente =  models.CharField('Tipo cliente', max_length=1, choices=opcliente, blank=False, null=False)
    opmercado = (("F", "Formal"), ("I", "Informal"))
    tipomercado = models.CharField('Tipo mercado', max_length=1, choices=opmercado, blank=False, null=True)
    
    def __str__(self):
        return f"{self.nombre}"

class Cosecha(models.Model):
    idcosecha = models.AutoField(primary_key=True)
    plantacion = models.ForeignKey(Plantacion, on_delete=models.CASCADE, verbose_name="Plantación")
    fecha = models.DateField('Fecha de cosecha', auto_now_add=True)
    estado = models.BooleanField('Finalizado', default=False)

    def __str__(self):
        return f"#{self.idcosecha}, {self.plantacion.parcela.nombre}, {self.fecha}"

class DetalleCosecha(models.Model):
    OPCIONES = (
        ("S", "Saco"),
        ("U", "Unidad"),
        ("C", "Caja"),
        ("Lb","Libra")
    )
    CATEGORIAS = (
        ('primera', 'Primera'),
        ('segunda', 'Segunda'),
        ('tercera', 'Tercera'),
    )
    cosecha = models.ForeignKey(Cosecha, on_delete=models.CASCADE)
    categoria = models.CharField('Categoria', max_length=10, choices=CATEGORIAS, blank=False, null=False)
    tipocosecha = models.CharField('Tipo de corte', max_length=2, choices=OPCIONES, blank=False, null=False)
    cantidad = models.IntegerField('Cantidad', blank=False, null=False)
    
    
    def __str__(self):
        return f"{self.categoria} - {self.cantidad} en Cosecha #{self.cosecha.idcosecha}"    

class Venta(models.Model):
    idventa = models.AutoField(primary_key=True)
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, verbose_name="Cliente")
    fecha = models.DateField('Fecha de venta', auto_now_add=True)
    opciones = (("C", "Contado"), ("D", "Credito"))
    tipoventa = models.CharField('Tipo venta', max_length=1, choices=opciones, blank=False, null=False)
    estado = models.BooleanField('Pagado', default=False)
    total = models.DecimalField('Total', default=0, max_digits=10, decimal_places=2)
    
    def save(self, *args, **kwargs):
        if self._state.adding:
            self.estado = True if self.tipoventa == 'C' else False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venta #{self.idventa}"

class DetalleVenta(models.Model):
    CATEGORIAS = (
        ('primera', 'Primera'),
        ('segunda', 'Segunda'),
        ('tercera', 'Tercera'),
    )
    
    venta = models.ForeignKey('Venta', on_delete=models.CASCADE)
    cosecha = models.ForeignKey('Cosecha', on_delete=models.CASCADE)
    categoria = models.CharField(max_length=10, choices=CATEGORIAS)
    tipocosecha = models.CharField('Tipo de cosecha', max_length=2, choices=DetalleCosecha.OPCIONES)
    cantidad = models.IntegerField(default=0)
    subtotal = models.DecimalField('Subtotal', default=0, max_digits=10, decimal_places=2)
    rechazo = models.DecimalField(max_digits=10, decimal_places=2, default=0) 

    def __str__(self):
        return f"{self.venta} - {self.cosecha} ({self.categoria} - {self.cantidad})"

class Compra(models.Model):
    idcompra = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Proveedor")
    fecha = models.DateField('Fecha de compra', auto_now_add=True)
    opciones = (("C", "Contado"), ("D", "Credito"))
    tipocompra = models.CharField('Tipo compra', max_length=1, choices=opciones, blank=False, null=False)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2)
    estado = models.BooleanField('Estado', default=False)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.estado = True if self.tipocompra == 'C' else False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Compra #{self.idcompra} - {self.fecha}"

class DetalleCompra(models.Model):
    compra = models.ForeignKey('Compra', on_delete=models.CASCADE)
    producto = models.CharField('Producto', max_length=300)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    preciounitario = models.DecimalField(max_digits=10, decimal_places=2)
    opciones = (("C", "Casa"), ("E", "Empresa"))
    tipodetalle = models.CharField('Tipo detalle', max_length=1, choices=opciones, blank=False, null=False)

    def subtotal(self):
        return self.cantidad * self.preciounitario

    def __str__(self):
        return f"{self.producto} x {self.cantidad} en Compra #{self.compra.idcompra}"

class Empleado(models.Model):
   idempleado = models.AutoField(primary_key=True)
   nombre = models.CharField('Nombre', max_length=300)
   telefono = models.CharField('Teléfono', max_length=300)
   estado = models.BooleanField('Estado', default=True)
   salario = models.DecimalField('Salario', max_digits=10, decimal_places=2)
   
   def __str__(self):
         return f"{self.nombre} - {self.telefono}"
    
class Planilla(models.Model):
    idplanilla = models.AutoField(primary_key=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, verbose_name="Empleado")
    fecha = models.DateField('Fecha de pago', auto_now_add=True)
    jornada = models.BooleanField('Jornada', default=False)
    horastrabajadas = models.DecimalField('Horas trabajadas', max_digits=5, decimal_places=2, default=0)
    horasextra = models.DecimalField('Horas extra', max_digits=5, decimal_places=2, default=0)
    pagoextra = models.DecimalField('Pago extra', max_digits=10, decimal_places=2, default=0)
    observaciones = models.TextField('Observaciones', blank=True, null=True)

    class Meta:
        # Evitar duplicados: un empleado no puede tener más de una planilla por día
        unique_together = ['empleado', 'fecha']
        ordering = ['-fecha', 'empleado__nombre']
    
    # ELIMINAR EL MÉTODO save() QUE SOBRESCRIBE pagoextra
    # def save(self, *args, **kwargs):
    #     # Este método causaba el problema - ELIMINADO
    #     super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.fecha} - {self.empleado.nombre}"
    
    @property
    def pago_jornada(self):
        """Retorna el pago de la jornada basado en si trabajó jornada completa o parcial"""
        if self.jornada:
            # Si marcó jornada completa, paga el salario completo
            return self.empleado.salario
        elif self.horastrabajadas > 0:
            # Si trabajó parcialmente, calcular proporcional
            salario_por_hora = self.empleado.salario / 8  # Asumiendo jornada de 8 horas
            return salario_por_hora * self.horastrabajadas
        else:
            return 0
    
    @property
    def pago_horas_extra(self):
        """Retorna el pago de las horas extra (horas * $2)"""
        return self.horasextra * 2 if self.horasextra else 0
    
    @property
    def total_dia(self):
        """Retorna el total del día: salario (si asistió) + (horas extra * 2) + pago extra"""
        return self.pago_jornada + self.pago_horas_extra + self.pagoextra 



