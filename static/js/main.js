/**
 =========================================================================
 SISTEMA DE CONTROL DE ASISTENCIA Y CÁLCULO DE NÓMINAS
 Módulo principal para la interfaz de usuario y generación de reportes
 =========================================================================
 */

let estaCargando = false;

// =========================================================================
// PARTE 1: CONFIGURACIÓN INICIAL (FLATPICKR)
// =========================================================================

document.addEventListener('DOMContentLoaded', () => {
    const configCalendario = {
        locale: "es",
        dateFormat: "Y-m-d",
        disableMobile: "true",
        animate: true,
        position: "below center",
        monthSelectorType: "static",
        static: true,
        showMonths: 1
    };

    flatpickr("#inicio", {
        ...configCalendario,
        defaultDate: new Date().fp_incr(-15)
    });

    flatpickr("#fin", {
        ...configCalendario,
        defaultDate: new Date()
    });
});

// =========================================================================
// PARTE 2: UTILIDADES DE INTERFAZ
// =========================================================================

// -------------------------------------------------------------------------
// 2.1 MOSTRAR MENSAJES DE ERROR
// -------------------------------------------------------------------------

function mostrarError(msg) {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div'); 
    t.className = 'toast';
    t.innerHTML = `<span>${msg}</span>`; 
    c.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

// -------------------------------------------------------------------------
// 2.2 CAMBIAR ENTRE PESTAÑAS (NÓMINA / LOGS)
// -------------------------------------------------------------------------

function cambiarTab(tipo) {
    const tNomina = document.getElementById('tab-nomina');
    const tLogs = document.getElementById('tab-logs');
    const bNomina = document.getElementById('btn-tab-nomina');
    const bLogs = document.getElementById('btn-tab-logs');

    if(tipo === 'nomina') {
        tNomina.classList.remove('hidden'); 
        tLogs.classList.add('hidden');
        bNomina.classList.add('active'); 
        bLogs.classList.remove('active');
    } else {
        tNomina.classList.add('hidden'); 
        tLogs.classList.remove('hidden');
        bNomina.classList.remove('active'); 
        bLogs.classList.add('active');
    }
}

// -------------------------------------------------------------------------
// 2.3 RENDERIZAR NÚMEROS CON ALINEACIÓN DE DECIMALES
// -------------------------------------------------------------------------

function renderNumber(valor, showCurrency = false) {
    if (valor === null || valor === undefined || valor === "") {
        valor = "0.00";
    }
    let limpio = valor.toString().replace(/[$, ]/g, '');
    let numero = parseFloat(limpio);
    if (isNaN(numero)) numero = 0;
    let formateado = numero.toFixed(2);
    let texto = showCurrency ? `$${formateado}` : formateado;
    let clase = showCurrency ? 'money' : 'money money-number';
    return `<div class="${clase}">${texto}</div>`;
}

// =========================================================================
// PARTE 3: LÓGICA PRINCIPAL DE REPORTE
// =========================================================================

async function generarReporte() {
    if (estaCargando) return;

    // -------------------------------------------------------------------------
    // 3.1 RECOLECTAR DATOS DEL FORMULARIO
    // -------------------------------------------------------------------------
    
    const payload = {
        nombre: document.getElementById('nombre').value.trim(),
        pago: document.getElementById('pago').value,
        bono: document.getElementById('bono').value,
        inicio: document.getElementById('inicio').value,
        fin: document.getElementById('fin').value
    };

    // -------------------------------------------------------------------------
    // 3.2 VALIDAR CAMPOS OBLIGATORIOS
    // -------------------------------------------------------------------------
    
    if (!payload.nombre) return mostrarError("Nombre de empleado obligatorio");
    if (!payload.pago || parseFloat(payload.pago) <= 0) return mostrarError("Costo hora debe ser mayor a 0");
    if (payload.bono === "" || parseFloat(payload.bono) < 0) return mostrarError("Bono inválido");
    if (!payload.inicio || !payload.fin) return mostrarError("Seleccione un rango de fechas");

    // -------------------------------------------------------------------------
    // 3.3 MOSTRAR ESTADO DE CARGA
    // -------------------------------------------------------------------------
    
    estaCargando = true;
    document.getElementById('btn-text').classList.add('oculto');
    document.getElementById('btn-loader').classList.remove('oculto');

    try {
        // ---------------------------------------------------------------------
        // 3.4 ENVIAR SOLICITUD AL BACKEND
        // ---------------------------------------------------------------------
        
        const res = await fetch('/consultar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        if (data.resumen.length === 0) throw new Error("No se encontraron registros");

        // ---------------------------------------------------------------------
        // 3.5 RENDERIZAR TABLA DE NÓMINA
        // ---------------------------------------------------------------------
        
        let htmlContenido = data.resumen.map(r => `
            <tr>
                <td>${r.fecha}</td>
                <td>${r.neto}</td>
                <td class="num">${renderNumber(r.horas_decimal)}</td>
                <td class="monto">${renderNumber(r.pago_horas, true)}</td>
                <td class="bono">${renderNumber(r.bono, true)}</td>
                <td class="monto">${renderNumber(r.total, true)}</td>
            </tr>
        `).join('');

        document.getElementById('body-nomina').innerHTML = htmlContenido;

        // ---------------------------------------------------------------------
        // 3.6 RENDERIZAR TOTALES DEL PIE DE PÁGINA
        // ---------------------------------------------------------------------
        
        const t = data.totales_pie;
        document.getElementById('t-tiempo').textContent = t.tiempo;
        document.getElementById('t-decimal').innerHTML = renderNumber(t.decimal);
        document.getElementById('t-pago').innerHTML = renderNumber(t.pago_h, true);
        document.getElementById('t-bono').innerHTML = renderNumber(t.bonos, true);
        document.getElementById('t-total').innerHTML = renderNumber(t.general, true);
        
        // ---------------------------------------------------------------------
        // 3.7 RENDERIZAR TABLA DE LOGS
        // ---------------------------------------------------------------------
        
        document.getElementById('body-detalles').innerHTML = data.detalles.map(d => `
            <tr>
                <td>${d.id}</td>
                <td>${d.nombre}</td>
                <td>${d.fh}</td>
            </tr>
        `).join('');

        // ---------------------------------------------------------------------
        // 3.8 ACTUALIZAR INTERFAZ
        // ---------------------------------------------------------------------
        
        document.getElementById('seccion-filtros').classList.add('hidden');
        document.getElementById('seccion-resultados').classList.remove('hidden');
        
        cambiarTab('nomina');

    } catch (e) {
        // ---------------------------------------------------------------------
        // 3.9 MANEJO DE ERRORES
        // ---------------------------------------------------------------------
        
        mostrarError(e.message || "Error de conexión");
    } finally {
        // ---------------------------------------------------------------------
        // 3.10 RESTAURAR ESTADO DEL BOTÓN
        // ---------------------------------------------------------------------
        
        estaCargando = false;
        document.getElementById('btn-text').classList.remove('oculto');
        document.getElementById('btn-loader').classList.add('oculto');
    }
}