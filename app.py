import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(page_title="Wehringer Steelers Teamcoach", layout="centered")

st.title("🎯 Wehringer Steelers - Teamcoach")

kader = [
    "Andrino Czombera", "Andreas Böhm", "Maximilian Zientner", "Michael Mak", 
    "Thomas Schaudt", "Marco Eser", "Dennis Güttner", "Michael Kummer", 
    "Michael Neumeier", "Wolfgang Schneider"
]

if "board_rounds" not in st.session_state:
    st.session_state.board_rounds = {
        "Kaiser B1": 1,
        "Board 2": 1,
        "Board 3": 1,
        "Board 4": 1
    }

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = [
        {"id": "S-1", "datum": "01.09.2026", "modus": "Up & Down", "boards": "4 Boards", "modus_leg": "Best of 5", "spieler": kader, "gaeste": []}
    ]

if "show_new_session" not in st.session_state:
    st.session_state.show_new_session = False

if "active_board" not in st.session_state:
    st.session_state.active_board = None

menu = st.sidebar.selectbox("Menü", ["Übersicht", "Kader", "Session", "Match-Archiv"])

if menu == "Übersicht":
    st.subheader("Übersicht")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Up & Down Abende", value=str(len(st.session_state.sessions_list)), delta="4 Runden pro Abend")
    with col2:
        st.metric(label="Gespielte Matches", value="2", delta="aus dem Archiv")
    with col3:
        st.metric(label="Aktive Spieler", value="10", delta="im Kader")
    with col4:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="01.09.2026")
        
    st.write("")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("### Letzte Session")
        st.caption("Die zuletzt gespeicherten Highlights")
        last_s = st.session_state.sessions_list[-1] if st.session_state.sessions_list else {"datum": "–"}
        st.info(f"**Datum:** {last_s['datum']}\n\n**Kaiser B1:** Noch offen\n\n**Höchstes Finish:** – (Spieler offen)\n\n**Meiste 180er:** – (Spieler offen)\n\n**Fahrstuhl-Award:** Offen")
    with col_r:
        st.markdown("### Spitzenreiter & Formkurve")
        st.caption("Sortiert nach Siegquote und absolvierten Matches")
        st.write("**Andrino Czombera** (50%)")
        st.progress(0.5)
        st.caption("1 Siege · 2 Matches")
        st.write("**Marco Eser** (0%)")
        st.progress(0.0)
        st.caption("0 Siege · 2 Matches")
        st.write("**Andreas Böhm** (0%)")
        st.progress(0.0)
        st.caption("0 Siege · 0 Matches")

    st.write("### Zuletzt ausgetragene Board-Matches")
    st.caption("Best of 5 und Gewinner für die Statistik")
    match_preview = {
        "Datum": ["01.09.2026"],
        "Runde": [1],
        "Board": ["B1"],
        "Spieler": ["Andrino Czombera vs Marco Eser"],
        "Ergebnis": ["3:1"],
        "Sieger": ["Andrino Czombera"]
    }
    st.dataframe(pd.DataFrame(match_preview), use_container_width=True, hide_index=True)

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
        st.metric(label="Gespielte Abende", value=str(len(st.session_state.sessions_list)), delta="gefilterte Sessions")
    with col2:
        st.metric(label="Ø Teilnehmer je Session", value="8", delta="aus der Mehrfachauswahl")
    with col3:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="01.09.2026")
        
    if st.button("➕ Neue Session starten", use_container_width=True):
        st.session_state.show_new_session = True

    if st.session_state.show_new_session:
        with st.form("new_session_form"):
            st.write("### Neue Session starten")
            st.write("Einmalig die Rahmenbedingungen festlegen.")
            col_a, col_b = st.columns(2)
            with col_a:
                session_datum = st.date_input("Datum", date.today())
                leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
            with col_b:
                spielmodus = st.selectbox("Spielmodus", ["Up & Down", "Liga (4er-Team)"])
                anzahl_boards = st.selectbox("Anzahl der Boards", ["4 Boards", "2 Boards", "3 Boards", "1 Board"])
            
            st.write("### Anwesende Spieler")
            anwesende = []
            cols = st.columns(2)
            half = len(kader) // 2
            with cols[0]:
                for spieler in kader[:half]:
                    if st.checkbox(spieler, value=True, key=f"form_kader_{spieler}"):
                        anwesende.append(spieler)
            with cols[1]:
                for spieler in kader[half:]:
                    if st.checkbox(spieler, value=True, key=f"form_kader_{spieler}"):
                        anwesende.append(spieler)
                        
            st.write("### Gastspieler (optional, max. 4)")
            g1 = st.text_input("Gastspieler 1", key="form_gast_1")
            g2 = st.text_input("Gastspieler 2", key="form_gast_2")
            g3 = st.text_input("Gastspieler 3", key="form_gast_3")
            g4 = st.text_input("Gastspieler 4", key="form_gast_4")
            
            submitted = st.form_submit_button("Session anlegen")
            cancel = st.form_submit_button("Abbrechen")
            
            if submitted:
                gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
                aktive_spieler = anwesende + gaeste
                new_id = f"S-{len(st.session_state.sessions_list) + 1}"
                st.session_state.sessions_list.append({
                    "id": new_id,
                    "datum": session_datum.strftime("%d.%m.%Y"),
                    "modus": spielmodus,
                    "boards": anzahl_boards,
                    "modus_leg": leg_modus,
                    "spieler": aktive_spieler,
                    "gaeste": gaeste
                })
                st.session_state.show_new_session = False
                st.success("Session erfolgreich erstellt!")
                st.rerun()
            if cancel:
                st.session_state.show_new_session = False
                st.rerun()

    st.write("### Bisherige Sessions & Board-Endstände")
    
    for idx, sess in enumerate(st.session_state.sessions_list):
        with st.container():
            col_info, col_del = st.columns([0.85, 0.15])
            with col_info:
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                st.markdown(f"**{sess['datum']}** — *{sess['modus']} · {sess['boards']} · {sess['modus_leg']} · {sess['id']}{gaeste_text}*")
            with col_del:
                if st.button("🗑️ Löschen", key=f"del_sess_{idx}"):
                    st.session_state.sessions_list.pop(idx)
                    st.rerun()
            
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                r_b1 = st.session_state.board_rounds["Kaiser B1"]
                label_b1 = f"🏆 Kaiser B1\nRunde {r_b1}/4" if r_b1 <= 4 else "🏆 Kaiser B1\nBeendet"
                if st.button(label_b1, use_container_width=True, key=f"btn_b1_{idx}"):
                    st.session_state.active_board = ("Kaiser B1", idx)
            with b2:
                r_b2 = st.session_state.board_rounds["Board 2"]
                label_b2 = f"🎯 Board 2\nRunde {r_b2}/4" if r_b2 <= 4 else "🎯 Board 2\nBeendet"
                if st.button(label_b2, use_container_width=True, key=f"btn_b2_{idx}"):
                    st.session_state.active_board = ("Board 2", idx)
            with b3:
                r_b3 = st.session_state.board_rounds["Board 3"]
                label_b3 = f"🎯 Board 3\nRunde {r_b3}/4" if r_b3 <= 4 else "🎯 Board 3\nBeendet"
                if st.button(label_b3, use_container_width=True, key=f"btn_b3_{idx}"):
                    st.session_state.active_board = ("Board 3", idx)
            with b4:
                r_b4 = st.session_state.board_rounds["Board 4"]
                label_b4 = f"🎯 Board 4\nRunde {r_b4}/4" if r_b4 <= 4 else "🎯 Board 4\nBeendet"
                if st.button(label_b4, use_container_width=True, key=f"btn_b4_{idx}"):
                    st.session_state.active_board = ("Board 4", idx)
            st.divider()

    if st.session_state.active_board:
        board_name, sess_idx = st.session_state.active_board
        current_round = st.session_state.board_rounds[board_name]
        st.markdown(f"--- \n### 📋 Erfassung für {board_name} — Runde {current_round} von 4")
        
        verfügbare_spieler = st.session_state.sessions_list[sess_idx].get("spieler", kader)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            s1 = st.selectbox("Spieler 1", verfügbare_spieler, key=f"active_s1_{board_name}")
        with col_s2:
            s2 = st.selectbox("Spieler 2", [p for p in verfügbare_spieler if p != s1], key=f"active_s2_{board_name}")
            
        ergebnis = st.text_input("Ergebnis (z. B. 3:1)", key=f"active_res_{board_name}")
        
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("Ergebnis speichern", key=f"active_save_{board_name}"):
                st.success(f"{board_name} (Runde {current_round}): {s1} vs {s2} [{ergebnis}] gespeichert!")
                if st.session_state.board_rounds[board_name] < 4:
                    st.session_state.board_rounds[board_name] += 1
                st.session_state.active_board = None
                st.rerun()
        with col_act2:
            if st.button("Schließen", key=f"active_close_{board_name}"):
                st.session_state.active_board = None
                st.rerun()

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
