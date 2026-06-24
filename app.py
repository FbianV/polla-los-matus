import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Polla Mundialera", page_icon="⚽", layout="centered")
st.title("🏆 Polla Mundialera")

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # REEMPLAZA ESTO CON EL ID DE TU GOOGLE SHEET
    SHEET_ID = 'TU_ID_LARGO_AQUI'
    sheet = client.open_by_key(SHEET_ID)
except Exception as e:
    st.error("Error conectando a la base de datos. Avisa al administrador.")
    st.stop()

# --- LÓGICA DE PUNTUACIÓN (Migrada de polla.py) ---
def calcular_puntos(row):
    # Google Sheets suele devolver strings vacíos ('') para celdas sin datos
    val_local = str(row.get('Goles_Local', '')).strip()
    val_visita = str(row.get('Goles_Visita', '')).strip()
    
    if val_local == '' or val_visita == '' or val_local == 'nan':
        return 0

    try:
        pred_local = int(row['Prediccion_Local'])
        pred_visita = int(row['Prediccion_Visita'])
        real_local = int(float(val_local))
        real_visita = int(float(val_visita))
    except (ValueError, TypeError):
        return 0

    if pred_local == real_local and pred_visita == real_visita:
        return 3

    ganador_pred = 1 if pred_local > pred_visita else (-1 if pred_local < pred_visita else 0)
    ganador_real = 1 if real_local > real_visita else (-1 if real_local < real_visita else 0)

    if ganador_pred == ganador_real:
        return 1

    return 0

# --- PANEL DE ADMINISTRACIÓN LATERAL ---
with st.sidebar:
    st.header("⚙️ Administración")
    st.write("Presiona este botón después de ingresar los resultados oficiales en Google Sheets.")
    
    if st.button("🔄 Actualizar Resultados y Ranking", type="primary"):
        with st.spinner("Descargando datos y calculando..."):
            try:
                # 1. Obtener Resultados Oficiales
                ws_resultados = sheet.worksheet("Resultados")
                df_resultados = pd.DataFrame(ws_resultados.get_all_records())
                df_resultados['Partidos'] = df_resultados['Partidos'].astype(str).str.strip()

                hojas_sistema = ['Ranking', 'Resultados', 'Graficos']
                usuarios = [ws.title for ws in sheet.worksheets() if ws.title not in hojas_sistema]
                
                diccionario_ranking = {}

                # 2. Procesar a cada usuario
                for usuario in usuarios:
                    ws_user = sheet.worksheet(usuario)
                    df_usuario = pd.DataFrame(ws_user.get_all_records())

                    if 'Partidos' not in df_usuario.columns:
                        continue

                    df_usuario['Partidos'] = df_usuario['Partidos'].astype(str).str.strip()

                    # Cruce temporal para traer los goles reales
                    df_temporal = pd.merge(df_usuario, df_resultados[['Partidos', 'Goles_Local', 'Goles_Visita']], on='Partidos', how='left')
                    
                    # Calcular puntuación
                    df_usuario['Puntuacion'] = df_temporal.apply(calcular_puntos, axis=1)
                    diccionario_ranking[usuario] = df_usuario['Puntuacion'].sum()

                    # Sobrescribir la hoja del usuario en Google Sheets con los nuevos puntos
                    ws_user.clear()
                    ws_user.update([df_usuario.columns.values.tolist()] + df_usuario.values.tolist())
                    
                    # Pequeña pausa para no saturar la API de Google
                    time.sleep(1)

                # 3. Actualizar la hoja de Ranking
                if diccionario_ranking:
                    df_ranking = pd.DataFrame(list(diccionario_ranking.items()), columns=['Usuario', 'Puntuacion'])
                    df_ranking = df_ranking.sort_values(by='Puntuacion', ascending=False).reset_index(drop=True)
                    df_ranking.insert(0, 'Posicion', df_ranking.index + 1)

                    ws_ranking = sheet.worksheet("Ranking")
                    ws_ranking.clear()
                    ws_ranking.update([df_ranking.columns.values.tolist()] + df_ranking.values.tolist())

                st.success("✅ ¡Cálculos finalizados y base de datos actualizada!")
                time.sleep(2)
                st.rerun() # Recarga la página web para mostrar los nuevos datos
                
            except Exception as e:
                st.error(f"Ocurrió un error: {e}")

# --- VISTA: RANKING (Página Principal) ---
st.header("📊 Clasificación Actual")
try:
    ranking_sheet = sheet.worksheet("Ranking")
    df_ranking_vista = pd.DataFrame(ranking_sheet.get_all_records())
    
    if not df_ranking_vista.empty:
        st.dataframe(
            df_ranking_vista.style.background_gradient(cmap='YlGn', subset=['Puntuacion']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("El ranking aún está vacío. Faltan resultados.")
except gspread.exceptions.WorksheetNotFound:
    st.warning("Aún no se ha generado la hoja de Ranking en la base de datos.")

st.divider()

# --- FORMULARIO: INGRESAR PREDICCIONES ---
st.header("✍️ Ingresar Predicción")

hojas_sistema = ['Ranking', 'Resultados', 'Graficos']
usuarios = [ws.title for ws in sheet.worksheets() if ws.title not in hojas_sistema]

if usuarios:
    usuario_sel = st.selectbox("¿Quién eres?", usuarios)

    resultados_sheet = sheet.worksheet("Resultados")
    df_resultados_form = pd.DataFrame(resultados_sheet.get_all_records())
    
    # Filtramos partidos donde no hay resultado oficial todavía
    df_pendientes = df_resultados_form[df_resultados_form['Goles_Local'].astype(str).str.strip() == '']
    partidos = df_pendientes['Partidos'].tolist()

    if not partidos:
        st.info("No hay partidos pendientes para predecir.")
    else:
        partido_sel = st.selectbox("Selecciona el partido", partidos)
        
        col1, col2 = st.columns(2)
        with col1:
            pred_local = st.number_input("Goles Local", min_value=0, step=1)
        with col2:
            pred_visita = st.number_input("Goles Visita", min_value=0, step=1)

        if st.button("Guardar Predicción", type="primary"):
            with st.spinner('Guardando en la base de datos...'):
                ws_usuario = sheet.worksheet(usuario_sel)
                celda_partido = ws_usuario.find(partido_sel)
                
                if celda_partido:
                    ws_usuario.update_cell(celda_partido.row, 2, pred_local)
                    ws_usuario.update_cell(celda_partido.row, 3, pred_visita)
                    st.success(f"✅ ¡Predicción guardada! {usuario_sel}: {partido_sel} ({pred_local} - {pred_visita})")
                    st.balloons()
                else:
                    st.error("No se encontró el partido en tu hoja personal.")

# --- VISTA: RESULTADOS REALES ---
with st.expander("Ver resultados oficiales de los partidos jugados"):
    df_jugados = df_resultados_form[df_resultados_form['Goles_Local'].astype(str).str.strip() != '']
    if not df_jugados.empty:
        st.dataframe(df_jugados, use_container_width=True, hide_index=True)
    else:
        st.write("Aún no se han jugado partidos.")