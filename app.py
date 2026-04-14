"""
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

app = Flask(__name__)

# --- CONFIGURACIÓN DE BASE DE DATOS (XAMPP) ---
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "control_asistencia"
}

def normalizar_texto(texto):
    """Elimina tildes y convierte a minúsculas para un filtrado preciso."""
    if not texto: return ""
    texto = str(texto).lower()
    return "".join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

def formatear_h(seg):
    if seg <= 0: return "00h 00m"
    h, m = int(seg // 3600), int((seg % 3600) // 60)
    return f"{h:02d}h {m:02d}m"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])
def consultar():
    datos = request.json
    nombre_buscado = normalizar_texto(datos['nombre'])
    pago_h = float(datos['pago'])
    bono_c = float(datos['bono'])
    inicio = datos['inicio'] 
    fin = datos['fin']       

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
        
        filtrados = []
        dias_dict = {}

        for reg in registros_crudos:
            nom_norm = normalizar_texto(reg['personName'])
            if nombre_buscado in nom_norm:
                filtrados.append({'fh': str(reg['authDateTime']), 'id': reg['employeeID'], 'nombre': reg['personName']})
                f_solo = str(reg['authDate'])
                if f_solo not in dias_dict: dias_dict[f_solo] = []
                dias_dict[f_solo].append(reg['authDateTime'])

        resumen_nomina = []
        total_acumulado_con_bono = 0
        total_acumulado_solo_horas = 0 # <--- Nueva variable global del periodo

        for f_str in sorted(dias_dict.keys(), reverse=True):
            m = sorted(dias_dict[f_str])
            n = len(m)
            
            if n == 4:
                t_neto = (m[1]-m[0]).total_seconds() + (m[3]-m[2]).total_seconds()
            elif n >= 2:
                t_neto = (m[-1]-m[0]).total_seconds()
            else:
                t_neto = 0

            horas_decimal = round(t_neto / 3600, 2)
            
            # --- CÁLCULOS SEPARADOS ---
            pago_solo_horas = horas_decimal * pago_h # <--- Pago sin el bono
            
            fecha_dt = datetime.strptime(f_str, "%Y-%m-%d")
            bono = bono_c if (fecha_dt.weekday() <= 4 and t_neto >= 18000) else 0.0
            
            pago_total_dia = pago_solo_horas + bono
            
            # Sumatorias finales
            total_acumulado_solo_horas += pago_solo_horas
            total_acumulado_con_bono += pago_total_dia
            
            resumen_nomina.append({
                'fecha': f_str,
                'neto': formatear_h(t_neto),
                'horas_decimal': horas_decimal,
                'pago_horas': f"${pago_solo_horas:.2f}", # <--- Enviamos el subtotal al JS
                'bono': f"${bono:.2f}",
                'total': f"${pago_total_dia:.2f}"
            })

        cursor.close()
        conn.close()

        return jsonify({
            'detalles': filtrados,
            'resumen': resumen_nomina,
            'total_solo_horas': f"${total_acumulado_solo_horas:.2f}", # <--- Total neto
            'total_general': f"${total_acumulado_con_bono:.2f}"       # <--- Total con bonos
        })

    except Exception as e:
        print(f"[ERROR DB] {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)