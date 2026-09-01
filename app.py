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

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = [
        {
            "id": "S-1",
            "datum": "01.09.2026",
            "modus": "Up & Down",
            "boards_count": 6,
            "boards": "6 Boards",
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

if "confirm_delete_idx" not in st.session_state:
    st.session_state.confirm_delete_idx = None

tab_übersicht, tab_kader, tab_session, tab_archiv = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv"])

def get_boards_list(boards_count):
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_board_players(session, round_num, board_name):
    boards_count = session.get("boards_count", 6)
    boards = get_boards_list(boards_count)
    if board_name not in boards:
        return ["Offen", "Offen"]
    b_idx = boards.index(board_name)
    
    if round_num == 1:
        spieler = session["spieler"]
        pairs = []
        for i in range(0, min(boards_count * 2, len(spieler) - len(spieler) % 2), 2):
            pairs.append((spieler[i], spieler[i+1]))
        while len(pairs) <= b_idx:
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
        return [w["Kaiser B1"], w.get("Board 2", "Offen") if boards_count > 1 else w["Kaiser B1"]]
    
    if b_idx > 0:
        prev_board = boards[b_idx - 1]
        next_board = boards[b_idx + 1] if b_idx + 1 < boards_count else None
        
        loser_from_above = l.get(prev_board, "Offen")
        winner_from_below = w.get(next_board, "Offen") if next_board else l.get(boards[b_idx], "Offen")
        return [loser_from_above, winner_from_below]
        
    return ["Offen", "Offen"]

def is_session_completed(sess):
    boards_count = sess.get("boards_count", 6)
    boards_list = get_boards_list(boards_count)
    res = sess.get("results", {})
    for b_name in boards_list:
        completed = [r for (r, b) in res.keys() if b == b_name]
        max_r = max(completed) if completed else 0
        if max_r < 4:
            return False
    return True

with tab_übersicht:
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
        last_s = st.session_state.sessions_list[0] if st.session_state.sessions_list else {"datum": "–"}
        st.info(f"**Datum:** {last_s['datum']}\n\n**Kaiser B1:** Noch offen\n\n**Höchstes Finish:** – (Spieler offen)\n\n**Meiste 180er:** – (Spieler offen)\n\n**Fahrstuhl-Award:** Offen")
    with col_r:
        st.markdown("### Spitzenreiter & Formkurve")
        st.caption("Sortiert nach Siegquote und absolvierten Matches")
        st.write("**Andrino Czombera** (50%)")
        st.progress(0.5)
        st.caption("1 Siege · 2 Matches")

    st.write("### Zuletzt ausgetragene Board-Matches")
    match_preview = {
        "Datum": ["01.09.2026"],
        "Runde": [1],
        "Board": ["B1"],
        "Spieler": ["Andrino Czombera vs Marco Eser"],
        "Ergebnis": ["3:1"],
        "Sieger": ["Andrino Czombera"]
    }
    st.dataframe(pd.DataFrame(match_preview), use_container_width=True, hide_index=True)

with tab_kader:
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

with tab_session:
    st.subheader("Up & Down Sessions")
    st.write("Exakt 4 Runden, Aufstieg Richtung B1 und Abstieg Richtung B6.")
    
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
            col_a, col_b = st.columns(2)
            with col_a:
                session_datum = st.date_input("Datum", date.today())
                leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
            with col_b:
                spielmodus = st.selectbox("Spielmodus", ["Up & Down", "Liga (4er-Team)"])
                anzahl_boards = st.selectbox("Anzahl der Boards", ["6 Boards", "5 Boards", "4 Boards", "3 Boards", "2 Boards", "1 Board"])
            
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
                boards_cnt = int(anzahl_boards.split()[0])
                
                new_session = {
                    "id": new_id,
                    "datum": session_datum.strftime("%d.%m.%Y"),
                    "modus": spielmodus,
                    "boards_count": boards_cnt,
                    "boards": anzahl_boards,
                    "modus_leg": leg_modus,
                    "spieler": aktive_spieler,
                    "gaeste": gaeste,
                    "results": {}
                }
                st.session_state.sessions_list.insert(0, new_session)
                st.session_state.show_new_session = False
                st.success("Session erfolgreich gestartet!")
                st.rerun()
            if cancel:
                st.session_state.show_new_session = False
                st.rerun()

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
            score1 = st.number_input(f"Legs für {s1}", min_value=0, max_value=5, value=3, key=f"d_score1_{board_name}_{session_idx}")
        with col2:
            remaining = [p for p in verfügbare_spieler if p != s1]
            default_s2_idx = remaining.index(auto_players[1]) if auto_players[1] in remaining else 0
            s2 = st.selectbox("Spieler 2", remaining, index=default_s2_idx if remaining else 0, key=f"d_s2_{board_name}_{session_idx}")
            score2 = st.number_input(f"Legs für {s2}", min_value=0, max_value=5, value=0, key=f"d_score2_{board_name}_{session_idx}")
            
        ergebnis = f"{score1}:{score2}"
        winner = s1 if score1 > score2 else (s2 if score2 > score1 else None)
        loser = s2 if winner == s1 else (s1 if winner == s2 else None)
        
        st.info(f"📊 Ergebnis: **{ergebnis}** | 🏆 Automatischer Sieger: **{winner if winner else 'Unentschieden'}**")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Ergebnis speichern", key=f"d_save_{board_name}_{session_idx}"):
                if score1 == score2:
                    st.error("Ein Unentschieden ist im Up & Down nicht möglich.")
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
    
    for idx, sess in enumerate(st.session_state.sessions_list):
        with st.container():
            gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
            status_text = " ✅ **[Abgeschlossen]**" if is_session_completed(sess) else ""
            st.markdown(f"**{sess['datum']}** — *{sess['modus']} · {sess['boards']} · {sess['modus_leg']} · {sess['id']}{gaeste_text}*{status_text}")
            
            boards_count = sess.get("boards_count", 6)
            active_boards_list = get_boards_list(boards_count)
            
            b_cols = st.columns(boards_count)
            for b_i, b_name in enumerate(active_boards_list):
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

with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    st.write("Hier kannst du gespeicherte Sessions verwalten und bei Bedarf sicher löschen.")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container():
                col_info, col_del = st.columns([0.8, 0.2])
                with col_info:
                    gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                    st.markdown(f"**{sess['id']}** — {sess['datum']} (*{sess['modus']} · {sess['boards']}*{gaeste_text})")
                with col_del:
                    if st.button("🗑️ Löschen", key=f"arch_del_btn_{idx}"):
                        st.session_state.confirm_delete_idx = idx
                
                if st.session_state.confirm_delete_idx == idx:
                    st.warning(f"Soll die Session **{sess['id']}** vom **{sess['datum']}** wirklich unwiderruflich gelöscht werden?")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("Ja, wirklich löschen", key=f"confirm_yes_{idx}", type="primary"):
                            st.session_state.sessions_list.pop(idx)
                            st.session_state.confirm_delete_idx = None
                            st.success("Session erfolgreich gelöscht.")
                            st.rerun()
                    with c_no:
                        if st.button("Abbrechen", key=f"confirm_no_{idx}"):
                            st.session_state.confirm_delete_idx = None
                            st.rerun()
                st.divider()
