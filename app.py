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
    
    # ID de tu Google Sheet
    SHEET_ID = '12BNsuzB8xqbvCvXhguZAPjBDthbxE0DXSC7gbRDrkaQ'
    sheet = client.open_by_key(SHEET_ID)
except Exception as e:
    st.error("Error conectando a la base de datos. Avisa al administrador.")
    st.stop()

# --- FUNCIÓN ANTIFALLOS PARA LEER HOJAS ---
def cargar_datos_seguros(worksheet):
    """
    Intenta leer la hoja normalmente. Si Google Sheets tiene celdas sucias 
    o encabezados vacíos que hacen explotar a gspread, usa el Plan B.
    """
    try:
        return pd.DataFrame(worksheet.get_all_records())
    except Exception:
        raw_data = worksheet.get_all_values()
        if not raw_data or len(raw_data) < 2:
            return pd.DataFrame() # Hoja vacía
        
        # Limpiamos los encabezados
        headers = [str(h).strip() for h in raw_data[0]]
        df = pd.DataFrame(raw_data[1:], columns=headers)
        
        # Eliminamos cualquier columna fantasma que no tenga nombre
        df = df.loc[:, df.columns != '']
        
        # Forzamos los textos a números donde corresponda para no romper las sumas
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='ignore')
            
        return df

# --- LÓGICA DE PUNTUACIÓN ---
def calcular_puntos(row):
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
                ws_resultados = sheet.worksheet("Resultados")
                df_resultados = cargar_datos_seguros(ws_resultados)
                
                if not df_resultados.empty and 'Partidos' in df_resultados.columns:
                    df_resultados['Partidos'] = df_resultados['Partidos'].astype(str).str.strip()

                hojas_sistema = ['Ranking', 'Resultados', 'Graficos']
                usuarios = [ws.title for ws in sheet.worksheets() if ws.title not in hojas_sistema]
                
                diccionario_ranking = {}

                for usuario in usuarios:
                    ws_user = sheet.worksheet(usuario)
                    df_usuario = cargar_datos_seguros(ws_user)

                    if df_usuario.empty or 'Partidos' not in df_usuario.columns:
                        continue

                    df_usuario['Partidos'] = df_usuario['Partidos'].astype(str).str.strip()

                    df_temporal = pd.merge(df_usuario, df_resultados[['Partidos', 'Goles_Local', 'Goles_Visita']], on='Partidos', how='left')
                    
                    df_usuario['Puntuacion'] = df_temporal.apply(calcular_puntos, axis=1)
                    diccionario_ranking[usuario] = df_usuario['Puntuacion'].sum()

                    ws_user.clear()
                    ws_user.update([df_usuario.columns.values.tolist()] + df_usuario.values.tolist())
                    
                    time.sleep(1)

                if diccionario_ranking:
                    df_ranking = pd.DataFrame(list(diccionario_ranking.items()), columns=['Usuario', 'Puntuacion'])
                    df_ranking = df_ranking.sort_values(by='Puntuacion', ascending=False).reset_index(drop=True)
                    df_ranking.insert(0, 'Posicion', df_ranking.index + 1)

                    ws_ranking = sheet.worksheet("Ranking")
                    ws_ranking.clear()
                    ws_ranking.update([df_ranking.columns.values.tolist()] + df_ranking.values.tolist())

                st.success("¡Cálculos finalizados y base de datos actualizada!")
                time.sleep(2)
                st.rerun() 
                
            except Exception as e:
                st.error(f"Ocurrió un error: {e}")

# Leemos la hoja de resultados oficial globalmente para usarla en todo el sitio
try:
    resultados_sheet = sheet.worksheet("Resultados")
    df_resultados_global = cargar_datos_seguros(resultados_sheet)
    
    if not df_resultados_global.empty:
        df_resultados_global['Estado'] = df_resultados_global.get('Estado', '').astype(str).str.strip().str.upper()
        df_resultados_global['Partidos'] = df_resultados_global['Partidos'].astype(str).str.strip()
except Exception as e:
    st.error("Error leyendo la hoja de Resultados. Asegúrate de haber agregado la columna 'Estado'.")
    st.stop()

# --- VISTA: RANKING (Página Principal) ---
st.header("La Clasific actual")
try:
    ranking_sheet = sheet.worksheet("Ranking")
    df_ranking_vista = cargar_datos_seguros(ranking_sheet)
    
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

# --- SECCIÓN: PARTIDOS EN JUEGO ---
hojas_sistema = ['Ranking', 'Resultados', 'Graficos']
usuarios = [ws.title for ws in sheet.worksheets() if ws.title not in hojas_sistema]

if not df_resultados_global.empty and 'Estado' in df_resultados_global.columns:
    df_jugando = df_resultados_global[df_resultados_global['Estado'] == 'J']

    if not df_jugando.empty:
        st.markdown("<h2 style='color: #ff4b4b;'>Predicts En Juego Ahora</h2>", unsafe_allow_html=True)
        
        with st.spinner("Cargando las predicciones de todos..."):
            datos_usuarios = {}
            for u in usuarios:
                ws_u = sheet.worksheet(u)
                df_u = cargar_datos_seguros(ws_u) # <-- AQUÍ SE APLICÓ LA CORRECCIÓN
                if not df_u.empty and 'Partidos' in df_u.columns:
                    df_u['Partidos'] = df_u['Partidos'].astype(str).str.strip()
                datos_usuarios[u] = df_u

            for _, row in df_jugando.iterrows():
                partido_actual = row['Partidos']
                st.markdown(f"#### {partido_actual}")
                
                lista_predicciones = []
                for u in usuarios:
                    df_u = datos_usuarios[u]
                    
                    if df_u.empty or 'Partidos' not in df_u.columns:
                        lista_predicciones.append({"Jugador": u, "Predicción": "Hoja vacía ❌"})
                        continue
                        
                    match_row = df_u[df_u['Partidos'] == partido_actual]
                    if not match_row.empty:
                        p_local = match_row.iloc[0].get('Prediccion_Local', '')
                        p_visita = match_row.iloc[0].get('Prediccion_Visita', '')
                        
                        if str(p_local).strip() != '' and str(p_visita).strip() != '' and str(p_local).strip() != 'nan':
                            lista_predicciones.append({"Jugador": u, "Predicción": f"{int(p_local)} - {int(p_visita)}"})
                        else:
                            lista_predicciones.append({"Jugador": u, "Predicción": "No ingresó ❌"})
                
                if lista_predicciones:
                    df_en_vivo = pd.DataFrame(lista_predicciones)
                    st.dataframe(df_en_vivo, use_container_width=True, hide_index=True)

        st.divider()

# --- FORMULARIO: INGRESAR PREDICCIONES ---
st.header("Dale con tu predict")

if usuarios:
    usuario_sel = st.selectbox("¿Quién eres?", usuarios)
    
    if not df_resultados_global.empty and 'Estado' in df_resultados_global.columns:
        df_pendientes = df_resultados_global[df_resultados_global['Estado'] == 'P']
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
    if not df_resultados_global.empty and 'Estado' in df_resultados_global.columns:
        df_jugados = df_resultados_global[df_resultados_global['Estado'] == 'F']
        if not df_jugados.empty:
            columnas_mostrar = ['Partidos', 'Goles_Local', 'Goles_Visita']
            # Filtramos solo las columnas que existan para no tener otro error
            columnas_finales = [col for col in columnas_mostrar if col in df_jugados.columns]
            st.dataframe(df_jugados[columnas_finales], use_container_width=True, hide_index=True)
        else:
            st.write("Aún no se han jugado partidos.")
    else:
        st.write("La hoja de resultados está vacía o sin formato.")