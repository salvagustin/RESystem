from django.urls import path
from django.contrib.auth import views as auth_views
from gestor.views import *
from . import views

urlpatterns = [
    path('', inicio, name='inicio'),
    path('logout/', auth_views.LogoutView.as_view(next_page='inicio'), name='logout'),


    path('parcelas/', views.lista_parcelas, name='lista_parcelas'),
    path('parcelas/crear/', views.crear_parcela, name='crear_parcela'),
    path('parcelas/editar/<int:pk>/', views.editar_parcela, name='editar_parcela'),
    path('parcelas/eliminar/<int:pk>/', views.eliminar_parcela, name='eliminar_parcela'),
    
    path('cultivos/', views.lista_cultivos, name='lista_cultivos'),
    path('cultivos/nuevo/', views.crear_cultivo, name='crear_cultivo'),
    path('cultivos/editar/<int:idcultivo>/', views.editar_cultivo, name='editar_cultivo'),
    path('cultivos/eliminar/<int:idcultivo>/', views.eliminar_cultivo, name='eliminar_cultivo'),

    path('plantaciones/', views.lista_plantaciones, name='lista_plantaciones'),
    path('plantaciones/crear/', views.crear_plantacion, name='crear_plantacion'),
    path('plantaciones/editar/<int:idplantacion>/', views.editar_plantacion, name='editar_plantacion'),
    path('plantaciones/eliminar/<int:idplantacion>/', views.eliminar_plantacion, name='eliminar_plantacion'),
    path('plantaciones/toggle_estado/<int:idplantacion>/', views.toggle_estado_plantacion, name='toggle_estado_plantacion'),


    path('cosechas/', views.lista_cosechas, name='lista_cosechas'),
    path('cosechas/crear/', views.crear_cosecha , name='crear_cosecha'),
    path('cosechas/editar/<int:idcosecha>/', views.editar_cosecha, name='editar_cosecha'),
    path('cosechas/eliminar/<int:idcosecha>/', views.eliminar_cosecha, name='eliminar_cosecha'),
    path('cosechas/cerrar/<int:id>/', views.cerrar_cosecha, name='cerrar_cosecha'),


    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/crear/', views.crear_cliente , name='crear_cliente'),
    path('clientes/editar/<int:idcliente>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/eliminar/<int:idcliente>/', views.eliminar_cliente, name='eliminar_cliente'),


    path('ventas/', views.lista_ventas, name='lista_ventas'),
    path('ventas/crear/', views.crear_venta, name='crear_venta'),
    path('ventas/editar/<int:idventa>/', views.editar_venta, name='editar_venta'),
    path('ventas/eliminar/<int:idventa>/', views.eliminar_venta, name='eliminar_venta'),
    path('ventas/toggle_estadoventa/<int:idventa>/', views.toggle_estado_venta, name='toggle_estado_venta'),
    path('ventas/detalles/<int:venta_id>/', views.obtener_detalles_venta, name='obtener_detalles_venta'),


    #path('dashboard/', views.dashboard_view, name='dashboard'),
    path('controlcalidad/', views.control_calidad, name='control_calidad'),
    path('reportes/', views.reportes_view, name='reportes'),

    path('ajax/categorias/', views.ajax_categorias, name='ajax_categorias'),
    path('ajax/tipocosechas/', views.ajax_tipocosechas, name='ajax_tipocosechas'),


#    # Mercado Formal
    path('clientesformales/', views.lista_clientesformales, name='lista_clientesformales'),
    path('ventasformales/', views.lista_ventasformales, name='lista_ventasformales'),
    path('entregasformales/', views.lista_entregasformales, name='lista_entregasformales'),

     # Mercado Informal
    path('clientesinformales/', views.lista_clientesinformales, name='lista_clientesinformales'),
    path('ventasinformales/', views.lista_ventasinformales, name='lista_ventasinformales'),
    path('entregasinformales/', views.lista_entregasinformales, name='lista_entregasinformales'),

     # Empleados
    path('empleados/', views.lista_empleados, name='lista_empleados'),
    path('empleados/crear/', views.crear_empleado, name='crear_empleado'),
    path('empleados/editar/<int:idempleado>/', views.editar_empleado, name='editar_empleado'),
    path('empleados/eliminar/<int:idempleado>/', views.eliminar_empleado, name='eliminar_empleado'),
    path('empleados/cambiar-estado/<int:idempleado>/', views.cambiar_estado_empleado, name='cambiar_estado_empleado'),

    path('planilla/', views.lista_planilla_semanal, name='lista_planilla'),
    path('agregarplanilla/', views.planilla_form_view, name='agregarplanilla'),
    path('planilla/fecha/<str:fecha_str>/', views.planilla_fecha_especifica, name='planilla_fecha'),
    path('planilla/hoy/', views.planilla_hoy, name='planilla_hoy'),
    
]
