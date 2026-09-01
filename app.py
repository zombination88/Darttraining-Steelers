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
        {
            "id": "S-1",
            "datum": "01.09.2026",
            "modus": "Up & Down",
            "boards": "4 Boards",
            "modus_leg": "Best of 5",
            "spieler": kader,
            "gaeste": [],
            "results": {}
        }
    ]

if "active_board_input" not in st.session_state:
    st.session_state.active_board_input = None

if "show_new_session" not in st.session_state:
    st.session_state.show_new_session = False

menu = st.sidebar.selectbox("Menü", ["Übersicht", "Kader", "Session", "Match-Archiv"])

def get_board_players(session, round_num, board_name):
    boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4"]
    b_idx = boards.index(board_name)
    
    if round_num == 1:
        spieler = session["spieler"]
        pairs = []
        for i in range(0, min(8, len(spieler) - len(spieler) % 2), 2):
            pairs.append((spieler[i], spieler[i+1]))
        while len(pairs) < 4:
            pairs.append((spieler[0] if spieler else "Offen", spieler[1] if len(spieler) > 1 else "Offen"))
        return list(pairs[b_idx])
    
    prev_r = round_num - 1
    res = session.get("results", {})
    w = {}
    l = {}
    for b in boards:
        match_info = res.get((prev_r, b))
        if match_info:
            w[b] = match_info["winner"]
            l[b] = match_info["loser"]
        else:
            def_players = get_board_players(session, prev_r, b)
            w[b] = def_players[0]
            l[b] = def_players[1]
            
    if b_idx == 0:
        return [w["Kaiser B1"], w["Board 2"]]
    elif b_idx == 1:
        return [l["Kaiser B1"], w["Board 3"]]
    elif b_idx == 2:
        return [l["Board 2"], w["Board 4"]]
    elif b_idx == 3:
        return [l["Board 3"], l["Board 4"]]
    return ["Offen", "Offen"]

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
            
            submitted = st.form_submit_button("Session starten")
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
                    "gaeste": gaeste,
                    "results": {}
                })
                st.session_state.show_new_session = False
                st.success("Session erfolgreich gestartet!")
                st.rerun()
            if cancel:
                st.session_state.show_new_session = False
                st.rerun()

    # Aktiver Eingabebereich für das ausgewählte Board
    if st.session_state.active_board_input:
        board_name, session_idx = st.session_state.active_board_input
        sess = st.session_state.sessions_list[session_idx]
        
        res = sess.get("results", {})
        completed_rounds = [r for (r, b) in res.keys() if b == board_name]
        current_round = max(completed_rounds) + 1 if completed_rounds else 1
        
        st.markdown("---")
        st.write(f"### 📋 Erfassung für {board_name} (Session {sess['id']}) — Runde {current_round} von 4")
        
        auto_players = get_board_players(sess, current_round, board_name)
        verfügbare_spieler = sess.get("spieler", kader)
        
        col1, col2 = st.columns(2)
        with col1:
            default_s1_idx = verfügbare_spieler.index(auto_players[0]) if auto_players[0] in verfügbare_spieler else 0
            s1 = st.selectbox("Spieler 1", verfügbare_spieler, index=default_s1_idx, key=f"d_s1_{board_name}_{session_idx}")
        with col2:
            remaining = [p for p in verfügbare_spieler if p != s1]
            default_s2_idx = remaining.index(auto_players[1]) if auto_players[1] in remaining else 0
            s2 = st.selectbox("Spieler 2", remaining, index=default_s2_idx if remaining else 0, key=f"d_s2_{board_name}_{session_idx}")
            
        ergebnis = st.text_input("Ergebnis (z. B. 3:1)", key=f"d_res_{board_name}_{session_idx}")
        
        winner = None
        loser = None
        if ergebnis and ":" in ergebnis:
            try:
                parts = ergebnis.split(":")
                score1 = int(parts[0].strip())
                score2 = int(parts[1].strip())
                if score1 > score2:
                    winner = s1
                    loser = s2
                elif score2 > score1:
                    winner = s2
                    loser = s1
                st.info(f"🏆 Automatischer Sieger: **{winner}**")
            except ValueError:
                st.warning("Ungültiges Format. Bitte z. B. 3:1 eingeben.")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Ergebnis speichern", key=f"d_save_{board_name}_{session_idx}"):
                if not winner:
                    st.error("Bitte ein gültiges Ergebnis eingeben.")
                else:
                    if "results" not in sess:
                        sess["results"] = {}
                    sess["results"][(current_round, board_name)] = {
                        "s1": s1,
                        "s2": s2,
                        "ergebnis": ergebnis,
                        "winner": winner,
                        "loser": loser
                    }
                    st.success(f"Ergebnis gespeichert! Sieger: {winner}")
                    st.session_state.active_board_input = None
                    st.rerun()
        with col_btn2:
            if st.button("Schließen", key=f"d_close_{board_name}_{session_idx}"):
                st.session_state.active_board_input = None
                st.rerun()
        st.markdown("---")

    st.write("### Bisherige Sessions & Board-Endstände")
    
    boards_list = ["Kaiser B1", "Board 2", "Board 3", "Board 4"]
    
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
            
            b_cols = st.columns(4)
            for b_i, b_name in enumerate(boards_list):
                with b_cols[b_i]:
                    res = sess.get("results", {})
                    completed = [r for (r, b) in res.keys() if b == b_name]
                    next_r = max(completed) + 1 if completed else 1
                    
                    if next_r <= 4:
                        label_btn = f"🎯 {b_name}\nRunde {next_r}/4"
                    else:
                        label_btn = f"🏆 {b_name}\nBeendet"
                        
                    if st.button(label_btn, use_container_width=True, key=f"btn_{b_name}_{idx}"):
                        st.session_state.active_board_input = (b_name, idx)
            st.divider()

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
