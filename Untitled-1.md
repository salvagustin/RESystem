# File Tree: RESystem

Generated on: 9/1/2025, 6:05:25 PM
Root path: `d:\PROJECTS\Python\RESystem`

```
├── 📁 .git/ 🚫 (auto-hidden)
├── 📁 gestor/
│   ├── 📁 __pycache__/ 🚫 (auto-hidden)
│   ├── 📁 migrations/
│   │   ├── 📁 __pycache__/ 🚫 (auto-hidden)
│   │   ├── 🐍 0001_initial.py
│   │   ├── 🐍 0002_remove_cliente_tipocompra_remove_compra_cosecha_and_more.py
│   │   ├── 🐍 0003_compra_estado_plantacion_estado_venta_estado_and_more.py
│   │   ├── 🐍 0004_venta_tipoentrega_alter_venta_estado.py
│   │   ├── 🐍 0005_rename_idfruto_plantacion_cultivo.py
│   │   ├── 🐍 0006_remove_venta_precio_venta_total.py
│   │   ├── 🐍 0007_alter_venta_tipoentrega.py
│   │   ├── 🐍 0008_alter_plantacion_estado.py
│   │   ├── 🐍 0009_remove_venta_cantidad_venta_primera_venta_rechazo_and_more.py
│   │   ├── 🐍 0010_cosecha_estado.py
│   │   ├── 🐍 0011_remove_cosecha_rechazo.py
│   │   ├── 🐍 0012_remove_venta_rechazo.py
│   │   ├── 🐍 0013_parcela_estado.py
│   │   ├── 🐍 0014_cosecha_tipocosecha_alter_parcela_estado.py
│   │   ├── 🐍 0015_remove_venta_tipoentrega.py
│   │   ├── 🐍 0016_alter_cosecha_tipocosecha_alter_parcela_estado_and_more.py
│   │   ├── 🐍 0017_rename_idfruto_cultivo_idcultivo.py
│   │   ├── 🐍 0018_alter_parcela_estado_alter_plantacion_estado.py
│   │   ├── 🐍 0019_remove_compra_cantidad_remove_compra_precio_and_more.py
│   │   ├── 🐍 0020_cliente_tipomercado.py
│   │   ├── 🐍 0021_remove_detalleventa_cosecha_and_more.py
│   │   ├── 🐍 0022_detalleventa_detallecompra.py
│   │   ├── 🐍 0023_remove_venta_total.py
│   │   ├── 🐍 0024_remove_detalleventa_primera_and_more.py
│   │   ├── 🐍 0025_remove_detalleventa_cantidad_and_more.py
│   │   ├── 🐍 0026_remove_detalleventa_primera_and_more.py
│   │   ├── 🐍 0027_remove_detalleventa_total_detalleventa_subtotal_and_more.py
│   │   ├── 🐍 0028_remove_cosecha_primera_remove_cosecha_segunda_and_more.py
│   │   ├── 🐍 0029_empleado_and_more.py
│   │   ├── 🐍 0030_remove_planilla_horastrabajas_remove_planilla_total_and_more.py
│   │   ├── 🐍 0031_alter_planilla_options_planilla_observaciones_and_more.py
│   │   ├── 🐍 0032_detallecompra_tipodetalle.py
│   │   ├── 🐍 0033_alter_compra_estado_alter_planilla_horasextra_and_more.py
│   │   ├── 🐍 0034_detalleventa_tipocosecha.py
│   │   ├── 🐍 0035_planilla_horastrabajadas.py
│   │   ├── 🐍 0036_alter_detallecosecha_tipocosecha_and_more.py
│   │   ├── 🐍 0037_alter_cultivo_options_alter_detallecultivo_options_and_more.py
│   │   ├── 🐍 0038_alter_detallecosecha_tipocosecha_and_more.py
│   │   └── 🐍 __init__.py
│   ├── 📁 signals/
│   │   └── 🐍 signals.py
│   ├── 📁 static/
│   │   ├── 📄 script.js
│   │   └── 🎨 style.css
│   ├── 📁 templates/
│   │   ├── 📁 Cliente/
│   │   │   ├── 🌐 form_cliente.html
│   │   │   └── 🌐 lista_clientes.html
│   │   ├── 📁 Compras/
│   │   │   ├── 🌐 form_compra.html
│   │   │   └── 🌐 lista_compras.html
│   │   ├── 📁 Cosecha/
│   │   │   ├── 🌐 form_cosecha.html
│   │   │   └── 🌐 lista_cosechas.html
│   │   ├── 📁 Cultivo/
│   │   │   ├── 🌐 form_cultivo.html
│   │   │   └── 🌐 lista_cultivo.html
│   │   ├── 📁 Empleado/
│   │   │   ├── 🌐 form_empleado.html
│   │   │   └── 🌐 lista_empleados.html
│   │   ├── 📁 MercadoFormal/
│   │   │   ├── 🌐 clientesformales.html
│   │   │   ├── 🌐 comprasformales.html
│   │   │   ├── 🌐 entregasformales.html
│   │   │   └── 🌐 ventasformales.html
│   │   ├── 📁 MercadoInformal/
│   │   │   ├── 🌐 clientesinformales.html
│   │   │   ├── 🌐 comprasinformales.html
│   │   │   ├── 🌐 entregasinformales.html
│   │   │   └── 🌐 ventasinformales.html
│   │   ├── 📁 Parcela/
│   │   │   ├── 🌐 form_parcela.html
│   │   │   └── 🌐 lista_parcela.html
│   │   ├── 📁 Planilla/
│   │   │   ├── 🌐 form_planilla.html
│   │   │   └── 🌐 lista_planilla.html
│   │   ├── 📁 Plantacion/
│   │   │   ├── 🌐 form_plantacion.html
│   │   │   └── 🌐 lista_plantaciones.html
│   │   ├── 📁 Venta/
│   │   │   ├── 🌐 form_venta.html
│   │   │   └── 🌐 lista_ventas.html
│   │   ├── 📁 registration/
│   │   │   └── 🌐 login.html
│   │   ├── 🌐 base.html
│   │   ├── 🌐 control_calidad.html
│   │   ├── 🌐 index.html
│   │   ├── 🌐 paginacion.html
│   │   ├── 🌐 reportes.html
│   │   └── 🌐 resumen.html
│   ├── 📁 templatetags/
│   │   ├── 📁 __pycache__/ 🚫 (auto-hidden)
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 custom_filters.py
│   ├── 🐍 __init__.py
│   ├── 🐍 admin.py
│   ├── 🐍 apps.py
│   ├── 🐍 forms.py
│   ├── 🐍 models.py
│   ├── 🐍 tests.py
│   ├── 🐍 urls.py
│   └── 🐍 views.py
├── 📁 system/
│   ├── 📁 __pycache__/ 🚫 (auto-hidden)
│   ├── 🐍 __init__.py
│   ├── 🐍 asgi.py
│   ├── 🐍 settings.py
│   ├── 🗄️ sql.sql
│   ├── 🐍 urls.py
│   └── 🐍 wsgi.py
├── 🐳 Dockerfile
├── 📄 db.sqlite3
├── 🐍 manage.py
└── 📄 requirements.txt
```

---
*Generated by FileTree Pro Extension*