from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.db.models import Sum, Count, DecimalField
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, permission_required
from collections import defaultdict
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import logout
from django.core.paginator import Paginator
from django.urls import reverse
from django.db.models.functions import ExtractMonth, Coalesce
from django.db.models.expressions import RawSQL
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.shortcuts import render
from collections import defaultdict
from .models import *
from .forms import *
from datetime import datetime, timedelta, date



horayfecha = datetime.now()
hoy = horayfecha.date()

@login_required
def inicio(request):
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
    dias_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    
    total_cultivos = Cultivo.objects.count()
    total_plantaciones = Plantacion.objects.count()
    total_ventas = Venta.objects.filter(fecha=hoy).aggregate(Sum('total')).get('total__sum') or 0
    plantaciones = Plantacion.objects.filter(estado=0)
    cosechas = Cosecha.objects.filter(estado=0)
    
    cosechas_hoy = Cosecha.objects.filter(fecha=hoy).aggregate(
        primera=Sum('primera'),
        segunda=Sum('segunda'),
        tercera=Sum('tercera')
    )
    
    # Ventas por día de la semana
    ventas_por_dia = [0] * 7
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        total_dia = Venta.objects.filter(fecha=dia).aggregate(Sum('total')).get('total__sum') or 0
        ventas_por_dia[i] = float(total_dia)
    
    # Cosechas detalladas hoy
    cosechas_detalle = Cosecha.objects.filter(fecha=hoy).select_related('plantacion')
    cosechas_hoy_detalle = defaultdict(lambda: {'primera': 0, 'segunda': 0, 'tercera': 0})
    for c in cosechas_detalle:
        cultivo = c.plantacion.cultivo.nombre
        cosechas_hoy_detalle[cultivo]['primera'] += c.primera or 0
        cosechas_hoy_detalle[cultivo]['segunda'] += c.segunda or 0
        cosechas_hoy_detalle[cultivo]['tercera'] += c.tercera or 0
    
    # Cosechas por calidad por día POR CULTIVO (ya está bien)
    cosechas_por_calidad_y_cultivo = defaultdict(lambda: {
        'primera': [0] * 7,
        'segunda': [0] * 7,
        'tercera': [0] * 7
    })
    cultivos_nombres = set()
    
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        cosechas_dia = Cosecha.objects.filter(fecha=dia).select_related('plantacion__cultivo')
        for c in cosechas_dia:
            cultivo = c.plantacion.cultivo.nombre
            cultivos_nombres.add(cultivo)
            cosechas_por_calidad_y_cultivo[cultivo]['primera'][i] += c.primera or 0
            cosechas_por_calidad_y_cultivo[cultivo]['segunda'][i] += c.segunda or 0
            cosechas_por_calidad_y_cultivo[cultivo]['tercera'][i] += c.tercera or 0
    
    context = {
        'total_cultivos': total_cultivos,
        'total_plantaciones': total_plantaciones,
        'total_ventas': total_ventas,
        'cosechas_hoy': cosechas_hoy,
        'dias_semana': dias_semana,  # Importante: pasar los días al template
        'ventas_por_dia': ventas_por_dia,
        'cosechas_hoy_detalle': dict(cosechas_hoy_detalle),
        'plantaciones': plantaciones,
        'cosechas': cosechas,
        'calidad_por_cultivo': dict(cosechas_por_calidad_y_cultivo),
        'cultivos_nombres': sorted(cultivos_nombres),
    }
    return render(request, 'index.html', context)

@login_required
def salir(request):
    logout(request)
    return redirect('login.html')

@login_required
def dashboard_view(request):
    return render(request, 'reportes.html')





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

    # Agregar información relacionada a cada parcela
    parcelas_data = []
    for parcela in parcelas:
        plantaciones = Plantacion.objects.filter(parcela=parcela)
        cultivos = list(set([f"{p.cultivo.nombre} ({p.cultivo.variedad})" for p in plantaciones]))
        total_plantas = plantaciones.aggregate(total=Sum('cantidad'))['total'] or 0

        cosechas = Cosecha.objects.filter(plantacion__in=plantaciones)
        total_cosechas = cosechas.count()

        total_vendido = Venta.objects.filter(cosecha__in=cosechas).aggregate(total=Sum('total'))['total'] or 0

        parcelas_data.append({
            'parcela': parcela,
            'cultivos': cultivos,
            'total_plantas': total_plantas,
            'total_cosechas': total_cosechas,
            'total_vendido': total_vendido,
        })

    # Paginación manual para datos procesados
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
        ventas = Venta.objects.filter(cosecha__plantacion__cultivo=cultivo)

        total_plantas = plantaciones.aggregate(total=Coalesce(Sum('cantidad'), 0))['total']
        total_cosechas = cosechas.aggregate(total=Count('idcosecha'))['total']        
        total_vendido = ventas.aggregate(
                                total=Coalesce(Sum('total'), 0, output_field=DecimalField())
                            )['total']

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

    # Anotar datos adicionales antes de paginar
    for plantacion in plantaciones:
        cosechas = plantacion.cosecha_set.all()
        plantacion.num_cosechas = cosechas.count()

        ventas = Venta.objects.filter(cosecha__in=cosechas)
        plantacion.total_vendido = ventas.aggregate(
            total=Coalesce(Sum('total'), Decimal('0.00'))
        )['total']

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
    ventas = Venta.objects.all().select_related('cosecha')

    # Preprocesar ventas por cosecha usando diccionarios agrupados por idcosecha
    ventas_por_cosecha = {}
    for venta in ventas:
        cid = venta.cosecha_id
        if cid not in ventas_por_cosecha:
            ventas_por_cosecha[cid] = {
                'primera': 0,
                'segunda': 0,
                'tercera': 0,
                'total': 0,
                'cantidad': 0,
            }
        ventas_por_cosecha[cid]['primera'] += venta.primera or 0
        ventas_por_cosecha[cid]['segunda'] += venta.segunda or 0
        ventas_por_cosecha[cid]['tercera'] += venta.tercera or 0
        ventas_por_cosecha[cid]['total'] += venta.total or 0
        ventas_por_cosecha[cid]['cantidad'] += 1

    # Crear diccionario de ventas para el template
    ventas_dict = {}
    for cosecha in cosechas:
        v = ventas_por_cosecha.get(cosecha.idcosecha, {
            'primera': 0,
            'segunda': 0,
            'tercera': 0,
            'total': 0,
            'cantidad': 0,
        })

        total_cosecha = (cosecha.primera or 0) + (cosecha.segunda or 0) + (cosecha.tercera or 0)
        total_vendido = v['total']
        # Calcula disponibles
        disponible_primera = max((cosecha.primera or 0) - v['primera'], 0)
        disponible_segunda = max((cosecha.segunda or 0) - v['segunda'], 0)
        disponible_tercera = max((cosecha.tercera or 0) - v['tercera'], 0)

        # Perdida total = todo lo no vendido
        perdida = disponible_primera + disponible_segunda + disponible_tercera

        # Diccionario que pasas al template
        ventas_dict[cosecha.idcosecha] = {
            'disponible_primera': disponible_primera,
            'disponible_segunda': disponible_segunda,
            'disponible_tercera': disponible_tercera,
            'total_cosecha': (cosecha.primera or 0) + (cosecha.segunda or 0) + (cosecha.tercera or 0),
            'total_vendido': v['total'],
            'cantidad_ventas': v['cantidad'],
            'perdida': perdida,  # 👈 Aquí ya tienes el número único de pérdida
        }



    # Filtro por texto
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
                    cosechas = cosechas.filter(tipocosecha=val)
                    break
        elif filtro == 'estado':
            if buscar in ['finalizado', 'true', '1', 'sí', 'si']:
                cosechas = cosechas.filter(estado=True)
            elif buscar in ['activo', 'no finalizado', 'false', '0', 'no']:
                cosechas = cosechas.filter(estado=False)

    # Filtro por fechas
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
    })

# Crear una nueva cosecha
@login_required
def crear_cosecha(request):
    plantacion_id = request.GET.get('plantacion_id')
    plantacion = None

    if request.method == 'POST':
        form = CosechaForm(request.POST)
        if form.is_valid():
            cosecha = form.save()
            if request.POST.get('ir_a_venta') == '1':
                return redirect(f"{reverse('crear_venta')}?cosecha_id={cosecha.idcosecha}")
            return redirect('lista_cosechas')  # Asegúrate de tener este nombre de URL
    else:
        if plantacion_id:
            plantacion = get_object_or_404(Plantacion, idplantacion=plantacion_id)
            form = CosechaForm(initial={'plantacion': plantacion})
        else:
            form = CosechaForm()

    return render(request, 'Cosecha/form_cosecha.html', {
        'form': form,
        'plantacion': plantacion
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
        if Venta.objects.filter(cosecha=cosecha).exists():
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
    buscar = request.GET.get('buscar', '')

    clientes = Cliente.objects.all().order_by('nombre')

    if buscar:
        buscar = buscar.strip().lower()
        if filtro == 'nombre':
            clientes = clientes.filter(nombre__icontains=buscar)
        elif filtro == 'telefono':
            clientes = clientes.filter(telefono__icontains=buscar)
        elif filtro == 'tipo':
            if buscar in ['comprador', 'c']:
                clientes = clientes.filter(tipocliente='C')
            elif buscar in ['proveedor', 'p']:
                clientes = clientes.filter(tipocliente='P')

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
        'buscar': request.GET.get('buscar', '')
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



# Mostrar lista de ventas
@login_required
def lista_ventas(request):
    filtro = request.GET.get('filtro', 'cliente')
    buscar = request.GET.get('buscar', '').strip().lower()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    cosechas = Cosecha.objects.filter(estado=0).order_by('-fecha')
    ventas = Venta.objects.select_related('cosecha__plantacion__parcela', 'cosecha__plantacion__cultivo', 'cliente').order_by('-idventa')

    # Filtro por texto
    if buscar:
        if filtro == 'parcela':
            ventas = ventas.filter(cosecha__plantacion__parcela__nombre__icontains=buscar)
        elif filtro == 'producto' or filtro == 'cultivo':
            ventas = ventas.filter(cosecha__plantacion__cultivo__nombre__icontains=buscar)
        elif filtro == 'cosecha':
            ventas = ventas.filter(cosecha__idcosecha__icontains=buscar)  # Asegúrate de tener campo 'nombre' en Cosecha
        elif filtro == 'cliente':
            ventas = ventas.filter(cliente__nombre__icontains=buscar)
        elif filtro == 'tipoventa':
            tipo_map = {
                'contado': 'C',
                'crédito': 'D',
                'credito': 'D'
            }
            for key, val in tipo_map.items():
                if buscar in key:
                    ventas = ventas.filter(tipoventa=val)
                    break
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
    try:
        paginator = Paginator(ventas, 10)
        ventas_paginadas = paginator.page(pagina)
    except:
        raise Http404("Página no encontrada")

    return render(request, 'Venta/lista_ventas.html', {
        'entity': ventas_paginadas,
        'paginator': paginator,
        'filtro': filtro,
        'buscar': buscar,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'cosechas': cosechas,
    })

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

@login_required
def crear_venta(request):
    cosecha_id = request.GET.get('cosecha_id')
    cosecha = None

    if cosecha_id:
        cosecha = get_object_or_404(Cosecha, idcosecha=cosecha_id)

    if request.method == 'POST':
        form = VentaForm(request.POST)
        if form.is_valid():
            venta = form.save(commit=False)
            if not venta.cosecha:
                venta.cosecha = cosecha

            # Obtener datos de disponibilidad
            total_primera = venta.cosecha.primera or 0
            total_segunda = venta.cosecha.segunda or 0
            total_tercera = venta.cosecha.tercera or 0

            # Excluir la venta actual si es edición
            ventas = Venta.objects.filter(cosecha=venta.cosecha)
            if venta.pk:
                ventas = ventas.exclude(pk=venta.pk)

            vendida_primera = ventas.aggregate(Sum('primera'))['primera__sum'] or 0
            vendida_segunda = ventas.aggregate(Sum('segunda'))['segunda__sum'] or 0
            vendida_tercera = ventas.aggregate(Sum('tercera'))['tercera__sum'] or 0

            disponible_primera = total_primera - vendida_primera
            disponible_segunda = total_segunda - vendida_segunda
            disponible_tercera = total_tercera - vendida_tercera

            errores = []
            if venta.primera and venta.primera > disponible_primera:
                errores.append(f"No hay suficiente **primera calidad** disponible. Solo quedan {disponible_primera}.")
            if venta.segunda and venta.segunda > disponible_segunda:
                errores.append(f"No hay suficiente **segunda calidad** disponible. Solo quedan {disponible_segunda}.")
            if venta.tercera and venta.tercera > disponible_tercera:
                errores.append(f"No hay suficiente **tercera calidad** disponible. Solo quedan {disponible_tercera}.")
            print(errores)
            if errores:
                for error in errores:
                    messages.error(request, error)
            else:
                venta.save()
                messages.success(request, "Venta guardada exitosamente.")
                return redirect('lista_ventas')
    else:
        if cosecha:
            form = VentaForm(initial={'cosecha': cosecha.idcosecha})
        else:
            form = VentaForm()

    cantidades = {}
    if cosecha:
        total_primera = cosecha.primera or 0
        total_segunda = cosecha.segunda or 0
        total_tercera = cosecha.tercera or 0

        ventas = Venta.objects.filter(cosecha=cosecha)
        vendida_primera = ventas.aggregate(Sum('primera'))['primera__sum'] or 0
        vendida_segunda = ventas.aggregate(Sum('segunda'))['segunda__sum'] or 0
        vendida_tercera = ventas.aggregate(Sum('tercera'))['tercera__sum'] or 0

        cantidades = {
            'Parcela': cosecha.plantacion.parcela.nombre,
            'Cultivo': cosecha.plantacion.cultivo.nombre,
            'Tipo': cosecha.get_tipocosecha_display(),
            'Primera (disponible)': total_primera - vendida_primera,
            'Segunda (disponible)': total_segunda - vendida_segunda,
            'Tercera (disponible)': total_tercera - vendida_tercera,
        }

    return render(request, 'Venta/form_venta.html', {
        'form': form,
        'cantidades': cantidades,
    })


# API para obtener datos por categoría de una cosecha
@login_required
def info_cosecha_api(request, cosecha_id):
    try:
        cosecha = Cosecha.objects.get(pk=cosecha_id)
        data = {
            'primera': cosecha.primera,
            'segunda': cosecha.segunda,
            'tercera': cosecha.tercera,
            'rechazo': cosecha.rechazo
        }
        return JsonResponse(data)
    except Cosecha.DoesNotExist:
        return JsonResponse({'error': 'Cosecha no encontrada'}, status=404)


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