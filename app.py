import streamlit as st
import pandas as pd
from datetime import date
import uuid

st.set_page_config(page_title="Wehringer Steelers Trainings", layout="centered")

st.title("🎯 Wehringer Steelers - Trainingsbetrieb")

# Hier werden die Google Sheets verbunden (Beispiel mit lokalen CSVs oder Google Sheets API)
# Für den Start nutzen wir den direkten Weg oder CSV-Fallback.
@st.cache_data(ttl=10)
def load_data():
    # Platzhalter für die Anbindung an deine Google Sheets
    sessions_df = pd.DataFrame(columns=["Session-ID", "Datum", "Spielmodus", "Leg-Modus", "Anzahl Boards", "Anwesende Spieler"])
    matches_df = pd.DataFrame(columns=["Session-ID", "Runde", "Board", "Spieler 1", "Spieler 2", "Ergebnis", "180er"])
    return sessions_df, matches_df

kader = [
    "Andreas Böhm", "Andrino Czombera", "Dennis Güttner", "Marco Eser", 
    "Maximilian Zientner", "Michael Kummer", "Michael Mak", 
    "Michael Neumeier", "Thomas Schaudt", "Wolfgang Schneider"
]

menu = st.sidebar.selectbox("Menü", ["Übersicht", "Neue Session starten", "Match-Eingabe"])

if menu == "Übersicht":
    st.subheader("Bisherige Trainings-Sessions")
    st.info("Hier entsteht die Auswertung aller absolvierten Abende.")

elif menu == "Neue Session starten":
    st.subheader("Neue Training-Session anlegen")
    
    with st.form("session_form"):
        datum = st.date_input("Datum", date.today())
        spielmodus = st.selectbox("Spielmodus", ["Up & Down", "Liga (4er-Team)"])
        leg_modus = st.selectbox("Leg-Modus", ["Best of 3", "Best of 5"])
        anzahl_boards = st.slider("Anzahl der Boards", 1, 6, 4)
        
        st.write("### Anwesende Spieler aus dem Kader")
        anwesende = []
        for spieler in kader:
            if st.checkbox(spieler, value=True):
                anwesende.append(spieler)
                
        submitted = st.form_submit_button("Session starten")
        
        if submitted:
            session_id = str(uuid.uuid4())[:8]
            st.success(f"Session erfolgreich gestartet! ID: {session_id}")
            # Hier wird die Session in Google Sheets gespeichert

elif menu == "Match-Eingabe":
    st.subheader("Runden- & Match-Erfassung")
    st.warning("Bitte zuerst eine Session starten, um Matches zuzuweisen.")
    
    # Dynamische Auswahl basierend auf aktiven Session-Teilnehmern
    runde = st.selectbox("Runde", ["Runde 1", "Runde 2", "Runde 3", "Runde 4"])
    board = st.selectbox("Board", [f"Board {i}" for i in range(1, 7)])
    
    # Beispielhaft angebundene Spieler der aktiven Session
    erfasste_spieler = kader # Wird später dynamisch aus der aktiven Session gezogen
    
    col1, col2 = st.columns(2)
    with col1:
        spieler_1 = st.selectbox("Spieler 1", erfasste_spieler, key="s1")
    with col2:
        spieler_2 = st.selectbox("Spieler 2", [s for s in erfasste_spieler if s != spieler_1], key="s2")
        
    ergebnis = st.text_input("Ergebnis (z. B. 3:0 oder 3:2)")
    highlight_180 = st.selectbox("180er erzielt von:", ["Keiner"] + [spieler_1, spieler_2])
    
    if st.button("Match speichern"):
        st.success(f"Match auf {board} ({spieler_1} vs {spieler_2}) erfolgreich gespeichert!")
