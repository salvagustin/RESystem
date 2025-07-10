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
from .models import *
from .forms import *
from datetime import datetime, timedelta, date
from django.utils.html import escape
from django.core.paginator import EmptyPage, PageNotAnInteger



horayfecha = datetime.now()
hoy = horayfecha.date()

@login_required
def inicio(request):
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
    dias_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

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
    # Cosechas de hoy agrupadas por categoría
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

    # Cosechas detalladas hoy por cultivo
    cosechas_detalle = DetalleCosecha.objects.filter(
        cosecha__fecha=hoy
    ).select_related('cosecha__plantacion__cultivo')
    
    cosechas_hoy_detalle = defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0})
    for detalle in cosechas_detalle:
        cultivo = detalle.cosecha.plantacion.cultivo.nombre
        cosechas_hoy_detalle[cultivo][detalle.categoria] += detalle.cantidad or 0

    # Cosechas por calidad por día POR CULTIVO (última semana)
    cosechas_por_calidad_y_cultivo = defaultdict(lambda: {
        'primera': [0] * 7,
        'segunda': [0] * 7,
        'tercera': [0] * 7
    })
    cultivos_nombres = set()

    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        detalles_dia = DetalleCosecha.objects.filter(
            cosecha__fecha=dia
        ).select_related('cosecha__plantacion__cultivo')
        
        for detalle in detalles_dia:
            cultivo = detalle.cosecha.plantacion.cultivo.nombre
            categoria = detalle.categoria
            cantidad = detalle.cantidad or 0
            cosechas_por_calidad_y_cultivo[cultivo][categoria][i] += cantidad
            cultivos_nombres.add(cultivo)

    # Compras del día (asumiendo que tienes un modelo similar para compras)
    # Si no tienes compras, puedes quitar esto o dejarlo en 0
    total_compras_hoy = 0  # Aquí puedes agregar la lógica para compras si la tienes

    context = {
        'total_cultivos': total_cultivos,
        'total_plantaciones': total_plantaciones,
        'total_ventas': total_ventas_hoy,  # Solo del día actual
        'total_compras': total_compras_hoy,
        'cosechas_hoy': resumen_hoy,
        'dias_semana': dias_semana,
        'ventas_por_dia': ventas_por_dia,
        'cosechas_hoy_detalle': dict(cosechas_hoy_detalle),
        'clientes': clientes,
        'cosechas': cosechas,
        'calidad_por_cultivo': dict(cosechas_por_calidad_y_cultivo),
        'cultivos_nombres': sorted(cultivos_nombres),
        'plantaciones': plantaciones,
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
    if request.method == 'POST':
        form = PlantacionForm(request.POST, instance=plantacion)
        if form.is_valid():
            form.save()
            return redirect('/plantaciones/')
    else:
        form = PlantacionForm(instance=plantacion)
    return render(request, 'Plantacion/form_plantacion.html', {'form': form})

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

    # Guardamos los valores originales antes del form
    original_primera = cosecha.primera
    original_segunda = cosecha.segunda
    original_tercera = cosecha.tercera
    original_estado = cosecha.estado

    # Cantidades vendidas actuales
    ventas = Venta.objects.filter(cosecha=cosecha).aggregate(
        total_primera=Sum('primera'),
        total_segunda=Sum('segunda'),
        total_tercera=Sum('tercera')
    )
    vendida_primera = ventas['total_primera'] or 0
    vendida_segunda = ventas['total_segunda'] or 0
    vendida_tercera = ventas['total_tercera'] or 0

    if request.method == 'POST':
        form = CosechaForm(request.POST, instance=cosecha)
        if form.is_valid():
            nueva_primera = form.cleaned_data['primera']
            nueva_segunda = form.cleaned_data['segunda']
            nueva_tercera = form.cleaned_data['tercera']

            # Validación: no permitir reducir por debajo de lo vendido
            if (nueva_primera < vendida_primera or
                nueva_segunda < vendida_segunda or
                nueva_tercera < vendida_tercera):
                form.add_error(None, "No puedes poner una cantidad menor a la ya vendida.")
            else:
                aumento = (
                    nueva_primera > original_primera or
                    nueva_segunda > original_segunda or
                    nueva_tercera > original_tercera
                )

                cosecha = form.save(commit=False)

                # ✅ Cambiar estado si estaba finalizado y hay aumento
                if original_estado and aumento:
                    cosecha.estado = False

                cosecha.save()

                if request.POST.get('ir_a_venta') == '1':
                    return redirect(f"{reverse('crear_venta')}?cosecha_id={cosecha.idcosecha}")
                return redirect('lista_cosechas')
    else:
        form = CosechaForm(instance=cosecha)

    return render(request, 'Cosecha/form_cosecha.html', {
        'form': form,
        'vendida_primera': vendida_primera,
        'vendida_segunda': vendida_segunda,
        'vendida_tercera': vendida_tercera,
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
@login_required
def obtener_disponibilidad_por_cultivo():
    cosechas_activas = Cosecha.objects.filter(estado=False)
    disponibilidad = {}

    for cosecha in cosechas_activas:
        cultivo = str(cosecha.plantacion)  # esto será el nombre del cultivo
        detalles_cosecha = DetalleCosecha.objects.filter(cosecha=cosecha)

        # Diccionario temporal para este cultivo
        cultivo_temp = {}

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

            # Solo agregar si hay disponibilidad
            if disponible > 0:
                if tipo not in cultivo_temp:
                    cultivo_temp[tipo] = {'primera': 0, 'segunda': 0, 'tercera': 0}
                
                cultivo_temp[tipo][categoria] += disponible

        # Solo agregar el cultivo si tiene al menos un producto disponible
        if cultivo_temp:
            # Verificar si hay al menos una categoría con disponibilidad > 0
            tiene_disponibilidad = False
            for tipo_data in cultivo_temp.values():
                if any(cantidad > 0 for cantidad in tipo_data.values()):
                    tiene_disponibilidad = True
                    break
            
            if tiene_disponibilidad:
                if cultivo not in disponibilidad:
                    disponibilidad[cultivo] = {}
                
                # Solo agregar tipos que tengan disponibilidad
                for tipo, categorias in cultivo_temp.items():
                    if any(cantidad > 0 for cantidad in categorias.values()):
                        disponibilidad[cultivo][tipo] = categorias

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
