import streamlit as st
import pandas as pd
from datetime import date
import json
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Wehringer Steeler - Teamtraining", layout="centered")

# --- KONFIGURATION ---
# WICHTIG: Füge hier den Link zu deiner eigenen Google Tabelle ein!
SHEET_URL = "HIER_DEINEN_TABELLEN_LINK_EINFÜGEN" 


# Verbindung zu Google Sheets herstellen
try:
    creds_dict = json.loads(st.secrets["google_json"])
    conn = st.connection("gsheets", type=GSheetsConnection, **creds_dict)
except Exception as e:
    st.error(f"Fehler bei der Datenbankverbindung. Bitte Secrets prüfen: {e}")
    st.stop()

def load_data():
    if SHEET_URL == "HIER_DEINEN_TABELLEN_LINK_EINFÜGEN" or SHEET_URL == "":
        st.warning("Bitte trage in Zeile 10 in der app.py noch deinen Google Sheets Link (die komplette https:// URL) ein!")
        return []
        
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="sessions", ttl=0)
        if df is not None and not df.empty and "json_data" in df.columns:
            raw_str = df["json_data"].dropna().iloc[0]
            raw_data = json.loads(raw_str)
            sessions = []
            for sess in raw_data:
                fixed_results = {}
                for k, v in sess.get("results", {}).items():
                    parts = k.split("_", 1)
                    if len(parts) == 2:
                        r_num = int(parts[0])
                        b_name = parts[1]
                        fixed_results[(r_num, b_name)] = v
                sess["results"] = fixed_results
                sessions.append(sess)
            return sessions
    except Exception as e:
        st.error(f"Fehler beim Laden aus Google Sheets: {e}")
    return []

def save_data(sessions):
    serializable_sessions = []
    for sess in sessions:
        sess_copy = sess.copy()
        fixed_results = {}
        for (r_num, b_name), v in sess.get("results", {}).items():
            fixed_results[f"{r_num}_{b_name}"] = v
        sess_copy["results"] = fixed_results
        serializable_sessions.append(sess_copy)
    
    json_str = json.dumps(serializable_sessions, ensure_ascii=False)
    df_to_save = pd.DataFrame({"json_data": [json_str]})
    
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet="sessions", data=df_to_save)
    except Exception as e:
        st.error(f"Fehler beim Speichern in Google Sheets: {e}")

col1, col2 = st.columns([1, 6])
with col1:
    try:
        st.image("logo.png.png", width=85)
    except Exception:
        pass
with col2:
    st.markdown("<h1 style='margin: 0; padding-top: 12px; font-size: 2.2rem;'>Wehringer Steeler - Teamtraining</h1>", unsafe_allow_html=True)

kader = [
    "Andreas Böhm",
    "Andrino Czombera",
    "Dennis Güttner",
    "Marco Eser",
    "Maximilian Zientner",
    "Michael Kummer",
    "Michael Mak",
    "Michael Neumeier",
    "Thomas Schaudt",
    "Wolfgang Schneider"
]

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = load_data()

tab_übersicht, tab_kader, tab_session, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv", "BDV-Regeln"])

def get_boards_list(boards_count):
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_board_players(session, round_num, board_name):
    boards_count = session.get("boards_count", 6)
    boards = get_boards_list(boards_count)
    if board_name not in boards:
        return ["Offen", "Offen"]
    b_idx = boards.index(board_name)
    
    is_2v2 = (session.get("modus") == "Koop 2vs2 (Up & Down)")
    
    if round_num == 1:
        spieler = session["spieler"]
        pairs = []
        
        if is_2v2:
            teams = []
            for i in range(0, len(spieler)-1, 2):
                teams.append(f"{spieler[i]} & {spieler[i+1]}")
            if len(spieler) % 2 != 0:
                teams.append(f"{spieler[-1]} & Offen")
                
            for i in range(0, min(boards_count * 2, len(teams) - len(teams) % 2), 2):
                pairs.append((teams[i], teams[i+1]))
            while len(pairs) <= b_idx:
                t1 = teams[0] if len(teams) > 0 else "Offen"
                t2 = teams[1] if len(teams) > 1 else "Offen"
                pairs.append((t1, t2))
        else:
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

def is_board_ready(session, board_name, next_r):
    if next_r == 1:
        return True
    
    boards_count = session.get("boards_count", 6)
    boards = get_boards_list(boards_count)
    if board_name not in boards:
        return False
        
    b_idx = boards.index(board_name)
    res = session.get("results", {})
    prev_r = next_r - 1
    
    req_boards = []
    if b_idx == 0:
        req_boards.append(boards[0])
        if boards_count > 1:
            req_boards.append(boards[1])
    else:
        req_boards.append(boards[b_idx - 1])
        if b_idx + 1 < boards_count:
            req_boards.append(boards[b_idx + 1])
        else:
            req_boards.append(boards[b_idx])
            
    for rb in req_boards:
        found = False
        for (r, b) in res.keys():
            if r == prev_r and b == rb:
                found = True
                break
        if not found:
            return False
            
    return True

def is_session_completed(sess):
    boards_count = sess.get("boards_count", 6)
    total_rounds = sess.get("total_rounds", 4)
    boards_list = get_boards_list(boards_count)
    res = sess.get("results", {})
    for b_name in boards_list:
        completed = [r for (r, b) in res.keys() if b == b_name]
        max_r = max(completed) if completed else 0
        if max_r < total_rounds:
            return False
    return True

@st.dialog("➕ Neue Session starten (Passwortgeschützt)")
def open_new_session_dialog():
    pwd = st.text_input("Passwort eingeben", type="password", key="dialog_pwd_input")
    if pwd != "1521":
        if pwd != "":
            st.error("Falsches Passwort!")
        return

    session_datum = st.date_input("Datum", date.today())
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
    total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=3)
    spielmodus = st.selectbox("Spielmodus", ["Up & Down", "Koop 2vs2 (Up & Down)", "Liga (4er-Team)"])
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
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True):
            st.rerun()
    with col_b2:
        if st.button("Session starten", type="primary", use_container_width=True):
            gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
            aktive_spieler = anwesende + gaeste
            new_id = f"S-{len(st.session_state.sessions_list) + 1}"
            boards_cnt = int(anzahl_boards.split()[0])
            
            new_session = {
                "id": new_id,
                "datum": session_datum.strftime("%d.%m.%Y"),
                "modus": spielmodus,
                "boards_count": boards_cnt,
                "total_rounds": total_rounds,
                "boards": anzahl_boards,
                "modus_leg": leg_modus,
                "spieler": aktive_spieler,
                "gaeste": gaeste,
                "results": {}
            }
            st.session_state.sessions_list.insert(0, new_session)
            save_data(st.session_state.sessions_list)
            st.success("Session erfolgreich gestartet!")
            st.rerun()

@st.dialog("⚙️ Session bearbeiten (Passwortgeschützt)")
def open_edit_session_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"edit_pwd_input_{session_idx}")
    if pwd != "1521":
        if pwd != "":
            st.error("Falsches Passwort!")
        return

    sess = st.session_state.sessions_list[session_idx]
    
    try:
        curr_date = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except:
        curr_date = date.today()

    session_datum = st.date_input("Datum", curr_date, key=f"edit_date_{session_idx}")
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"], index=["Best of 5", "Best of 3"].index(sess.get("modus_leg", "Best of 5")), key=f"edit_leg_{session_idx}")
    total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=sess.get("total_rounds", 4)-1, key=f"edit_rounds_{session_idx}")
    
    modi_list = ["Up & Down", "Koop 2vs2 (Up & Down)", "Liga (4er-Team)"]
    curr_modus = sess.get("modus", "Up & Down")
    if curr_modus not in modi_list: modi_list.append(curr_modus)
    spielmodus = st.selectbox("Spielmodus", modi_list, index=modi_list.index(curr_modus), key=f"edit_modus_{session_idx}")
    
    board_opts = ["6 Boards", "5 Boards", "4 Boards", "3 Boards", "2 Boards", "1 Board"]
    curr_b = sess.get("boards", "6 Boards")
    if curr_b not in board_opts: board_opts.append(curr_b)
    anzahl_boards = st.selectbox("Anzahl der Boards", board_opts, index=board_opts.index(curr_b), key=f"edit_bcount_{session_idx}")
    
    st.write("### Anwesende Spieler anpassen")
    anwesende = []
    cols = st.columns(2)
    half = len(kader) // 2
    
    curr_spieler = sess.get("spieler", [])
    curr_gaeste = sess.get("gaeste", [])
    
    with cols[0]:
        for spieler in kader[:half]:
            if st.checkbox(spieler, value=(spieler in curr_spieler), key=f"edit_kader_{spieler}_{session_idx}"):
                anwesende.append(spieler)
    with cols[1]:
        for spieler in kader[half:]:
            if st.checkbox(spieler, value=(spieler in curr_spieler), key=f"edit_kader_{spieler}_{session_idx}"):
                anwesende.append(spieler)
                
    st.write("### Gastspieler anpassen")
    g1 = st.text_input("Gastspieler 1", value=curr_gaeste[0] if len(curr_gaeste)>0 else "", key=f"edit_gast1_{session_idx}")
    g2 = st.text_input("Gastspieler 2", value=curr_gaeste[1] if len(curr_gaeste)>1 else "", key=f"edit_gast2_{session_idx}")
    g3 = st.text_input("Gastspieler 3", value=curr_gaeste[2] if len(curr_gaeste)>2 else "", key=f"edit_gast3_{session_idx}")
    g4 = st.text_input("Gastspieler 4", value=curr_gaeste[3] if len(curr_gaeste)>3 else "", key=f"edit_gast4_{session_idx}")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True, key=f"edit_cancel_{session_idx}"):
            st.rerun()
    with col_b2:
        if st.button("Änderungen speichern", type="primary", use_container_width=True, key=f"edit_save_{session_idx}"):
            gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
            aktive_spieler = anwesende + gaeste
            boards_cnt = int(anzahl_boards.split()[0])
            
            sess["datum"] = session_datum.strftime("%d.%m.%Y")
            sess["modus"] = spielmodus
            sess["boards_count"] = boards_cnt
            sess["total_rounds"] = total_rounds
            sess["boards"] = anzahl_boards
            sess["modus_leg"] = leg_modus
            sess["spieler"] = aktive_spieler
            sess["gaeste"] = gaeste
            
            st.session_state.sessions_list[session_idx] = sess
            save_data(st.session_state.sessions_list)
            st.success("Session erfolgreich aktualisiert!")
            st.rerun()

@st.dialog("📋 Board-Erfassung")
def open_board_dialog(board_name, session_idx):
    sess = st.session_state.sessions_list[session_idx]
    total_rounds = sess.get("total_rounds", 4)
    
    res = sess.get("results", {})
    completed_rounds = [r for (r, b) in res.keys() if b == board_name]
    current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > total_rounds:
        st.warning(f"{board_name} hat alle {total_rounds} Runden bereits beendet.")
        if st.button("Schließen", use_container_width=True):
            st.rerun()
        return

    st.write(f"### {board_name} (Session {sess['id']}) — Runde {current_round} von {total_rounds}")
    
    auto_players = get_board_players(sess, current_round, board_name)
    
    is_2v2 = (sess.get("modus") == "Koop 2vs2 (Up & Down)")
    if is_2v2:
        base_teams = []
        spieler_list = sess.get("spieler", kader)
        for i in range(0, len(spieler_list)-1, 2):
            base_teams.append(f"{spieler_list[i]} & {spieler_list[i+1]}")
        if len(spieler_list) % 2 != 0:
            base_teams.append(f"{spieler_list[-1]} & Offen")
        verfügbare_spieler = list(set(base_teams + auto_players))
        if "Offen" not in verfügbare_spieler: verfügbare_spieler.append("Offen")
    else:
        verfügbare_spieler = sess.get("spieler", kader)
        if "Offen" not in verfügbare_spieler: verfügbare_spieler.append("Offen")
    
    col1, col2 = st.columns(2)
    with col1:
        default_s1_idx = verfügbare_spieler.index(auto_players[0]) if auto_players[0] in verfügbare_spieler else 0
        s1 = st.selectbox("Team / Spieler 1", verfügbare_spieler, index=default_s1_idx, key=f"d_s1_{board_name}_{session_idx}")
        score1 = st.number_input(f"Legs für Heim", min_value=0, max_value=5, value=3, key=f"d_score1_{board_name}_{session_idx}")
    with col2:
        remaining = [p for p in verfügbare_spieler if p != s1]
        default_s2_idx = remaining.index(auto_players[1]) if auto_players[1] in remaining else 0
        s2 = st.selectbox("Team / Spieler 2", remaining, index=default_s2_idx if remaining else 0, key=f"d_s2_{board_name}_{session_idx}")
        score2 = st.number_input(f"Legs für Gast", min_value=0, max_value=5, value=0, key=f"d_score2_{board_name}_{session_idx}")
        
    ergebnis = f"{score1}:{score2}"
    winner = s1 if score1 > score2 else (s2 if score2 > score1 else None)
    loser = s2 if winner == s1 else (s1 if winner == s2 else None)
    
    st.info(f"📊 Ergebnis: **{ergebnis}** | 🏆 Sieger: **{winner if winner else 'Unentschieden'}**")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Ergebnis speichern", type="primary", use_container_width=True, key=f"d_save_{board_name}_{session_idx}"):
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
                save_data(st.session_state.sessions_list)
                st.success("Ergebnis gespeichert!")
                st.rerun()
    with col_btn2:
        if st.button("Schließen", use_container_width=True, key=f"d_close_{board_name}_{session_idx}"):
            st.rerun()

@st.dialog("🗑️ Session löschen (Passwortgeschützt)")
def open_delete_dialog(session_idx):
    if session_idx >= len(st.session_state.sessions_list):
        st.rerun()
        return
        
    sess = st.session_state.sessions_list[session_idx]
    st.warning(f"Soll die Session **{sess['id']}** vom **{sess['datum']}** wirklich unwiderruflich gelöscht werden?")
    
    pwd = st.text_input("Passwort zur Bestätigung", type="password", key=f"del_pwd_input_{session_idx}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Abbrechen", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Unwiderruflich löschen", type="primary", use_container_width=True):
            if pwd == "1521":
                st.session_state.sessions_list.pop(session_idx)
                save_data(st.session_state.sessions_list)
                st.success("Session erfolgreich gelöscht!")
                st.rerun()
            elif pwd != "":
                st.error("Falsches Passwort!")

with tab_übersicht:
    st.subheader("Übersicht & Live-Status")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Neue Session starten", type="primary", use_container_width=True, key="quick_start_btn"):
            open_new_session_dialog()
    with col_btn2:
        active_sessions_for_btn = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
        if active_sessions_for_btn:
            if st.button("⚙️ Aktive Session bearbeiten", use_container_width=True, key="edit_active_btn"):
                open_edit_session_dialog(st.session_state.sessions_list.index(active_sessions_for_btn[0]))
        else:
            st.button("⚙️ Aktive Session bearbeiten", use_container_width=True, disabled=True)
        
    st.write("")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Up & Down Abende", value=str(len(st.session_state.sessions_list)), delta="Runden pro Abend")
    with col2:
        st.metric(label="Gespielte Matches", value="Dynamisch", delta="siehe Kader")
    with col3:
        st.metric(label="Aktive Spieler", value="10", delta="im Kader")
    with col4:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="01.09.2026")
        
    st.write("")
    
    st.markdown("### 🔴 Laufende Session")
    if not active_sessions_for_btn:
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Übersicht zu sehen.")
    else:
        curr_sess = active_sessions_for_btn[0]
        st.caption(f"Session-ID: **{curr_sess['id']}** vom {curr_sess['datum']} ({curr_sess['modus']})")
        
        boards_count = curr_sess.get("boards_count", 6)
        active_boards_list = get_boards_list(boards_count)
        total_rounds = curr_sess.get("total_rounds", 4)
        
        session_stats = {p: {"legs_won": 0, "legs_lost": 0} for p in curr_sess.get("spieler", [])}
        for match in curr_sess.get("results", {}).values():
            s1 = match.get("s1", "")
            s2 = match.get("s2", "")
            ergebnis = match.get("ergebnis", "0:0")
            
            try:
                l1, l2 = map(int, ergebnis.split(":"))
            except ValueError:
                l1, l2 = 0, 0
            
            for p in s1.split(" & "):
                if p in session_stats:
                    session_stats[p]["legs_won"] += l1
                    session_stats[p]["legs_lost"] += l2
            for p in s2.split(" & "):
                if p in session_stats:
                    session_stats[p]["legs_won"] += l2
                    session_stats[p]["legs_lost"] += l1
        
        cols_per_row = 3
        for i in range(0, len(active_boards_list), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(active_boards_list):
                    b_name = active_boards_list[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            res = curr_sess.get("results", {})
                            completed_rounds = [r for (r, b) in res.keys() if b == b_name]
                            next_r = max(completed_rounds) + 1 if completed_rounds else 1
                            
                            st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                            
                            if next_r <= total_rounds:
                                ready = is_board_ready(curr_sess, b_name, next_r)
                                ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                                st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                                
                                players_now = get_board_players(curr_sess, min(next_r, total_rounds), b_name)
                                p1, p2 = players_now[0], players_now[1]
                                
                                p1_display = p1.replace(" & ", "<br>&<br>")
                                p2_display = p2.replace(" & ", "<br>&<br>")
                                
                                p1_first = p1.split(" & ")[0]
                                p2_first = p2.split(" & ")[0]
                                
                                p1_stat = f"Legs: {session_stats.get(p1_first, {}).get('legs_won', 0)}:{session_stats.get(p1_first, {}).get('legs_lost', 0)}" if p1 != "Offen" else ""
                                p2_stat = f"Legs: {session_stats.get(p2_first, {}).get('legs_won', 0)}:{session_stats.get(p2_first, {}).get('legs_lost', 0)}" if p2 != "Offen" else ""
                                
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Runde {next_r}/{total_rounds}</p>", unsafe_allow_html=True)
                                
                                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.0em;'>{p1_display}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='text-align: center; color: gray; font-size: 0.8em;'>{p1_stat}</div>", unsafe_allow_html=True)
                                
                                st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 5px 0;'>VS</div>", unsafe_allow_html=True)
                                
                                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.0em;'>{p2_display}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='text-align: center; color: gray; font-size: 0.8em; margin-bottom: 15px;'>{p2_stat}</div>", unsafe_allow_html=True)
                                
                                if st.button("🎯 Ergebnis eintragen", key=f"live_btn_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                                    open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess))
                            else:
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle {total_rounds} Runden beendet</p>", unsafe_allow_html=True)
                                st.success("✅ Board abgeschlossen")

    st.write("")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("### Letzte Session")
        last_s = st.session_state.sessions_list[0] if st.session_state.sessions_list else {"datum": "–"}
        st.info(f"**Datum:** {last_s.get('datum', '–')}\n\n**Kaiser B1:** Noch offen\n\n**Höchstes Finish:** – (Spieler offen)\n\n**Meiste 180er:** – (Spieler offen)\n\n**Fahrstuhl-Award:** Offen")
    with col_r:
        st.markdown("### Spitzenreiter & Formkurve")
        st.caption("Sortiert nach Siegquote und absolvierten Matches")
        st.write("**Andrino Czombera**")
        st.progress(0.0)

    st.write("### Zuletzt ausgetragene Board-Matches")
    st.caption("Best of 5 und Gewinner für die Statistik")
    
    all_matches = []
    for sess in st.session_state.sessions_list:
        sess_date = sess.get("datum", "")
        for (round_num, board_name), m_info in sess.get("results", {}).items():
            all_matches.append({
                "Datum": sess_date,
                "Runde": round_num,
                "Board": board_name,
                "Spieler": f"{m_info['s1']}\n{m_info['s2']}",
                "Ergebnis": m_info['ergebnis'],
                "Sieger": m_info['winner'] if m_info['winner'] else "Offen"
            })
            
    if all_matches:
        df_matches = pd.DataFrame(all_matches)
        st.dataframe(df_matches, use_container_width=True, hide_index=True)
    else:
        st.info("Bisher wurden keine Board-Matches ausgetragen.")

with tab_kader:
    st.subheader("Kader & Spielerbilanz")
    st.write("Live berechnete Bilanz des festen Stammkaders (exklusive Gastspieler).")
    
    stats = {p: {"Matches": 0, "Siege": 0, "Niederlagen": 0} for p in kader}
    
    player_matches_played = 0
    total_wins = 0
    total_losses = 0
    
    for sess in st.session_state.sessions_list:
        for match in sess.get("results", {}).values():
            winner = match.get("winner", "")
            loser = match.get("loser", "")
            
            if winner:
                for p in winner.split(" & "):
                    if p in stats:
                        stats[p]["Matches"] += 1
                        stats[p]["Siege"] += 1
                        player_matches_played += 1
                        total_wins += 1
            if loser:
                for p in loser.split(" & "):
                    if p in stats:
                        stats[p]["Matches"] += 1
                        stats[p]["Niederlagen"] += 1
                        player_matches_played += 1
                        total_losses += 1

    total_games = total_wins + total_losses
    avg_win_rate = f"{(total_wins / total_games * 100):.0f}%" if total_games > 0 else "0%"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
    with col2:
        st.metric(label="Absolvierte Spieler-Matches", value=str(player_matches_played), delta="aus Sessions")
    with col3:
        st.metric(label="Ø Siegquote", value=avg_win_rate, delta="gesamt")
        
    st.write("### Spielerübersicht & Rangliste")
    suche = st.text_input("Spieler suchen...", "")
    
    table_rows = []
    for p in kader:
        m = stats[p]["Matches"]
        s = stats[p]["Siege"]
        n = stats[p]["Niederlagen"]
        quote = f"{(s / m * 100):.0f}%" if m > 0 else "0%"
        table_rows.append({
            "Spieler": p,
            "Matches": m,
            "Siege": s,
            "Niederlagen": n,
            "Siegquote": quote
        })
        
    df_kader = pd.DataFrame(table_rows)
    if suche:
        df_kader = df_kader[df_kader["Spieler"].str.contains(suche, case=False)]
    st.dataframe(df_kader, use_container_width=True, hide_index=True)

with tab_session:
    st.subheader("Up & Down Sessions")
    st.write("Aufstieg Richtung B1 und Abstieg Richtung B6.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Gespielte Abende", value=str(len(st.session_state.sessions_list)), delta="gefilterte Sessions")
    with col2:
        st.metric(label="Ø Teilnehmer je Session", value="8", delta="aus der Mehrfachauswahl")
    with col3:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="01.09.2026")
        
    if st.button("➕ Neue Session starten", use_container_width=True, key="tab_session_new"):
        open_new_session_dialog()

    st.write("### Bisherige Sessions & Board-Endstände")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden. Starte über den Button oben eine neue Session.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container():
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                status_text = " ✅ **[Abgeschlossen]**" if is_session_completed(sess) else ""
                total_rounds = sess.get("total_rounds", 4)
                st.markdown(f"**{sess['datum']}** — *{sess['modus']} · {sess['boards']} · {total_rounds} Runden · {sess['modus_leg']} · {sess['id']}{gaeste_text}*{status_text}")
                
                boards_count = sess.get("boards_count", 6)
                active_boards_list = get_boards_list(boards_count)
                
                b_cols = st.columns(boards_count)
                for b_i, b_name in enumerate(active_boards_list):
                    with b_cols[b_i]:
                        res = sess.get("results", {})
                        completed = [r for (r, b) in res.keys() if b == b_name]
                        next_r = max(completed) + 1 if completed else 1
                        
                        if next_r <= total_rounds:
                            label_btn = f"🎯 {b_name}\nRunde {next_r}/{total_rounds}"
                        else:
                            label_btn = f"🏆 {b_name}\nBeendet"
                            
                        if st.button(label_btn, use_container_width=True, key=f"btn_{b_name}_{idx}"):
                            open_board_dialog(b_name, idx)
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
                    total_rounds = sess.get("total_rounds", 4)
                    st.markdown(f"**{sess['id']}** — {sess['datum']} (*{sess['modus']} · {sess['boards']} · {total_rounds} Runden*{gaeste_text})")
                with col_del:
                    if st.button("🗑️ Löschen", key=f"arch_del_btn_{idx}"):
                        open_delete_dialog(idx)
                st.divider()

with tab_regeln:
    st.markdown("""
# **Leitfaden Ligabetrieb BDV – Bezirk Schwaben**
1.  Mannschaft & Meldung
2.  Spielmodus & Ablauf (Liga und Pokal)
3.  Spielbericht & Online-Meldung
4.  Mannschaftsvorstellung (Kader)

### 1. Mannschaft & Meldung
  - **Mannschaftsmeldung:** Erledigt.
  - **Spielerkader:** Besteht aus 10 Spielern. Die namentliche Meldung erfolgt bis zum 31. August in der Online-Software (nuLiga).

### 2. Spielmodus & Ablauf (Liga und Pokal)
  - **Heimspieltag ist Dienstag **
  - **Modus:** 4er-Team; ein Spieltag umfasst 8 Einzel und 2 Doppel (501 Steeldart, Best-of-5, Double-Out).
  - **Aufstellung (3 Blöcke):**
      - **Block 1:** 4 Einzelspieler.
      - **Block 2:** 4 Einzelspieler (Reihenfolge 1–4 fix, Wechseloption auf den Positionen möglich).
      - **Block 3:** 2 Doppel (freie Aufstellung aus dem Tageskader von maximal 8 Spielern; Spieler aus den Einzeln können erneut eingesetzt werden).
  - **Rahmenbedingungen:**
      - **Spielzeit:** Mo–Do ab 20:00 Uhr.
      - **Austragung:** Parallel auf zwei Boards.
      - **Einwerfzeit:** 30 Minuten für Gäste.
  - **Board-Zuordnung & Schreiber:**
    - Die Heimmannschaft schreibt und beginnt auf Board 1.  
    - Die Gastmannschaft schreibt und beginnt auf Board 2.  
  - **Schwabenpokal:**
    - Nur K.O. Runden
    - Es können bis zu 4-5 Spiele mehr in der Session zur Liga sein (je nach Teamgröße)

### 3. Spielbericht & Online-Meldung
  - **Papier-Spielbericht:** Händische Führung; alle Sätze und Legs werden notiert und von beiden Kapitänen unterschrieben.
  - **Ergebnismeldung:** Muss innerhalb von 6 Stunden nach Spielbeginn via Online-Schnellerfassung gemeldet werden.
  - **Berichtsabgabe:** Vollständige Online-Eingabe innerhalb von 48 Stunden.
  - **Aufbewahrung:** Die Originale müssen bis Saisonende im Verein aufbewahrt werden.

### 4. Mannschaftsvorstellung (Kader)
  - Andreas Böhm
  - Andrino Czombera (Teamcaptain)
  - Dennis Güttner
  - Marco Eser
  - Maximilian Zientner
  - Michael Kummer
  - Michael Mak
  - Michael Neumeier
  - Thomas Schaudt
  - Wolfgang Schneider
    """)
```eof

Bitte kopiere den Code und tausche in Zeile 10 `"HIER_DEINEN_TABELLEN_LINK_EINFÜGEN"` durch deinen tatsächlichen Link aus (Achte darauf, dass die Anführungszeichen `"` am Anfang und am Ende des Links stehen bleiben).
