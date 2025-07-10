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


class DetalleVentaSimpleForm(forms.Form):
    cultivo = forms.ModelChoiceField(
        queryset=Plantacion.objects.all(),
        label='Cultivo / Plantación',
    )
    categoria = forms.ChoiceField(choices=[
        ('primera', 'Primera'),
        ('segunda', 'Segunda'),
        ('tercera', 'Tercera'),
    ])
    cantidad = forms.IntegerField(min_value=1, label='Cantidad')
   #tipocosecha = forms.ChoiceField(choices=Cosecha.OPCIONES, label='Presentación')

DetalleVentaSimpleFormSet = formset_factory(
DetalleVentaSimpleForm, extra=1, can_delete=True)


class ProductoForm(forms.Form):
    cultivo = forms.ModelChoiceField(queryset=Plantacion.objects.all(), label='Cultivo')
    categoria = forms.ChoiceField(choices=[
        ('primera', 'Primera'),
        ('segunda', 'Segunda'),
        ('tercera', 'Tercera'),
    ])
    cantidad = forms.IntegerField(min_value=1)
    #tipocosecha = forms.ChoiceField(choices=Cosecha.OPCIONES, label='Presentación')

ProductoFormSet = formset_factory(ProductoForm, extra=1, can_delete=True)
