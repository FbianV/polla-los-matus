import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import base64

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Polla Mundialera", page_icon="⚽", layout="centered")

def poner_video_fondo(ruta_video):
    try:
        with open(ruta_video, "rb") as video_file:
            video_bytes = video_file.read()
        
        encoded_video = base64.b64encode(video_bytes).decode()

        st.markdown(
            f"""
            <style>
            /* Fondo transparente de la app base */
            .stApp {{
                background-color: transparent;
            }}
            
            /* Truco para centrar video vertical en pantallas anchas sin que se vea deforme */
            #video-fondo {{
                position: fixed;
                top: 50%;
                left: 50%;
                min-width: 100vw;
                min-height: 100vh;
                width: auto;
                height: auto;
                z-index: -1;
                transform: translate(-50%, -50%); /* Ancla el video al centro exacto */
                object-fit: cover;
                opacity: 0.4;
            }}

            /* Contenedor principal con efecto vidrio (Glassmorphism) */
            .block-container {{
                background: rgba(20, 20, 20, 0.7); /* Fondo oscuro semi-transparente */
                backdrop-filter: blur(10px); /* Difumina el video detrás del cuadro */
                border-radius: 20px; /* Bordes redondeados */
                padding: 3rem 2rem; /* Espaciado interno */
                margin-top: 2rem;
                margin-bottom: 2rem;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5); /* Sombra elegante */
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            </style>
            <video id="video-fondo" autoplay loop muted playsinline>
                <source src="data:video/mp4;base64,{encoded_video}" type="video/mp4">
            </video>
            """,
            unsafe_allow_html=True
        )
    except FileNotFoundError:
        pass

poner_video_fondo("EditDuro.mp4")

st.markdown(
    "<h1 style='text-align: center; color: #FFD700; text-shadow: 2px 2px 8px rgba(0,0,0,0.8); font-size: 3.5rem; margin-bottom: 0;'>Polla Mundialera</h1>", 
    unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align: center; font-size: 1.2rem; font-style: italic; color: #E0E0E0; margin-bottom: 2rem;'>Donde se separan los expertos de las mufas malayas</p>", 
    unsafe_allow_html=True
)

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # REEMPLAZA ESTO CON EL ID DE TU GOOGLE SHEET
    SHEET_ID = '12BNsuzB8xqbvCvXhguZAPjBDthbxE0DXSC7gbRDrkaQ'
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
    st.header("Resultados")
    st.write("Presiona este botón después de ingresar los resultados oficiales en Google Sheets.")
    
    if st.button("Actualizar Resultados y Ranking", type="primary"):
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

                st.success("¡Cálculos finalizados y base de datos actualizada!")
                time.sleep(2)
                st.rerun() # Recarga la página web para mostrar los nuevos datos
                
            except Exception as e:
                st.error(f"Ocurrió un error: {e}")

# --- VISTA: RANKING (Página Principal) ---
st.header("La Clasific actual")
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
st.header("Dale con tu predict")

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
                    st.success(f"¡Predicción guardada! {usuario_sel}: {partido_sel} ({pred_local} - {pred_visita})")
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
