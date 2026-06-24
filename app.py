import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Polla Mundialera", page_icon="⚽", layout="centered")
st.title("🏆 Polla Mundialera")

# --- CONEXIÓN A GOOGLE SHEETS ---
# En Streamlit Cloud, el JSON se pasa a través de st.secrets. 
# Para pruebas locales, Streamlit lee de un archivo .streamlit/secrets.toml
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

# --- VISTA: RANKING ---
st.header("📊 Clasificación Actual")
try:
    ranking_sheet = sheet.worksheet("Ranking")
    df_ranking = pd.DataFrame(ranking_sheet.get_all_records())
    
    # Aplicar un poco de estilo al DataFrame en la web
    st.dataframe(
        df_ranking.style.background_gradient(cmap='YlGn', subset=['Puntuacion']),
        use_container_width=True,
        hide_index=True
    )
except gspread.exceptions.WorksheetNotFound:
    st.warning("Aún no se ha generado el ranking.")

st.divider()

# --- FORMULARIO: INGRESAR PREDICCIONES ---
st.header("✍️ Ingresar Predicción")

# Obtener nombres de las hojas que corresponden a usuarios
hojas_sistema = ['Ranking', 'Resultados', 'RankingAlt', 'Graficos']
usuarios = [ws.title for ws in sheet.worksheets() if ws.title not in hojas_sistema]

usuario_sel = st.selectbox("¿Quién eres?", usuarios)

# Leer los partidos disponibles desde la hoja Resultados
resultados_sheet = sheet.worksheet("Resultados")
df_resultados = pd.DataFrame(resultados_sheet.get_all_records())
# Filtramos para no mostrar partidos que ya tienen resultado real
df_pendientes = df_resultados[df_resultados['Goles_Local'].isna() | (df_resultados['Goles_Local'] == '')]
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
            
            # Buscar la fila del partido exacto en la hoja del usuario
            celda_partido = ws_usuario.find(partido_sel)
            
            if celda_partido:
                # Actualiza la columna B (Prediccion_Local) y C (Prediccion_Visita)
                ws_usuario.update_cell(celda_partido.row, 2, pred_local)
                ws_usuario.update_cell(celda_partido.row, 3, pred_visita)
                st.success(f"✅ ¡Predicción guardada! {usuario_sel}: {partido_sel} ({pred_local} - {pred_visita})")
                st.balloons()
            else:
                st.error("No se encontró el partido en tu hoja personal.")

# --- VISTA: RESULTADOS REALES ---
with st.expander("Ver resultados oficiales de los partidos jugados"):
    df_jugados = df_resultados[df_resultados['Goles_Local'].astype(str) != '']
    st.dataframe(df_jugados, use_container_width=True, hide_index=True)