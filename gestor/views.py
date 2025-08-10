from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.db.models import Sum, Count, DecimalField, Avg, F, ExpressionWrapper, DurationField, Case, When, IntegerField
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from collections import defaultdict
from decimal import Decimal
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


@login_required
def inicio(request):
    import json  # Agregar esta importación
    
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
    dias_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

    # Función para obtener el nombre legible del tipo de cosecha
    def get_tipo_cosecha_display(codigo):
        opciones = {
            "S": "Saco",
            "U": "Unidad", 
            "MS": "Medio saco",
            "C": "Caja",
            "MC": "Media caja",
            "Lb": "Libras"
        }
        return opciones.get(codigo, codigo)

    # Totales generales
    total_cultivos = Cultivo.objects.count()
    total_plantaciones = Plantacion.objects.count()
    
    # Total de ventas del día (usando DetalleVenta)
    total_ventas_hoy = DetalleVenta.objects.filter(
        venta__fecha=hoy
    ).aggregate(
        total=Sum(F('subtotal'))
    )['total'] or 0

    # Plantaciones y cosechas disponibles
    plantaciones = Plantacion.objects.filter(estado=0)
    cosechas = Cosecha.objects.filter(estado=0)
    clientes = Cliente.objects.filter(tipocliente='C')
    
    # Cosechas de hoy agrupadas por categoría (mantenemos el original)
    cosechas_hoy = DetalleCosecha.objects.filter(
        cosecha__fecha=hoy
    ).values('categoria').annotate(
        total=Sum('cantidad')
    )
    
    resumen_hoy = {'primera': 0, 'segunda': 0, 'tercera': 0}
    for item in cosechas_hoy:
        resumen_hoy[item['categoria']] = item['total'] or 0

    # Ventas por día de la semana (usando DetalleVenta)
    ventas_por_dia = []
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        total_dia = DetalleVenta.objects.filter(
            venta__fecha=dia
        ).aggregate(
            total=Sum(F('subtotal'))
        )['total'] or 0
        ventas_por_dia.append(float(total_dia))

    # Cosechas detalladas hoy por cultivo Y TIPO DE COSECHA
    cosechas_detalle = DetalleCosecha.objects.filter(
        cosecha__fecha=hoy
    ).select_related('cosecha__plantacion__cultivo')
    
    cosechas_hoy_detalle = {}
    
    for detalle in cosechas_detalle:
        cultivo = detalle.cosecha.plantacion.cultivo.nombre
        tipo_cosecha_display = get_tipo_cosecha_display(detalle.tipocosecha)
        categoria = detalle.categoria
        cantidad = detalle.cantidad or 0
        
        if cultivo not in cosechas_hoy_detalle:
            cosechas_hoy_detalle[cultivo] = {}
        
        if tipo_cosecha_display not in cosechas_hoy_detalle[cultivo]:
            cosechas_hoy_detalle[cultivo][tipo_cosecha_display] = {
                'primera': 0, 'segunda': 0, 'tercera': 0
            }
        
        cosechas_hoy_detalle[cultivo][tipo_cosecha_display][categoria] += cantidad

    # Cosechas por calidad por día POR CULTIVO (última semana)
    cosechas_por_calidad_cultivo_tipo = {}
    cultivos_nombres = set()
    tipos_cosecha = set()

    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        detalles_dia = DetalleCosecha.objects.filter(
            cosecha__fecha=dia
        ).select_related('cosecha__plantacion__cultivo')
        
        for detalle in detalles_dia:
            cultivo = detalle.cosecha.plantacion.cultivo.nombre
            tipo_cosecha_display = get_tipo_cosecha_display(detalle.tipocosecha)
            categoria = detalle.categoria
            cantidad = detalle.cantidad or 0
            
            if cultivo not in cosechas_por_calidad_cultivo_tipo:
                cosechas_por_calidad_cultivo_tipo[cultivo] = {}
            
            if tipo_cosecha_display not in cosechas_por_calidad_cultivo_tipo[cultivo]:
                cosechas_por_calidad_cultivo_tipo[cultivo][tipo_cosecha_display] = {
                    'primera': [0] * 7,
                    'segunda': [0] * 7,
                    'tercera': [0] * 7
                }
            
            cosechas_por_calidad_cultivo_tipo[cultivo][tipo_cosecha_display][categoria][i] += cantidad
            cultivos_nombres.add(cultivo)
            tipos_cosecha.add(tipo_cosecha_display)

    # Obtener cultivos que se cosecharon HOY (no toda la semana)
    cultivos_hoy = set()
    cosechas_detalle_hoy = DetalleCosecha.objects.filter(
        cosecha__fecha=hoy
    ).select_related('cosecha__plantacion__cultivo')
    
    for detalle in cosechas_detalle_hoy:
        cultivos_hoy.add(detalle.cosecha.plantacion.cultivo.nombre)
    
    # Estructura consolidada por cultivo (suma todos los tipos de cosecha)
    cosechas_por_calidad_y_cultivo = {}
    
    for cultivo in cultivos_nombres:
        cosechas_por_calidad_y_cultivo[cultivo] = {
            'primera': [0] * 7,
            'segunda': [0] * 7,
            'tercera': [0] * 7
        }
        
        if cultivo in cosechas_por_calidad_cultivo_tipo:
            for tipo, calidades in cosechas_por_calidad_cultivo_tipo[cultivo].items():
                for categoria, dias in calidades.items():
                    for i, cantidad in enumerate(dias):
                        cosechas_por_calidad_y_cultivo[cultivo][categoria][i] += cantidad

    # Solo crear datos de gráfico para cultivos que se cosecharon hoy
    cosechas_por_calidad_cultivos_hoy = {}
    for cultivo in cultivos_hoy:
        if cultivo in cosechas_por_calidad_y_cultivo:
            cosechas_por_calidad_cultivos_hoy[cultivo] = cosechas_por_calidad_y_cultivo[cultivo]

    # Compras del día
    total_compras_hoy = 0

    # Convertir datos a JSON para JavaScript
    dias_semana_json = json.dumps(dias_semana)
    ventas_por_dia_json = json.dumps(ventas_por_dia)
    calidad_por_cultivo_json = json.dumps(cosechas_por_calidad_cultivos_hoy)  # Solo cultivos de hoy
    cultivos_hoy_json = json.dumps(sorted(list(cultivos_hoy)))  # Solo cultivos de hoy

    context = {
        'total_cultivos': total_cultivos,
        'total_plantaciones': total_plantaciones,
        'total_ventas': total_ventas_hoy,
        'total_compras': total_compras_hoy,
        'cosechas_hoy': resumen_hoy,
        'cosechas_hoy_detalle': cosechas_hoy_detalle,
        'clientes': clientes,
        'cosechas': cosechas,
        'plantaciones': plantaciones,
        
        # Datos para JavaScript (ya convertidos a JSON)
        'dias_semana': dias_semana_json,
        'ventas_por_dia': ventas_por_dia_json,
        'calidad_por_cultivo': calidad_por_cultivo_json,
        'cultivos_hoy': cultivos_hoy_json,  # Solo cultivos cosechados hoy (para JS)
        'cultivos_hoy_lista': sorted(list(cultivos_hoy)),  # Para el template HTML
        
        # Datos adicionales para otros usos
        'calidad_por_cultivo_tipo': cosechas_por_calidad_cultivo_tipo,
        'tipos_cosecha': sorted(tipos_cosecha),
    }
    return render(request, 'index.html', context)

@login_required
def control_calidad(request):
    # Prepara las ventas agrupadas por cosecha usando DetalleVenta
    ventas = DetalleVenta.objects.values('cosecha').annotate(
        v1=Sum(Case(When(categoria='primera', then='cantidad'), default=0, output_field=IntegerField())),
        v2=Sum(Case(When(categoria='segunda', then='cantidad'), default=0, output_field=IntegerField())),
        v3=Sum(Case(When(categoria='tercera', then='cantidad'), default=0, output_field=IntegerField()))
    )
    ventas_dict = {v['cosecha']: v for v in ventas}
    
    cosechas = Cosecha.objects.select_related('plantacion__cultivo', 'plantacion__parcela')
    
    agrupados = {
        'parcelas': defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0, 'perdida': 0}),
        'cultivos': defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0, 'perdida': 0}),
        'plantaciones': defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0, 'perdida': 0}),
        'cosechas': []
    }
    
    for c in cosechas:
        # Obtener datos de cosecha desde DetalleCosecha
        detalles_cosecha = DetalleCosecha.objects.filter(cosecha=c)
        cosecha_data = detalles_cosecha.aggregate(
            primera=Sum(Case(When(categoria='primera', then='cantidad'), default=0, output_field=IntegerField())),
            segunda=Sum(Case(When(categoria='segunda', then='cantidad'), default=0, output_field=IntegerField())),
            tercera=Sum(Case(When(categoria='tercera', then='cantidad'), default=0, output_field=IntegerField()))
        )
        
        # Obtener datos de venta
        venta = ventas_dict.get(c.idcosecha, {'v1': 0, 'v2': 0, 'v3': 0})
        
        # Calcular pérdidas
        primera_cosecha = cosecha_data['primera'] or 0
        segunda_cosecha = cosecha_data['segunda'] or 0
        tercera_cosecha = cosecha_data['tercera'] or 0
        
        p_perdida = max(primera_cosecha - venta['v1'], 0)
        s_perdida = max(segunda_cosecha - venta['v2'], 0)
        t_perdida = max(tercera_cosecha - venta['v3'], 0)
        perdida_total = p_perdida + s_perdida + t_perdida
        
        agrupados['cosechas'].append({
            'nombre': f"Cosecha #{c.idcosecha}",
            'primera': primera_cosecha,
            'segunda': segunda_cosecha,
            'tercera': tercera_cosecha,
            'perdida': perdida_total
        })
        
        # Claves de agrupación
        plantacion_id = c.plantacion.idplantacion
        cultivo_id = c.plantacion.cultivo.idcultivo
        parcela_id = c.plantacion.parcela.idparcela
        
        # Acumulación por categoría
        agrupados['plantaciones'][plantacion_id]['primera'] += primera_cosecha
        agrupados['plantaciones'][plantacion_id]['segunda'] += segunda_cosecha
        agrupados['plantaciones'][plantacion_id]['tercera'] += tercera_cosecha
        
        agrupados['cultivos'][cultivo_id]['primera'] += primera_cosecha
        agrupados['cultivos'][cultivo_id]['segunda'] += segunda_cosecha
        agrupados['cultivos'][cultivo_id]['tercera'] += tercera_cosecha
        
        agrupados['parcelas'][parcela_id]['primera'] += primera_cosecha
        agrupados['parcelas'][parcela_id]['segunda'] += segunda_cosecha
        agrupados['parcelas'][parcela_id]['tercera'] += tercera_cosecha
        
        # Acumulación de pérdida
        agrupados['plantaciones'][plantacion_id]['perdida'] += perdida_total
        agrupados['cultivos'][cultivo_id]['perdida'] += perdida_total
        agrupados['parcelas'][parcela_id]['perdida'] += perdida_total
    
    # Convertir a listas con nombres
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
    
    # Lista de bloques para el template
    bloques = [
        {'titulo': '📍 Parcelas', 'items': parcelas_data},
        {'titulo': '🌱 Cultivos', 'items': cultivos_data},
        {'titulo': '🌿 Plantaciones', 'items': plantaciones_data},
        {'titulo': '🌾 Cosechas', 'items': cosechas_data},
    ]
    
    return render(request, 'control_calidad.html', {'bloques': bloques})

    
@login_required    
def reportes_view(request):
    parcelas = Parcela.objects.all()
    cultivos = Cultivo.objects.all()

    # Producción por calidad
    produccion_por_cultivo = defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0, 'total': 0})
    for cultivo in cultivos:
        cosechas = Cosecha.objects.filter(plantacion__cultivo=cultivo)
        
        # Ahora obtenemos los datos de DetalleCosecha
        detalles = DetalleCosecha.objects.filter(cosecha__in=cosechas)
        
        suma = detalles.aggregate(
            primera=Sum(Case(When(categoria='primera', then='cantidad'), default=0, output_field=IntegerField())),
            segunda=Sum(Case(When(categoria='segunda', then='cantidad'), default=0, output_field=IntegerField())),
            tercera=Sum(Case(When(categoria='tercera', then='cantidad'), default=0, output_field=IntegerField()))
        )
        
        produccion_por_cultivo[cultivo.nombre] = {
            'primera': suma['primera'] or 0,
            'segunda': suma['segunda'] or 0,
            'tercera': suma['tercera'] or 0,
            'total': sum(filter(None, [suma['primera'], suma['segunda'], suma['tercera']]))
        }

    # Producción por tipo de parcela
    produccion_por_tipo_parcela = {'Campo abierto': 0, 'Malla': 0}
    cosechas = Cosecha.objects.select_related('plantacion__parcela')
    for cosecha in cosechas:
        tipo = dict(Parcela.Opciones).get(cosecha.plantacion.parcela.tipoparcela)
        
        # Obtener total de esta cosecha desde DetalleCosecha
        detalles = DetalleCosecha.objects.filter(cosecha=cosecha)
        total = detalles.aggregate(total=Sum('cantidad'))['total'] or 0
        
        produccion_por_tipo_parcela[tipo] += total

    # Ciclo promedio de cada cultivo
    duraciones = Plantacion.objects.annotate(
        dias=ExpressionWrapper(F('cosecha__fecha') - F('fecha'), output_field=DurationField())
    ).values('cultivo__nombre').annotate(promedio=Avg('dias'))
    ciclo_promedio = {d['cultivo__nombre']: d['promedio'].days if d['promedio'] else 0 for d in duraciones}

    # Rendimiento por planta
    rendimiento_por_plantacion = {}
    plantaciones = Plantacion.objects.select_related('cultivo', 'parcela')
    for p in plantaciones:
        # Obtener total de cosecha desde DetalleCosecha
        detalles = DetalleCosecha.objects.filter(cosecha__plantacion=p)
        total = detalles.aggregate(suma=Sum('cantidad'))['suma'] or 0
        
        rendimiento = total / p.cantidad if p.cantidad else 0
        rendimiento_por_plantacion[p.idplantacion] = {
            'cultivo': p.cultivo.nombre,
            'parcela': p.parcela.nombre,
            'rendimiento': round(rendimiento, 2)
        }

    # Historial de cultivos por parcela
    historial_por_parcela = defaultdict(list)
    plantaciones_hist = Plantacion.objects.select_related('cultivo', 'parcela')
    for p in plantaciones_hist:
        historial_por_parcela[p.parcela.nombre].append({
            'cultivo': p.cultivo.nombre,
            'variedad': p.cultivo.variedad,
            'fecha': p.fecha,
            'estado': 'Activa' if not p.estado else 'Finalizada'
        })

    # Estado de parcelas
    estado_parcelas = {p.nombre: 'Ocupada' if p.estado else 'Libre' for p in parcelas}

    # Resumen de cosechas por fecha y calidad
    resumen_cosechas_fecha = defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0})
    cosechas = Cosecha.objects.all()
    for c in cosechas:
        detalles = DetalleCosecha.objects.filter(cosecha=c)
        for detalle in detalles:
            resumen_cosechas_fecha[c.fecha][detalle.categoria] += detalle.cantidad

    context = {
        'produccion_por_cultivo': dict(produccion_por_cultivo),
        'produccion_por_tipo_parcela': produccion_por_tipo_parcela,
        'ciclo_promedio': ciclo_promedio,
        'rendimiento_por_plantacion': rendimiento_por_plantacion,
        'historial_por_parcela': dict(historial_por_parcela),
        'estado_parcelas': estado_parcelas,
        'resumen_cosechas_fecha': dict(resumen_cosechas_fecha),
    }

    return render(request, 'reportes.html', context)


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

        cultivos_info.append({
            'cultivo': cultivo,
            'total_plantas': total_plantas,
            'total_cosechas': total_cosechas,
            'total_vendido': total_vendido
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
        if form.is_valid():
            form.save()
            messages.success(request, "El cultivo ha sido creado exitosamente.")
            return redirect('/cultivos/')
    else:
        form = CultivoForm()
    return render(request, 'Cultivo/form_cultivo.html', {'form': form})

# Editar un cultivo existente
@login_required
def editar_cultivo(request, idcultivo):
    if not request.user.has_perm('gestor.change_cultivo'):
        messages.error(request, "No tienes permiso para editar cultivos.")
        return redirect('inicio') 
    cultivo = get_object_or_404(Cultivo, pk=idcultivo)
    if request.method == 'POST':
        form = CultivoForm(request.POST, instance=cultivo)
        if form.is_valid():
            form.save()
            messages.success(request, f"El cultivo '{cultivo.nombre}' ha sido actualizado exitosamente.")
            return redirect('/cultivos')
    else:
        form = CultivoForm(instance=cultivo)
    return render(request, 'Cultivo/form_cultivo.html', {'form': form})

# Eliminar un cultivo
@login_required
def eliminar_cultivo(request, idcultivo):
    if not request.user.has_perm('gestor.delete_cultivo'):
        messages.error(request, "No tienes permiso para eliminar cultivos.")
        return redirect('inicio') 
    cultivo = get_object_or_404(Cultivo, pk=idcultivo)
    if request.method == 'POST':
        if Plantacion.objects.filter(cultivo=cultivo).exists():
            messages.error(request, f"No se puede eliminar el cultivo '{cultivo.nombre}' porque tiene plantaciones asociadas.")
        else:
            cultivo.delete()
            messages.success(request, f"El cultivo '{cultivo.nombre}' ha sido eliminado exitosamente.")
    return redirect('/cultivos')



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




# Mostrar lista de cocechas
@login_required
def lista_cosechas(request):
    filtro = request.GET.get('filtro', 'parcela')
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    cosechas = Cosecha.objects.select_related('plantacion__parcela', 'plantacion__cultivo').order_by('-idcosecha')

    if buscar:
        if filtro == 'parcela':
            cosechas = cosechas.filter(plantacion__parcela__nombre__icontains=buscar)
        elif filtro == 'cultivo':
            cosechas = cosechas.filter(plantacion__cultivo__nombre__icontains=buscar)
        elif filtro == 'tipo':
            tipo_map = {
                'saco': 'S', 'unidad': 'U', 'medio saco': 'MS',
                'caja': 'C', 'media caja': 'MC', 'libras': 'Lb'
            }
            for key, val in tipo_map.items():
                if buscar in key:
                    cosechas = cosechas.filter(detallecosecha__tipocosecha=val)
                    break
        elif filtro == 'estado':
            if buscar in ['finalizado', 'true', '1', 'sí', 'si']:
                cosechas = cosechas.filter(estado=True)
            elif buscar in ['activo', 'no finalizado', 'false', '0', 'no']:
                cosechas = cosechas.filter(estado=False)

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

    cosechas = cosechas.annotate(
        primera=Sum(Case(
            When(detallecosecha__categoria='primera', then='detallecosecha__cantidad'),
            default=0, output_field=IntegerField()
        )),
        segunda=Sum(Case(
            When(detallecosecha__categoria='segunda', then='detallecosecha__cantidad'),
            default=0, output_field=IntegerField()
        )),
        tercera=Sum(Case(
            When(detallecosecha__categoria='tercera', then='detallecosecha__cantidad'),
            default=0, output_field=IntegerField()
        )),
    )

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
    for cosecha in cosechas:
        v = ventas_por_cosecha.get(cosecha.idcosecha, {
            'primera': 0, 'segunda': 0, 'tercera': 0,
            'total': 0, 'cantidad': 0,
        })
        disponible_primera = max((cosecha.primera or 0) - v['primera'], 0)
        disponible_segunda = max((cosecha.segunda or 0) - v['segunda'], 0)
        disponible_tercera = max((cosecha.tercera or 0) - v['tercera'], 0)
        total_cosecha = (cosecha.primera or 0) + (cosecha.segunda or 0) + (cosecha.tercera or 0)
        perdida = disponible_primera + disponible_segunda + disponible_tercera

        ventas_dict[cosecha.idcosecha] = {
            'disponible_primera': disponible_primera,
            'disponible_segunda': disponible_segunda,
            'disponible_tercera': disponible_tercera,
            'total_cosecha': total_cosecha,
            'total_vendido': v['total'],
            'cantidad_ventas': v['cantidad'],
            'perdida': perdida,
        }

    # Agrupamos detalles por cosecha (FUERA del bucle anterior)
    categoria_display = dict(DetalleCosecha.CATEGORIAS)
    tipo_display = dict(DetalleCosecha.OPCIONES)

    detalle_cosechas = DetalleCosecha.objects.select_related('cosecha').values(
        'cosecha_id', 'categoria', 'tipocosecha'
    ).annotate(total=Sum('cantidad'))

    # Agrupar ventas por cosecha y categoría
    ventas_detalle = DetalleVenta.objects.values('cosecha_id', 'categoria').annotate(
        cantidad_vendida=Sum('cantidad')
    )
    ventas_detalle_map = {
        (v['cosecha_id'], v['categoria']): v['cantidad_vendida'] or 0 for v in ventas_detalle
    }

    detalle_por_cosecha = defaultdict(list)
    for d in detalle_cosechas:
        cantidad_cosechada = d['total'] or 0
        cantidad_vendida = ventas_detalle_map.get((d['cosecha_id'], d['categoria']), 0)
        disponibilidad = max(cantidad_cosechada - cantidad_vendida, 0)

        detalle_por_cosecha[d['cosecha_id']].append({
            'categoria': d['categoria'],
            'categoria_display': categoria_display.get(d['categoria'], d['categoria']),
            'tipocosecha': d['tipocosecha'],
            'tipocosecha_display': tipo_display.get(d['tipocosecha'], d['tipocosecha']),
            'cantidad': cantidad_cosechada,
            'cantidad_vendida': cantidad_vendida,
            'disponible': disponibilidad,
        })

    # Paginación
    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(cosechas, 10)
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
        'detalle_por_cosecha': dict(detalle_por_cosecha),  # 👉 lo que usarás en el modal
    })

# Crear una nueva cosecha
@login_required
def crear_cosecha(request):
    plantacion_id = request.GET.get('plantacion_id')
    plantacion = get_object_or_404(Plantacion, idplantacion=plantacion_id) if plantacion_id else None

    if request.method == 'POST':
        form = CosechaForm(request.POST)

        # Obtener los cortes desde el campo oculto en formato JSON
        cortes_json = request.POST.get('cortes_json', '[]')
        try:
            cortes = json.loads(cortes_json)
        except json.JSONDecodeError:
            cortes = []

        if form.is_valid():
            cosecha = form.save()
            messages.success(request, f"La cosecha #{cosecha.idcosecha} ha sido creada exitosamente.")
            # Guardar cada detalle como instancia de DetalleCosecha
            for corte in cortes:
                DetalleCosecha.objects.create(
                    cosecha=cosecha,
                    categoria=corte['categoria'],
                    tipocosecha=corte['tipocosecha'],
                    cantidad=corte['cantidad']
                )

            if request.POST.get('ir_a_venta') == '1':
                return redirect(f"{reverse('crear_venta')}?cosecha_id={cosecha.idcosecha}")

            return redirect('lista_cosechas')
    else:
        form = CosechaForm(initial={'plantacion': plantacion, 'estado': False})

    return render(request, 'Cosecha/form_cosecha.html', {
        'form': form,
        'plantacion': plantacion,
        'categoria_choices': DetalleCosecha.CATEGORIAS,
        'tipocosecha_choices': DetalleCosecha.OPCIONES,
    })

# Editar una cosecha existente
@login_required
def editar_cosecha(request, idcosecha):
    if not request.user.has_perm('gestor.change_cosecha'):
        messages.error(request, "No tienes permiso para editar cosechas.")
        return redirect('inicio') 

    cosecha = get_object_or_404(Cosecha, pk=idcosecha)
    detalles_existentes = DetalleCosecha.objects.filter(cosecha=cosecha)

     # 🔹 Obtenemos la plantación asociada para mostrar en el template
    plantacion = cosecha.plantacion

    # Cantidades vendidas actuales desde DetalleVenta
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
                    cantidad=corte['cantidad']
                )

            if request.POST.get('ir_a_venta') == '1':
                return redirect(f"{reverse('crear_venta')}?cosecha_id={cosecha.idcosecha}")
            return redirect('lista_cosechas')
    else:
        form = CosechaForm(instance=cosecha)

    # Convertimos los detalles existentes a JSON para JS
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
        'detalles_json': detalles_json,  # 🔹 Para inicializar la tabla en JS
        'categoria_choices': DetalleCosecha.CATEGORIAS,
        'tipocosecha_choices': DetalleCosecha.OPCIONES,
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


# VENTAS
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
            messages.success(request, "Venta registrada correctamente.")

            for producto in productos:
                cultivo_id = producto['cultivo_id']
                categoria = producto['categoria'].lower()
                tipo = producto['tipocosecha'].lower()
                cantidad = int(producto['cantidad'])
                subtotal = float(producto['total'])

                cosechas = Cosecha.objects.filter(
                    plantacion_id=cultivo_id,
                    detallecosecha__tipocosecha=tipo,
                    estado=False
                ).distinct().order_by('fecha')

                cantidad_restante = cantidad
                subtotal_unitario = subtotal / cantidad if cantidad > 0 else 0

                for cosecha in cosechas:
                    detalle = DetalleCosecha.objects.filter(
                        cosecha=cosecha,
                        tipocosecha=tipo,
                        categoria=categoria
                    ).first()

                    if not detalle:
                        continue

                    total_cosechado = detalle.cantidad

                    total_vendido = DetalleVenta.objects.filter(
                        cosecha=cosecha,
                        categoria=categoria
                    ).aggregate(total=Sum('cantidad'))['total'] or 0

                    disponible = max(total_cosechado - total_vendido, 0)

                    if disponible <= 0:
                        continue

                    usar = min(cantidad_restante, disponible)

                    DetalleVenta.objects.create(
                        venta=venta,
                        cosecha=cosecha,
                        categoria=categoria,
                        cantidad=usar,
                        subtotal=subtotal_unitario * usar
                    )

                    cantidad_restante -= usar
                    if cantidad_restante <= 0:
                        break

            # 🔁 Verificar si cada cosecha fue completamente vendida
            cosechas_afectadas = Cosecha.objects.filter(estado=False)
            for cosecha in cosechas_afectadas:
                agotada = True
                detalles = DetalleCosecha.objects.filter(cosecha=cosecha)

                for cat in ['primera', 'segunda', 'tercera']:
                    detalle_cat = detalles.filter(categoria=cat).first()
                    if not detalle_cat:
                        continue

                    total_cosechado = detalle_cat.cantidad
                    total_vendido = DetalleVenta.objects.filter(
                        cosecha=cosecha,
                        categoria=cat
                    ).aggregate(total=Sum('cantidad'))['total'] or 0

                    if total_vendido < total_cosechado:
                        agotada = False
                        break

                if agotada:
                    cosecha.estado = True
                    cosecha.save()

            messages.success(request, "Venta registrada correctamente.")
            return redirect('lista_ventas')

        messages.error(request, "Formulario inválido o faltan productos.")

        cultivos = Plantacion.objects.filter(
            idplantacion__in=Cosecha.objects.filter(estado=False).values_list('plantacion_id', flat=True)
        ).distinct()
        tipo_cosecha_opciones = Cosecha.OPCIONES
        cantidades = obtener_disponibilidad_por_cultivo()

        return render(request, 'Venta/form_venta.html', {
            'form': form,
            'cultivos': cultivos,
            'tipo_cosecha_opciones': tipo_cosecha_opciones,
            'cantidades': cantidades,
            'cliente': cliente,
        })

    else:
        form = VentaForm()
        cultivos = Plantacion.objects.filter(
            idplantacion__in=Cosecha.objects.filter(estado=False).values_list('plantacion_id', flat=True)
        ).distinct()
        tipo_cosecha_opciones = DetalleCosecha.OPCIONES
        cantidades = obtener_disponibilidad_por_cultivo()
        print(cantidades)
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

# Editar una venta existente
@login_required
def editar_venta(request, idventa):
    if not request.user.has_perm('gestor.change_venta'):
        messages.error(request, "No tienes permiso para editar ventas.")
        return redirect('inicio')
    venta = get_object_or_404(Venta, pk=idventa)
    cosecha = get_object_or_404(Cosecha, idcosecha=venta.cosecha.idcosecha)

    # Calcular cantidades disponibles
    total_primera = cosecha.primera or 0
    total_segunda = cosecha.segunda or 0
    total_tercera = cosecha.tercera or 0

    # Excluir esta venta actual para calcular correctamente la disponibilidad
    ventas = Venta.objects.filter(cosecha=cosecha).exclude(pk=venta.pk)
    vendida_primera = ventas.aggregate(Sum('primera'))['primera__sum'] or 0
    vendida_segunda = ventas.aggregate(Sum('segunda'))['segunda__sum'] or 0
    vendida_tercera = ventas.aggregate(Sum('tercera'))['tercera__sum'] or 0

    disponible_primera = total_primera - vendida_primera
    disponible_segunda = total_segunda - vendida_segunda
    disponible_tercera = total_tercera - vendida_tercera

    cantidades = {
        'Parcela': cosecha.plantacion.parcela.nombre,
        'Cultivo': cosecha.plantacion.cultivo.nombre,
        'Tipo': cosecha.get_tipocosecha_display(),
        'Primera (disponible)': disponible_primera,
        'Segunda (disponible)': disponible_segunda,
        'Tercera (disponible)': disponible_tercera,
    }

    if request.method == 'POST':
        form = VentaForm(request.POST, instance=venta)
        if form.is_valid():
            nueva_venta = form.save(commit=False)

            errores = []
            if nueva_venta.primera and nueva_venta.primera > disponible_primera:
                errores.append(f"No hay suficiente **primera calidad** disponible. Solo quedan {disponible_primera}.")
            if nueva_venta.segunda and nueva_venta.segunda > disponible_segunda:
                errores.append(f"No hay suficiente **segunda calidad** disponible. Solo quedan {disponible_segunda}.")
            if nueva_venta.tercera and nueva_venta.tercera > disponible_tercera:
                errores.append(f"No hay suficiente **tercera calidad** disponible. Solo quedan {disponible_tercera}.")

            if errores:
                for error in errores:
                    messages.error(request, error)
            else:
                nueva_venta.save()
                messages.success(request, "Venta actualizada correctamente.")
                return redirect('/ventas/')
    else:
        form = VentaForm(instance=venta)

    return render(request, 'Venta/form_venta.html', {
        'form': form,
        'cosechas': cosecha,
        'cantidades': cantidades,
    })

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
        messages.success(request, f"La venta #{venta.idventa} ha sido marcada como pagada.")
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

    return render(request, 'MercadoFormal/entregasformales.html' )

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
        cliente__tipomercado='F'  # 'F' = Formal según tu modelo
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

    return render(request, 'MercadoInformal/entregasinformales.html' )

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
        cliente__tipomercado='I'  # 'F' = Formal según tu modelo
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


#######EMPLEADOS#########
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


#PLANILLAS  

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

    empleados = Empleado.objects.filter(estado=True)
    if buscar:
        empleados = empleados.filter(nombre__icontains=buscar)

    planillas_semana = Planilla.objects.filter(
        fecha__range=(domingo_inicio, sabado_fin)
    ).select_related('empleado')

    planillas_dict = {
        f"{p.empleado.idempleado}_{p.fecha}": p
        for p in planillas_semana
    }

    empleados_data = []
    for empleado in empleados:
        info = {
            'empleado': empleado,
            'dias': [],
            'total_semana': 0.0,
            'total_extra_semana': 0.0
        }

        for i, dia in enumerate(dias_semana):
            key = f"{empleado.idempleado}_{dia}"
            planilla = planillas_dict.get(key)
            
            if planilla:
                if planilla.jornada:
                    pago_dia = float(empleado.salario)
                else:
                    pago_dia = 0.0
                    
                horas_extra = float(planilla.horasextra) if planilla.horasextra else 0.0
                pago_extra_dia = float(planilla.pagoextra) if planilla.pagoextra else 0.0
                
                # Obtener observaciones si existe el campo
                observaciones = ""
                if hasattr(planilla, 'observaciones') and planilla.observaciones:
                    observaciones = planilla.observaciones
                    
            else:
                pago_dia = 0.0
                horas_extra = 0.0
                pago_extra_dia = 0.0
                observaciones = ""

            info['dias'].append({
                'nombre_dia': nombres_dias[i],
                'salario_dia': pago_dia,
                'horas_extra': horas_extra,
                'pago_extra': pago_extra_dia,
                'observaciones': observaciones  # AGREGADO: Incluir observaciones
            })

            info['total_semana'] += pago_dia
            info['total_extra_semana'] += pago_extra_dia

        info['total_general'] = info['total_semana'] + info['total_extra_semana']
        
        # Convertir a JSON con las observaciones incluidas
        info['dias_json'] = json.dumps(info['dias'], cls=DjangoJSONEncoder)

        empleados_data.append(info)

    pagina = request.GET.get("page", 1)
    try:
        paginator = Paginator(empleados_data, 10)
        empleados_paginados = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'Planilla/lista_planilla.html', {
        'empleados_data': empleados_paginados,
        'nombres_dias': nombres_dias,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': request.GET.get('buscar', ''),
        'semana': semana_str,
        'fecha_inicio': domingo_inicio,
        'fecha_fin': sabado_fin,
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
            
            # Obtener todos los empleados activos
            empleados = Empleado.objects.filter(estado=True)
            
            for empleado in empleados:
                # Construir los nombres de los campos para este empleado
                jornada_key = f'empleado_{empleado.idempleado}_jornada'
                horas_key = f'empleado_{empleado.idempleado}_horasextra'
                pago_key = f'empleado_{empleado.idempleado}_pagoextra'
                obs_key = f'empleado_{empleado.idempleado}_observaciones'
                
                # Obtener los valores del POST
                jornada = request.POST.get(jornada_key) == 'on'  # Checkbox
                horas_extra = request.POST.get(horas_key, '0')
                pago_extra = request.POST.get(pago_key, '0')
                observaciones = request.POST.get(obs_key, '').strip()
                
                # Convertir a decimal
                try:
                    horas_extra = float(horas_extra) if horas_extra else 0
                    pago_extra = float(pago_extra) if pago_extra else 0
                except ValueError:
                    horas_extra = 0
                    pago_extra = 0
                
                # Verificar si ya existe una planilla para este empleado en esta fecha
                try:
                    planilla = Planilla.objects.get(empleado=empleado, fecha=fecha_obj)
                    # Actualizar planilla existente
                    planilla.jornada = jornada
                    planilla.horasextra = horas_extra
                    planilla.pagoextra = pago_extra
                    if hasattr(planilla, 'observaciones'):
                        planilla.observaciones = observaciones
                    planilla.save()
                    empleados_actualizados += 1
                    
                except Planilla.DoesNotExist:
                    # Solo crear nueva planilla si hay datos relevantes
                    if jornada or horas_extra > 0 or pago_extra > 0 or observaciones:
                        planilla_data = {
                            'empleado': empleado,
                            'fecha': fecha_obj,
                            'jornada': jornada,
                            'horasextra': horas_extra,
                            'pagoextra': pago_extra,
                        }
                        
                        # Agregar observaciones solo si el campo existe
                        if hasattr(Planilla, 'observaciones'):
                            planilla_data['observaciones'] = observaciones
                            
                        Planilla.objects.create(**planilla_data)
                        empleados_creados += 1
                
                empleados_procesados += 1
                if jornada or horas_extra > 0 or pago_extra > 0 or observaciones:
                    empleados_con_datos += 1
        
        # Mensaje de éxito personalizado
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
        
        return redirect('lista_planilla')  # Redirigir a la lista de planillas
        
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
    return redirect(f"{reverse('agregarplanilla')}?fecha={fecha_str}")

# Vista para obtener planilla de hoy directamente
@login_required
def planilla_hoy(request):
    """Vista para ir directamente a la planilla de hoy"""
    hoy = datetime.now().date().strftime('%Y-%m-%d')
    return redirect(f"{reverse('agregarplanilla')}?fecha={hoy}")

