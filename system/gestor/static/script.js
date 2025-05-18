document.addEventListener('DOMContentLoaded', function() {

    // MENU LATERAL
    const menuBtn = document.getElementById('menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');

    menuBtn.addEventListener('click', function() {
        sidebar.classList.add('active');
        overlay.style.display = 'block';
        menuBtn.style.zIndex = 50;
    });

    overlay.addEventListener('click', function() {
        sidebar.classList.remove('active');
        overlay.style.display = 'none';
        menuBtn.style.zIndex = 100;
    });


    // SUBMENÚ ADMINISTRACIÓN
    const adminToggle = document.getElementById('adminToggle');
    if (adminToggle) {
        const dropdownMenu = adminToggle.nextElementSibling;

        adminToggle.addEventListener('click', function (e) {
            e.preventDefault();
            dropdownMenu.style.display = dropdownMenu.style.display === 'block' ? 'none' : 'block';
        });
    }
    // SUBMENÚ ADMINISTRACIÓN MERCADO FORMAL
    const adminToggle2 = document.getElementById('adminToggle2');
    if (adminToggle2) {
        const dropdownMenu2 = adminToggle2.nextElementSibling;

        adminToggle2.addEventListener('click', function (e) {
            e.preventDefault();
            dropdownMenu2.style.display = dropdownMenu2.style.display === 'block' ? 'none' : 'block';
        });
    }


    
    const modalVenta = document.getElementById('modalVenta');
    if (modalVenta) {
        modalVenta.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
    
            const id = button.getAttribute('data-id');
            const cliente = button.getAttribute('data-cliente');
            const parcela = button.getAttribute('data-parcela');
            const cosecha = button.getAttribute('data-cosecha');
            const cosechaId = button.getAttribute('data-cosecha-id');
            const tipo = button.getAttribute('data-tipo');
            const producto = button.getAttribute('data-producto');
            const fecha = button.getAttribute('data-fecha');
            const primera = button.getAttribute('data-primera');
            const segunda = button.getAttribute('data-segunda');
            const tercera = button.getAttribute('data-tercera');
            const total = button.getAttribute('data-total');
            const estado = button.getAttribute('data-estado');
            let estadoTexto = '';

            if (estado === "True") {
                estadoTexto = "Pagado";
            } else if (estado === "False") {
                estadoTexto = "Pendiente";
            }
            document.getElementById('ventaId').textContent = id;
            document.getElementById('ventaCliente').textContent = cliente;
            document.getElementById('ventaParcela').textContent = parcela;
            document.getElementById('ventaCosecha').textContent = cosecha;
            document.getElementById('ventaCosechaId').textContent = cosechaId;
            document.getElementById('ventaTipo').textContent = tipo;
            document.getElementById('ventaProducto').textContent = producto;
            document.getElementById('ventaFecha').textContent = fecha;
            document.getElementById('ventaPrimera').textContent = primera;
            document.getElementById('ventaSegunda').textContent = segunda;
            document.getElementById('ventaTercera').textContent = tercera;
            document.getElementById('ventaTotal').textContent = total;
            document.getElementById('ventaEstado').textContent = estadoTexto;
    
            document.getElementById('btnEditarVenta').href = `/ventas/editar/${id}/`;
            document.getElementById('formEliminarVenta').action = `/ventas/eliminar/${id}/`;
        });
    }


    const modalParcela = document.getElementById('modalParcela');
    if (modalParcela) {
        modalParcela.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
    
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');
            const tipo = button.getAttribute('data-tipo');
            const estado = button.getAttribute('data-estado');
            let estadoTexto = '';

            if (estado === "False") {
                estadoTexto = "Finalizada";
            } else if (estado === "True") {
                estadoTexto = "Activo";
            }
            document.getElementById('parcelaId').textContent = id;
            document.getElementById('parcelaNombre').textContent = nombre;
            document.getElementById('parcelaTipo').textContent = tipo;
            document.getElementById('parcelaEstado').textContent = estadoTexto;
            document.getElementById('parcelaEstado').classList.add(estado === "True" ? 'text-success' : 'text-danger');
    
            document.getElementById('btnEditarParcela').href = `/parcelas/editar/${id}/`;
            document.getElementById('formEliminarParcela').action = `/parcelas/eliminar/${id}/`;
        });
    }


    const modalCultivo = document.getElementById('modalCultivo');
    if (modalCultivo) {
        modalCultivo.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
    
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');
            const variedad = button.getAttribute('data-variedad');
    
            document.getElementById('cultivoId').textContent = id;
            document.getElementById('cultivoNombre').textContent = nombre;
            document.getElementById('cultivoVariedad').textContent = variedad;
    
            document.getElementById('btnEditarCultivo').href = `/cultivos/editar/${id}/`;
            document.getElementById('formEliminarCultivo').action = `/cultivos/eliminar/${id}/`;
        });
    }


    function getCookie(name) {
      let cookieValue = null;
      if (document.cookie && document.cookie !== '') {
          const cookies = document.cookie.split(';');
          for (let cookie of cookies) {
              cookie = cookie.trim();
              if (cookie.startsWith(name + '=')) {
                  cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                  break;
              }
          }
      }
      return cookieValue;
    }

    const modalPlantacion = document.getElementById('modalPlantacion');
    if (modalPlantacion) {
        modalPlantacion.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;

            const id = button.getAttribute('data-id');
            const parcela = button.getAttribute('data-parcela');
            const cultivo = button.getAttribute('data-cultivo');
            const fecha = button.getAttribute('data-fecha');
            const cantidad = button.getAttribute('data-cantidad');
            const estado = button.getAttribute('data-estado'); // "True" o "False"

            let estadoTexto = '';
            const btnToggle = document.getElementById('btnToggleEstadoPlantacion');

            if (estado === "True") {
                estadoTexto = "Activo";
                btnToggle.disabled = false; // habilitar botón
            } else if (estado === "False") {
                estadoTexto = "Finalizado";
                btnToggle.disabled = true; // deshabilitar botón
            }

            document.getElementById('plantacionId').textContent = id;
            document.getElementById('plantacionParcela').textContent = parcela;
            document.getElementById('plantacionCultivo').textContent = cultivo;
            document.getElementById('plantacionFecha').textContent = fecha;
            document.getElementById('plantacionCantidad').textContent = cantidad;
            document.getElementById('plantacionEstado').textContent = estadoTexto;

            document.getElementById('btnEditarPlantacion').href = `/plantaciones/editar/${id}/`;
            document.getElementById('formEliminarPlantacion').action = `/plantaciones/eliminar/${id}/`;

            // Guardar el ID actual para usarlo en el botón de Finalizar
            plantacionIdActual = id;
        });

        // Acción para cambiar estado (Finalizar)
        document.getElementById('btnToggleEstadoPlantacion').addEventListener('click', () => {
            if (!plantacionIdActual) return;

            fetch(`/plantaciones/toggle_estado/${plantacionIdActual}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Accept': 'application/json'
                },
            })
            .then(res => res.json())
            .then(data => {
                if (data.estado !== undefined) {
                    location.reload();
                } else {
                    alert("Error al actualizar estado");
                }
            })
            .catch(() => alert("Fallo en la solicitud al servidor"));
        });
    }

// Botón para ir al formulario de nueva plantación
document.getElementById("btnIrFormulario").addEventListener("click", function () {
    const parcelaId = document.getElementById("selectParcela").value;
    if (parcelaId) {
        window.location.href = `/plantaciones/crear/?parcela_id=${parcelaId}`;
    } else {
        alert("Debes seleccionar una parcela.");
    }
});

let plantacionIdActual = null;


    
    const modalCosecha = document.getElementById('modalCosecha');
    if (modalCosecha) {
        modalCosecha.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
    
            const id = button.getAttribute('data-id');
            const parcela = button.getAttribute('data-parcela');
            const cultivo = button.getAttribute('data-cultivo');
            const plantacion = button.getAttribute('data-plantacion');
            const fecha = button.getAttribute('data-fecha');
            const primera = button.getAttribute('data-primera');
            const segunda = button.getAttribute('data-segunda');
            const tercera = button.getAttribute('data-tercera');
            const estado = button.getAttribute('data-estado');
            const tipocosecha = button.getAttribute('data-tipocosecha');
            const total = parseFloat(primera) + parseFloat(segunda) + parseFloat(tercera);
            const disponiblePrimera = button.getAttribute('data-disponible-primera');
            const disponibleSegunda = button.getAttribute('data-disponible-segunda');
            const disponibleTercera = button.getAttribute('data-disponible-tercera');
    
            document.getElementById('cosechaId').textContent = id;
            document.getElementById('cosechaParcela').textContent = parcela;
            document.getElementById('cosechaCultivo').textContent = cultivo;
            document.getElementById('cosechaPlantacion').textContent = plantacion;
            document.getElementById('cosechaFecha').textContent = fecha;
            document.getElementById('cosechaPrimera').textContent = primera;
            document.getElementById('cosechaSegunda').textContent = segunda;
            document.getElementById('cosechaTercera').textContent = tercera;
            document.getElementById('cosechaEstado').textContent = estado == '1' ? 'Activo' : 'Finalizado';
            document.getElementById('cosechaTipo').textContent = tipocosecha;
            document.getElementById('cosechaTotal').textContent = total.toFixed(2);
            document.getElementById('disponiblePrimera').textContent = disponiblePrimera;
            document.getElementById('disponibleSegunda').textContent = disponibleSegunda;
            document.getElementById('disponibleTercera').textContent = disponibleTercera;

    
            document.getElementById('btnEditarCosecha').href = `/cosechas/editar/${id}/`;
            document.getElementById('formEliminarCosecha').action = `/cosechas/eliminar/${id}/`;
        });
    }


    const modalCliente = document.getElementById('modalCliente');
    if (modalCliente) {
        modalCliente.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
    
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');
            const telefono = button.getAttribute('data-telefono');
            const tipocliente = button.getAttribute('data-tipocliente');
    
            document.getElementById('clienteId').textContent = id;
            document.getElementById('clienteNombre').textContent = nombre;
            document.getElementById('clienteTelefono').textContent = telefono;
            document.getElementById('clienteTipo').textContent = tipocliente;
    
            document.getElementById('btnEditarCliente').href = `/clientes/editar/${id}/`;
            document.getElementById('formEliminarCliente').action = `/clientes/eliminar/${id}/`;
        });
    }


    



    
  //GRAFICOS
  const ctxVentas = document.getElementById("ventasSemanaChart").getContext("2d");
  const ctxCalidad = document.getElementById("graficoCalidad").getContext("2d");

  const ventasChart = new Chart(ctxVentas, {
    type: 'bar',
    data: {
      labels: window.diasSemana,
      datasets: [{
        label: 'Ventas ($)',
        data: window.ventasPorDia,
        backgroundColor: 'rgba(0, 123, 255, 0.5)',
        borderColor: 'rgba(0, 123, 255, 1)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: { beginAtZero: true }
      }
    }
  });

  let calidadChart;

  function renderCalidadChart(cultivo) {
    const data = window.calidadPorCultivo[cultivo];

    if (!data) {
      console.warn("No hay datos para:", cultivo);
      return;
    }

    const nuevaData = {
      labels: window.diasSemana,
      datasets: [
        {
          label: 'Primera',
          data: data.primera,
          borderColor: 'green',
          backgroundColor: 'rgba(0,128,0,0.1)',
          fill: true
        },
        {
          label: 'Segunda',
          data: data.segunda,
          borderColor: 'blue',
          backgroundColor: 'rgba(0,0,255,0.1)',
          fill: true
        },
        {
          label: 'Tercera',
          data: data.tercera,
          borderColor: 'orange',
          backgroundColor: 'rgba(255,165,0,0.1)',
          fill: true
        }
      ]
    };

    if (calidadChart) {
      calidadChart.destroy();
    }

    calidadChart = new Chart(ctxCalidad, {
      type: 'line',
      data: nuevaData,
      options: {
        responsive: true,
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  }

  // Inicializar con el primer cultivo
  const select = document.getElementById("selectCultivo");
  if (select && select.value) {
    renderCalidadChart(select.value);
  }

  select.addEventListener("change", function () {
    renderCalidadChart(this.value);
  });







  });

