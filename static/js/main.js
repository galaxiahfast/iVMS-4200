let estaCargando = false;

// Configuración inicial de fechas con Flatpickr
document.addEventListener('DOMContentLoaded', () => {
    // Configuración refinada para un calendario compacto y centrado
        const configCalendario = {
        locale: "es",
        dateFormat: "Y-m-d",
        disableMobile: "true",
        animate: true,
        position: "below center",
        ignoredFocusElements: [], 
        monthSelectorType: "static",
        // --- ESTAS DOS SON LA SOLUCIÓN ---
        static: true,             // El calendario se renderiza justo después del input
        showMonths: 1             // Evita que intente calcular anchos para múltiples meses
    };

    // Inicializar el calendario "Desde" (hace 7 días)
    flatpickr("#inicio", {
        ...configCalendario,
        defaultDate: new Date().fp_incr(-7)
    });

    // Inicializar el calendario "Hasta" (hoy)
    flatpickr("#fin", {
        ...configCalendario,
        defaultDate: new Date()
    });
});

function mostrarError(msg) {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div'); t.className = 'toast';
    t.innerHTML = `<span>${msg}</span>`; c.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

function cambiarTab(tipo) {
    const tNomina = document.getElementById('tab-nomina');
    const tLogs = document.getElementById('tab-logs');
    const bNomina = document.getElementById('btn-tab-nomina');
    const bLogs = document.getElementById('btn-tab-logs');

    if(tipo === 'nomina') {
        tNomina.classList.remove('hidden'); tLogs.classList.add('hidden');
        bNomina.classList.add('active'); bLogs.classList.remove('active');
    } else {
        tNomina.classList.add('hidden'); tLogs.classList.remove('hidden');
        bNomina.classList.remove('active'); bLogs.classList.add('active');
    }
}

async function generarReporte() {
    if (estaCargando) return;

    const payload = {
        nombre: document.getElementById('nombre').value.trim(),
        pago: document.getElementById('pago').value,
        bono: document.getElementById('bono').value,
        inicio: document.getElementById('inicio').value,
        fin: document.getElementById('fin').value
    };

    // Validaciones básicas
    if (!payload.nombre) return mostrarError("Nombre de empleado obligatorio");
    if (!payload.pago || parseFloat(payload.pago) <= 0) return mostrarError("Costo hora debe ser mayor a 0");
    if (payload.bono === "" || parseFloat(payload.bono) < 0) return mostrarError("Bono inválido");
    if (!payload.inicio || !payload.fin) return mostrarError("Seleccione un rango de fechas");

    estaCargando = true;
    document.getElementById('btn-text').classList.add('oculto');
    document.getElementById('btn-loader').classList.remove('oculto');

    try {
        const res = await fetch('/consultar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        if (data.resumen.length === 0) throw new Error("No se encontraron registros");

        // --- RENDERIZAR TABLA DE NÓMINA (Actualizada con Pago Horas) ---
        document.getElementById('body-nomina').innerHTML = data.resumen.map(r => `
            <tr>
                <td><b>${r.fecha}</b></td>
                <td>${r.neto}</td>
                <td>${r.horas_decimal}</td>
                <td class="text-blue">${r.pago_horas}</td> <td class="text-green">${r.bono}</td>
                <td><b>${r.total}</b></td>
            </tr>
        `).join('');
        
        // --- MOSTRAR TOTALES (Neto vs Con Bonos) ---
        // Creamos un HTML con ambos totales para mayor claridad
        document.getElementById('total-general').innerHTML = `
            <div style="font-size: 0.8em; color: #666;">Total solo horas: ${data.total_solo_horas}</div>
            <div style="color: #2c3e50;">TOTAL A PAGAR: ${data.total_general}</div>
        `;

        // Renderizar tabla de Logs de Marcaje (Se mantiene igual)
        document.getElementById('body-detalles').innerHTML = data.detalles.map(d => `
            <tr><td>${d.fh}</td><td>ID: ${d.id}</td><td>${d.nombre}</td></tr>
        `).join('');

        document.getElementById('seccion-filtros').classList.add('hidden');
        document.getElementById('seccion-resultados').classList.remove('hidden');

    } catch (e) {
        mostrarError(e.message || "Error de conexión");
    } finally {
        estaCargando = false;
        document.getElementById('btn-text').classList.remove('oculto');
        document.getElementById('btn-loader').classList.add('oculto');
    }
}