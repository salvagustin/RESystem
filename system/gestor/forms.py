from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
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
            'plantacion': forms.HiddenInput(),  # Oculta el campo de selección
            'estado': forms.HiddenInput(),  # Oculta el campo de selección
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('primera', css_class='col-md-4 mb-3'),
                Column('segunda', css_class='col-md-4 mb-3'),
                Column('tercera', css_class='col-md-4 mb-3'),
            ),
            Row(
                Column('estado', css_class='col-md-6 mb-3'),
            ),
            Row(
                Column(Submit('submit', 'Guardar', css_class='btn btn-primary'), css_class='d-flex justify-content-end')
            )
        )

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = '__all__'

class VentaForm(forms.ModelForm):
    class Meta:
        model = Venta
        fields = '__all__'
        widgets = {
            'cosecha': forms.HiddenInput(),  # Oculta el campo
            #'estado': forms.HiddenInput(),  # Oculta el campo
        }

