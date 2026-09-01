import streamlit as st
import pandas as pd
from datetime import date
import uuid

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
    st.write("Exakt 4 Runden, Aufstieg Richtung B1 und Abstieg Richtung B4.")
    
    with st.expander("➕ Gastspieler für diesen Abend hinzufügen (fließen nicht in die Statistik ein)"):
        gast_1 = st.text_input("Gastspieler 1", "")
        gast_2 = st.text_input("Gastspieler 2", "")
        gast_3 = st.text_input("Gastspieler 3", "")
        gast_4 = st.text_input("Gastspieler 4", "")
        
        aktuelle_gaeste = [g for g in [gast_1, gast_2, gast_3, gast_4] if g.strip() != ""]
        if aktuelle_gaeste:
            st.success(f"Aktive Gastspieler heute: {', '.join(aktuelle_gaeste)}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Gespielte Abende", value="1", delta="gefilterte Sessions")
    with col2:
        st.metric(label="Ø Teilnehmer je Session", value=f"{8 + len(aktuelle_gaeste)}", delta="inkl. Gäste")
    with col3:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="01.09.2026")
        
    if st.button("➕ Neue Session starten"):
        st.success("Session-Dialog geöffnet.")

    st.write("### Bisherige Sessions & Board-Endstände")
    with st.container():
        st.markdown("**01.09.2026** — *Up & Down · 4 Boards · Best of 5*")
        
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            st.info("**Kaiser B1**")
            st.text_input("Ergebnis B1", key="res_b1")
        with b2:
            st.info("**Board 2**")
            st.text_input("Ergebnis B2", key="res_b2")
        with b3:
            st.info("**Board 3**")
            st.text_input("Ergebnis B3", key="res_b3")
        with b4:
            st.info("**Board 4**")
            st.text_input("Ergebnis B4", key="res_b4")

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
