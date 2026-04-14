import requests
from requests.auth import HTTPDigestAuth
import mysql.connector
from datetime import datetime, timedelta
import time
import json

# --- CONFIGURACIÓN ---
CH_CONFIG = {
    "IP": "192.168.2.239",
    "USER": "admin",
    "PASS": "Temporal1.",
}

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "control_asistencia"
}

def conectar_db():
    return mysql.connector.connect(**DB_CONFIG)

def obtener_ultimo_registro():
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(authDateTime) FROM control_de_horas")
        res = cursor.fetchone()[0]
        conn.close()
        return res
    except:
        return None

def sincronizar(inicio_dt, fin_dt, ejecutar_limpieza=False):
    # REDONDEO: Forzamos formato %Y-%m-%dT%H:%M:00 para evitar Error 400
    inicio_str = inicio_dt.strftime("%Y-%m-%dT%H:%M:00")
    fin_str = fin_dt.strftime("%Y-%m-%dT%H:%M:00")
    
    url = f"http://{CH_CONFIG['IP']}/ISAPI/AccessControl/AcsEvent?format=json"
    posicion = 0
    ids_en_checador = []
    nuevos_totales = 0

    conn = conectar_db()
    cursor = conn.cursor()

    print(f">> PASO: Consultando al checador desde {inicio_str} hasta {fin_str}")

    while True:
        payload = {
            "AcsEventCond": {
                "searchID": "sync_task", # ID simple
                "searchResultPosition": posicion,
                "maxResults": 100,
                "major": 5,
                "minor": 0,
                "startTime": inicio_str,
                "endTime": fin_str
            }
        }
        
        try:
            r = requests.post(
                url, 
                data=json.dumps(payload), 
                auth=HTTPDigestAuth(CH_CONFIG['USER'], CH_CONFIG['PASS']), 
                timeout=15,
                headers={'Content-Type': 'application/json'}
            )
            
            if r.status_code != 200:
                print(f">> ERROR {r.status_code}: {r.text}")
                break
            
            data = r.json().get('AcsEvent', {})
            bloque = data.get('InfoList', [])
            total_en_equipo = data.get('totalMatches', 0)
            
            if not bloque: break

            for e in bloque:
                nombre = e.get('name') or e.get('employeeName')
                emp_id = e.get('employeeNo') or e.get('employeeNoString')
                
                if nombre and emp_id:
                    f_h = e.get('time', '').replace('T', ' ')[:19]
                    
                    if ejecutar_limpieza:
                        ids_en_checador.append((str(emp_id), f_h))

                    sql_ins = """INSERT IGNORE INTO control_de_horas 
                                 (employeeID, personName, authDateTime, authDate, authTime, direction, deviceName) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                    
                    cursor.execute(sql_ins, (emp_id, nombre, f_h, f_h.split(' ')[0], f_h.split(' ')[1], 
                                             "IN" if e.get('attendanceStatus') == "checkIn" else "OUT", "Checador"))
                    
                    if cursor.rowcount > 0:
                        nuevos_totales += 1
            
            conn.commit()
            posicion += len(bloque)
            print(f"   [PROGRESO] Leídos {posicion} de {total_en_equipo} eventos...", end="\r")
            
            if posicion >= total_en_equipo: break
                
        except Exception as ex:
            print(f"\n>> ERROR CRÍTICO: {ex}")
            break

    borrados = 0
    if ejecutar_limpieza:
        print("\n>> PASO: Iniciando limpieza de registros borrados en el equipo...")
        sql_query = "SELECT employeeID, authDateTime FROM control_de_horas WHERE authDateTime BETWEEN %s AND %s"
        cursor.execute(sql_query, (inicio_str.replace('T', ' '), fin_str.replace('T', ' ')))
        registros_db = cursor.fetchall()
        
        for reg in registros_db:
            id_db = str(reg[0])
            fh_db = reg[1].strftime("%Y-%m-%d %H:%M:%S")
            if (id_db, fh_db) not in ids_en_checador:
                cursor.execute("DELETE FROM control_de_horas WHERE employeeID = %s AND authDateTime = %s", (reg[0], reg[1]))
                borrados += 1
        conn.commit()

    conn.close()
    return nuevos_totales, borrados

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  SISTEMA DE SINCRONIZACIÓN HIKVISION - MODO ESPEJO")
    print("="*55)
    
    # --- PASO 1: ARRANQUE (Mantenimiento 30 días) ---
    print("\n[PASO 1]: EJECUTANDO MANTENIMIENTO INICIAL (30 DÍAS)")
    ahora_inicio = datetime.now()
    inicio_30 = (ahora_inicio - timedelta(days=30)).replace(second=0, microsecond=0)
    
    n, b = sincronizar(inicio_30, ahora_inicio, ejecutar_limpieza=True)
    print(f"\n[RESULTADO]: {n} agregados, {b} eliminados de la DB local.")

    # --- PASO 2: VIGILANCIA (1 Minuto) ---
    print("\n" + "-"*55)
    print("[PASO 2]: ENTRANDO EN VIGILANCIA CADA MINUTO")
    print("-"*55)
    
    while True:
        ahora = datetime.now()
        print(f"\n[{ahora.strftime('%H:%M:%S')}] Iniciando chequeo...")
        
        ultimo_reg = obtener_ultimo_registro()
        
        # Redondeamos inicio a :00 para evitar Error 400
        if ultimo_reg:
            inicio_busqueda = ultimo_reg.replace(second=0, microsecond=0)
        else:
            inicio_busqueda = (ahora - timedelta(days=1)).replace(second=0, microsecond=0)
        
        # Fin de búsqueda también redondeado
        fin_busqueda = ahora.replace(second=0, microsecond=0)
        
        n_rapido, _ = sincronizar(inicio_busqueda, fin_busqueda, ejecutar_limpieza=False)
        
        if n_rapido > 0:
            print(f">> ÉXITO: {n_rapido} nuevos registros guardados.")
        else:
            print(">> INFO: Sin novedades.")
        
        print(f"Esperando 60 segundos...")
        time.sleep(60)