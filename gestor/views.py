from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.db.models import Sum, Count, DecimalField, Avg, F, ExpressionWrapper, DurationField, Case, When, IntegerField
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth import logout
from django.core.paginator import Paginator
from django.urls import reverse
from django.db.models.functions import ExtractMonth, Coalesce
from django.db.models.expressions import RawSQL
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.shortcuts import render
from django.db import transaction
from collections import defaultdict
import json
from django.core.serializers.json import DjangoJSONEncoder
from .models import *
from .forms import *
from datetime import datetime, timedelta, date
from django.utils.html import escape
from django.core.paginator import EmptyPage, PageNotAnInteger



horayfecha = datetime.now()
hoy = horayfecha.date()
grupos_permitidos = ['Administrador']

@login_required
def inicio(request):
    from django.db.models import Sum, F, DecimalField, ExpressionWrapper
    from datetime import date, timedelta
    import json
    
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
    dias_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

    # Obtener proveedores
    proveedores = Cliente.objects.filter(tipocliente='P').order_by('nombre')

    # Función auxiliar para calcular totales con multiplicadores (usar la que ya tienes)
    def calcular_totales_con_multiplicadores(cosecha):
        """
        Calcula los totales de una cosecha aplicando los multiplicadores
        del DetalleCultivo cuando el tipo no es 'U' (Unidad)
        """
        detalles_cosecha = DetalleCosecha.objects.filter(cosecha=cosecha)
        cultivo = cosecha.plantacion.cultivo
        detalles_cultivo = DetalleCultivo.objects.filter(cultivo=cultivo)
        
        # Crear diccionario de multiplicadores
        multiplicadores = {}
        for dc in detalles_cultivo:
            clave = f"{dc.categoria}_{dc.tipocosecha}"
            multiplicadores[clave] = dc.cantidad
        
        totales = {'primera': 0, 'segunda': 0, 'tercera': 0}
        
        for detalle in detalles_cosecha:
            cantidad_base = detalle.cantidad
            
            # Si no es unidad, aplicar multiplicador
            if detalle.tipocosecha != 'U':
                clave = f"{detalle.categoria}_{detalle.tipocosecha}"
                multiplicador = multiplicadores.get(clave, 1)
                cantidad_total = cantidad_base * multiplicador
            else:
                cantidad_total = cantidad_base
                
            totales[detalle.categoria] += cantidad_total
        
        return totales

    # Función para calcular totales de cosechas por día con equivalencias
    def calcular_cosechas_totales_por_dia(fecha_inicio, num_dias=7):
        """Calcula totales de cosechas por día aplicando equivalencias"""
        cosechas_por_dia = {}
        cosechas_por_cultivo_dia = {}
        
        for i in range(num_dias):
            dia = fecha_inicio + timedelta(days=i)
            cosechas_del_dia = Cosecha.objects.filter(fecha=dia)
            
            total_dia = {'primera': 0, 'segunda': 0, 'tercera': 0}
            cultivos_dia = {}
            
            for cosecha in cosechas_del_dia:
                totales_cosecha = calcular_totales_con_multiplicadores(cosecha)
                cultivo_nombre = cosecha.plantacion.cultivo.nombre
                
                # Agregar al total del día
                for categoria, cantidad in totales_cosecha.items():
                    total_dia[categoria] += cantidad
                
                # Agregar por cultivo
                if cultivo_nombre not in cultivos_dia:
                    cultivos_dia[cultivo_nombre] = {'primera': 0, 'segunda': 0, 'tercera': 0}
                
                for categoria, cantidad in totales_cosecha.items():
                    cultivos_dia[cultivo_nombre][categoria] += cantidad
            
            cosechas_por_dia[i] = total_dia
            cosechas_por_cultivo_dia[i] = cultivos_dia
        
        return cosechas_por_dia, cosechas_por_cultivo_dia

    # Totales generales
    total_cultivos = Cultivo.objects.count()
    total_plantaciones = Plantacion.objects.count()
    
    # Total de ventas del día
    total_ventas_hoy = DetalleVenta.objects.filter(
        venta__fecha=hoy
    ).aggregate(
        total=Sum(F('subtotal'))
    )['total'] or 0

    # Total de compras del día
    total_compras_hoy = DetalleCompra.objects.filter(
        compra__fecha=hoy
    ).aggregate(
        total=Sum(
            ExpressionWrapper(
                F('cantidad') * F('preciounitario'),
                output_field=DecimalField()
            )
        )
    )['total'] or 0

    # Plantaciones, cosechas y clientes disponibles
    plantaciones = Plantacion.objects.filter(estado=0)
    cosechas = Cosecha.objects.filter(estado=0)
    clientes = Cliente.objects.filter(tipocliente='C')
    
    # Calcular cosechas con equivalencias para la semana
    cosechas_semana, cosechas_por_cultivo_semana = calcular_cosechas_totales_por_dia(inicio_semana, 7)
    
    # Cosechas de HOY con equivalencias aplicadas
    cosechas_hoy_totales = cosechas_semana.get(hoy.weekday(), {'primera': 0, 'segunda': 0, 'tercera': 0})
    
    # Total único de cosechas de hoy (suma de todas las categorías)
    total_cosechas_hoy = sum(cosechas_hoy_totales.values())
    
    # Cosechas detalladas de hoy por cultivo (con equivalencias)
    cosechas_hoy_por_cultivo = cosechas_por_cultivo_semana.get(hoy.weekday(), {})
    
    # Obtener todos los cultivos que se cosecharon en la semana
    todos_cultivos_semana = set()
    for dia_cultivos in cosechas_por_cultivo_semana.values():
        todos_cultivos_semana.update(dia_cultivos.keys())
    
    # Cultivos cosechados hoy
    cultivos_hoy = set(cosechas_hoy_por_cultivo.keys())
    
    # Preparar datos para gráficos de la semana por cultivo
    datos_graficos_cultivo = {}
    for cultivo in todos_cultivos_semana:
        datos_graficos_cultivo[cultivo] = {
            'primera': [0] * 7,
            'segunda': [0] * 7,
            'tercera': [0] * 7
        }
        
        for dia in range(7):
            if dia in cosechas_por_cultivo_semana:
                if cultivo in cosechas_por_cultivo_semana[dia]:
                    cultivo_data = cosechas_por_cultivo_semana[dia][cultivo]
                    datos_graficos_cultivo[cultivo]['primera'][dia] = cultivo_data.get('primera', 0)
                    datos_graficos_cultivo[cultivo]['segunda'][dia] = cultivo_data.get('segunda', 0)
                    datos_graficos_cultivo[cultivo]['tercera'][dia] = cultivo_data.get('tercera', 0)

    # Ventas por día de la semana
    ventas_por_dia = []
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        total_dia = DetalleVenta.objects.filter(
            venta__fecha=dia
        ).aggregate(
            total=Sum(F('subtotal'))
        )['total'] or 0
        ventas_por_dia.append(float(total_dia))

    # Compras por día de la semana
    compras_por_dia = []
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        total_dia = DetalleCompra.objects.filter(
            compra__fecha=dia
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('cantidad') * F('preciounitario'),
                    output_field=DecimalField()
                )
            )
        )['total'] or 0
        compras_por_dia.append(float(total_dia))

    # Preparar datos JSON para JavaScript
    dias_semana_json = json.dumps(dias_semana)
    ventas_por_dia_json = json.dumps(ventas_por_dia)
    compras_por_dia_json = json.dumps(compras_por_dia)
    
    # Solo cultivos que se cosecharon esta semana para los gráficos
    cultivos_semana_lista = sorted(list(todos_cultivos_semana))
    cultivos_hoy_lista = sorted(list(cultivos_hoy))
    
    # Datos de gráficos solo para cultivos de esta semana
    calidad_por_cultivo_json = json.dumps(datos_graficos_cultivo)
    cultivos_semana_json = json.dumps(cultivos_semana_lista)
    cultivos_hoy_json = json.dumps(cultivos_hoy_lista)

    context = {
        # Totales generales
        'total_cultivos': total_cultivos,
        'total_plantaciones': total_plantaciones,
        'total_ventas': total_ventas_hoy,
        'total_compras': total_compras_hoy,
        
        # Cosechas de hoy
        'total_cosechas_hoy': total_cosechas_hoy,
        'cosechas_hoy': cosechas_hoy_totales,  # Por categoría
        'cosechas_hoy_por_cultivo': cosechas_hoy_por_cultivo,  # Por cultivo
        
        # Listas para modales
        'clientes': clientes,
        'cosechas': cosechas,
        'plantaciones': plantaciones,
        'proveedores': proveedores,
        
        # Datos para JavaScript (gráficos)
        'dias_semana': dias_semana_json,
        'ventas_por_dia': ventas_por_dia_json,
        'compras_por_dia': compras_por_dia_json,
        'calidad_por_cultivo': calidad_por_cultivo_json,
        'cultivos_semana': cultivos_semana_json,
        'cultivos_hoy': cultivos_hoy_json,
        
        # Para el template HTML
        'cultivos_semana_lista': cultivos_semana_lista,
        'cultivos_hoy_lista': cultivos_hoy_lista,
        
        # Datos adicionales
        'cosechas_semana_completa': cosechas_semana,
        'fecha_inicio_semana': inicio_semana,
        'fecha_hoy': hoy,
    }
    
    return render(request, 'index.html', context)


def custom_logout(request):
    """Vista personalizada para logout que siempre funciona"""
    logout(request)
    return redirect('inicio') 

@login_required
def control_calidad(request):
    from collections import defaultdict

    cosechas = Cosecha.objects.select_related('plantacion__cultivo', 'plantacion__parcela')

    agrupados = {
        'parcelas': defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0, 'perdida': 0}),
        'cultivos': defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0, 'perdida': 0}),
        'plantaciones': defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0, 'perdida': 0}),
        'cosechas': []
    }

    for c in cosechas:
        cosecha_data = calcular_totales_con_multiplicadores(c)
        venta = calcular_ventas_con_multiplicadores(c)

        p_perdida = max(cosecha_data['primera'] - venta['primera'], 0)
        s_perdida = max(cosecha_data['segunda'] - venta['segunda'], 0)
        t_perdida = max(cosecha_data['tercera'] - venta['tercera'], 0)
        perdida_total = p_perdida + s_perdida + t_perdida

        agrupados['cosechas'].append({
            'nombre': f"Cosecha #{c.idcosecha}",
            'primera': cosecha_data['primera'],
            'segunda': cosecha_data['segunda'],
            'tercera': cosecha_data['tercera'],
            'perdida': perdida_total
        })

        pid = c.plantacion.idplantacion
        cid = c.plantacion.cultivo.idcultivo
        parcela_id = c.plantacion.parcela.idparcela

        for cat in ['primera', 'segunda', 'tercera']:
            agrupados['plantaciones'][pid][cat] += cosecha_data[cat]
            agrupados['cultivos'][cid][cat] += cosecha_data[cat]
            agrupados['parcelas'][parcela_id][cat] += cosecha_data[cat]

        agrupados['plantaciones'][pid]['perdida'] += perdida_total
        agrupados['cultivos'][cid]['perdida'] += perdida_total
        agrupados['parcelas'][parcela_id]['perdida'] += perdida_total

    parcelas_data = [
        {'nombre': Parcela.objects.get(idparcela=pid).nombre, **val}
        for pid, val in agrupados['parcelas'].items()
    ]
    cultivos_data = [
        {'nombre': str(Cultivo.objects.get(idcultivo=cid)), **val}
        for cid, val in agrupados['cultivos'].items()
    ]
    plantaciones_data = [
        {'nombre': f"Plantación #{pid}", **val}
        for pid, val in agrupados['plantaciones'].items()
    ]
    cosechas_data = agrupados['cosechas']

    bloques = [
        {'titulo': '📍 Parcelas', 'items': parcelas_data},
        {'titulo': '🌱 Cultivos', 'items': cultivos_data},
        {'titulo': '🌿 Plantaciones', 'items': plantaciones_data},
        {'titulo': '🌾 Cosechas', 'items': cosechas_data},
    ]

    return render(request, 'control_calidad.html', {'bloques': bloques})
 

@login_required
def reportes_view(request):
    from django.db.models import Avg, ExpressionWrapper, F, DurationField
    from collections import defaultdict

    parcelas = Parcela.objects.all()
    cultivos = Cultivo.objects.all()
    tipos_cosecha = ['S', 'C', 'U', 'Lb']
    categorias = ['primera', 'segunda', 'tercera', 'perdida']

    datos_cosecha_cultivos = {}
    for cultivo in cultivos:
        datos_cosecha_cultivos[cultivo.nombre] = {t: {c: 0 for c in categorias} for t in tipos_cosecha}
        cosechas = Cosecha.objects.filter(plantacion__cultivo=cultivo)

        for c in cosechas:
            t = calcular_totales_con_multiplicadores(c)
            for cat in ['primera', 'segunda', 'tercera']:
                datos_cosecha_cultivos[cultivo.nombre]['U'][cat] += t[cat]

    estadisticas_cultivos = {}
    for cultivo in cultivos:
        cosechas = Cosecha.objects.filter(plantacion__cultivo=cultivo)
        totales = {'primera': 0, 'segunda': 0, 'tercera': 0}
        total_vendido = 0
        for c in cosechas:
            t = calcular_totales_con_multiplicadores(c)
            v = calcular_ventas_con_multiplicadores(c)
            for cat in ['primera', 'segunda', 'tercera']:
                totales[cat] += t[cat]
                total_vendido += v[cat]

        n = cosechas.count()
        total_cosechado = sum(totales.values())

        estadisticas_cultivos[cultivo.nombre] = {
            'variedad': cultivo.variedad,
            'promedio_primera': round(totales['primera'] / n, 2) if n else 0,
            'promedio_segunda': round(totales['segunda'] / n, 2) if n else 0,
            'promedio_tercera': round(totales['tercera'] / n, 2) if n else 0,
            'total_cosechado': total_cosechado,
            'total_vendido': total_vendido,
            'num_cosechas': n
        }

    produccion_por_tipo_parcela = {'Campo abierto': 0, 'Malla': 0}
    cosechas = Cosecha.objects.select_related('plantacion__parcela')
    for c in cosechas:
        tipo = dict(Parcela.Opciones).get(c.plantacion.parcela.tipoparcela)
        totales = calcular_totales_con_multiplicadores(c)
        produccion_por_tipo_parcela[tipo] += sum(totales.values())

    duraciones = Plantacion.objects.annotate(
        dias=ExpressionWrapper(F('cosecha__fecha') - F('fecha'), output_field=DurationField())
    ).values('cultivo__nombre').annotate(promedio=Avg('dias'))

    ciclo_promedio = {d['cultivo__nombre']: d['promedio'].days if d['promedio'] else 0 for d in duraciones}

    rendimiento_por_plantacion = {}
    for p in Plantacion.objects.select_related('cultivo', 'parcela'):
        total = 0
        for c in Cosecha.objects.filter(plantacion=p):
            total += sum(calcular_totales_con_multiplicadores(c).values())
        rendimiento = total / p.cantidad if p.cantidad else 0
        rendimiento_por_plantacion[p.idplantacion] = {
            'cultivo': p.cultivo.nombre,
            'parcela': p.parcela.nombre,
            'rendimiento': round(rendimiento, 2)
        }

    historial_por_parcela = defaultdict(list)
    for p in Plantacion.objects.select_related('cultivo', 'parcela'):
        historial_por_parcela[p.parcela.nombre].append({
            'cultivo': p.cultivo.nombre,
            'variedad': p.cultivo.variedad,
            'fecha': p.fecha,
            'estado': 'Activa' if not p.estado else 'Finalizada'
        })

    estado_parcelas = {p.nombre: 'Ocupada' if p.estado else 'Libre' for p in parcelas}

    datos_grafico_filtros = {}
    for cultivo in cultivos:
        datos_grafico_filtros[cultivo.nombre] = {'primera': {}, 'segunda': {}, 'tercera': {}}
        cosechas = Cosecha.objects.filter(plantacion__cultivo=cultivo)
        for c in cosechas:
            t = calcular_totales_con_multiplicadores(c)
            for cat in ['primera', 'segunda', 'tercera']:
                datos_grafico_filtros[cultivo.nombre][cat]['U'] = \
                    datos_grafico_filtros[cultivo.nombre][cat].get('U', 0) + t[cat]

    resumen_cosechas_fecha = defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0})
    for c in Cosecha.objects.all():
        t = calcular_totales_con_multiplicadores(c)
        for cat in ['primera', 'segunda', 'tercera']:
            resumen_cosechas_fecha[c.fecha][cat] += t[cat]

    context = {
        'datos_cosecha_cultivos': datos_cosecha_cultivos,
        'tipos_cosecha': tipos_cosecha,
        'categorias': categorias,
        'estadisticas_cultivos': estadisticas_cultivos,
        'produccion_por_tipo_parcela': produccion_por_tipo_parcela,
        'ciclo_promedio': ciclo_promedio,
        'rendimiento_por_plantacion': rendimiento_por_plantacion,
        'historial_por_parcela': dict(historial_por_parcela),
        'estado_parcelas': estado_parcelas,
        'resumen_cosechas_fecha': dict(resumen_cosechas_fecha),
        'datos_grafico_filtros': datos_grafico_filtros,
        'opciones_tipocosecha': DetalleCosecha.OPCIONES,
        'cultivos_nombres': [c.nombre for c in cultivos]
    }

    return render(request, 'reportes.html', context)


@login_required
def resumen_view(request):
    filtro = request.GET.get('filtro', 'parcela')
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    plantaciones = Plantacion.objects.select_related('parcela', 'cultivo').order_by('-fecha')

    # Filtros de búsqueda
    if buscar:
        if filtro == 'parcela':
            plantaciones = plantaciones.filter(parcela__nombre__icontains=buscar)
        elif filtro == 'cultivo':
            plantaciones = plantaciones.filter(cultivo__nombre__icontains=buscar)
        elif filtro == 'estado':
            if buscar in ['disponible', 'true', '1', 'd', 'f']:
                plantaciones = plantaciones.filter(estado=False)
            elif buscar in ['ocupada', 'false', '0', 'o']:
                plantaciones = plantaciones.filter(estado=True)

    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            plantaciones = plantaciones.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            plantaciones = plantaciones.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Construir la data para el template
    data = []
    for p in plantaciones:
        dias_siembra = (date.today() - p.fecha).days if p.fecha else 0
        cosechas = Cosecha.objects.filter(plantacion=p).order_by("fecha")

        # ✅ Días distintos en que hubo cosecha
        dias_corte = cosechas.values("fecha").distinct().count()

        # Ciclo promedio: desde siembra hasta primera cosecha
        ciclo_promedio = (cosechas.first().fecha - p.fecha).days if cosechas.exists() else 0
        total_cortes = cosechas.count()

        cantidad_producida = 0
        perdida = 0
        vendido = 0      # cantidad de producto
        dinero_vendido = 0  # 💵 total de dinero vendido

        for c in cosechas:
            t = calcular_totales_con_multiplicadores(c)
            v = calcular_ventas_con_multiplicadores(c)
            cantidad_producida += sum(t.values())
            perdido = t['tercera'] - v['tercera']
            perdida += perdido if perdido > 0 else 0
            vendido += sum(v.values())

            # 💵 sumar dinero vendido de esta cosecha
            dinero_vendido += DetalleVenta.objects.filter(cosecha=c).aggregate(
                total=models.Sum('subtotal')
            )['total'] or 0

        promedio = cantidad_producida / p.cantidad if p.cantidad else 0

        data.append({
            "parcela": p.parcela.nombre,
            "cultivo": p.cultivo.nombre,
            "variedad": p.cultivo.variedad,
            "estado": p.estado,
            "plantas": p.cantidad,
            "dias_siembra": dias_siembra,
            "dias_corte": dias_corte,
            "ciclo_promedio": ciclo_promedio,
            "total_cortes": total_cortes,
            "promedio": round(promedio, 2),
            "cantidad_producida": cantidad_producida,
            "perdida": perdida,
            "vendido": vendido,               # cantidad de producto
            "dinero_vendido": dinero_vendido  # 💵 total en dinero
        })

    return render(request, "resumen.html", {
        "data": data,
        "filtro": filtro,
        "buscar": buscar,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
    })



#######PARCELAS#########


# Mostrar lista de parcelas
@login_required
def lista_parcelas(request):
    filtro = request.GET.get('filtro', 'nombre')
    buscar = request.GET.get('buscar', '')

    parcelas = Parcela.objects.all().order_by('nombre')

    if buscar:
        buscar = buscar.strip().lower()
        if filtro == 'nombre':
            parcelas = parcelas.filter(nombre__icontains=buscar)
        elif filtro == 'tipo':
            if buscar in ['campo abierto', 'a', 'campo']:
                parcelas = parcelas.filter(tipoparcela='A')
            elif buscar in ['malla', 'm']:
                parcelas = parcelas.filter(tipoparcela='M')
        elif filtro == 'estado':
            if buscar in ['ocupada', '1', 'true', 'sí', 'si', 'o']:
                parcelas = parcelas.filter(estado=True)
            elif buscar in ['disponible', '0', 'false', 'no', 'd']:
                parcelas = parcelas.filter(estado=False)

    parcelas_data = []
    for parcela in parcelas:
        plantaciones = Plantacion.objects.filter(parcela=parcela)
        cultivos = list(set([f"{p.cultivo.nombre} ({p.cultivo.variedad})" for p in plantaciones]))
        total_plantas = plantaciones.aggregate(total=Sum('cantidad'))['total'] or 0

        cosechas = Cosecha.objects.filter(plantacion__in=plantaciones)
        total_cosechas = cosechas.count()

        # Cambiado: Total vendido calculado desde DetalleVenta
        total_vendido = DetalleVenta.objects.filter(cosecha__in=cosechas).aggregate(
            total=Sum('subtotal')
        )['total'] or 0
        parcelas_data.append({
            'parcela': parcela,
            'cultivos': cultivos,
            'total_plantas': total_plantas,
            'total_cosechas': total_cosechas,
            'total_vendido': total_vendido,
        })

    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(parcelas_data, 10)
        parcelas_paginadas = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'Parcela/lista_parcela.html', {
        'entity': parcelas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar
    })

@login_required
def crear_parcela(request):
    if not request.user.groups.filter(name__in=grupos_permitidos).exists():
        messages.error(request, "No tienes permiso.")
        return redirect('inicio')
    if request.method == 'POST':
        form = ParcelaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "La parcela ha sido creada exitosamente.")
            return redirect('/parcelas/')
    else:
        form = ParcelaForm()
    return render(request, 'Parcela/form_parcela.html', {'form': form})

@login_required
def editar_parcela(request, pk):
    if not request.user.has_perm('gestor.change_parcela'):
        messages.error(request, "No tienes permiso para editar parcelas.")
        return redirect('inicio') 
    parcela = get_object_or_404(Parcela, pk=pk)
    if request.method == 'POST':
        form = ParcelaForm(request.POST, instance=parcela)
        if form.is_valid():
            form.save()
            messages.success(request, f"La parcela '{parcela.nombre}' ha sido actualizada exitosamente.")
            return redirect('/parcelas')
    else:
        form = ParcelaForm(instance=parcela)
    return render(request, 'Parcela/form_parcela.html', {'form': form})

@login_required
def eliminar_parcela(request, pk):
    if not request.user.has_perm('gestor.delete_parcela'):
        messages.error(request, "No tienes permiso para eliminar parcelas.")
        return redirect('inicio') 
    parcela = get_object_or_404(Parcela, pk=pk)

    if request.method == 'POST':
        if Plantacion.objects.filter(parcela=parcela).exists():
            messages.error(request, f"No se puede eliminar la parcela '{parcela.nombre}' porque tiene plantaciones asociadas.")
        else:
            parcela.delete()
            messages.success(request, f"La parcela '{parcela.nombre}' ha sido eliminada exitosamente.")
        return redirect('/parcelas')

    return redirect('/parcelas')





#######CULTIVOS#########

# Mostrar lista de cultivos
@login_required
def lista_cultivos(request):
    filtro = request.GET.get('filtro', 'nombre')
    buscar = request.GET.get('buscar', '').strip().lower()

    cultivos = Cultivo.objects.all().order_by('nombre')

    if buscar:
        if filtro == 'nombre':
            cultivos = cultivos.filter(nombre__icontains=buscar)
        elif filtro == 'variedad':
            cultivos = cultivos.filter(variedad__icontains=buscar)

    # Preparar la lista enriquecida
    cultivos_info = []
    for cultivo in cultivos:
        plantaciones = cultivo.plantacion_set.all()
        cosechas = Cosecha.objects.filter(plantacion__cultivo=cultivo)

        total_plantas = plantaciones.aggregate(total=Coalesce(Sum('cantidad'), 0))['total']
        total_cosechas = cosechas.aggregate(total=Count('idcosecha'))['total']        
        total_vendido = DetalleVenta.objects.filter(cosecha__in=cosechas).aggregate(
            total=Sum('subtotal')
        )['total'] or 0

        # Obtener detalles de cultivo para mostrar información adicional
        detalles = cultivo.detallecultivo_set.all()
        
        cultivos_info.append({
            'cultivo': cultivo,
            'total_plantas': total_plantas,
            'total_cosechas': total_cosechas,
            'total_vendido': total_vendido,
            'detalles': detalles
        })
        
    # Paginación manual (ya no se pagina directamente `cultivos`, sino `cultivos_info`)
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(cultivos_info, 10)
        cultivos_paginados = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'Cultivo/lista_cultivo.html', {
        'entity': cultivos_paginados,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': request.GET.get('buscar', '')
    })

# Crear un nuevo cultivo
@login_required
def crear_cultivo(request):
    if request.method == 'POST':
        form = CultivoForm(request.POST)
        
        # Obtener los detalles desde el campo JSON
        detalles_json = request.POST.get('detalles_json', '[]')
        try:
            detalles = json.loads(detalles_json)
        except json.JSONDecodeError:
            detalles = []

        if form.is_valid():
            # Validar que haya al menos un detalle (opcional)
            # if not detalles:
            #     messages.error(request, "Debe agregar al menos un detalle de cultivo.")
            #     return render(request, 'Cultivo/form_cultivo.html', {
            #         'form': form,
            #         'categoria_choices': DetalleCultivo.CATEGORIAS,
            #         'tipocosecha_choices': DetalleCultivo.OPCIONES,
            #         'action': 'Crear'
            #     })

            # Guardar el cultivo
            cultivo = form.save()
            
            # Guardar cada detalle
            for detalle_data in detalles:
                DetalleCultivo.objects.create(
                    cultivo=cultivo,
                    categoria=detalle_data['categoria'],
                    tipocosecha=detalle_data['tipocosecha'],
                    cantidad=detalle_data['cantidad']
                )

            messages.success(request, f"El cultivo '{cultivo.nombre}' y sus detalles han sido creados exitosamente.")
            return redirect('lista_cultivos')
    else:
        form = CultivoForm()
    
    return render(request, 'Cultivo/form_cultivo.html', {
        'form': form,
        'categoria_choices': DetalleCultivo.CATEGORIAS,
        'tipocosecha_choices': DetalleCultivo.OPCIONES,
        'action': 'Crear'
    })

# Editar un cultivo existente
@login_required
def editar_cultivo(request, idcultivo):
    if not request.user.has_perm('gestor.change_cultivo'):
        messages.error(request, "No tienes permiso para editar cultivos.")
        return redirect('inicio') 
    
    cultivo = get_object_or_404(Cultivo, pk=idcultivo)
    detalles_existentes = DetalleCultivo.objects.filter(cultivo=cultivo)
    
    if request.method == 'POST':
        form = CultivoForm(request.POST, instance=cultivo)
        
        # Obtener los detalles desde el campo JSON
        detalles_json = request.POST.get('detalles_json', '[]')
        try:
            detalles = json.loads(detalles_json)
        except json.JSONDecodeError:
            detalles = []

        if form.is_valid():
            # Guardar el cultivo
            cultivo = form.save()
            
            # Eliminar detalles existentes y crear los nuevos
            DetalleCultivo.objects.filter(cultivo=cultivo).delete()
            
            # Crear los nuevos detalles
            for detalle_data in detalles:
                DetalleCultivo.objects.create(
                    cultivo=cultivo,
                    categoria=detalle_data['categoria'],
                    tipocosecha=detalle_data['tipocosecha'],
                    cantidad=detalle_data['cantidad']
                )

            messages.success(request, f"El cultivo '{cultivo.nombre}' y sus detalles han sido actualizados exitosamente.")
            return redirect('lista_cultivos')
    else:
        form = CultivoForm(instance=cultivo)

    # Convertir detalles existentes a JSON para JavaScript
    from django.core.serializers.json import DjangoJSONEncoder
    detalles_existentes_json = json.dumps(list(detalles_existentes.values(
        'categoria', 'tipocosecha', 'cantidad'
    )), cls=DjangoJSONEncoder)
    
    return render(request, 'Cultivo/form_cultivo.html', {
        'form': form,
        'categoria_choices': DetalleCultivo.CATEGORIAS,
        'tipocosecha_choices': DetalleCultivo.OPCIONES,
        'action': 'Editar',
        'cultivo': cultivo,
        'detalles_existentes': detalles_existentes_json,
    })

# Ver detalles de un cultivo
@login_required
def detalle_cultivo(request, idcultivo):
    cultivo = get_object_or_404(Cultivo, pk=idcultivo)
    detalles = cultivo.detalles.all()
    
    # Obtener estadísticas
    plantaciones = cultivo.plantacion_set.all()
    cosechas = Cosecha.objects.filter(plantacion__cultivo=cultivo)
    
    total_plantas = plantaciones.aggregate(total=Coalesce(Sum('cantidad'), 0))['total']
    total_cosechas = cosechas.aggregate(total=Count('idcosecha'))['total']        
    total_vendido = DetalleVenta.objects.filter(cosecha__in=cosechas).aggregate(
        total=Sum('subtotal')
    )['total'] or 0
    
    return render(request, 'Cultivo/detalle_cultivo.html', {
        'cultivo': cultivo,
        'detalles': detalles,
        'total_plantas': total_plantas,
        'total_cosechas': total_cosechas,
        'total_vendido': total_vendido
    })

# Eliminar un cultivo
@login_required
def eliminar_cultivo(request, idcultivo):
    if not request.user.has_perm('gestor.delete_cultivo'):
        messages.error(request, "No tienes permiso para eliminar cultivos.")
        return redirect('inicio')
    
    cultivo = get_object_or_404(Cultivo, pk=idcultivo)
    
    if request.method == 'POST':
        nombre = cultivo.nombre
        cultivo.delete()
        messages.success(request, f"El cultivo '{nombre}' ha sido eliminado exitosamente.")
        return redirect('/cultivos/')
    
    return render(request, 'Cultivo/confirmar_eliminar.html', {'cultivo': cultivo})

@login_required
def api_detalles_cultivo(request, cultivo_id):
    cultivo = get_object_or_404(Cultivo, pk=cultivo_id)
    detalles = cultivo.detallecultivo_set.all()

    data = {
        "detalles": [
            {
                "categoria": d.get_categoria_display(),
                "tipocosecha": d.get_tipocosecha_display(),
                "cantidad": d.cantidad,
            }
            for d in detalles
        ]
    }
    return JsonResponse(data)


############   PLANTACIONES  ####################

# Mostrar lista de plantaciones
@login_required
def lista_plantaciones(request):
    filtro = request.GET.get('filtro', 'parcela')
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    plantaciones = Plantacion.objects.select_related('parcela', 'cultivo').order_by('-fecha')
    parcelas = Parcela.objects.filter(estado=0).order_by('-idparcela')

    # Filtro por texto
    if buscar:
        if filtro == 'parcela':
            plantaciones = plantaciones.filter(parcela__nombre__icontains=buscar)
        elif filtro == 'cultivo':
            plantaciones = plantaciones.filter(cultivo__nombre__icontains=buscar)
        elif filtro == 'estado':
            if buscar in ['disponible', 'true', '1', 'D', 'd', 'f']:
                plantaciones = plantaciones.filter(estado=False)
            elif buscar in ['ocupada', 'O', 'false', '0', 'o']:
                plantaciones = plantaciones.filter(estado=True)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            plantaciones = plantaciones.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            plantaciones = plantaciones.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Cálculo de total vendido por plantación
    for plantacion in plantaciones:
        cosechas = plantacion.cosecha_set.all()
        plantacion.num_cosechas = cosechas.count()

        total_vendido = DetalleVenta.objects.filter(cosecha__in=cosechas).aggregate(
            total=Sum('subtotal')
        )['total'] or 0

        plantacion.total_vendido = total_vendido  # este atributo sí se manda al template

    # Paginación
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(plantaciones, 10)
        plantaciones_paginadas = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'Plantacion/lista_plantaciones.html', {
        'parcelas': parcelas,
        'entity': plantaciones_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    })

# Cambiar estado de plantación
@login_required
@require_POST
def toggle_estado_plantacion(request, idplantacion):
    if not request.user.has_perm('gestor.change_plantacion'):
        messages.error(request, "No tienes permiso para editar plantaciones.")
        return redirect('inicio') 
    try:
        plantacion = Plantacion.objects.select_related('parcela').get(pk=idplantacion)

        # Cambiar el estado de la plantación
        plantacion.estado = not plantacion.estado
        plantacion.save()
        messages.success(request, f"El estado de la plantación en parcela '{plantacion.parcela.nombre}' ha sido actualizado.")
        parcela = plantacion.parcela

        # Si no hay más plantaciones activas en la parcela, se marca como disponible
        hay_activas = Plantacion.objects.filter(parcela=parcela, estado=True).exists()
        parcela.estado = not hay_activas  # True si está libre, False si ocupada
        parcela.save()

        return JsonResponse({'estado': plantacion.estado})

    except Plantacion.DoesNotExist:
        return JsonResponse({'error': 'Plantación no encontrada'}, status=404)

# Crear una nueva plantación
@login_required
def crear_plantacion(request):
    parcela_id = request.POST.get('parcela_id') or request.GET.get('parcela_id')
    parcela = get_object_or_404(Parcela, idparcela=parcela_id) if parcela_id else None

    if request.method == 'POST':
        form = PlantacionForm(request.POST)
        if form.is_valid():
            plantacion = form.save(commit=False)
            plantacion.parcela = parcela  # ⬅️ Asignación forzada
            plantacion.save()
            messages.success(request, f"La plantación en parcela '{parcela.nombre}' ha sido creada exitosamente.")
            return redirect('lista_plantaciones')
    else:
        form = PlantacionForm()

    return render(request, 'Plantacion/form_plantacion.html', {
        'form': form,
        'parcela': parcela
    })

# Editar una plantación existente
@login_required
def editar_plantacion(request, idplantacion):
    if not request.user.has_perm('gestor.change_plantacion'):
        messages.error(request, "No tienes permiso para editar plantaciones.")
        return redirect('inicio') 
    plantacion = get_object_or_404(Plantacion, pk=idplantacion)
    parcela = Parcela.objects.get(idparcela=plantacion.parcela.idparcela)
    if request.method == 'POST':
        form = PlantacionForm(request.POST, instance=plantacion)
        if form.is_valid():
            form.save()
            messages.success(request, f"La plantación en parcela '{plantacion.parcela.nombre}' ha sido actualizada exitosamente.")
            return redirect('/plantaciones/')
    else:
        form = PlantacionForm(instance=plantacion)
    return render(request, 'Plantacion/form_plantacion.html', {'form': form, 'parcela': parcela})

# Eliminar una plantación
@login_required
def eliminar_plantacion(request, idplantacion):
    if not request.user.has_perm('gestor.change_plantacion'):
        messages.error(request, "No tienes permiso para eliminar plantaciones.")
        return redirect('inicio') 
    plantacion = get_object_or_404(Plantacion, pk=idplantacion)
    if request.method == 'POST':
        if Cosecha.objects.filter(plantacion=plantacion).exists():
            messages.error(request, f"No se puede eliminar la plantación en parcela '{plantacion.parcela}' porque tiene cortes asociadas.")
        else:
            plantacion.delete()
            messages.success(request, f"La plantación en parcela '{plantacion.parcela}' fue eliminada exitosamente.")
    return redirect('/plantaciones')



############   COSECHAS  ####################



# Mostrar lista de cocechas
@login_required
def lista_cosechas(request):
    filtro = request.GET.get('filtro', 'parcela')
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    cosechas = Cosecha.objects.select_related('plantacion__parcela', 'plantacion__cultivo').order_by('-idcosecha')

    # Filtros existentes...
    if buscar:
        if filtro == 'parcela':
            cosechas = cosechas.filter(plantacion__parcela__nombre__icontains=buscar)
        elif filtro == 'cultivo':
            cosechas = cosechas.filter(plantacion__cultivo__nombre__icontains=buscar)
        # ... otros filtros

    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            cosechas = cosechas.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            cosechas = cosechas.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # ===== CÁLCULO MEJORADO CON MULTIPLICADORES =====
    cosechas_con_totales = []
    
    for cosecha in cosechas:
        # Calcular totales con multiplicadores
        totales = calcular_totales_con_multiplicadores(cosecha)
        cosecha.primera = totales['primera']
        cosecha.segunda = totales['segunda'] 
        cosecha.tercera = totales['tercera']
        cosechas_con_totales.append(cosecha)
    
    # Resto del código para ventas y detalles...
    ventas = DetalleVenta.objects.select_related('cosecha')
    ventas_por_cosecha = {}

    for venta in ventas:
        cid = venta.cosecha_id
        if cid not in ventas_por_cosecha:
            ventas_por_cosecha[cid] = {
                'primera': 0, 'segunda': 0, 'tercera': 0,
                'total': 0, 'cantidad': 0,
            }

        ventas_por_cosecha[cid][venta.categoria] += venta.cantidad or 0
        ventas_por_cosecha[cid]['total'] += float(venta.subtotal or 0)
        ventas_por_cosecha[cid]['cantidad'] += venta.cantidad or 0

    ventas_dict = {}
    for cosecha in cosechas_con_totales:
        v = ventas_por_cosecha.get(cosecha.idcosecha, {
            'primera': 0, 'segunda': 0, 'tercera': 0,
            'total': 0, 'cantidad': 0,
        })
        ventas_convertidas = calcular_ventas_con_multiplicadores(cosecha)

        disponible_primera = max((cosecha.primera or 0) - ventas_convertidas['primera'], 0)
        disponible_segunda = max((cosecha.segunda or 0) - ventas_convertidas['segunda'], 0)
        disponible_tercera = max((cosecha.tercera or 0) - ventas_convertidas['tercera'], 0)

        ventas_primera = ventas_convertidas['primera']
        ventas_segunda = ventas_convertidas['segunda']
        ventas_tercera = ventas_convertidas['tercera']

        total_cultivos_vendidos = ventas_primera + ventas_segunda + ventas_tercera

        total_cosecha = (cosecha.primera or 0) + (cosecha.segunda or 0) + (cosecha.tercera or 0)
        perdida = disponible_primera + disponible_segunda + disponible_tercera
        
        ventas_dict[cosecha.idcosecha] = {
            'disponible_primera': disponible_primera,
            'disponible_segunda': disponible_segunda,
            'disponible_tercera': disponible_tercera,
            'total_cosecha': total_cosecha,
            'total_vendido': v['total'],
            'cantidad_ventas': total_cultivos_vendidos,
            'perdida': perdida,
        }

    # Agrupar detalles por cosecha
    categoria_display = dict(DetalleCosecha.CATEGORIAS)
    tipo_display = dict(DetalleCosecha.OPCIONES)

    detalle_cosechas = DetalleCosecha.objects.select_related('cosecha').values(
        'cosecha_id', 'categoria', 'tipocosecha'
    ).annotate(total=Sum('cantidad'))

    ventas_detalle = DetalleVenta.objects.values('cosecha_id', 'categoria').annotate(
        cantidad_vendida=Sum('cantidad')
    )
    ventas_detalle_map = {
        (v['cosecha_id'], v['categoria']): v['cantidad_vendida'] or 0 for v in ventas_detalle
    }

    detalle_por_cosecha = defaultdict(list)
    total_por_cosecha = {}  # NUEVO

    for d in detalle_cosechas:
        cosecha_id = d['cosecha_id']
        cosecha_obj = Cosecha.objects.get(idcosecha=cosecha_id)
        cultivo = cosecha_obj.plantacion.cultivo

        multiplicador = 1
        if d['tipocosecha'] != 'U':
            try:
                detalle_cultivo = DetalleCultivo.objects.get(
                    cultivo=cultivo,
                    categoria=d['categoria'],
                    tipocosecha=d['tipocosecha']
                )
                multiplicador = detalle_cultivo.cantidad
            except DetalleCultivo.DoesNotExist:
                multiplicador = 1

        cantidad_base = d['total'] or 0
        cantidad_total = cantidad_base * multiplicador
        cantidad_vendida = ventas_detalle_map.get((cosecha_id, d['categoria']), 0)
        disponibilidad = max(cantidad_base - cantidad_vendida, 0)

        detalle_por_cosecha[cosecha_id].append({
            'categoria': d['categoria'],
            'categoria_display': categoria_display.get(d['categoria'], d['categoria']),
            'tipocosecha': d['tipocosecha'],
            'tipocosecha_display': tipo_display.get(d['tipocosecha'], d['tipocosecha']),
            'cantidad_original': cantidad_base,
            'multiplicador': multiplicador,
            'cantidad_total': cantidad_total,
            'cantidad_vendida': cantidad_vendida,
            'disponible': disponibilidad,
            

        })

        # Acumular total por cosecha
        if cosecha_id not in total_por_cosecha:
            total_por_cosecha[cosecha_id] = 0
        total_por_cosecha[cosecha_id] += cantidad_total

    # Paginación
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(cosechas_con_totales, 10)
        cosechas_paginadas = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    plantaciones = Plantacion.objects.filter(estado=0).order_by('-fecha')

    return render(request, 'Cosecha/lista_cosechas.html', {
        'entity': cosechas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'plantaciones': plantaciones,
        'ventas_dict': ventas_dict,
        'detalle_por_cosecha': dict(detalle_por_cosecha),
        'total_por_cosecha': total_por_cosecha, 
         
    })

# Crear una nueva cosecha
@login_required
def crear_cosecha(request):
    plantacion_id = request.GET.get('plantacion_id')
    plantacion = get_object_or_404(Plantacion, idplantacion=plantacion_id) if plantacion_id else None

    if request.method == 'POST':
        form = CosechaForm(request.POST)
        cortes_json = request.POST.get('cortes_json', '[]')
        
        try:
            cortes = json.loads(cortes_json)
        except json.JSONDecodeError:
            cortes = []

        if form.is_valid():
            cosecha = form.save()
            
            # Guardar cada detalle
            for corte in cortes:
                DetalleCosecha.objects.create(
                    cosecha=cosecha,
                    categoria=corte['categoria'],
                    tipocosecha=corte['tipocosecha'],
                    cantidad=corte['cantidad']
                )

            messages.success(request, f"La cosecha #{cosecha.idcosecha} ha sido creada exitosamente.")

            if request.POST.get('ir_a_venta') == '1':
                return redirect(f"{reverse('crear_venta')}?cosecha_id={cosecha.idcosecha}")

            return redirect('lista_cosechas')
    else:
        form = CosechaForm(initial={'plantacion': plantacion, 'estado': False})

    # Obtener tipos disponibles para el cultivo si hay plantación
    tipos_disponibles = []
    multiplicadores = {}
    tipos_ya_agregados = set()
    
    if plantacion:
        detalles_cultivo = DetalleCultivo.objects.filter(cultivo=plantacion.cultivo)
        
        # Primero los tipos específicos del cultivo
        for detalle in detalles_cultivo:
            tipo_key = f"{detalle.categoria}_{detalle.tipocosecha}"
            
            if tipo_key not in tipos_ya_agregados:
                tipos_disponibles.append({
                    'value': detalle.tipocosecha,
                    'label': detalle.get_tipocosecha_display(),
                    'categoria': detalle.categoria
                })
                tipos_ya_agregados.add(tipo_key)
            
            clave = f"{detalle.categoria}_{detalle.tipocosecha}"
            multiplicadores[clave] = detalle.cantidad

        # SIEMPRE agregar "Unidad" para todas las categorías
        categorias = ['primera', 'segunda', 'tercera']
        for categoria in categorias:
            unidad_key = f"{categoria}_U"
            if unidad_key not in tipos_ya_agregados:
                tipos_disponibles.append({
                    'value': 'U',
                    'label': 'Unidad',
                    'categoria': categoria
                })
            
            # Multiplicador para unidades siempre es 1
            multiplicadores[f"{categoria}_U"] = 1

    return render(request, 'Cosecha/form_cosecha.html', {
        'form': form,
        'plantacion': plantacion,
        'categoria_choices': DetalleCosecha.CATEGORIAS,
        'tipocosecha_choices': DetalleCosecha.OPCIONES,
        'tipos_disponibles': json.dumps(tipos_disponibles),
        'multiplicadores': json.dumps(multiplicadores),
    })

# Editar una cosecha existente
@login_required
def editar_cosecha(request, idcosecha):
    if not request.user.has_perm('gestor.change_cosecha'):
        messages.error(request, "No tienes permiso para editar cosechas.")
        return redirect('inicio') 

    cosecha = get_object_or_404(Cosecha, pk=idcosecha)
    detalles_existentes = DetalleCosecha.objects.filter(cosecha=cosecha)

    # Obtenemos la plantación asociada para mostrar en el template
    plantacion = cosecha.plantacion

    # Cantidades vendidas actuales desde DetalleVenta (en UNIDADES)
    detalle_ventas = DetalleVenta.objects.filter(cosecha=cosecha)
    vendida_primera = detalle_ventas.filter(categoria='primera').aggregate(total=Sum('cantidad'))['total'] or 0
    vendida_segunda = detalle_ventas.filter(categoria='segunda').aggregate(total=Sum('cantidad'))['total'] or 0
    vendida_tercera = detalle_ventas.filter(categoria='tercera').aggregate(total=Sum('cantidad'))['total'] or 0

    if request.method == 'POST':
        form = CosechaForm(request.POST, instance=cosecha)
        cortes_json = request.POST.get('cortes_json', '[]')
        try:
            cortes = json.loads(cortes_json)
        except json.JSONDecodeError:
            cortes = []

        if form.is_valid():
            cosecha = form.save(commit=False)
            cosecha.save()
            messages.success(request, f"La cosecha #{cosecha.idcosecha} ha sido actualizada exitosamente.")

            # Borrar los detalles viejos y crear los nuevos
            DetalleCosecha.objects.filter(cosecha=cosecha).delete()
            for corte in cortes:
                DetalleCosecha.objects.create(
                    cosecha=cosecha,
                    categoria=corte['categoria'],
                    tipocosecha=corte['tipocosecha'],
                    cantidad=corte['cantidad']  # Esta es la cantidad BASE (ej: 1 caja, no 100 unidades)
                )

            return redirect('lista_cosechas')
    else:
        form = CosechaForm(instance=cosecha)

    # Obtener tipos disponibles para el cultivo y multiplicadores
    detalles_cultivo = DetalleCultivo.objects.filter(cultivo=plantacion.cultivo)
    
    tipos_disponibles = []
    multiplicadores = {}
    tipos_ya_agregados = set()
    
    # Primero los tipos específicos del cultivo
    for detalle in detalles_cultivo:
        tipo_key = f"{detalle.categoria}_{detalle.tipocosecha}"
        
        if tipo_key not in tipos_ya_agregados:
            tipos_disponibles.append({
                'value': detalle.tipocosecha,
                'label': detalle.get_tipocosecha_display(),
                'categoria': detalle.categoria,
                'cantidad': detalle.cantidad
            })
            tipos_ya_agregados.add(tipo_key)
        
        clave = f"{detalle.categoria}_{detalle.tipocosecha}"
        multiplicadores[clave] = detalle.cantidad

    # SIEMPRE agregar "Unidad" para todas las categorías
    categorias = ['primera', 'segunda', 'tercera']
    for categoria in categorias:
        unidad_key = f"{categoria}_U"
        if unidad_key not in tipos_ya_agregados:
            tipos_disponibles.append({
                'value': 'U',
                'label': 'Unidad',
                'categoria': categoria,
                'cantidad': 1
            })
        
        # Multiplicador para unidades siempre es 1
        multiplicadores[f"{categoria}_U"] = 1

    # Convertimos los detalles existentes a JSON para JS
    # IMPORTANTE: Guardamos la cantidad BASE, no la multiplicada
    from django.core.serializers.json import DjangoJSONEncoder
    detalles_json = json.dumps(list(detalles_existentes.values(
        'categoria', 'tipocosecha', 'cantidad'
    )), cls=DjangoJSONEncoder)

    return render(request, 'Cosecha/form_cosecha.html', {
        'form': form,
        'plantacion': plantacion, 
        'vendida_primera': vendida_primera,
        'vendida_segunda': vendida_segunda,
        'vendida_tercera': vendida_tercera,
        'detalles_existentes': detalles_existentes,
        'detalles_json': detalles_json,  # Para inicializar la tabla en JS
        'categoria_choices': DetalleCosecha.CATEGORIAS,
        'tipocosecha_choices': DetalleCosecha.OPCIONES,
        'tipos_disponibles': json.dumps(tipos_disponibles),
        'multiplicadores': json.dumps(multiplicadores),
    })

# Eliminar una cosecha
@login_required
def eliminar_cosecha(request, idcosecha):
    if not request.user.has_perm('gestor.delete_cosecha'):
        messages.error(request, "No tienes permiso para eliminar cosechas.")
        return redirect('inicio')
    cosecha = get_object_or_404(Cosecha, pk=idcosecha)
    if request.method == 'POST':
        if DetalleVenta.objects.filter(cosecha=cosecha).exists():
            messages.error(request, f"No se puede eliminar el corte #{idcosecha} porque tiene ventas asociadas.")
        else:
            cosecha.delete()
            messages.success(request, f"La cosecha #{idcosecha} ha sido eliminada exitosamente.")
    return redirect('/cosechas')

# Cerrar Cosecha
@login_required
@csrf_exempt
def cerrar_cosecha(request, id):
    if not request.user.has_perm('gestor.change_cosecha'):
        messages.error(request, "No tienes permiso para editar cosechas.")
        return redirect('inicio')
    if request.method == 'POST':
        try:
            cosecha = Cosecha.objects.get(idcosecha=id)
            cosecha.estado = 1  # Finalizado
            cosecha.save()
            return JsonResponse({'success': True})
        except Cosecha.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Cosecha no encontrada'}, status=404)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@login_required
def obtener_tipos_cosecha(request):
    """
    Vista AJAX que devuelve los tipos de cosecha disponibles 
    para un cultivo específico + SIEMPRE incluye "Unidad"
    """
    plantacion_id = request.GET.get('plantacion_id')
    
    if not plantacion_id:
        return JsonResponse({'tipos': [], 'multiplicadores': {}})
    
    try:
        plantacion = Plantacion.objects.get(idplantacion=plantacion_id)
        cultivo = plantacion.cultivo
        
        # Obtener detalles del cultivo con sus multiplicadores
        detalles_cultivo = DetalleCultivo.objects.filter(cultivo=cultivo)
        
        tipos_disponibles = []
        multiplicadores = {}
        tipos_ya_agregados = set()
        
        # Primero agregar los tipos específicos del cultivo
        for detalle in detalles_cultivo:
            tipo_key = f"{detalle.categoria}_{detalle.tipocosecha}"
            
            if tipo_key not in tipos_ya_agregados:
                tipos_disponibles.append({
                    'value': detalle.tipocosecha,
                    'label': detalle.get_tipocosecha_display(),
                    'categoria': detalle.categoria,
                    'cantidad': detalle.cantidad
                })
                tipos_ya_agregados.add(tipo_key)
            
            # Clave única para categoria + tipocosecha
            clave = f"{detalle.categoria}_{detalle.tipocosecha}"
            multiplicadores[clave] = detalle.cantidad
        
        # SIEMPRE agregar "Unidad" para todas las categorías
        categorias = ['primera', 'segunda', 'tercera']
        for categoria in categorias:
            unidad_key = f"{categoria}_U"
            if unidad_key not in tipos_ya_agregados:
                tipos_disponibles.append({
                    'value': 'U',
                    'label': 'Unidad',
                    'categoria': categoria,
                    'cantidad': 1  # Las unidades no se multiplican
                })
            
            # Multiplicador para unidades siempre es 1
            multiplicadores[f"{categoria}_U"] = 1
        
        return JsonResponse({
            'tipos': tipos_disponibles,
            'multiplicadores': multiplicadores
        })
        
    except Plantacion.DoesNotExist:
        return JsonResponse({'tipos': [], 'multiplicadores': {}})

# Función auxiliar para calcular totales con multiplicadores
def calcular_totales_con_multiplicadores(cosecha):
    """
    Calcula los totales de una cosecha aplicando los multiplicadores
    del DetalleCultivo cuando el tipo no es 'U' (Unidad)
    """
    detalles_cosecha = DetalleCosecha.objects.filter(cosecha=cosecha)
    cultivo = cosecha.plantacion.cultivo
    detalles_cultivo = DetalleCultivo.objects.filter(cultivo=cultivo)
    
    # Crear diccionario de multiplicadores
    multiplicadores = {}
    for dc in detalles_cultivo:
        clave = f"{dc.categoria}_{dc.tipocosecha}"
        multiplicadores[clave] = dc.cantidad
    
    totales = {'primera': 0, 'segunda': 0, 'tercera': 0}
    
    for detalle in detalles_cosecha:
        cantidad_base = detalle.cantidad
        
        # Si no es unidad, aplicar multiplicador
        if detalle.tipocosecha != 'U':
            clave = f"{detalle.categoria}_{detalle.tipocosecha}"
            multiplicador = multiplicadores.get(clave, 1)
            cantidad_total = cantidad_base * multiplicador
        else:
            cantidad_total = cantidad_base
            
        totales[detalle.categoria] += cantidad_total
    
    return totales

def calcular_ventas_con_multiplicadores(cosecha):
    ventas = DetalleVenta.objects.filter(cosecha=cosecha)
    ventas_convertidas = {'primera': 0, 'segunda': 0, 'tercera': 0}

    for venta in ventas:
        cultivo = cosecha.plantacion.cultivo
        multiplicador = 1

        try:
            detalle_cultivo = DetalleCultivo.objects.get(
                cultivo=cultivo,
                categoria=venta.categoria,
                tipocosecha=venta.tipocosecha
            )
            multiplicador = detalle_cultivo.cantidad
        except DetalleCultivo.DoesNotExist:
            multiplicador = 1

        cantidad_real = venta.cantidad * multiplicador
        ventas_convertidas[venta.categoria] += cantidad_real

    return ventas_convertidas

############   CLIENTES  ####################

# Mostrar lista de clientes
@login_required
def lista_clientes(request):
    filtro = request.GET.get('filtro', 'nombre')
    buscar = request.GET.get('buscar', '').strip().lower()

    # Consulta base
    clientes = Cliente.objects.all()

    # Filtros de búsqueda
    if buscar:
        if filtro == 'nombre':
            clientes = clientes.filter(nombre__icontains=buscar)
        elif filtro == 'telefono':
            clientes = clientes.filter(telefono__icontains=buscar)
        elif filtro == 'tipo':
            if buscar in ['comprador', 'c']:
                clientes = clientes.filter(tipocliente='C')
            elif buscar in ['proveedor', 'p']:
                clientes = clientes.filter(tipocliente='P')
        elif filtro == 'tipomercado':
            if buscar in ['formal', 'f']:
                clientes = clientes.filter(tipomercado='F')
            elif buscar in ['informal', 'i']:
                clientes = clientes.filter(tipomercado='I')

    # Anotar cantidad total vendida por cliente
    clientes = clientes.annotate(
        total_cantidad_vendida=Sum('venta__detalleventa__cantidad')
    ).order_by('nombre')

    # Paginación
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(clientes, 10)
        clientes_paginados = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'Cliente/lista_clientes.html', {
        'entity': clientes_paginados,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': request.GET.get('buscar', ''),
    })

# Crear un nuevo cliente
@login_required
def crear_cliente(request):
    if not request.user.has_perm('gestor.add_cliente'):
        messages.error(request, "No tienes permiso para agregar clientes.")
        return redirect('inicio')
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "El cliente ha sido creado exitosamente.")
            return redirect('/clientes/')
    else:
        form = ClienteForm()
    return render(request, 'Cliente/form_cliente.html', {'form': form})

# Editar un cliente existente
@login_required
def editar_cliente(request, idcliente):
    if not request.user.has_perm('gestor.change_cliente'):
        messages.error(request, "No tienes permiso para editar clientes.")
        return redirect('inicio')
    cliente = get_object_or_404(Cliente, pk=idcliente)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"El cliente '{cliente.nombre}' ha sido actualizado exitosamente.")
            # Verifica si se envió la bandera para redirigir a otra vista (opcional)
            if request.POST.get('ir_a_detalle') == '1':
                return redirect(f"{reverse('detalle_cliente')}?cliente_id={cliente.idcliente}")
            return redirect('lista_clientes')  # Nombre de la vista de lista de clientes
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'Cliente/form_cliente.html', {'form': form})

# Eliminar un cliente
@login_required
def eliminar_cliente(request, idcliente):
    if not request.user.has_perm('gestor.delete_cliente'):
        messages.error(request, "No tienes permiso para eliminar clientes.")
        return redirect('inicio')
    cliente = get_object_or_404(Cliente, pk=idcliente)
    if request.method == 'POST':
        tiene_ventas = Venta.objects.filter(cliente=cliente).exists()
        tiene_compras = Compra.objects.filter(cliente=cliente).exists()
        if tiene_ventas or tiene_compras:
            messages.error(request, f"No se puede eliminar el cliente '{cliente}' porque tiene ventas o compras asociadas.")
        else:
            cliente.delete()
            messages.success(request, f"El cliente '{cliente}' ha sido eliminado exitosamente.")
    return redirect('/clientes')


############   VENTAS  ####################
@login_required
def obtener_detalles_venta(request, venta_id):
    try:
        venta = Venta.objects.prefetch_related(
            'detalleventa_set__cosecha__plantacion__cultivo',
            'detalleventa_set__cosecha__plantacion__parcela',
            'detalleventa_set__cosecha__detallecosecha_set',
        ).get(idventa=venta_id)
    except Venta.DoesNotExist:
        return JsonResponse({'error': 'Venta no encontrada'}, status=404)

    detalles = []
    total_venta = 0  # Variable para acumular el total
    
    for detalle_venta in venta.detalleventa_set.all():
        # Obtener el tipo de cosecha desde DetalleCosecha
        detalle_cosecha = detalle_venta.cosecha.detallecosecha_set.filter(
            categoria=detalle_venta.categoria
        ).first()
        
        subtotal = float(detalle_venta.subtotal)
        total_venta += subtotal  # Sumar al total
        
        detalles.append({
            'cultivo': detalle_venta.cosecha.plantacion.cultivo.nombre,
            'parcela': detalle_venta.cosecha.plantacion.parcela.nombre,
            'cantidad': detalle_venta.cantidad,
            'categoria': detalle_venta.get_categoria_display(),
            'tipocosecha': detalle_cosecha.get_tipocosecha_display() if detalle_cosecha else 'N/A',
            'subtotal': subtotal,
        })
 
    
    return JsonResponse({
        'detalles': detalles,
        'total': total_venta  # Enviar el total calculado
    })

# Mostrar lista de ventas
@login_required
def lista_ventas(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    clientes = Cliente.objects.filter(tipocliente='C').order_by('nombre')

    ventas = Venta.objects.select_related('cliente').prefetch_related(
        'detalleventa_set__cosecha__plantacion__parcela',
        'detalleventa_set__cosecha__plantacion__cultivo'
    ).order_by('-idventa')

    # Filtro por texto
    if buscar:
        if filtro == 'parcela':
            ventas = ventas.filter(detalleventa__cosecha__plantacion__parcela__nombre__icontains=buscar)
        elif filtro in ['producto', 'cultivo']:
            ventas = ventas.filter(detalleventa__cosecha__plantacion__cultivo__nombre__icontains=buscar)
        elif filtro == 'cliente':
            ventas = ventas.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'tipoventa':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                ventas = ventas.filter(tipoventa=tipo)
        elif filtro == 'estado':
            if buscar in ['pagado', 'true', '1', 'sí', 'si']:
                ventas = ventas.filter(estado=True)
            elif buscar in ['pendiente', 'false', '0', 'no']:
                ventas = ventas.filter(estado=False)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            ventas = ventas.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            ventas = ventas.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(ventas, 10)
    try:
        ventas_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        ventas_paginadas = paginator.page(1)
    except EmptyPage:
        ventas_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'Venta/lista_ventas.html', {
        'entity': ventas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'clientes': clientes,
    })

# Disponibilidad para ventas
def obtener_disponibilidad_por_cultivo():
    cosechas_activas = Cosecha.objects.filter(estado=False)
    disponibilidad = {}

    for cosecha in cosechas_activas:
        cultivo = str(cosecha.plantacion)  # esto será el nombre del cultivo
        detalles_cosecha = DetalleCosecha.objects.filter(cosecha=cosecha)

        for detalle in detalles_cosecha:
            tipo = detalle.tipocosecha
            categoria = detalle.categoria
            cantidad_total = detalle.cantidad

            # Obtener total vendido para esta cosecha, tipo y categoría
            vendidos = DetalleVenta.objects.filter(
                cosecha=cosecha,
                categoria=categoria
            ).aggregate(total=Sum('cantidad'))['total'] or 0

            disponible = max(cantidad_total - vendidos, 0)

            # Solo procesar si hay disponibilidad
            if disponible > 0:
                # Inicializar el cultivo si no existe
                if cultivo not in disponibilidad:
                    disponibilidad[cultivo] = {}
                
                # Inicializar el tipo si no existe
                if tipo not in disponibilidad[cultivo]:
                    disponibilidad[cultivo][tipo] = {'primera': 0, 'segunda': 0, 'tercera': 0}
                
                # AQUÍ ESTÁ LA CORRECCIÓN: Sumar directamente al diccionario principal
                disponibilidad[cultivo][tipo][categoria] += disponible

    # Limpiar tipos sin disponibilidad
    cultivos_a_eliminar = []
    for cultivo, tipos in disponibilidad.items():
        tipos_a_eliminar = []
        for tipo, categorias in tipos.items():
            if all(cantidad == 0 for cantidad in categorias.values()):
                tipos_a_eliminar.append(tipo)
        
        for tipo in tipos_a_eliminar:
            del disponibilidad[cultivo][tipo]
        
        if not disponibilidad[cultivo]:
            cultivos_a_eliminar.append(cultivo)
    
    for cultivo in cultivos_a_eliminar:
        del disponibilidad[cultivo]

    return disponibilidad

@login_required
def crear_venta(request):
    cliente_id = request.POST.get('cliente_id') or request.GET.get('cliente_id')
    cliente = get_object_or_404(Cliente, idcliente=cliente_id) if cliente_id else None

    if request.method == 'POST':
        form = VentaForm(request.POST)
        productos_data = request.POST.get('productos_json')

        if not cliente_id:
            messages.error(request, "ID de cliente no proporcionado.")
            return redirect('lista_ventas')

        if form.is_valid() and productos_data:
            productos = json.loads(productos_data)

            if not productos:
                messages.error(request, "No hay productos para registrar.")
                return redirect('lista_ventas')

            venta = form.save(commit=False)
            venta.cliente = cliente
            venta.total = sum(float(prod['total']) for prod in productos)
            venta.save()

            for producto in productos:
                cultivo_id = producto['cultivo_id']
                categoria = producto['categoria'].lower()
                tipo = producto['tipocosecha'].lower()
                cantidad = int(producto['cantidad'])
                subtotal = float(producto['total'])

                detalles_cosecha = DetalleCosecha.objects.filter(
                    cosecha__plantacion_id=cultivo_id,
                    cosecha__estado=False,
                    tipocosecha=tipo,
                    categoria=categoria
                ).select_related('cosecha').order_by('cosecha__fecha')

                cantidad_restante = cantidad
                subtotal_unitario = subtotal / cantidad if cantidad > 0 else 0

                for detalle in detalles_cosecha:
                    cosecha = detalle.cosecha
                    total_cosechado = detalle.cantidad

                    total_vendido = DetalleVenta.objects.filter(
                        cosecha=cosecha,
                        categoria=categoria,
                        tipocosecha=tipo
                    ).aggregate(total=Sum('cantidad'))['total'] or 0

                    disponible = max(total_cosechado - total_vendido, 0)

                    if disponible <= 0:
                        continue

                    usar = min(cantidad_restante, disponible)

                    DetalleVenta.objects.create(
                        venta=venta,
                        cosecha=cosecha,
                        categoria=categoria,
                        tipocosecha=tipo,  # ✔ Guardar tipocosecha
                        cantidad=usar,
                        subtotal=subtotal_unitario * usar
                    )

                    cantidad_restante -= usar
                    if cantidad_restante <= 0:
                        break

            # Actualizar estado de las cosechas agotadas
            cosechas_afectadas = Cosecha.objects.filter(estado=False)
            for cosecha in cosechas_afectadas:
                agotada = True
                detalles = DetalleCosecha.objects.filter(cosecha=cosecha)

                for cat in ['primera', 'segunda', 'tercera']:
                    for tipo_op in [op[0] for op in DetalleCosecha.OPCIONES]:
                        detalle_cat = detalles.filter(categoria=cat, tipocosecha=tipo_op).first()
                        if not detalle_cat:
                            continue

                        total_cosechado = detalle_cat.cantidad
                        total_vendido = DetalleVenta.objects.filter(
                            cosecha=cosecha,
                            categoria=cat,
                            tipocosecha=tipo_op
                        ).aggregate(total=Sum('cantidad'))['total'] or 0

                        if total_vendido < total_cosechado:
                            agotada = False
                            break
                    if not agotada:
                        break

                if agotada:
                    cosecha.estado = True
                    cosecha.save()

            messages.success(request, "Venta registrada correctamente.")
            return redirect('lista_ventas')

        messages.error(request, "Formulario inválido o faltan productos.")

    else:
        form = VentaForm()

    cultivos = Plantacion.objects.filter(
        idplantacion__in=Cosecha.objects.filter(estado=False).values_list('plantacion_id', flat=True)
    ).distinct()
    tipo_cosecha_opciones = DetalleCosecha.OPCIONES
    cantidades = obtener_disponibilidad_por_cultivo()

    return render(request, 'Venta/form_venta.html', {
        'form': form,
        'cultivos': cultivos,
        'tipo_cosecha_opciones': tipo_cosecha_opciones,
        'cantidades': cantidades,
        'cliente': cliente,
    })


@login_required
def ajax_categorias(request):
    cultivo_id = request.GET.get('cultivo_id')
    if not cultivo_id:
        return JsonResponse({'categorias': []})

    # Esto puede ajustarse según tu lógica, pero suponiendo que usas siempre todas las categorías:
    categorias = [op[0] for op in DetalleCosecha.CATEGORIAS]
    return JsonResponse({'categorias': categorias})

@login_required
def ajax_categorias(request):
    cultivo_id = request.GET.get('cultivo_id')
    productos_temporales = request.GET.get('productos_temporales', '[]')
    
    if not cultivo_id:
        return JsonResponse({'categorias': []})

    try:
        productos_temp = json.loads(productos_temporales)
    except:
        productos_temp = []

    # Obtener categorías que realmente tienen disponibilidad
    cosechas = Cosecha.objects.filter(plantacion_id=cultivo_id, estado=False)
    categorias_disponibles = set()

    for cosecha in cosechas:
        detalles = DetalleCosecha.objects.filter(cosecha=cosecha)
        
        for detalle in detalles:
            categoria = detalle.categoria
            tipo = detalle.tipocosecha
            cantidad_total = detalle.cantidad
            
            # Obtener total vendido para esta cosecha y categoría
            vendidos = DetalleVenta.objects.filter(
                cosecha=cosecha,
                categoria=categoria
            ).aggregate(total=Sum('cantidad'))['total'] or 0
            
            # Calcular cantidad usada en productos temporales
            usados_temp = sum(
                int(prod['cantidad']) for prod in productos_temp 
                if prod['cultivo_id'] == cultivo_id and 
                   prod['categoria'] == categoria and 
                   prod['tipocosecha'] == tipo
            )
            
            disponible = max(cantidad_total - vendidos - usados_temp, 0)
            
            # Solo agregar la categoría si tiene disponibilidad
            if disponible > 0:
                categorias_disponibles.add(categoria)

    # Convertir a lista y ordenar
    categorias_lista = list(categorias_disponibles)
    categorias_lista.sort()
    
    return JsonResponse({'categorias': categorias_lista})

@login_required
def ajax_tipocosechas(request):
    
    cultivo_id = request.GET.get('cultivo_id')
    categoria = request.GET.get('categoria')
    productos_temporales = request.GET.get('productos_temporales', '[]')

    if not cultivo_id or not categoria:
        return JsonResponse({'tipos': []})

    try:
        productos_temp = json.loads(productos_temporales)
    except:
        productos_temp = []

    cosechas = Cosecha.objects.filter(plantacion_id=cultivo_id, estado=False)
    tipos_disponibles = set()

    for cosecha in cosechas:
        detalles = DetalleCosecha.objects.filter(cosecha=cosecha, categoria=categoria)
        
        for detalle in detalles:
            tipo = detalle.tipocosecha
            cantidad_total = detalle.cantidad
            
            # Obtener total vendido para esta cosecha, tipo y categoría
            vendidos = DetalleVenta.objects.filter(
                cosecha=cosecha,
                categoria=categoria
            ).aggregate(total=Sum('cantidad'))['total'] or 0
            
            # Calcular cantidad usada en productos temporales
            usados_temp = sum(
                int(prod['cantidad']) for prod in productos_temp 
                if prod['cultivo_id'] == cultivo_id and 
                   prod['categoria'] == categoria and 
                   prod['tipocosecha'] == tipo
            )
            
            disponible = max(cantidad_total - vendidos - usados_temp, 0)
            
            # Solo agregar el tipo si tiene disponibilidad
            if disponible > 0:
                tipos_disponibles.add(tipo)

    # Crear opciones solo para los tipos que tienen disponibilidad
    opciones = []
    for valor, nombre in DetalleCosecha.OPCIONES:
        if valor in tipos_disponibles:
            opciones.append({'valor': valor, 'nombre': nombre})

    return JsonResponse({'tipos': opciones})

@login_required
def editar_venta(request, idventa):
    venta = get_object_or_404(Venta, idventa=idventa)
    cliente = venta.cliente
    
    if request.method == 'POST':
        data = request.POST
        productos_data = data.get('productos_json')  # Cambié el nombre para que coincida con el form
        
        
        
        if not productos_data:
            messages.error(request, "No se recibieron datos de productos.")
            return redirect('editar_venta', idventa=idventa)
        
        try:
            productos_nuevos = json.loads(productos_data)
        except json.JSONDecodeError as e:
            
            messages.error(request, "Error al procesar los datos de productos.")
            return redirect('editar_venta', idventa=idventa)
        
        
        
        if not productos_nuevos:
            
            venta.detalleventa_set.all().delete()
            venta.total = 0
            venta.save()
            messages.success(request, "Venta actualizada - sin productos.")
            return redirect('lista_ventas')

        

        # Calcular total
        total = sum(float(p['total']) for p in productos_nuevos)
        

        # Verificar disponibilidad para los productos nuevos
        for i, producto in enumerate(productos_nuevos):
            
            
            cultivo_id = producto['cultivo_id']
            tipocosecha = producto['tipocosecha']
            categoria = producto['categoria']
            cantidad_solicitada = int(producto['cantidad'])

            # Obtener disponibilidad actual (excluyendo esta venta)
            cosechas_activas = Cosecha.objects.filter(
                plantacion_id=cultivo_id, 
                estado=False
            )
            
            total_disponible = 0
            for cosecha in cosechas_activas:
                detalle_cosecha = DetalleCosecha.objects.filter(
                    cosecha=cosecha,
                    categoria=categoria,
                    tipocosecha=tipocosecha
                ).first()
                
                if detalle_cosecha:
                    total_cosechado = detalle_cosecha.cantidad
                    
                    # Total vendido EXCLUYENDO esta venta que estamos editando
                    vendidos = DetalleVenta.objects.filter(
                        cosecha=cosecha,
                        categoria=categoria,
                        tipocosecha=tipocosecha
                    ).exclude(venta=venta).aggregate(
                        total=Sum('cantidad')
                    )['total'] or 0
                    
                    total_disponible += max(total_cosechado - vendidos, 0)

            # También sumar lo que ya tenía esta venta para este producto específico
            cantidad_actual_venta = DetalleVenta.objects.filter(
                venta=venta,
                cosecha__plantacion_id=cultivo_id,
                categoria=categoria,
                tipocosecha=tipocosecha
            ).aggregate(total=Sum('cantidad'))['total'] or 0

            total_disponible += cantidad_actual_venta
            

            if cantidad_solicitada > total_disponible:
                messages.error(
                    request,
                    f"No hay suficiente stock disponible. Solicitado: {cantidad_solicitada}, "
                    f"Disponible: {total_disponible} para {categoria} - {tipocosecha}"
                )
                return redirect('editar_venta', idventa=idventa)

        # Actualizar cabecera de venta
        venta.total = total
        venta.save()

        # 🔹 Eliminar detalles existentes
        detalles_eliminados = venta.detalleventa_set.count()
        venta.detalleventa_set.all().delete()

        # 🔹 Crear nuevos detalles
        detalles_creados = 0
        for producto in productos_nuevos:
            cultivo_id = producto['cultivo_id']
            categoria = producto['categoria'].lower()
            tipo = producto['tipocosecha'].lower()
            cantidad = int(producto['cantidad'])
            subtotal = float(producto['total'])


            # Usar la misma lógica de distribución que en crear_venta
            detalles_cosecha = DetalleCosecha.objects.filter(
                cosecha__plantacion_id=cultivo_id,
                cosecha__estado=False,
                tipocosecha=tipo,
                categoria=categoria
            ).select_related('cosecha').order_by('cosecha__fecha')

            cantidad_restante = cantidad
            subtotal_unitario = subtotal / cantidad if cantidad > 0 else 0

            for detalle_cosecha in detalles_cosecha:
                cosecha_actual = detalle_cosecha.cosecha
                total_cosechado = detalle_cosecha.cantidad

                # Ahora que ya eliminamos los detalles de esta venta, podemos calcular normalmente
                total_vendido = DetalleVenta.objects.filter(
                    cosecha=cosecha_actual,
                    categoria=categoria,
                    tipocosecha=tipo
                ).aggregate(total=Sum('cantidad'))['total'] or 0

                disponible = max(total_cosechado - total_vendido, 0)

                if disponible <= 0:
                    continue

                usar = min(cantidad_restante, disponible)

                DetalleVenta.objects.create(
                    venta=venta,
                    cosecha=cosecha_actual,
                    categoria=categoria,
                    tipocosecha=tipo,
                    cantidad=usar,
                    subtotal=subtotal_unitario * usar
                )
                
                detalles_creados += 1

                cantidad_restante -= usar
                if cantidad_restante <= 0:
                    break


        # Actualizar estado de las cosechas agotadas
        cosechas_afectadas = Cosecha.objects.filter(estado=False)
        for cosecha in cosechas_afectadas:
            agotada = True
            detalles = DetalleCosecha.objects.filter(cosecha=cosecha)

            for cat in ['primera', 'segunda', 'tercera']:
                for tipo_op in [op[0] for op in DetalleCosecha.OPCIONES]:
                    detalle_cat = detalles.filter(categoria=cat, tipocosecha=tipo_op).first()
                    if not detalle_cat:
                        continue

                    total_cosechado = detalle_cat.cantidad
                    total_vendido = DetalleVenta.objects.filter(
                        cosecha=cosecha,
                        categoria=cat,
                        tipocosecha=tipo_op
                    ).aggregate(total=Sum('cantidad'))['total'] or 0

                    if total_vendido < total_cosechado:
                        agotada = False
                        break
                if not agotada:
                    break

            if agotada:
                cosecha.estado = True
                cosecha.save()

        
        messages.success(request, "Venta actualizada correctamente.")
        return redirect('lista_ventas')

    else:
        # Preparar productos existentes para mostrar
        productos = []
        for detalle in venta.detalleventa_set.all():
            productos.append({
                'cultivo_id': detalle.cosecha.plantacion_id,
                'cultivo_text': str(detalle.cosecha.plantacion.cultivo),
                'categoria': detalle.categoria,
                'tipocosecha': detalle.tipocosecha,
                'cantidad': detalle.cantidad,
                'total': float(detalle.subtotal),
                'tipocosecha_text': detalle.get_tipocosecha_display()
            })

        tipo_cosecha_opciones = DetalleCosecha.OPCIONES
        cantidades = obtener_disponibilidad_por_cultivo()

        # Ajustar disponibilidad sumando lo que ya estaba en la venta
        for prod in productos:
            cultivo = prod['cultivo_text']
            tipo = prod['tipocosecha']
            categoria = prod['categoria']
            if cultivo in cantidades and tipo in cantidades[cultivo]:
                cantidades[cultivo][tipo][categoria] += prod['cantidad']

        



        clientes = Cliente.objects.filter(tipocliente='C').order_by('nombre')
        cultivos = Plantacion.objects.filter(
            idplantacion__in=Cosecha.objects.filter(estado=False).values_list('plantacion_id', flat=True)
        ).distinct()

        context = {
            'venta': venta,
            'form': VentaForm(instance=venta),
            'productos_json': json.dumps(productos),
            'tipo_cosecha_opciones': tipo_cosecha_opciones,
            'cantidades': cantidades,
            'cliente':cliente,
            'clientes': clientes,
            'cultivos': cultivos,
            'es_edicion': True,
        }
        return render(request, 'Venta/form_venta.html', context)

# Eliminar una venta
@login_required
def eliminar_venta(request, idventa):
    if not request.user.has_perm('gestor.delete_venta'):
        messages.error(request, "No tienes permiso para eliminar ventas.")
        return redirect('inicio')
    venta = get_object_or_404(Venta, pk=idventa)
    if request.method == 'POST':
        venta.delete()  # `delete()` ya actualiza el estado de la cosecha
        messages.success(request, f"La venta #{idventa} fue eliminada exitosamente.")
    return redirect('/ventas')

# Cambiar estado de venta
@login_required
@require_POST
def toggle_estado_venta(request, idventa):
    if not request.user.has_perm('gestor.change_venta'):
        messages.error(request, "No tienes permiso para cerrar ventas.")
        return redirect('inicio')
    try:
        venta = Venta.objects.get(pk=idventa)
        venta.estado = True
        venta.save()
        
        return JsonResponse({'estado': venta.estado})
    except Venta.DoesNotExist:
        return JsonResponse({'error': 'Venta no encontrada'}, status=404)




############   MERCADO FORMAL ####################

# Mostrar lista de cliente formales
@login_required
def lista_clientesformales(request):
    filtro = request.GET.get('filtro', 'nombre')
    buscar = request.GET.get('buscar', '').strip().lower()

    # Consulta base
    clientes = Cliente.objects.filter(tipomercado='F')

    # Filtros de búsqueda
    if buscar:
        if filtro == 'nombre':
            clientes = clientes.filter(nombre__icontains=buscar)
        elif filtro == 'telefono':
            clientes = clientes.filter(telefono__icontains=buscar)
        elif filtro == 'tipo':
            if buscar in ['comprador', 'c']:
                clientes = clientes.filter(tipocliente='C')
            elif buscar in ['proveedor', 'p']:
                clientes = clientes.filter(tipocliente='P')

    # Anotar cantidad total vendida por cliente
    clientes = clientes.annotate(
        total_cantidad_vendida=Sum('venta__detalleventa__cantidad')
    ).order_by('nombre')

    # Paginación
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(clientes, 10)
        clientes_paginados = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'MercadoFormal/clientesformales.html', {
        'entity': clientes_paginados,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': request.GET.get('buscar', ''),
    })

# Mostrar lista de entregas formales
@login_required
def lista_entregasformales(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    clientes = Cliente.objects.filter(tipocliente='C').order_by('nombre')

    ventas = Venta.objects.select_related('cliente').prefetch_related(
    'detalleventa_set__cosecha__plantacion__parcela',
    'detalleventa_set__cosecha__plantacion__cultivo'
    ).filter(
        cliente__tipomercado='F',  # 'F' = Formal según tu modelo
        estado=False  # Solo ventas no pagadas
    ).order_by('-idventa')

    # Filtro por texto
    if buscar:
        if filtro == 'parcela':
            ventas = ventas.filter(detalleventa__cosecha__plantacion__parcela__nombre__icontains=buscar)
        elif filtro in ['producto', 'cultivo']:
            ventas = ventas.filter(detalleventa__cosecha__plantacion__cultivo__nombre__icontains=buscar)
        elif filtro == 'cliente':
            ventas = ventas.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'tipoventa':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                ventas = ventas.filter(tipoventa=tipo)
        elif filtro == 'estado':
            if buscar in ['pagado', 'true', '1', 'sí', 'si']:
                ventas = ventas.filter(estado=True)
            elif buscar in ['pendiente', 'false', '0', 'no']:
                ventas = ventas.filter(estado=False)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            ventas = ventas.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            ventas = ventas.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(ventas, 10)
    try:
        ventas_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        ventas_paginadas = paginator.page(1)
    except EmptyPage:
        ventas_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'MercadoFormal/entregasformales.html', {
        'entity': ventas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'clientes': clientes,
    })

# Mostrar lista de ventas formales
@login_required
def lista_ventasformales(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    clientes = Cliente.objects.filter(tipocliente='C').order_by('nombre')

    ventas = Venta.objects.select_related('cliente').prefetch_related(
    'detalleventa_set__cosecha__plantacion__parcela',
    'detalleventa_set__cosecha__plantacion__cultivo'
    ).filter(
        cliente__tipomercado='F',  # 'F' = Formal según tu modelo
        estado=True  # Solo ventas pagadas
    ).order_by('-idventa')

    # Filtro por texto
    if buscar:
        if filtro == 'parcela':
            ventas = ventas.filter(detalleventa__cosecha__plantacion__parcela__nombre__icontains=buscar)
        elif filtro in ['producto', 'cultivo']:
            ventas = ventas.filter(detalleventa__cosecha__plantacion__cultivo__nombre__icontains=buscar)
        elif filtro == 'cliente':
            ventas = ventas.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'tipoventa':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                ventas = ventas.filter(tipoventa=tipo)
        elif filtro == 'estado':
            if buscar in ['pagado', 'true', '1', 'sí', 'si']:
                ventas = ventas.filter(estado=True)
            elif buscar in ['pendiente', 'false', '0', 'no']:
                ventas = ventas.filter(estado=False)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            ventas = ventas.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            ventas = ventas.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(ventas, 10)
    try:
        ventas_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        ventas_paginadas = paginator.page(1)
    except EmptyPage:
        ventas_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'MercadoFormal/ventasformales.html', {
        'entity': ventas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'clientes': clientes,
    })

# Mostrar lista de compras formales
@login_required
def lista_comprasformales(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    # Obtener proveedores (clientes con tipo 'P' si existe esa distinción)
    proveedores = Cliente.objects.filter(tipocliente='P', tipomercado='F').order_by('nombre') if hasattr(Cliente, 'tipocliente') else Cliente.objects.all().order_by('nombre')
    print(proveedores)
    compras = Compra.objects.select_related('cliente').prefetch_related(
        'detallecompra_set'
    ).filter(cliente__tipomercado='F').order_by('-idcompra')

    # Filtro por texto
    if buscar:
        if filtro == 'proveedor':
            compras = compras.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'producto':
            compras = compras.filter(detallecompra__producto__icontains=buscar)
        elif filtro == 'tipocompra':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                compras = compras.filter(tipocompra=tipo)
        elif filtro == 'estado':
            if buscar in ['activo', 'true', '1', 'sí', 'si']:
                compras = compras.filter(estado=True)
            elif buscar in ['inactivo', 'false', '0', 'no']:
                compras = compras.filter(estado=False)
        elif filtro == 'tipodetalle':
            tipo_map = {'casa': 'C', 'empresa': 'E'}
            tipo = tipo_map.get(buscar)
            if tipo:
                compras = compras.filter(detallecompra__tipodetalle=tipo)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            compras = compras.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            compras = compras.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(compras, 10)
    try:
        compras_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        compras_paginadas = paginator.page(1)
    except EmptyPage:
        compras_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'MercadoFormal/comprasformales.html', {
        'entity': compras_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'proveedores': proveedores,
    })



    
############   MERCADO INFORMAL ####################

# Mostrar lista de cliente formales
@login_required
def lista_clientesinformales(request):
    filtro = request.GET.get('filtro', 'nombre')
    buscar = request.GET.get('buscar', '').strip().lower()

    # Consulta base
    clientes = Cliente.objects.filter(tipomercado='I')

    # Filtros de búsqueda
    if buscar:
        if filtro == 'nombre':
            clientes = clientes.filter(nombre__icontains=buscar)
        elif filtro == 'telefono':
            clientes = clientes.filter(telefono__icontains=buscar)
        elif filtro == 'tipo':
            if buscar in ['comprador', 'c']:
                clientes = clientes.filter(tipocliente='C')
            elif buscar in ['proveedor', 'p']:
                clientes = clientes.filter(tipocliente='P')

    # Anotar cantidad total vendida por cliente
    clientes = clientes.annotate(
        total_cantidad_vendida=Sum('venta__detalleventa__cantidad')
    ).order_by('nombre')

    # Paginación
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(clientes, 10)
        clientes_paginados = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'MercadoInformal/clientesinformales.html', {
        'entity': clientes_paginados,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': request.GET.get('buscar', ''),
    })

# Mostrar lista de entregas formales
@login_required
def lista_entregasinformales(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    clientes = Cliente.objects.filter(tipocliente='C').order_by('nombre')

    ventas = Venta.objects.select_related('cliente').prefetch_related(
    'detalleventa_set__cosecha__plantacion__parcela',
    'detalleventa_set__cosecha__plantacion__cultivo'
    ).filter(
        cliente__tipomercado='I',
        estado=False  
    ).order_by('-idventa')

    # Filtro por texto
    if buscar:
        if filtro == 'parcela':
            ventas = ventas.filter(detalleventa__cosecha__plantacion__parcela__nombre__icontains=buscar)
        elif filtro in ['producto', 'cultivo']:
            ventas = ventas.filter(detalleventa__cosecha__plantacion__cultivo__nombre__icontains=buscar)
        elif filtro == 'cliente':
            ventas = ventas.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'tipoventa':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                ventas = ventas.filter(tipoventa=tipo)
        elif filtro == 'estado':
            if buscar in ['pagado', 'true', '1', 'sí', 'si']:
                ventas = ventas.filter(estado=True)
            elif buscar in ['pendiente', 'false', '0', 'no']:
                ventas = ventas.filter(estado=False)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            ventas = ventas.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            ventas = ventas.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(ventas, 10)
    try:
        ventas_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        ventas_paginadas = paginator.page(1)
    except EmptyPage:
        ventas_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'MercadoInformal/entregasinformales.html', {
        'entity': ventas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'clientes': clientes,
    })

# Mostrar lista de ventas informales
@login_required
def lista_ventasinformales(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    clientes = Cliente.objects.filter(tipocliente='C').order_by('nombre')

    ventas = Venta.objects.select_related('cliente').prefetch_related(
    'detalleventa_set__cosecha__plantacion__parcela',
    'detalleventa_set__cosecha__plantacion__cultivo'
    ).filter(
        cliente__tipomercado='I', 
        estado=True
    ).order_by('-idventa')

    # Filtro por texto
    if buscar:
        if filtro == 'parcela':
            ventas = ventas.filter(detalleventa__cosecha__plantacion__parcela__nombre__icontains=buscar)
        elif filtro in ['producto', 'cultivo']:
            ventas = ventas.filter(detalleventa__cosecha__plantacion__cultivo__nombre__icontains=buscar)
        elif filtro == 'cliente':
            ventas = ventas.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'tipoventa':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                ventas = ventas.filter(tipoventa=tipo)
        elif filtro == 'estado':
            if buscar in ['pagado', 'true', '1', 'sí', 'si']:
                ventas = ventas.filter(estado=True)
            elif buscar in ['pendiente', 'false', '0', 'no']:
                ventas = ventas.filter(estado=False)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            ventas = ventas.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            ventas = ventas.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(ventas, 10)
    try:
        ventas_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        ventas_paginadas = paginator.page(1)
    except EmptyPage:
        ventas_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'MercadoInformal/ventasinformales.html', {
        'entity': ventas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'clientes': clientes,
    })

# Mostrar lista de compras informales
@login_required
def lista_comprasinformales(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    # Obtener proveedores (clientes con tipo 'P' si existe esa distinción)
    proveedores = Cliente.objects.filter(tipocliente='P', tipomercado='I').order_by('nombre') if hasattr(Cliente, 'tipocliente') else Cliente.objects.all().order_by('nombre')

    compras = Compra.objects.select_related('cliente').prefetch_related(
        'detallecompra_set'
    ).filter(cliente__tipomercado='I').order_by('-idcompra')

    # Filtro por texto
    if buscar:
        if filtro == 'proveedor':
            compras = compras.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'producto':
            compras = compras.filter(detallecompra__producto__icontains=buscar)
        elif filtro == 'tipocompra':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                compras = compras.filter(tipocompra=tipo)
        elif filtro == 'estado':
            if buscar in ['activo', 'true', '1', 'sí', 'si']:
                compras = compras.filter(estado=True)
            elif buscar in ['inactivo', 'false', '0', 'no']:
                compras = compras.filter(estado=False)
        elif filtro == 'tipodetalle':
            tipo_map = {'casa': 'C', 'empresa': 'E'}
            tipo = tipo_map.get(buscar)
            if tipo:
                compras = compras.filter(detallecompra__tipodetalle=tipo)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            compras = compras.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            compras = compras.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(compras, 10)
    try:
        compras_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        compras_paginadas = paginator.page(1)
    except EmptyPage:
        compras_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'MercadoInformal/comprasinformales.html', {
        'entity': compras_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'proveedores': proveedores,
    })




############   EMPLEADOS  ####################
# Mostrar lista de empleados
@login_required
def lista_empleados(request):
    filtro = request.GET.get('filtro', 'nombre')
    buscar = request.GET.get('buscar', '').strip().lower()

    empleados = Empleado.objects.all().order_by('nombre')

    if buscar:
        if filtro == 'nombre':
            empleados = empleados.filter(nombre__icontains=buscar)
        elif filtro == 'telefono':
            empleados = empleados.filter(telefono__icontains=buscar)
        elif filtro == 'salario':
            try:
                salario_buscar = float(buscar)
                empleados = empleados.filter(salario=salario_buscar)
            except ValueError:
                empleados = empleados.none()

    # Preparar la lista enriquecida
    empleados_info = []
    for empleado in empleados:
        # Aquí puedes agregar información adicional relacionada con el empleado
        # Por ejemplo, si tienes modelos relacionados como AsignacionTrabajo, etc.
        
        empleados_info.append({
            'empleado': empleado,
            'estado_texto': 'Activo' if empleado.estado else 'Inactivo',
            'salario_formateado': f"${empleado.salario:,.2f}"
        })
        
    # Paginación manual
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(empleados_info, 10)
        empleados_paginados = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'Empleado/lista_empleados.html', {
        'entity': empleados_paginados,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': request.GET.get('buscar', '')
    })

# Crear un nuevo empleado
@login_required
def crear_empleado(request):
    if request.method == 'POST':
        form = EmpleadoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "El empleado ha sido creado exitosamente.")
            return redirect('/empleados/')
    else:
        form = EmpleadoForm()
    return render(request, 'Empleado/form_empleado.html', {'form': form})

# Editar un empleado existente
@login_required
def editar_empleado(request, idempleado):
    if not request.user.has_perm('gestor.change_empleado'):
        messages.error(request, "No tienes permiso para editar empleados.")
        return redirect('inicio') 
    empleado = get_object_or_404(Empleado, pk=idempleado)
    if request.method == 'POST':
        form = EmpleadoForm(request.POST, instance=empleado)
        if form.is_valid():
            form.save()
            messages.success(request, f"El empleado '{empleado.nombre}' ha sido actualizado exitosamente.")
            return redirect('/empleados')
    else:
        form = EmpleadoForm(instance=empleado)
    return render(request, 'Empleado/form_empleado.html', {'form': form})

# Eliminar un empleado
@login_required
def eliminar_empleado(request, idempleado):
    if not request.user.has_perm('gestor.delete_empleado'):
        messages.error(request, "No tienes permiso para eliminar empleados.")
        return redirect('inicio') 
    empleado = get_object_or_404(Empleado, pk=idempleado)
    if request.method == 'POST':
        # Verifica si el empleado tiene registros relacionados antes de eliminar
        # Ajusta esto según tus modelos relacionados
        # Por ejemplo, si tienes AsignacionTrabajo:
        # if AsignacionTrabajo.objects.filter(empleado=empleado).exists():
        #     messages.error(request, f"No se puede eliminar el empleado '{empleado.nombre}' porque tiene asignaciones de trabajo.")
        # else:
        empleado.delete()
        messages.success(request, f"El empleado '{empleado.nombre}' ha sido eliminado exitosamente.")
    return redirect('/empleados')

# Vista adicional para cambiar estado del empleado (activar/desactivar)
@login_required
def cambiar_estado_empleado(request, idempleado):
    if not request.user.has_perm('gestor.change_empleado'):
        messages.error(request, "No tienes permiso para cambiar el estado de empleados.")
        return redirect('inicio')
    
    empleado = get_object_or_404(Empleado, pk=idempleado)
    empleado.estado = not empleado.estado
    empleado.save()
    
    estado_texto = "activado" if empleado.estado else "desactivado"
    messages.success(request, f"El empleado '{empleado.nombre}' ha sido {estado_texto} exitosamente.")
    
    return redirect('/empleados')


############   PLANILLAS  ####################

def obtener_semana_actual():
    """Obtiene el domingo y sábado de la semana actual (domingo como primer día)"""
    hoy = datetime.now().date()
    dias_desde_domingo = (hoy.weekday() + 1) % 7  # Convertir para que domingo sea 0
    domingo = hoy - timedelta(days=dias_desde_domingo)
    sabado = domingo + timedelta(days=6)
    return domingo, sabado

def obtener_dias_semana(fecha_inicio):
    """Genera las fechas de los 7 días de la semana empezando desde domingo"""
    dias = []
    for i in range(7):
        dia = fecha_inicio + timedelta(days=i)
        dias.append(dia)
    return dias

@login_required
def lista_planilla_semanal(request):
    filtro = request.GET.get('filtro', 'empleado')
    buscar = request.GET.get('buscar', '').strip().lower()
    semana_str = request.GET.get('semana', '')

    if semana_str:
        try:
            anio, semana_num = semana_str.split('-W')
            anio = int(anio)
            semana_num = int(semana_num)
            lunes = datetime.strptime(f'{anio}-W{semana_num}-1', "%G-W%V-%u").date()
            domingo_inicio = lunes - timedelta(days=1)
            sabado_fin = lunes + timedelta(days=5)
        except ValueError:
            raise Http404("Semana inválida")
    else:
        domingo_inicio, sabado_fin = obtener_semana_actual()

    dias_semana = obtener_dias_semana(domingo_inicio)
    nombres_dias = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    empleados = Empleado.objects.filter(estado=True).order_by('nombre')
    if buscar:
        empleados = empleados.filter(nombre__icontains=buscar)

    planillas_semana = Planilla.objects.filter(
        fecha__range=(domingo_inicio, sabado_fin)
    ).select_related('empleado')

    planillas_dict = {
        f"{p.empleado.idempleado}_{p.fecha}": p
        for p in planillas_semana
    }

    # Totales generales
    total_pago_general = 0.0
    total_pagos_extra_general = 0.0
    total_horas_extra_general = 0.0
    total_jornadas_general = 0

    empleados_data = []
    for empleado in empleados:
        info = {
            'empleado': empleado,
            'dias': [],
            'total_salarios_semana': 0.0,
            'total_horas_extra_semana': 0.0,
            'total_pagos_extra_semana': 0.0,
            'horastrabajadas': 0.0,  # Total de horas trabajadas en la semana
        }

        for i, dia in enumerate(dias_semana):
            key = f"{empleado.idempleado}_{dia}"
            planilla = planillas_dict.get(key)
            
            if planilla:
                # Calcular salario basado en horas trabajadas
                horas_trabajadas = float(planilla.horastrabajadas) if planilla.horastrabajadas else 0.0
                salario_por_hora = float(empleado.salario) / 8  # Asumiendo jornada de 8 horas
                
                if planilla.jornada:
                    # Si marcó jornada completa, paga el salario completo
                    salario_dia = float(empleado.salario)
                elif horas_trabajadas > 0:
                    # Si trabajó parcialmente, calcular proporcional
                    salario_dia = salario_por_hora * horas_trabajadas
                else:
                    salario_dia = 0.0
                
                horas_extra = float(planilla.horasextra) if planilla.horasextra else 0.0
                pago_extra_dia = float(planilla.pagoextra) if planilla.pagoextra else 0.0
                observaciones = getattr(planilla, 'observaciones', '') or ''

                # Contar jornada si trabajó (completa o parcial)
                if planilla.jornada or horas_trabajadas > 0:
                    total_jornadas_general += 1
                    
                # Sumar horas trabajadas al total semanal
                info['horastrabajadas'] += horas_trabajadas
            else:
                salario_dia = 0.0
                horas_extra = 0.0
                horas_trabajadas = 0.0
                pago_extra_dia = 0.0
                observaciones = ""

            pago_horas_extra = horas_extra * 2
            total_dia = salario_dia + pago_horas_extra + pago_extra_dia

            info['dias'].append({
                'nombre_dia': nombres_dias[i],
                'salario_dia': salario_dia,
                'horas_trabajadas': horas_trabajadas,  # Agregar horas trabajadas al día
                'horas_extra': horas_extra,
                'pago_horas_extra': pago_horas_extra,
                'pago_extra': pago_extra_dia,
                'total_dia': total_dia,
                'observaciones': observaciones
            })

            info['total_salarios_semana'] += salario_dia
            info['total_horas_extra_semana'] += pago_horas_extra
            info['total_pagos_extra_semana'] += pago_extra_dia

        info['total_general'] = (
            info['total_salarios_semana'] +
            info['total_horas_extra_semana'] +
            info['total_pagos_extra_semana']
        )

        info['total_semana'] = info['total_salarios_semana']
        info['total_extra_semana'] = info['total_horas_extra_semana'] + info['total_pagos_extra_semana']
        info['dias_json'] = json.dumps(info['dias'], cls=DjangoJSONEncoder)

        empleados_data.append(info)

        # Sumar a totales generales
        total_pago_general += info['total_general']
        total_pagos_extra_general += info['total_pagos_extra_semana']
        total_horas_extra_general += info['total_horas_extra_semana']

    total_pago_general = round(total_pago_general, 2)
    total_pagos_extra_general = round(total_pagos_extra_general, 2)
    total_horas_extra_general = round(total_horas_extra_general, 2)

    return render(request, 'Planilla/lista_planilla.html', {
        'empleados_data': empleados_data,
        'nombres_dias': nombres_dias,
        'filtro': filtro,
        'buscar': request.GET.get('buscar', ''),
        'semana': semana_str,
        'fecha_inicio': domingo_inicio,
        'fecha_fin': sabado_fin,
        # Totales generales
        'total_pago_general': total_pago_general,
        'total_pagos_extra_general': total_pagos_extra_general,
        'total_horas_extra_general': total_horas_extra_general,
        'total_jornadas_general': total_jornadas_general,
    })

@login_required
def planilla_form_view(request):
    """Vista para mostrar y procesar el formulario de planilla diaria"""
    
    if request.method == 'GET':
        # Obtener la fecha del parámetro GET o usar la fecha actual
        fecha_str = request.GET.get('fecha', datetime.now().date().strftime('%Y-%m-%d'))
        
        try:
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_obj = datetime.now().date()
        
        # Obtener todos los empleados activos
        empleados = Empleado.objects.filter(estado=True).order_by('nombre')
        
        # Verificar si ya existe planilla para esta fecha
        planillas_existentes = Planilla.objects.filter(fecha=fecha_obj).select_related('empleado')
        
        # Crear diccionario para fácil acceso a las planillas existentes
        planillas_dict = {planilla.empleado.idempleado: planilla for planilla in planillas_existentes}
        
        # Determinar si es edición
        es_edicion = len(planillas_existentes) > 0
        
        context = {
            'empleados': empleados,
            'fecha_edicion': fecha_obj,
            'planillas_dict': planillas_dict,
            'es_edicion': es_edicion,
            'fecha_str': fecha_str
        }
        
        return render(request, 'Planilla/form_planilla.html', context)
    
    elif request.method == 'POST':
        # Procesar el formulario (igual que antes)
        return procesar_planilla_diaria(request)

@login_required 
def procesar_planilla_diaria(request):
    """Procesa y guarda los datos de la planilla diaria (crear o editar)"""
    
    try:
        fecha = request.POST.get('fecha')
        if not fecha:
            messages.error(request, 'La fecha es requerida.')
            return redirect('agregarplanilla')
        
        # Convertir fecha string a objeto date
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        
        empleados_procesados = 0
        empleados_con_datos = 0
        empleados_actualizados = 0
        empleados_creados = 0
        
        # Usar transacción para asegurar consistencia
        with transaction.atomic():
            
            empleados = Empleado.objects.filter(estado=True)
            
            for empleado in empleados:
                # Campos dinámicos para cada empleado
                jornada_key = f'empleado_{empleado.idempleado}_jornada'
                horas_key = f'empleado_{empleado.idempleado}_horasextra'
                pago_key = f'empleado_{empleado.idempleado}_pagoextra'
                obs_key = f'empleado_{empleado.idempleado}_observaciones'
                horastrab_key = f'empleado_{empleado.idempleado}_horastrabajadas'
                
                # Obtener valores del POST
                jornada = request.POST.get(jornada_key) == 'on'
                horas_extra = request.POST.get(horas_key, '0')
                pago_extra = request.POST.get(pago_key, '0')
                observaciones = request.POST.get(obs_key, '').strip()
                horas_trab = request.POST.get(horastrab_key, '0')
                
                # Convertir a Decimal de forma segura
                try:
                    horas_extra = Decimal(horas_extra) if horas_extra else Decimal(0)
                except (InvalidOperation, ValueError):
                    horas_extra = Decimal(0)

                try:
                    pago_extra = Decimal(pago_extra) if pago_extra else Decimal(0)
                except (InvalidOperation, ValueError):
                    pago_extra = Decimal(0)

                try:
                    horas_trab = Decimal(horas_trab) if horas_trab else Decimal(0)
                except (InvalidOperation, ValueError):
                    horas_trab = Decimal(0)
                
                # Verificar si ya existe una planilla para este empleado en esa fecha
                try:
                    planilla = Planilla.objects.get(empleado=empleado, fecha=fecha_obj)
                    # Actualizar planilla existente
                    planilla.jornada = jornada
                    planilla.horasextra = horas_extra
                    planilla.pagoextra = pago_extra
                    planilla.horastrabajadas = horas_trab
                    if hasattr(planilla, 'observaciones'):
                        planilla.observaciones = observaciones
                    planilla.save()
                    empleados_actualizados += 1
                    
                except Planilla.DoesNotExist:
                    # Crear planilla solo si hay datos
                    if jornada or horas_extra > 0 or pago_extra > 0 or horas_trab > 0 or observaciones:
                        planilla_data = {
                            'empleado': empleado,
                            'fecha': fecha_obj,
                            'jornada': jornada,
                            'horasextra': horas_extra,
                            'pagoextra': pago_extra,
                            'horastrabajadas': horas_trab,
                        }
                        if hasattr(Planilla, 'observaciones'):
                            planilla_data['observaciones'] = observaciones
                        
                        Planilla.objects.create(**planilla_data)
                        empleados_creados += 1
                
                empleados_procesados += 1
                if jornada or horas_extra > 0 or pago_extra > 0 or horas_trab > 0 or observaciones:
                    empleados_con_datos += 1
        
        # Mensajes de éxito
        if empleados_actualizados > 0 and empleados_creados > 0:
            messages.success(
                request, 
                f'Planilla procesada exitosamente. '
                f'Se actualizaron {empleados_actualizados} registros y se crearon {empleados_creados} nuevos.'
            )
        elif empleados_actualizados > 0:
            messages.success(
                request, 
                f'Planilla actualizada exitosamente. '
                f'Se actualizaron {empleados_actualizados} registros.'
            )
        elif empleados_creados > 0:
            messages.success(
                request, 
                f'Planilla creada exitosamente. '
                f'Se crearon {empleados_creados} nuevos registros.'
            )
        else:
            messages.warning(
                request, 
                'No se realizaron cambios. Asegúrate de marcar asistencias o agregar datos.'
            )
        
        return redirect('lista_planilla')
    
    except Exception as e:
        messages.error(
            request, 
            f'Error al guardar la planilla: {str(e)}'
        )
        return redirect('agregarplanilla')

# Nueva vista para crear planilla de una fecha específica
@login_required
def planilla_fecha_especifica(request, fecha_str):
    """Vista para crear/editar planilla de una fecha específica"""
    # Verificar si existe planilla para esa fecha
    existe_planilla = Planilla.objects.filter(fecha=fecha_str).exists()

    if not existe_planilla:
        messages.warning(request, f"No existe planilla para la fecha {fecha_str}.")
        return redirect('lista_planilla')

    # Si existe, redirigir a la vista de edición
    return redirect(f"{reverse('agregarplanilla')}?fecha={fecha_str}")

# Vista para obtener planilla de hoy directamente
@login_required
def planilla_hoy(request):
    """Vista para ir directamente a la planilla de hoy"""
    hoy = datetime.now().date().strftime('%Y-%m-%d')
    return redirect(f"{reverse('agregarplanilla')}?fecha={hoy}")


############   COMPRAS  ####################


# Mostrar lista de compras
@login_required
def lista_compras(request):
    filtro = request.GET.get('filtro', 'cliente').lower()
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    # Obtener proveedores (clientes con tipo 'P' si existe esa distinción)
    proveedores = Cliente.objects.filter(tipocliente='P').order_by('nombre') if hasattr(Cliente, 'tipocliente') else Cliente.objects.all().order_by('nombre')

    compras = Compra.objects.select_related('cliente').prefetch_related(
        'detallecompra_set'
    ).order_by('-idcompra')

    # Filtro por texto
    if buscar:
        if filtro == 'proveedor':
            compras = compras.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'producto':
            compras = compras.filter(detallecompra__producto__icontains=buscar)
        elif filtro == 'tipocompra':
            tipo_map = {'contado': 'C', 'crédito': 'D', 'credito': 'D'}
            tipo = tipo_map.get(buscar)
            if tipo:
                compras = compras.filter(tipocompra=tipo)
        elif filtro == 'estado':
            if buscar in ['activo', 'true', '1', 'sí', 'si']:
                compras = compras.filter(estado=True)
            elif buscar in ['inactivo', 'false', '0', 'no']:
                compras = compras.filter(estado=False)
        elif filtro == 'tipodetalle':
            tipo_map = {'casa': 'C', 'empresa': 'E'}
            tipo = tipo_map.get(buscar)
            if tipo:
                compras = compras.filter(detallecompra__tipodetalle=tipo)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            compras = compras.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            compras = compras.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass

    # Paginación
    pagina = request.GET.get("page", 1)
    paginator = Paginator(compras, 10)
    try:
        compras_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        compras_paginadas = paginator.page(1)
    except EmptyPage:
        compras_paginadas = paginator.page(paginator.num_pages)

    return render(request, 'Compras/lista_compras.html', {
        'entity': compras_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'proveedores': proveedores,
    })

# Crear nueva compra
@login_required
def crear_compra(request):
    proveedor_id = request.POST.get('proveedor_id') or request.GET.get('proveedor_id')
    proveedor = get_object_or_404(Cliente, idcliente=proveedor_id) if proveedor_id else None

    if request.method == 'POST':
        form = CompraForm(request.POST)
        productos_data = request.POST.get('productos_json')

        if not proveedor_id:
            messages.error(request, "ID de proveedor no proporcionado.")
            return redirect('lista_compras')

        if form.is_valid() and productos_data:
            productos = json.loads(productos_data)

            if not productos:
                messages.error(request, "No hay productos para registrar.")
                return redirect('lista_compras')

            compra = form.save(commit=False)
            compra.cliente = proveedor
            compra.total = sum(float(prod['subtotal']) for prod in productos)
            compra.save()

            # Crear detalles de compra
            for producto in productos:
                DetalleCompra.objects.create(
                    compra=compra,
                    producto=producto['producto'],
                    cantidad=float(producto['cantidad']),
                    preciounitario=float(producto['preciounitario']),
                    tipodetalle=producto['tipodetalle']
                )

            messages.success(request, "Compra registrada correctamente.")
            return redirect('lista_compras')

        messages.error(request, "Formulario inválido o faltan productos.")

    else:
        form = CompraForm()

    # Obtener proveedores para el formulario
    proveedores = Cliente.objects.filter(tipocliente='P').order_by('nombre') if hasattr(Cliente, 'tipocliente') else Cliente.objects.all().order_by('nombre')
    
    opciones_tipo = Compra.opciones if hasattr(Compra, 'opciones') else [("C", "Contado"), ("D", "Credito")]
    opciones_detalle = DetalleCompra.opciones if hasattr(DetalleCompra, 'opciones') else [("C", "Casa"), ("E", "Empresa")]

    return render(request, 'Compras/form_compra.html', {
        'form': form,
        'proveedores': proveedores,
        'opciones_tipo': opciones_tipo,
        'opciones_detalle': opciones_detalle,
        'proveedor': proveedor,
    })

# Editar compra
@login_required
def editar_compra(request, idcompra):
    if not request.user.has_perm('gestor.change_compra'):
        messages.error(request, "No tienes permiso para editar compras.")
        return redirect('inicio')
    
    compra = get_object_or_404(Compra, pk=idcompra)
    detalles = DetalleCompra.objects.filter(compra=compra)
    proveedor = compra.cliente
    if request.method == 'POST':
        form = CompraForm(request.POST, instance=compra)
        productos_data = request.POST.get('productos_json')

        if form.is_valid() and productos_data:
            productos = json.loads(productos_data)

            if not productos:
                messages.error(request, "No hay productos para actualizar.")
                return render(request, 'Compras/form_compra.html', {
                    'form': form,
                    'compra': compra,
                    'detalles': detalles,
                })

            # Actualizar la compra
            compra = form.save(commit=False)
            compra.total = sum(float(prod['subtotal']) for prod in productos)
            compra.save()

            # Eliminar detalles anteriores y crear nuevos
            DetalleCompra.objects.filter(compra=compra).delete()
            
            for producto in productos:
                DetalleCompra.objects.create(
                    compra=compra,
                    producto=producto['producto'],
                    cantidad=float(producto['cantidad']),
                    preciounitario=float(producto['preciounitario']),
                    tipodetalle=producto['tipodetalle']
                )

            messages.success(request, "Compra actualizada correctamente.")
            return redirect('lista_compras')

        messages.error(request, "Error al actualizar la compra.")

    else:
        form = CompraForm(instance=compra)

    proveedores = Cliente.objects.filter(tipocliente='P').order_by('nombre') if hasattr(Cliente, 'tipocliente') else Cliente.objects.all().order_by('nombre')
    opciones_tipo = Compra.opciones if hasattr(Compra, 'opciones') else [("C", "Contado"), ("D", "Credito")]
    opciones_detalle = DetalleCompra.opciones if hasattr(DetalleCompra, 'opciones') else [("C", "Casa"), ("E", "Empresa")]

    # Convertir detalles a formato JSON para el frontend
    detalles_json = []
    for detalle in detalles:
        detalles_json.append({
            'producto': detalle.producto,
            'cantidad': float(detalle.cantidad),
            'preciounitario': float(detalle.preciounitario),
            'tipodetalle': detalle.tipodetalle,
            'subtotal': float(detalle.subtotal())
        })

    return render(request, 'Compras/form_compra.html', {
        'form': form,
        'proveedores': proveedores,
        'proveedor':proveedor,
        'opciones_tipo': opciones_tipo,
        'opciones_detalle': opciones_detalle,
        'compra': compra,
        'detalles': detalles,
        'detalles_json': json.dumps(detalles_json),
    })

# Eliminar compra
@login_required
def eliminar_compra(request, idcompra):
    if not request.user.has_perm('gestor.delete_compra'):
        messages.error(request, "No tienes permiso para eliminar compras.")
        return redirect('inicio')
    
    compra = get_object_or_404(Compra, pk=idcompra)
    
    if request.method == 'POST':
        # Primero eliminar los detalles (por si hay restricciones FK)
        DetalleCompra.objects.filter(compra=compra).delete()
        compra.delete()
        messages.success(request, f"La compra #{idcompra} fue eliminada exitosamente.")
        return redirect('lista_compras')
    
    return render(request, 'Compras/confirmar_eliminar.html', {
        'compra': compra,
        'detalles': DetalleCompra.objects.filter(compra=compra)
    })

# Cambiar estado de compra
@require_POST
def toggle_estado_compra(request, idcompra):
    if not request.user.has_perm('gestor.change_compra'):
        messages.error(request, "No tienes permiso para cambiar el estado de compras.")
        return redirect('inicio')
    
    try:
        compra = Compra.objects.get(pk=idcompra)
        
        if not compra.estado:  # Solo marcar como pagada si está pendiente
            compra.estado = True
            compra.save()
            
        

        return JsonResponse({'estado': compra.estado})
    except Compra.DoesNotExist:
        return JsonResponse({'error': 'Compra no encontrada'}, status=404)

# Ver detalles de una compra específica
@login_required
def ver_compra(request, idcompra):
    compra = get_object_or_404(Compra, pk=idcompra)
    detalles = DetalleCompra.objects.filter(compra=compra)
    
    return render(request, 'Compras/ver_compra.html', {
        'compra': compra,
        'detalles': detalles,
    })

# Reporte de compras por proveedor
@login_required
def reporte_compras_proveedor(request):
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    
    compras = Compra.objects.select_related('cliente')
    
    # Filtros
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            compras = compras.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            compras = compras.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            pass
    
    if proveedor_id:
        compras = compras.filter(cliente_id=proveedor_id)
    
    # Resumen por proveedor
    reporte = compras.values(
        'cliente__nombre'
    ).annotate(
        total_compras=Sum('total'),
        cantidad_compras=models.Count('idcompra')
    ).order_by('cliente__nombre')
    
    proveedores = Cliente.objects.filter(tipocliente='P').order_by('nombre') if hasattr(Cliente, 'tipocliente') else Cliente.objects.all().order_by('nombre')
    
    return render(request, 'Compras/reporte_compras.html', {
        'reporte': reporte,
        'proveedores': proveedores,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'proveedor_id': proveedor_id,
    })


@login_required
def detalles_compra_ajax(request, compra_id):
    """
    Vista para obtener los detalles de una compra específica via AJAX
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Solicitud no válida'}, status=400)
    
    try:
        compra = get_object_or_404(Compra, pk=compra_id)
        detalles = DetalleCompra.objects.filter(compra=compra)
        
        detalles_data = []
        for detalle in detalles:
            detalles_data.append({
                'producto': detalle.producto,
                'cantidad': float(detalle.cantidad),
                'preciounitario': float(detalle.preciounitario),
                'tipodetalle': detalle.tipodetalle,
                'subtotal': float(detalle.subtotal())
            })
        
        return JsonResponse({
            'detalles': detalles_data,
            'total': float(compra.total)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

