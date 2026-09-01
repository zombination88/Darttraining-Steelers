import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(page_title="Wehringer Steelers Teamcoach", layout="centered")

st.title("🎯 Wehringer Steelers - Teamcoach")

kader = [
    "Andreas Böhm", "Andrino Czombera (Captain)", "Dennis Güttner", "Marco Eser", 
    "Maximilian Zientner", "Michael Kummer", "Michael Mak", 
    "Michael Neumeier", "Thomas Schaudt", "Wolfgang Schneider"
]

menu = st.sidebar.selectbox("Menü", ["Übersicht", "Kader", "Session", "Match-Archiv"])

if menu == "Übersicht":
    st.subheader("Übersicht")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Up & Down Abende", value="1", delta="4 Runden pro Abend")
    with col2:
        st.metric(label="Gespielte Matches", value="2", delta="aus dem Archiv")
    with col3:
        st.metric(label="Aktive Spieler", value="10", delta="im Kader")
    with col4:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="01.09.2026")

elif menu == "Kader":
    st.subheader("Kader & Spielerbilanz")
    st.write("Live berechnete Bilanz des festen Stammkaders (exklusive Gastspieler).")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
    with col2:
        st.metric(label="Absolvierte Spiele", value="4", delta="Teilnahmen insgesamt")
    with col3:
        st.metric(label="Ø Siegquote", value="5%", delta="aus erfassten Matchdaten")
        
    st.write("### Spielerübersicht & Rangliste")
    suche = st.text_input("Spieler suchen...", "")
    
    kader_data = {
        "Spieler": kader,
        "Matches": [2, 2, 0, 0, 0, 0, 0, 0, 0, 0],
        "Siege": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "Niederlagen": [1, 2, 0, 0, 0, 0, 0, 0, 0, 0],
        "Siegquote": ["50%", "0%", "0%", "0%", "0%", "0%", "0%", "0%", "0%", "0%"]
    }
    df_kader = pd.DataFrame(kader_data)
    if suche:
        df_kader = df_kader[df_kader["Spieler"].str.contains(suche, case=False)]
    st.dataframe(df_kader, use_container_width=True, hide_index=True)

elif menu == "Session":
    st.subheader("Up & Down Sessions")
    
    with st.expander("➕ Neue Session starten (inkl. Gastspieler-Erfassung)"):
        with st.form("new_session_form"):
            session_datum = st.date_input("Datum des Abends", date.today())
            anzahl_boards = st.slider("Anzahl Boards", 1, 6, 4)
            
            st.write("### Gastspieler hinzufügen (fließen nicht in die Statistik ein)")
            g1 = st.text_input("Gastspieler 1")
            g2 = st.text_input("Gastspieler 2")
            g3 = st.text_input("Gastspieler 3")
            g4 = st.text_input("Gastspieler 4")
            
            submit_session = st.form_submit_button("Session anlegen")
            if submit_session:
                gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
                st.success(f"Session für den {session_datum} mit {anzahl_boards} Boards erstellt! Gäste: {', '.join(gaeste) if gaeste else 'Keine'}")

    st.write("### Laufende Session & Board-Erfassung (Runde für Runde)")
    st.info("Wähle ein Board aus, um die Ergebnisse für die jeweiligen Runden (1 bis 4) einzutragen.")

    selected_board = st.selectbox("Board auswählen für Eingabe:", [f"Board {i}" for i in range(1, 5)])
    selected_runde = st.selectbox("Runde auswählen:", ["Runde 1", "Runde 2", "Runde 3", "Runde 4"])

    with st.form(key="board_input_form"):
        st.write(f"### Eingabe für {selected_board} - {selected_runde}")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            spieler_a = st.selectbox("Spieler 1", kader, key="s_a")
        with col_s2:
            spieler_b = st.selectbox("Spieler 2", kader, key="s_b")
            
        ergebnis = st.text_input("Ergebnis (z.B. 3:1)", "")
        highlight_180 = st.checkbox("180er erzielt?")
        high_finish = st.text_input("High Finish (optional)", "")
        
        save_match = st.form_submit_button("Ergebnis für diese Runde speichern")
        if save_match:
            st.success(f"Ergebnis für {selected_board} ({selected_runde}): {spieler_a} vs {spieler_b} [{ergebnis}] gespeichert!")

elif menu == "Match-Archiv":
    st.subheader("Trainingsmatches")
    st.write("Board-Matches nach Runde, Ergebnis und Gewinner durchsuchen.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Erfasste Matches", value="2", delta="im gewählten Zeitraum")
    with col2:
        st.metric(label="Spieler beteiligt", value="2", delta="in der aktuellen Liste")
    with col3:
        st.metric(label="Sieger eingetragen", value="1", delta="für die Kaderstatistik")
        
    st.write("### Match-Archiv")
    match_data = {
        "Session-ID": ["S-1", "S-1"],
        "Datum": ["01.09.2026", "01.09.2026"],
        "Leg-Modus": ["Best of 5", "Best of 5"],
        "Runde": [1, 1],
        "Board": ["B1", "B1"],
        "180er": ["Ja", "Nein"],
        "High Finish": ["–", "–"],
        "Spieler 1": ["Andrino Czombera", "Andrino Czombera"],
        "Spieler 2": ["Marco Eser", "Marco Eser"],
        "Ergebnis": ["3:1", "–"],
        "Gewinner": ["Andrino Czombera", "Offen"]
    }
    df_matches = pd.DataFrame(match_data)
    st.dataframe(df_matches, use_container_width=True, hide_index=True)
