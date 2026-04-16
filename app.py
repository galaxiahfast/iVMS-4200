"""
SISTEMA DE CONTROL DE ASISTENCIA Y CÁLCULO DE NÓMINAS
Módulo principal para la gestión de marcaciones y generación de reportes

-- 1. Crear la base de datos
CREATE DATABASE IF NOT EXISTS control_asistencia;
USE control_asistencia;

-- 2. Crear la tabla según las especificaciones de la imagen
CREATE TABLE IF NOT EXISTS control_de_horas (
    -- Identificador del empleado (ID)
    employeeID VARCHAR(50) NOT NULL,
    
    -- Nombre del personal (Person Name)
    personName VARCHAR(255),
    
    -- Fecha y Hora de Autenticación (Authentication Date and Time)
    -- Usamos DATETIME como formato base
    authDateTime DATETIME NOT NULL,
    
    -- Fecha de Autenticación (Authentication Date)
    authDate DATE,
    
    -- Hora de Autenticación (Authentication Time)
    authTime TIME,
    
    -- Dirección (Direction: Enter IN / Exit OUT)
    direction VARCHAR(10),
    
    -- Nombre del Dispositivo (Device Name)
    deviceName VARCHAR(255),
    
    -- Número de Serie del Dispositivo (Device Serial No.)
    deviceSN VARCHAR(100),
    
    -- Número de Tarjeta (Card No.)
    cardNo VARCHAR(50),
    
    -- LLAVE PRIMARIA COMPUESTA:
    -- Evita que se repita el mismo marcaje para el mismo empleado en el mismo segundo
    PRIMARY KEY (employeeID, authDateTime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

from flask import Flask, render_template, request, jsonify
import mysql.connector
from datetime import datetime
import unicodedata
from decimal import Decimal, getcontext, ROUND_HALF_UP

# =========================================================================
# CONFIGURACIÓN INICIAL
# =========================================================================

app = Flask(__name__)

# Precisión global suficiente para cálculos monetarios
getcontext().prec = 28

# Configuración de conexión a base de datos MySQL
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "control_asistencia"
}

# =========================================================================
# FUNCIONES AUXILIARES
# =========================================================================

def normalizar_texto(texto):
    """
    Elimina tildes y convierte a minúsculas para un filtrado preciso.
    
    PARÁMETROS:
        texto: str - Texto a normalizar
    
    RETORNA:
        str - Texto normalizado sin acentos y en minúsculas
    """
    if not texto: return ""
    texto = str(texto).lower()
    return "".join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

def formatear_h(seg):
    """
    Convierte segundos a formato legible HH:MM:SS.
    
    PARÁMETROS:
        seg: int/float - Cantidad de segundos a formatear
    
    RETORNA:
        str - Tiempo formateado como "02h 15m 30s"
    """
    if seg <= 0: return "00h 00m 00s"
    h = int(seg // 3600)
    m = int((seg % 3600) // 60)
    s = int(seg % 60)
    return f"{h:02d}h {m:02d}m {s:02d}s"

# =========================================================================
# RUTAS PRINCIPALES
# =========================================================================

@app.route('/')
def index():
    """
    Ruta principal que carga la interfaz de usuario.
    
    RETORNA:
        template: Renderiza el archivo index.html
    """
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])
def consultar():
    """
    Endpoint principal para el cálculo de nóminas.
    
    PROCESO:
        PARTE 1: RECEPCIÓN DE DATOS DEL FORMULARIO
        PARTE 2: CONSULTA A BASE DE DATOS MySQL
        PARTE 3: FILTRADO Y PREPARACIÓN DE DATOS
        PARTE 4: PROCESAMIENTO DE NÓMINA
            4.1 INICIALIZAR ACUMULADORES (TOTALES DEL PERÍODO)
            4.2 PROCESAR DÍA POR DÍA (CÁLCULOS INDIVIDUALES)
                4.2.1 CALCULAR TIEMPO TRABAJADO DEL DÍA (POR PARES ENTRADA-SALIDA)
                4.2.2 CONVERTIR A HORAS DECIMALES DEL DÍA
                4.2.3 CALCULAR PAGO POR HORAS DEL DÍA
                4.2.4 CALCULAR BONO DEL DÍA
                4.2.5 CALCULAR TOTAL DEL DÍA
                4.2.6 GUARDAR EN RESUMEN DEL DÍA
            4.3 ACUMULAR PARA TOTALES DEL PERÍODO
            4.4 TOTALES FINALES DEL PERÍODO
        PARTE 5: ENVÍO DE RESPUESTA AL FRONTEND
    
    RETORNA:
        JSON: Objeto con detalles, resumen de nómina y totales
    """
    
    # =========================================================================
    # PARTE 1: RECEPCIÓN DE DATOS DEL FORMULARIO
    # =========================================================================

    datos = request.json
    
    nombre_buscado = normalizar_texto(datos['nombre'])
    pago_h = Decimal(datos['pago'])
    bono_c = Decimal(datos['bono'])
    inicio = datos['inicio']
    fin = datos['fin']
    
    # =========================================================================
    # PARTE 2: CONSULTA A BASE DE DATOS MySQL
    # =========================================================================

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT personName, employeeID, authDateTime, authDate 
            FROM control_de_horas 
            WHERE authDate BETWEEN %s AND %s
            ORDER BY authDateTime ASC
        """
        cursor.execute(query, (inicio, fin))
        registros_crudos = cursor.fetchall()
        
        # =========================================================================
        # PARTE 3: FILTRADO Y PREPARACIÓN DE DATOS
        # =========================================================================

        filtrados = []
        dias_dict = {}
        
        for reg in registros_crudos:
            nom_norm = normalizar_texto(reg['personName'])
            if nombre_buscado in nom_norm:
                filtrados.append({
                    'fh': str(reg['authDateTime']),
                    'id': reg['employeeID'],
                    'nombre': reg['personName']
                })
                f_solo = str(reg['authDate'])
                dias_dict.setdefault(f_solo, []).append(reg['authDateTime'])
        
        # =========================================================================
        # PARTE 4: PROCESAMIENTO DE NÓMINA
        # =========================================================================
        
        # -------------------------------------------------------------------------
        # 4.1 INICIALIZAR ACUMULADORES (TOTALES DEL PERÍODO)
        # -------------------------------------------------------------------------

        resumen_nomina = []
        total_segundos_periodo = 0
        total_decimal_periodo = Decimal('0')
        total_bonos_periodo = Decimal('0')
        total_acumulado_solo_horas = Decimal('0')
        total_acumulado_con_bono = Decimal('0')
        
        # -------------------------------------------------------------------------
        # 4.2 PROCESAR DÍA POR DÍA (CÁLCULOS INDIVIDUALES)
        # -------------------------------------------------------------------------

        for f_str in sorted(dias_dict.keys(), reverse=True):
            marcaciones = sorted(dias_dict[f_str])
            cantidad_marcaciones = len(marcaciones)
            
            # 4.2.1 CALCULAR TIEMPO TRABAJADO DEL DÍA (POR PARES ENTRADA-SALIDA)
            
            if cantidad_marcaciones == 0:
                tiempo_neto = 0
                tiene_impares = False
                
            elif cantidad_marcaciones % 2 == 0:
                tiempo_neto = 0
                tiene_impares = False
                for i in range(0, cantidad_marcaciones, 2):
                    entrada = marcaciones[i]
                    salida = marcaciones[i + 1]
                    if salida > entrada:
                        tiempo_neto += (salida - entrada).total_seconds()
                
            else:
                tiempo_neto = 0
                tiene_impares = True
                cantidad_pares = cantidad_marcaciones - 1
                for i in range(0, cantidad_pares, 2):
                    entrada = marcaciones[i]
                    salida = marcaciones[i + 1]
                    if salida > entrada:
                        tiempo_neto += (salida - entrada).total_seconds()
                print(f"⚠️ ADVERTENCIA: Día {f_str} tiene {cantidad_marcaciones} marcaciones (impar). Se ignora la última marcación.")
            
            # 4.2.2 CONVERTIR A HORAS DECIMALES DEL DÍA
            
            tiempo_neto_dec = Decimal(str(tiempo_neto))
            horas_decimal = tiempo_neto_dec / Decimal('3600')
            
            # 4.2.3 CALCULAR PAGO POR HORAS DEL DÍA
            
            pago_horas = horas_decimal * pago_h
            
            # 4.2.4 CALCULAR BONO DEL DÍA
            
            fecha_actual = datetime.strptime(f_str, "%Y-%m-%d")
            if fecha_actual.weekday() <= 4 and tiempo_neto >= 18000:
                bono_dia = bono_c
            else:
                bono_dia = Decimal('0')
            
            # 4.2.5 CALCULAR TOTAL DEL DÍA
            
            total_dia = pago_horas + bono_dia
            
            # 4.2.6 GUARDAR EN RESUMEN DEL DÍA
            
            resumen_nomina.append({
                'fecha': f_str,
                'neto': formatear_h(tiempo_neto),
                'horas_decimal': str(horas_decimal.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)),
                'pago_horas': f"${pago_horas.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)}",
                'bono': f"${bono_dia.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)}",
                'total': f"${total_dia.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)}",
                'requiere_revision': tiene_impares if cantidad_marcaciones > 0 else False
            })
            
            # ---------------------------------------------------------------------
            # 4.3 ACUMULAR PARA TOTALES DEL PERÍODO
            # ---------------------------------------------------------------------
            
            total_segundos_periodo += tiempo_neto
            total_decimal_periodo += horas_decimal
            total_bonos_periodo += bono_dia
            total_acumulado_solo_horas += pago_horas
            total_acumulado_con_bono += total_dia
        
        # -------------------------------------------------------------------------
        # 4.4 TOTALES FINALES DEL PERÍODO
        # -------------------------------------------------------------------------
        
        cursor.close()
        conn.close()
        
        # =========================================================================
        # PARTE 5: ENVÍO DE RESPUESTA AL FRONTEND
        # =========================================================================
        
        return jsonify({
            'detalles': filtrados,
            'resumen': resumen_nomina,
            'totales_pie': {
                'tiempo': formatear_h(total_segundos_periodo),
                'decimal': str(total_decimal_periodo.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)),
                'pago_h': f"${total_acumulado_solo_horas.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)}",
                'bonos': f"${total_bonos_periodo.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)}",
                'general': f"${total_acumulado_con_bono.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)}"
            },
            'total_general': f"${total_acumulado_con_bono.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)}"
        })
    
    except Exception as e:
        print(f"[ERROR DB] {str(e)}")
        return jsonify({'error': str(e)}), 500

# =========================================================================
# EJECUCIÓN PRINCIPAL
# =========================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
