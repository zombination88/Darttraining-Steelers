import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(page_title="Wehringer Steelers Teamcoach", layout="centered")

st.title("🎯 Wehringer Steelers - Teamcoach")

kader = [
    "Andreas Böhm", "Andrino Czombera", "Dennis Güttner", "Marco Eser", 
    "Maximilian Zientner", "Michael Kummer", "Michael Mak", 
    "Michael Neumeier", "Thomas Schaudt", "Wolfgang Schneider"
]

if "board_rounds" not in st.session_state:
    st.session_state.board_rounds = {
        "Kaiser B1": 1,
        "Board 2": 1,
        "Board 3": 1,
        "Board 4": 1
    }

menu = st.sidebar.selectbox("Menü", ["Übersicht", "Kader", "Session", "Match-Archiv"])

@st.dialog("Neue Session starten")
def open_new_session_dialog():
    st.write("### Up & Down Session einrichten")
    session_datum = st.date_input("Datum", date.today())
    st.write("Gastspieler hinzufügen (optional, fließen nicht in die Statistik ein):")
    g1 = st.text_input("Gastspieler 1")
    g2 = st.text_input("Gastspieler 2")
    g3 = st.text_input("Gastspieler 3")
    g4 = st.text_input("Gastspieler 4")
    
    if st.button("Session jetzt anlegen"):
        gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
        st.success(f"Session für den {session_datum} erfolgreich erstellt! Gäste: {', '.join(gaeste) if gaeste else 'Keine'}")
        st.rerun()

@st.dialog("Board-Eingabe (Runde für Runde)")
def open_board_dialog(board_name):
    current_round = st.session_state.board_rounds[board_name]
    st.write(f"### Erfassung für {board_name} — Runde {current_round} von 4")
    
    col1, col2 = st.columns(2)
    with col1:
        s1 = st.selectbox("Spieler 1", kader, key=f"s1_{board_name}")
    with col2:
        s2 = st.selectbox("Spieler 2", [p for p in kader if p != s1], key=f"s2_{board_name}")
        
    ergebnis = st.text_input("Ergebnis (z. B. 3:1)", key=f"res_{board_name}")
    highlight_180 = st.selectbox("180er erzielt von:", ["Keiner", s1, s2], key=f"180_{board_name}")
    
    if st.button("Ergebnis speichern", key=f"save_{board_name}"):
        st.success(f"{board_name} (Runde {current_round}): {s1} vs {s2} [{ergebnis}] gespeichert!")
        if st.session_state.board_rounds[board_name] < 4:
            st.session_state.board_rounds[board_name] += 1
        st.rerun()

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
    st.write("Exakt 4 Runden, Aufstieg Richtung B1 und Abstieg Richtung B4.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Gespielte Abende", value="1", delta="gefilterte Sessions")
    with col2:
        st.metric(label="Ø Teilnehmer je Session", value="8", delta="aus der Mehrfachauswahl")
    with col3:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="01.09.2026")
        
    if st.button("➕ Neue Session starten", use_container_width=True):
        open_new_session_dialog()

    st.write("### Bisherige Sessions & Board-Endstände")
    with st.container():
        st.markdown("**01.09.2026** — *Up & Down · 4 Boards · Best of 5*")
        
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            r_b1 = st.session_state.board_rounds["Kaiser B1"]
            label_b1 = f"🏆 Kaiser B1\nRunde {r_b1}/4" if r_b1 <= 4 else "🏆 Kaiser B1\nBeendet"
            if st.button(label_b1, use_container_width=True, key="btn_b1"):
                open_board_dialog("Kaiser B1")
        with b2:
            r_b2 = st.session_state.board_rounds["Board 2"]
            label_b2 = f"🎯 Board 2\nRunde {r_b2}/4" if r_b2 <= 4 else "🎯 Board 2\nBeendet"
            if st.button(label_b2, use_container_width=True, key="btn_b2"):
                open_board_dialog("Board 2")
        with b3:
            r_b3 = st.session_state.board_rounds["Board 3"]
            label_b3 = f"🎯 Board 3\nRunde {r_b3}/4" if r_b3 <= 4 else "🎯 Board 3\nBeendet"
            if st.button(label_b3, use_container_width=True, key="btn_b3"):
                open_board_dialog("Board 3")
        with b4:
            r_b4 = st.session_state.board_rounds["Board 4"]
            label_b4 = f"🎯 Board 4\nRunde {r_b4}/4" if r_b4 <= 4 else "🎯 Board 4\nBeendet"
            if st.button(label_b4, use_container_width=True, key="btn_b4"):
                open_board_dialog("Board 4")

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
