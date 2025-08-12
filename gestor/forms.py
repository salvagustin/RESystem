from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from django.forms import inlineformset_factory
from django.forms import formset_factory
from .models import *

class ParcelaForm(forms.ModelForm):
    class Meta:
        model = Parcela
        fields = ['nombre', 'tipoparcela', 'estado']
        widgets = {
            'estado': forms.HiddenInput(),  # Oculta el campo de selección
        }

class CultivoForm(forms.ModelForm):
    class Meta:
        model = Cultivo
        fields = ['nombre', 'variedad']

class PlantacionForm(forms.ModelForm):
    class Meta:
        model = Plantacion
        fields = ['cultivo', 'cantidad']

class CosechaForm(forms.ModelForm):
    class Meta:
        model = Cosecha
        fields = '__all__'
        widgets = {
            'plantacion': forms.HiddenInput(),
            'estado': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('estado', css_class='col-md-6 mb-3'),
            ),
            Row(
                Column(Submit('submit', 'Guardar', css_class='btn btn-primary'), css_class='d-flex justify-content-end')
            )
        )

class DetalleCosechaForm(forms.ModelForm):
    class Meta:
        model = DetalleCosecha
        fields = '__all__'
        widgets = {
            'cosecha': forms.HiddenInput()
        }

DetalleCosechaFormSet = inlineformset_factory(
    Cosecha,
    DetalleCosecha,
    form=DetalleCosechaForm,
    extra=1,
    can_delete=True
)

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = '__all__'

class VentaForm(forms.ModelForm):
    class Meta:
        model = Venta
        exclude = ['cliente', 'estado', 'fecha', 'total']

class DetalleVentaForm(forms.ModelForm):
    class Meta:
        model = DetalleVenta
        fields = '__all__'
        widgets = {
            'venta': forms.HiddenInput(),
            'cosecha': forms.HiddenInput(),
        }

DetalleVentaFormSet = inlineformset_factory(
    Venta, DetalleVenta, form=DetalleVentaForm,
    extra=1, can_delete=True
)



class EmpleadoForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = ['nombre', 'telefono', 'estado', 'salario']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el nombre del empleado'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el número de teléfono'
            }),
            'estado': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'salario': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el salario',
                'step': '0.01',
                'min': '0'
            })
        }
        labels = {
            'nombre': 'Nombre',
            'telefono': 'Teléfono',
            'estado': 'Activo',
            'salario': 'Salario'
        }
    
    def clean_salario(self):
        salario = self.cleaned_data.get('salario')
        if salario and salario < 0:
            raise forms.ValidationError("El salario no puede ser negativo.")
        return salario
    
    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if telefono and len(telefono.strip()) < 8:
            raise forms.ValidationError("El número de teléfono debe tener al menos 8 caracteres.")
        return telefono




class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ['tipocompra']
        widgets = {
            'tipocompra': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
        }
        labels = {
            'tipocompra': 'Tipo de Compra',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Personalizar opciones del select
        self.fields['tipocompra'].choices = Compra.opciones if hasattr(Compra, 'opciones') else [("C", "Contado"), ("D", "Credito")]

class DetalleCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleCompra
        fields = ['producto', 'cantidad', 'preciounitario', 'tipodetalle']
        widgets = {
            'producto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del producto',
                'maxlength': 300
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'preciounitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'tipodetalle': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'producto': 'Producto',
            'cantidad': 'Cantidad',
            'preciounitario': 'Precio Unitario',
            'tipodetalle': 'Tipo de Detalle',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Personalizar opciones del select
        self.fields['tipodetalle'].choices = DetalleCompra.opciones if hasattr(DetalleCompra, 'opciones') else [("C", "Casa"), ("E", "Empresa")]

class FiltroCompraForm(forms.Form):
    FILTRO_CHOICES = [
        ('proveedor', 'Proveedor'),
        ('producto', 'Producto'),
        ('tipocompra', 'Tipo Compra'),
        ('estado', 'Estado'),
        ('tipodetalle', 'Tipo Detalle'),
    ]
    
    filtro = forms.ChoiceField(
        choices=FILTRO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='proveedor'
    )
    
    buscar = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar...'
        })
    )
    
    fecha_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    fecha_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
