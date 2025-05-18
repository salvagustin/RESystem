from django.urls import path
from gestor.views import *
from . import views

urlpatterns = [
    path('', inicio, name='inicio'),
    path('parcelas/', views.lista_parcelas, name='lista_parcelas'),
    path('parcelas/crear/', views.crear_parcela, name='crear_parcela'),
    path('parcelas/editar/<int:pk>/', views.editar_parcela, name='editar_parcela'),
    path('parcelas/eliminar/<int:pk>/', views.eliminar_parcela, name='eliminar_parcela'),
    
    path('cultivos/', views.lista_cultivos, name='lista_cultivos'),
    path('cultivos/nuevo/', views.crear_cultivo, name='crear_cultivo'),
    path('cultivos/editar/<int:idfruto>/', views.editar_cultivo, name='editar_cultivo'),
    path('cultivos/eliminar/<int:idfruto>/', views.eliminar_cultivo, name='eliminar_cultivo'),

    path('plantaciones/', views.lista_plantaciones, name='lista_plantaciones'),
    path('plantaciones/crear/', views.crear_plantacion, name='crear_plantacion'),
    path('plantaciones/editar/<int:idplantacion>/', views.editar_plantacion, name='editar_plantacion'),
    path('plantaciones/eliminar/<int:idplantacion>/', views.eliminar_plantacion, name='eliminar_plantacion'),
    path('plantaciones/toggle_estado/<int:idplantacion>/', views.toggle_estado_plantacion, name='toggle_estado_plantacion'),


    path('cosechas/', views.lista_cosechas, name='lista_cosechas'),
    path('cosechas/crear/', views.crear_cosecha , name='crear_cosecha'),
    path('cosechas/editar/<int:idcosecha>/', views.editar_cosecha, name='editar_cosecha'),
    path('cosechas/eliminar/<int:idcosecha>/', views.eliminar_cosecha, name='eliminar_cosecha'),


    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/crear/', views.crear_cliente , name='crear_cliente'),
    path('clientes/editar/<int:idcliente>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/eliminar/<int:idcliente>/', views.eliminar_cliente, name='eliminar_cliente'),


    path('ventas/', views.lista_ventas, name='lista_ventas'),
    path('ventas/crear/', views.crear_venta, name='crear_venta'),
    path('ventas/editar/<int:idventa>/', views.editar_venta, name='editar_venta'),
    path('ventas/eliminar/<int:idventa>/', views.eliminar_venta, name='eliminar_venta'),
    path('ventas/toggle_estado/<int:idventa>/', views.toggle_estado_venta, name='toggle_estado_venta'),

]
