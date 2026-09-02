import streamlit as st
import pandas as pd
from datetime import date
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wehringer Steeler - Teamtraining", layout="centered")

# --- KONFIGURATION ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1Z0TqSb-4qCES7gMrFv0MUCVdcnRV5kiaDCokzKTrr-8/edit?gid=0#gid=0"

@st.cache_resource
def init_connection():
    try:
        creds_dict = json.loads(st.secrets["google_json"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).worksheet("sessions")
        return sheet
    except Exception as e:
        return None

sheet_conn = init_connection()

def load_data():
    if not sheet_conn:
        return []
        
    try:
        data = sheet_conn.get_all_records()
        if data and "json_data" in data[0]:
            raw_str = data[0]["json_data"]
            if raw_str:
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
    if not sheet_conn:
        return
        
    serializable_sessions = []
    for sess in sessions:
        sess_copy = sess.copy()
        fixed_results = {}
        for (r_num, b_name), v in sess.get("results", {}).items():
            fixed_results[f"{r_num}_{b_name}"] = v
        sess_copy["results"] = fixed_results
        serializable_sessions.append(sess_copy)
    
    json_str = json.dumps(serializable_sessions, ensure_ascii=False)
    try:
        sheet_conn.clear()
        sheet_conn.update([["json_data"], [json_str]])
    except Exception as e:
        st.error(f"Fehler beim Speichern in Google Sheets: {e}")

col1, col2 = st.columns([1, 6])
with col1:
    try:
        st.image("logo.png.png", width=85)
    except Exception:
        pass
    
    with st.popover("🎵 ▾", help="Vereinssong abspielen"):
        try:
            with open("vereinssong.mp3", "rb") as audio_file:
                audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3")
        except Exception:
            st.warning("`vereinssong.mp3` nicht gefunden.")

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
    "Wolfgang Scheider"
]

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = load_data()

tab_übersicht, tab_kader, tab_session, tab_archiv, tab_bdv = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv", "BDV-Regeln"])

def get_boards_list(session, round_num=None):
    boards_count = session.get("boards_count", 4)
    modus = session.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num is not None and round_num > singles_rounds
    
    if in_coop_phase:
        return ["Kaiser B1", "Board 2"]
        
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_resting_player(session, round_num):
    spieler = session.get("spieler", [])
    boards = get_boards_list(session, round_num)
    boards_count = len(boards)
    max_active = boards_count * 2
    
    if len(spieler) <= max_active or len(spieler) % 2 == 0:
        return None
        
    res = session.get("results", {})
    if round_num == 1:
        return spieler[-1]
        
    prev_r = round_num - 1
    last_board = boards[-1]
    prev_match = res.get((prev_r, last_board))
    if prev_match and prev_match.get("loser"):
        return prev_match.get("loser")
    
    shift = (round_num - 1) % len(spieler)
    return spieler[shift]

def get_board_players(session, round_num, board_name):
    boards = get_boards_list(session, round_num)
    if board_name not in boards:
        return ["Offen", "Offen"]
    b_idx = boards.index(board_name)
    
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session["spieler"].copy()
    max_active_pl = len(boards) * 2
    has_resting = (len(spieler) > max_active_pl and len(spieler) % 2 != 0)
    resting_p = get_resting_player(session, round_num) if has_resting else None
    active_spieler = [p for p in spieler if p != resting_p] if resting_p else spieler.copy()
    
    if round_num == 1 and not in_coop_phase:
        all_sessions = st.session_state.sessions_list
        try:
            s_idx = all_sessions.index(session)
        except:
            s_idx = 0
        
        prev_sess = None
        if s_idx + 1 < len(all_sessions):
            prev_sess = all_sessions[s_idx + 1]
            
        if prev_sess and "results" in prev_sess:
            prev_total = prev_sess.get("total_rounds", 4)
            prev_modus = prev_sess.get("modus", "Up & Down")
            prev_is_std = (prev_modus == "Standard-Training (Einzel + Coop)")
            prev_singles = prev_sess.get("singles_rounds", prev_total - 2 if prev_is_std and prev_total > 2 else prev_total)
            target_r = prev_singles if prev_is_std else prev_total
            
            prev_boards = get_boards_list(prev_sess, target_r)
            prev_results = prev_sess.get("results", {})
            
            prev_players_bottom_to_top = []
            for pb in reversed(prev_boards):
                match_inf = prev_results.get((target_r, pb))
                p1, p2 = "Offen", "Offen"
                if match_inf:
                    p1 = match_inf.get("s1", "Offen")
                    p2 = match_inf.get("s2", "Offen")
                else:
                    p_pair = get_board_players(prev_sess, target_r, pb)
                    p1, p2 = p_pair[0], p_pair[1]
                if p2 != "Offen" and p2 not in prev_players_bottom_to_top:
                    prev_players_bottom_to_top.append(p2)
                if p1 != "Offen" and p1 not in prev_players_bottom_to_top:
                    prev_players_bottom_to_top.append(p1)
            
            returning_players = [p for p in prev_players_bottom_to_top if p in active_spieler]
            new_players = [p for p in active_spieler if p not in prev_players_bottom_to_top]
            
            ordered_players = new_players + returning_players
            for p in active_spieler:
                if p not in ordered_players:
                    ordered_players.append(p)
            active_spieler = ordered_players[:len(active_spieler)]

    pairs = []
    
    if is_2v2 or in_coop_phase:
        teams = []
        all_sessions = st.session_state.sessions_list
        try:
            s_idx = all_sessions.index(session)
        except:
            s_idx = 0
            
        if in_coop_phase:
            coop_shift = (s_idx + (round_num - singles_rounds)) % len(active_spieler)
            active_spieler = active_spieler[coop_shift:] + active_spieler[:coop_shift]
            
        for i in range(0, len(active_spieler)-1, 2):
            teams.append(f"{active_spieler[i]} & {active_spieler[i+1]}")
        if len(active_spieler) % 2 != 0:
            teams.append(f"{active_spieler[-1]} & Offen")
            
        coop_boards_cnt = 2
        for i in range(0, min(coop_boards_cnt * 2, len(teams) - len(teams) % 2), 2):
            pairs.append((teams[i], teams[i+1]))
        while len(pairs) <= b_idx:
            t1 = teams[0] if len(teams) > 0 else "Offen"
            t2 = teams[1] if len(teams) > 1 else "Offen"
            pairs.append((t1, t2))
        return list(pairs[b_idx])
    else:
        boards_count = session.get("boards_count", 4)
        
        if round_num == 1:
            for i in range(0, min(boards_count * 2, len(active_spieler) - len(active_spieler) % 2), 2):
                pairs.append((active_spieler[i], active_spieler[i+1]))
            while len(pairs) <= b_idx:
                pairs.append((active_spieler[0] if active_spieler else "Offen", active_spieler[1] if len(active_spieler) > 1 else "Offen"))
            return list(pairs[b_idx])
        
        prev_r = round_num - 1
        res = session.get("results", {})
        w = {}
        l = {}
        for b in boards:
            match_info = res.get((prev_r, b))
            if match_info and match_info.get("winner"):
                w[b] = match_info["winner"]
                l[b] = match_info["loser"]
            else:
                def_players = get_board_players(session, prev_r, b)
                w[b] = def_players[0]
                l[b] = def_players[1]
                
        if b_idx == 0:
            return [w.get("Kaiser B1", "Offen"), w.get("Board 2", "Offen") if len(boards) > 1 else w.get("Kaiser B1", "Offen")]
        
        if b_idx > 0 and b_idx < len(boards) - 1:
            prev_board = boards[b_idx - 1]
            next_board = boards[b_idx + 1]
            loser_from_above = l.get(prev_board, "Offen")
            winner_from_below = w.get(next_board, "Offen")
            return [loser_from_above, winner_from_below]
            
        if b_idx == len(boards) - 1:
            prev_board = boards[b_idx - 1]
            loser_from_above = l.get(prev_board, "Offen")
            if has_resting:
                return [loser_from_above, resting_p if resting_p else "Offen"]
            else:
                loser_from_current = l.get(boards[b_idx], "Offen")
                return [loser_from_above, loser_from_current]
            
    return ["Offen", "Offen"]

def is_board_ready(session, board_name, next_r):
    if next_r == 1:
        return True
    
    modus = session.get("modus", "Up & Down")
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if modus == "Standard-Training (Einzel + Coop)" and total_rounds > 2 else total_rounds)
    
    if modus == "Standard-Training (Einzel + Coop)" and next_r == singles_rounds + 1:
        return True
        
    boards = get_boards_list(session, next_r)
    if board_name not in boards:
        return False
        
    b_idx = boards.index(board_name)
    res = session.get("results", {})
    prev_r = next_r - 1
    
    req_boards = []
    if b_idx == 0:
        req_boards.append(boards[0])
        if len(boards) > 1:
            req_boards.append(boards[1])
    else:
        req_boards.append(boards[b_idx - 1])
        if b_idx + 1 < len(boards):
            req_boards.append(boards[b_idx + 1])
        else:
            req_boards.append(boards[b_idx])
            
    for rb in req_boards:
        found = False
        for (r, b), v in res.items():
            if r == prev_r and b == rb and v.get("winner"):
                found = True
                break
        if not found:
            return False
            
    return True

def is_session_completed(sess):
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    for r in range(1, total_rounds + 1):
        boards_in_round = get_boards_list(sess, r)
        for b_name in boards_in_round:
            match_info = res.get((r, b_name))
            if not match_info or not match_info.get("winner"):
                return False
    return True

@st.dialog("🔄 Spieler auswechseln")
def open_substitution_dialog(board_name, session_idx, round_num, slot_num, current_player):
    sess = st.session_state.sessions_list[session_idx]
    alle_spieler = list(set(sess.get("spieler", kader) + [current_player]))
    if "Offen" not in alle_spieler:
        alle_spieler.append("Offen")
    alle_spieler.sort()

    st.write(f"### Auswechslung für {board_name} (Runde {round_num})")
    st.write(f"Aktueller Spieler: **{current_player}**")
    
    idx = alle_spieler.index(current_player) if current_player in alle_spieler else 0
    new_sel = st.selectbox("Aus Kader wählen:", alle_spieler, index=idx, key=f"sub_sel_{board_name}_{round_num}_{slot_num}")
    new_txt = st.text_input("Oder neuen Gast eintragen:", placeholder="Name...", key=f"sub_txt_{board_name}_{round_num}_{slot_num}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Abbrechen", use_container_width=True, key=f"sub_cancel_{board_name}_{round_num}_{slot_num}"):
            st.rerun()
    with col2:
        if st.button("Änderung speichern", type="primary", use_container_width=True, key=f"sub_save_{board_name}_{round_num}_{slot_num}"):
            final_name = new_txt.strip() if new_txt.strip() else new_sel
            if "results" not in sess:
                sess["results"] = {}
            
            if (round_num, board_name) not in sess["results"]:
                auto_p = get_board_players(sess, round_num, board_name)
                sess["results"][(round_num, board_name)] = {
                    "s1": auto_p[0],
                    "s2": auto_p[1],
                    "ergebnis": "0:0",
                    "winner": "",
                    "loser": "",
                    "180_s1": 0,
                    "180_s2": 0,
                    "avg_s1": 0.0,
                    "avg_s2": 0.0
                }
            
            if slot_num == 1:
                sess["results"][(round_num, board_name)]["s1"] = final_name
            else:
                sess["results"][(round_num, board_name)]["s2"] = final_name
                
            save_data(st.session_state.sessions_list)
            st.success("Spieler erfolgreich gewechselt!")
            st.rerun()

@st.dialog("📊 Spielablauf & Rundenübersicht")
def open_session_archive_dialog(session_idx):
    sess = st.session_state.sessions_list[session_idx]
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    st.caption(f"Modus: {sess['modus']} | Boards: {sess['boards']} | Leg-Modus: {sess['modus_leg']}")
    
    res = sess.get("results", {})
    total_rounds = sess.get("total_rounds", 4)
    modus = sess.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    
    if not res:
        st.info("Für diese Session wurden noch keine Matches erfasst.")
    else:
        for r in range(1, total_rounds + 1):
            phase_lbl = f"Runde {r}/{total_rounds} (Einzel)" if not (is_standard_training and r > singles_rounds) else f"Doppelrunde {r-singles_rounds}/{total_rounds-singles_rounds} (Coop)"
            st.markdown(f"#### 🎯 {phase_lbl}")
            boards_in_r = get_boards_list(sess, r)
            
            for b_name in boards_in_r:
                match_info = res.get((r, b_name))
                if match_info:
                    h_name = match_info.get("s1", "–")
                    g_name = match_info.get("s2", "–")
                    erg = match_info.get("ergebnis", "–")
                    win = match_info.get("winner", "Offen")
                    h180 = match_info.get("180_s1", 0)
                    g180 = match_info.get("180_s2", 0)
                    havg = match_info.get("avg_s1", 0.0)
                    gavg = match_info.get("avg_s2", 0.0)
                else:
                    auto_p = get_board_players(sess, r, b_name)
                    h_name = auto_p[0]
                    g_name = auto_p[1]
                    erg = "Ausstehend"
                    win = "–"
                    h180, g180, havg, gavg = 0, 0, 0.0, 0.0

                with st.container(border=True):
                    st.markdown(f"**{b_name}**: `{h_name}` vs `{g_name}`")
                    c1, c2, c3 = st.columns(3)
                    c1.caption(f"Ergebnis: **{erg}**")
                    c2.caption(f"Sieger: 👑 **{win}**")
                    c3.caption(f"180er: {h180}/{g180} | Ø: {havg}/{gavg}")
            
            if is_standard_training and r == singles_rounds:
                st.markdown("##### 🏆 Board-Endstand nach den Einzel-Runden:")
                singles_boards = get_boards_list(sess, singles_rounds)
                for b_name in singles_boards:
                    p_list = get_board_players(sess, singles_rounds, b_name)
                    m_inf = res.get((singles_rounds, b_name))
                    winner_str = m_inf.get("winner", "–") if m_inf else "–"
                    st.markdown(f"- **{b_name}**: `{p_list[0]}` vs `{p_list[1]}` ➔ Sieger: **{winner_str}**")
                
            st.divider()
            
    if st.button("Schließen", use_container_width=True, key=f"arch_dlg_close_{session_idx}"):
        st.rerun()

@st.dialog("➕ Neue Session starten (Passwortgeschützt)")
def open_new_session_dialog():
    pwd = st.text_input("Passwort eingeben", type="password", key="dialog_pwd_input")
    if pwd != "1521":
        if pwd != "":
            st.error("Falsches Passwort!")
        return

    session_datum = st.date_input("Datum", date.today(), key="new_sess_date")
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"], key="new_sess_leg")
    spielmodus = st.selectbox("Spielmodus", ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)"], key="new_sess_modus")
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        st.write("### Runden-Aufteilung")
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=3, key="new_sess_singles")
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 5)), index=1, key="new_sess_coop")
        total_rounds = singles_rounds + coop_rounds
        st.info(f"ℹ️ Standard-Training: {singles_rounds} Runden Einzel + {coop_rounds} Runden Doppel/Koop (auf exakt 2 Boards).")
    else:
        singles_rounds = 0
        coop_rounds = 0
        total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=3, key="new_sess_total_r")
        
    anzahl_boards = st.selectbox("Anzahl der Boards (für Einzel)", ["4 Boards", "6 Boards", "5 Boards", "3 Boards", "2 Boards", "1 Board"], index=0, key="new_sess_bcount")
    
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
        if st.button("Abbrechen", use_container_width=True, key="new_sess_cancel"):
            st.rerun()
    with col_b2:
        if st.button("Session starten", type="primary", use_container_width=True, key="new_sess_start"):
            gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
            aktive_spieler = anwesende + gaeste
            new_id = f"S-{len(st.session_state.sessions_list) + 1}"
            boards_cnt = int(anzahl_boards.split()[0])
            
            new_session = {
                "id": new_id,
                "datum": session_datum.strftime("%d.%m.%Y"),
                "modus": spielmodus,
                "boards_count": boards_cnt,
                "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds,
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
    
    modi_list = ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)"]
    curr_modus = sess.get("modus", "Up & Down")
    if curr_modus not in modi_list: modi_list.append(curr_modus)
    spielmodus = st.selectbox("Spielmodus", modi_list, index=modi_list.index(curr_modus), key=f"edit_modus_{session_idx}")
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        curr_total = sess.get("total_rounds", 6)
        curr_singles = sess.get("singles_rounds", curr_total - 2 if curr_total > 2 else 4)
        curr_coop = curr_total - curr_singles
        
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=curr_singles-1 if 1 <= curr_singles <= 10 else 3, key=f"edit_singles_{session_idx}")
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 5)), index=curr_coop-1 if 1 <= curr_coop <= 4 else 1, key=f"edit_coop_{session_idx}")
        total_rounds = singles_rounds + coop_rounds
    else:
        singles_rounds = 0
        coop_rounds = 0
        total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=sess.get("total_rounds", 4)-1, key=f"edit_rounds_{session_idx}")
    
    board_opts = ["4 Boards", "6 Boards", "5 Boards", "3 Boards", "2 Boards", "1 Board"]
    curr_b = sess.get("boards", "4 Boards")
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
            sess["singles_rounds"] = singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds
            sess["total_rounds"] = total_rounds
            sess["boards"] = anzahl_boards
            sess["modus_leg"] = leg_modus
            sess["spieler"] = aktive_spieler
            sess["gaeste"] = gaeste
            
            st.session_state.sessions_list[session_idx] = sess
            save_data(st.session_state.sessions_list)
            st.success("Session erfolgreich aktualisiert!")
            st.rerun()

@st.dialog("📋 Board-Erfassung & 180er/Average-Tracking")
def open_board_dialog(board_name, session_idx):
    sess = st.session_state.sessions_list[session_idx]
    total_rounds = sess.get("total_rounds", 4)
    
    res = sess.get("results", {})
    completed_rounds = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
    current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > total_rounds:
        st.warning(f"{board_name} hat alle {total_rounds} Runden bereits beendet.")
        if st.button("Schließen", use_container_width=True, key=f"board_close_{board_name}_{session_idx}"):
            st.rerun()
        return

    st.write(f"### {board_name} (Session {sess['id']}) — Runde {current_round} von {total_rounds}")
    
    existing_match = res.get((current_round, board_name))
    
    if existing_match:
        current_p1 = existing_match.get("s1", "Offen")
        current_p2 = existing_match.get("s2", "Offen")
        try:
            score1 = int(existing_match.get("ergebnis", "0:0").split(":")[0])
            score2 = int(existing_match.get("ergebnis", "0:0").split(":")[1])
        except:
            score1, score2 = 0, 0
        t1_180 = int(existing_match.get("180_s1", 0))
        t2_180 = int(existing_match.get("180_s2", 0))
        avg1 = float(existing_match.get("avg_s1", 0.0))
        avg2 = float(existing_match.get("avg_s2", 0.0))
    else:
        auto_players = get_board_players(sess, current_round, board_name)
        current_p1, current_p2 = auto_players[0], auto_players[1]
        score1, score2 = 0, 0
        t1_180, t2_180 = 0, 0
        avg1, avg2 = 0.0, 0.0

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Heim:** `{current_p1}`")
        in_score1 = st.number_input(f"Legs Heim", min_value=0, max_value=5, value=score1, key=f"d_score1_{board_name}_{session_idx}")
        in_180_1 = st.number_input(f"🎯 180er von {current_p1}", min_value=0, max_value=20, value=t1_180, key=f"d_180_1_{board_name}_{session_idx}")
        in_avg_1 = st.number_input(f"📊 Match-Average {current_p1}", min_value=0.0, max_value=180.0, value=avg1, step=0.1, key=f"d_avg_1_{board_name}_{session_idx}")
        
    with col2:
        st.markdown(f"**Gast:** `{current_p2}`")
        in_score2 = st.number_input(f"Legs Gast", min_value=0, max_value=5, value=score2, key=f"d_score2_{board_name}_{session_idx}")
        in_180_2 = st.number_input(f"🎯 180er von {current_p2}", min_value=0, max_value=20, value=t2_180, key=f"d_180_2_{board_name}_{session_idx}")
        in_avg_2 = st.number_input(f"📊 Match-Average {current_p2}", min_value=0.0, max_value=180.0, value=avg2, step=0.1, key=f"d_avg_2_{board_name}_{session_idx}")
        
    ergebnis = f"{in_score1}:{in_score2}"
    winner = current_p1 if in_score1 > in_score2 else (current_p2 if in_score2 > in_score1 else None)
    loser = current_p2 if winner == current_p1 else (current_p1 if winner == current_p2 else None)
    
    st.info(f"📊 Ergebnis: **{ergebnis}** | 🏆 Sieger: **{winner if winner else 'Unentschieden'}**")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Ergebnis abschließen", type="primary", use_container_width=True, key=f"d_save_{board_name}_{session_idx}"):
            if in_score1 == in_score2:
                st.error("Ein Unentschieden ist im Up & Down nicht möglich.")
            else:
                if "results" not in sess:
                    sess["results"] = {}
                sess["results"][(current_round, board_name)] = {
                    "s1": current_p1,
                    "s2": current_p2,
                    "ergebnis": ergebnis,
                    "winner": winner,
                    "loser": loser,
                    "180_s1": in_180_1,
                    "180_s2": in_180_2,
                    "avg_s1": in_avg_1,
                    "avg_s2": in_avg_2
                }
                save_data(st.session_state.sessions_list)
                st.success("Ergebnis und Statistiken erfolgreich gespeichert!")
                st.rerun()
    with col_btn2:
        if st.button("Schließen", use_container_width=True, key=f"d_close_{board_name}_{session_idx}"):
            st.rerun()

@st.dialog("⚡ Schnelldurchlauf & Spieler ändern (Passwortgeschützt)")
def open_quick_entry_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"quick_pwd_{session_idx}")
    if pwd != "1521":
        if pwd != "":
            st.error("Falsches Passwort!")
        return

    sess = st.session_state.sessions_list[session_idx]
    st.write(f"### Schnelldurchlauf Session {sess['id']} ({sess['datum']})")
    
    total_rounds = sess.get("total_rounds", 4)
    modus = sess.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    
    r_options = []
    for r in range(1, total_rounds + 1):
        if is_standard_training and r > singles_rounds:
            r_options.append((r, f"Doppelrunde {r-singles_rounds}/{total_rounds-singles_rounds} (Coop)"))
        else:
            r_options.append((r, f"Runde {r}/{total_rounds} (Einzel)"))
            
    selected_r_tuple = st.selectbox("Wähle Runde aus:", r_options, format_func=lambda x: x[1], key=f"qe_round_sel_{session_idx}")
    chosen_r = selected_r_tuple[0]
    is_coop_round = is_standard_training and chosen_r > singles_rounds
    
    st.markdown(f"#### 🎯 Partien & Spieler für {selected_r_tuple[1]}")
    boards_in_r = get_boards_list(sess, chosen_r)
    available_players = sess.get("spieler", kader)
    if "Offen" not in available_players:
        available_players_opt = available_players + ["Offen"]
    else:
        available_players_opt = available_players
    
    if "results" not in sess:
        sess["results"] = {}
        
    for b_name in boards_in_r:
        st.markdown(f"##### **{b_name}**")
        current_m = sess["results"].get((chosen_r, b_name), {"s1": "Offen", "s2": "Offen", "ergebnis": "0:0", "180_s1": 0, "180_s2": 0})
        
        curr_s1 = current_m.get("s1", "Offen")
        curr_s2 = current_m.get("s2", "Offen")
        
        try:
            s_l1, s_l2 = map(int, current_m.get("ergebnis", "0:0").split(":"))
        except:
            s_l1, s_l2 = 0, 0
            
        c1_180 = int(current_m.get("180_s1", 0))
        c2_180 = int(current_m.get("180_s2", 0))
        
        if is_coop_round or modus == "Koop 2vs2 (Up & Down)":
            parts1 = [p.strip() for p in curr_s1.split("&")] if " & " in curr_s1 else [curr_s1, "Offen"]
            parts2 = [p.strip() for p in curr_s2.split("&")] if " & " in curr_s2 else [curr_s2, "Offen"]
            
            p1_a = parts1[0] if len(parts1) > 0 else "Offen"
            p1_b = parts1[1] if len(parts1) > 1 else "Offen"
            p2_a = parts2[0] if len(parts2) > 0 else "Offen"
            p2_b = parts2[1] if len(parts2) > 1 else "Offen"
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.markdown("**Heim-Team**")
                idx1 = available_players_opt.index(p1_a) if p1_a in available_players_opt else 0
                sel_p1a = st.selectbox(f"Heim S1 ({b_name})", available_players_opt, index=idx1, key=f"qe_{b_name}_{chosen_r}_p1a_{session_idx}")
                idx2 = available_players_opt.index(p1_b) if p1_b in available_players_opt else (1 if len(available_players_opt)>1 else 0)
                sel_p1b = st.selectbox(f"Heim S2 ({b_name})", available_players_opt, index=idx2, key=f"qe_{b_name}_{chosen_r}_p1b_{session_idx}")
                final_s1 = f"{sel_p1a} & {sel_p1b}"
                
                in_l1 = st.number_input(f"Legs Heim ({b_name})", min_value=0, max_value=5, value=s_l1, key=f"qe_l1_{b_name}_{chosen_r}_{session_idx}")
                in_180_1 = st.number_input(f"180er Heim ({b_name})", min_value=0, max_value=20, value=c1_180, key=f"qe_180_1_{b_name}_{chosen_r}_{session_idx}")
                
            with col_t2:
                st.markdown("**Gast-Team**")
                idx3 = available_players_opt.index(p2_a) if p2_a in available_players_opt else (2 if len(available_players_opt)>2 else 0)
                sel_p2a = st.selectbox(f"Gast S1 ({b_name})", available_players_opt, index=idx3, key=f"qe_{b_name}_{chosen_r}_p2a_{session_idx}")
                idx4 = available_players_opt.index(p2_b) if p2_b in available_players_opt else (3 if len(available_players_opt)>3 else 0)
                sel_p2b = st.selectbox(f"Gast S2 ({b_name})", available_players_opt, index=idx4, key=f"qe_{b_name}_{chosen_r}_p2b_{session_idx}")
                final_s2 = f"{sel_p2a} & {sel_p2b}"
                
                in_l2 = st.number_input(f"Legs Gast ({b_name})", min_value=0, max_value=5, value=s_l2, key=f"qe_l2_{b_name}_{chosen_r}_{session_idx}")
                in_180_2 = st.number_input(f"180er Gast ({b_name})", min_value=0, max_value=20, value=c2_180, key=f"qe_180_2_{b_name}_{chosen_r}_{session_idx}")
                
        else:
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                idx_s1 = available_players_opt.index(curr_s1) if curr_s1 in available_players_opt else 0
                final_s1 = st.selectbox(f"Heim ({b_name})", available_players_opt, index=idx_s1, key=f"qe_{b_name}_{chosen_r}_s1_{session_idx}")
                in_l1 = st.number_input(f"Legs Heim ({b_name})", min_value=0, max_value=5, value=s_l1, key=f"qe_l1_{b_name}_{chosen_r}_{session_idx}")
                in_180_1 = st.number_input(f"180er Heim ({b_name})", min_value=0, max_value=20, value=c1_180, key=f"qe_180_1_{b_name}_{chosen_r}_{session_idx}")
                
            with col_p2:
                idx_s2 = available_players_opt.index(curr_s2) if curr_s2 in available_players_opt else (1 if len(available_players_opt)>1 else 0)
                final_s2 = st.selectbox(f"Gast ({b_name})", available_players_opt, index=idx_s2, key=f"qe_{b_name}_{chosen_r}_s2_{session_idx}")
                in_l2 = st.number_input(f"Legs Gast ({b_name})", min_value=0, max_value=5, value=s_l2, key=f"qe_l2_{b_name}_{chosen_r}_{session_idx}")
                in_180_2 = st.number_input(f"180er Gast ({b_name})", min_value=0, max_value=20, value=c2_180, key=f"qe_180_2_{b_name}_{chosen_r}_{session_idx}")
                
        winner = final_s1 if in_l1 > in_l2 else (final_s2 if in_l2 > in_l1 else "")
        loser = final_s2 if winner == final_s1 else (final_s1 if winner == final_s2 else "")
        
        sess["results"][(chosen_r, b_name)] = {
            "s1": final_s1,
            "s2": final_s2,
            "ergebnis": f"{in_l1}:{in_l2}",
            "winner": winner,
            "loser": loser,
            "180_s1": in_180_1,
            "180_s2": in_180_2,
            "avg_s1": current_m.get("avg_s1", 0.0),
            "avg_s2": current_m.get("avg_s2", 0.0)
        }
        st.divider()
        
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True, key=f"qe_cancel_{session_idx}"):
            st.rerun()
    with col_b2:
        if st.button("Ergebnisse speichern", type="primary", use_container_width=True, key=f"qe_save_{session_idx}"):
            save_data(st.session_state.sessions_list)
            st.success("Schnelldurchlauf erfolgreich gespeichert!")
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
        if st.button("Abbrechen", use_container_width=True, key=f"del_cancel_{session_idx}"):
            st.rerun()
    with col2:
        if st.button("Unwiderruflich löschen", type="primary", use_container_width=True, key=f"del_confirm_{session_idx}"):
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
        if st.button("➕ Neue Session starten", type="primary", use_container_width=True, key="overview_quick_start_btn"):
            open_new_session_dialog()
    with col_btn2:
        active_sessions_for_btn = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
        if active_sessions_for_btn:
            if st.button("⚙️ Aktive Session bearbeiten", use_container_width=True, key="overview_edit_active_btn"):
                open_edit_session_dialog(st.session_state.sessions_list.index(active_sessions_for_btn[0]))
        else:
            latest_session_idx = 0 if st.session_state.sessions_list else None
            if latest_session_idx is not None:
                if st.button("⚙️ Letzte Session bearbeiten", use_container_width=True, key="overview_edit_latest_btn"):
                    open_edit_session_dialog(latest_session_idx)
            else:
                st.button("⚙️ Aktive Session bearbeiten", use_container_width=True, disabled=True, key="overview_edit_active_disabled_btn")
        
    st.write("")
    
    total_sessions_count = len(st.session_state.sessions_list)
    total_180s_all = 0
    for s in st.session_state.sessions_list:
        for m in s.get("results", {}).values():
            total_180s_all += int(m.get("180_s1", 0)) + int(m.get("180_s2", 0))
            
    current_kaiser = "Noch offen"
    if st.session_state.sessions_list:
        latest_s = st.session_state.sessions_list[0]
        k_matches = [(r, m) for (r, b), m in latest_s.get("results", {}).items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
        if k_matches:
            k_matches.sort(key=lambda x: x[0], reverse=True)
            current_kaiser = k_matches[0][1].get("winner")

    curr_sess = st.session_state.sessions_list[0] if st.session_state.sessions_list else None
    active_players_count = len(curr_sess.get("spieler", [])) if curr_sess else 0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(label="Trainingsabende", value=str(total_sessions_count), delta="gesamt")
    with m2:
        st.metric(label="Team 180er 🎯", value=str(total_180s_all), delta="geworfen")
    with m3:
        st.metric(label="Aktueller Kaiser 👑", value=current_kaiser, delta="Board 1")
    with m4:
        st.metric(label="Anwesende Spieler", value=str(active_players_count), delta="im Training")
        
    st.write("")
    
    curr_sess_for_live = None
    for s in st.session_state.sessions_list:
        if not is_session_completed(s):
            curr_sess_for_live = s
            break
    if not curr_sess_for_live and st.session_state.sessions_list:
        curr_sess_for_live = st.session_state.sessions_list[0]

    if not curr_sess_for_live:
        st.markdown("### 🔴 Laufende Session")
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Übersicht zu sehen.")
    else:
        is_completed_curr = is_session_completed(curr_sess_for_live)
        status_label = "✅ [Abgeschlossen]" if is_completed_curr else "🔴 Laufende Session"
        st.markdown(f"### {status_label}")
        st.caption(f"Session-ID: **{curr_sess_for_live['id']}** vom {curr_sess_for_live['datum']} ({curr_sess_for_live['modus']})")
        
        total_rounds = curr_sess_for_live.get("total_rounds", 4)
        modus_s = curr_sess_for_live.get("modus", "Up & Down")
        is_std = (modus_s == "Standard-Training (Einzel + Coop)")
        singles_r = curr_sess_for_live.get("singles_rounds", total_rounds - 2 if is_std and total_rounds > 2 else total_rounds)
        
        res = curr_sess_for_live.get("results", {})
        current_active_round = 1
        for r_check in range(1, total_rounds + 1):
            boards_in_r = get_boards_list(curr_sess_for_live, r_check)
            round_complete = True
            for b_n in boards_in_r:
                if not res.get((r_check, b_n), {}).get("winner"):
                    round_complete = False
                    break
            if not round_complete:
                current_active_round = r_check
                break
            else:
                if r_check == total_rounds:
                    current_active_round = total_rounds
                    
        active_boards_list = get_boards_list(curr_sess_for_live, current_active_round)
        
        spieler_list = curr_sess_for_live.get("spieler", [])
        max_active_pl = len(active_boards_list) * 2
        has_rest = (len(spieler_list) > max_active_pl and len(spieler_list) % 2 != 0)
        if has_rest:
            r_player = get_resting_player(curr_sess_for_live, current_active_round)
            if r_player:
                st.info(f"☕ Pause in dieser Runde: **{r_player}**")

        if is_std and current_active_round > singles_r:
            phase_name = f"Doppelrunde {current_active_round - singles_r}/{total_rounds - singles_r} (Coop)"
        else:
            phase_name = f"Runde {current_active_round}/{total_rounds} (Einzel)"

        st.markdown(f"#### {phase_name} ({len(active_boards_list)} Boards aktiv)")
        
        cols_per_row = 3
        for i in range(0, len(active_boards_list), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(active_boards_list):
                    b_name = active_boards_list[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            next_r = current_active_round
                            
                            st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                            
                            if next_r <= total_rounds:
                                ready = is_board_ready(curr_sess_for_live, b_name, next_r)
                                ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                                st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                                
                                existing_match = res.get((next_r, b_name))
                                if existing_match:
                                    p1 = existing_match.get("s1", "Offen")
                                    p2 = existing_match.get("s2", "Offen")
                                else:
                                    players_now = get_board_players(curr_sess_for_live, next_r, b_name)
                                    p1, p2 = players_now[0], players_now[1]
                                
                                r_label = f"Runde {next_r}/{total_rounds}" if not (is_std and next_r > singles_r) else f"Doppelrunde {next_r-singles_r}/{total_rounds-singles_r}"
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>{r_label}</p>", unsafe_allow_html=True)
                                
                                if p1 in ["-", "Offen"]:
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; color: gray; margin: 8px 0;'>-</div>", unsafe_allow_html=True)
                                else:
                                    sc1, sc2 = st.columns([5, 2])
                                    sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p1}</div>", unsafe_allow_html=True)
                                    with sc2:
                                        if st.button("🔄 Ändern", key=f"sub_btn1_{b_name}_{next_r}", help="Spieler 1 auswechseln"):
                                            open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess_for_live), next_r, 1, p1)
                                
                                st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                                
                                if p2 in ["-", "Offen"]:
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; color: gray; margin: 8px 0;'>-</div>", unsafe_allow_html=True)
                                else:
                                    sc3, sc4 = st.columns([5, 2])
                                    sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                                    with sc4:
                                        if st.button("🔄 Ändern", key=f"sub_btn2_{b_name}_{next_r}", help="Spieler 2 auswechseln"):
                                            open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess_for_live), next_r, 2, p2)
                                
                                st.write("")
                                if st.button("🎯 Ergebnis eintragen", key=f"live_btn_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                                    open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess_for_live))
                            else:
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle {total_rounds} Runden beendet</p>", unsafe_allow_html=True)
                                st.success("✅ Board abgeschlossen")

    st.write("")
    st.write("### Zuletzt ausgetragene Board-Matches")
    st.caption("Best of 5 und Gewinner für die Statistik")
    
    all_matches = []
    for sess in st.session_state.sessions_list:
        sess_date = sess.get("datum", "")
        for (round_num, board_name), m_info in sess.get("results", {}).items():
            if not m_info.get("winner"):
                continue
            all_matches.append({
                "Datum": sess_date,
                "Runde": round_num,
                "Board": board_name,
                "Spieler": f"{m_info['s1']} vs {m_info['s2']}",
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
    st.write("Live berechnete Bilanz des festen Stammkaders (exklusive Gastspieler) inklusive Legs, 180er, Match-Averages und Gesamtschnitt des Teams.")
    
    stats = {p: {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0} for p in kader}
    
    player_matches_played = 0
    team_session_avgs = []
    
    for sess in st.session_state.sessions_list:
        sess_avgs = []
        for match in sess.get("results", {}).values():
            winner = match.get("winner", "")
            loser = match.get("loser", "")
            s1 = match.get("s1", "")
            s2 = match.get("s2", "")
            ergebnis = match.get("ergebnis", "0:0")
            
            try:
                l1, l2 = map(int, ergebnis.split(":"))
            except ValueError:
                l1, l2 = 0, 0
                
            h1 = int(match.get("180_s1", 0))
            h2 = int(match.get("180_s2", 0))
            a1 = float(match.get("avg_s1", 0.0))
            a2 = float(match.get("avg_s2", 0.0))
            
            if s1 in stats and " & " not in s1:
                stats[s1]["180er"] += h1
                stats[s1]["Legs_Won"] += l1
                stats[s1]["Legs_Lost"] += l2
                if a1 > 0:
                    stats[s1]["Avg_Sum"] += a1
                    stats[s1]["Avg_Count"] += 1
                    sess_avgs.append(a1)
            if s2 in stats and " & " not in s2:
                stats[s2]["180er"] += h2
                stats[s2]["Legs_Won"] += l2
                stats[s2]["Legs_Lost"] += l1
                if a2 > 0:
                    stats[s2]["Avg_Sum"] += a2
                    stats[s2]["Avg_Count"] += 1
                    sess_avgs.append(a2)
            
            if winner and " & " not in winner:
                for p in winner.split(" & "):
                    if p in stats:
                        stats[p]["Matches"] += 1
                        stats[p]["Siege"] += 1
                        player_matches_played += 1
            if loser and " & " not in loser:
                for p in loser.split(" & "):
                    if p in stats:
                        stats[p]["Matches"] += 1
                        stats[p]["Niederlagen"] += 1
                        player_matches_played += 1

        if sess_avgs:
            t_avg = sum(sess_avgs) / len(sess_avgs)
            team_session_avgs.append({"Datum": sess.get("datum", "Unbekannt"), "Team-Average": round(t_avg, 1)})

    best_wr = 0.0
    best_wr_player = "–"
    for p in kader:
        m = stats[p]["Matches"]
        s = stats[p]["Siege"]
        if m >= 2:
            wr = s / m
            if wr > best_wr:
                best_wr = wr
                best_wr_player = p

    best_wr_str = f"{(best_wr * 100):.0f}%" if best_wr > 0 else "–"

    all_team_avgs = [stats[p]["Avg_Sum"] / stats[p]["Avg_Count"] for p in kader if stats[p]["Avg_Count"] > 0]
    overall_team_avg = f"{(sum(all_team_avgs) / len(all_team_avgs)):.1f}" if all_team_avgs else "–"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
    with col2:
        st.metric(label="Absolvierte Matches", value=str(player_matches_played), delta="aus Sessions")
    with col3:
        st.metric(label="Beste Siegquote", value=best_wr_str, delta=best_wr_player)
    with col4:
        st.metric(label="Team-Gesamtschnitt", value=overall_team_avg, delta="Ø Average")
        
    st.write("")
    st.markdown("### 📈 Team-Entwicklung (Gesamt-Average über Sessions)")
    if team_session_avgs:
        df_trend = pd.DataFrame(team_session_avgs)
        st.line_chart(df_trend.set_index("Datum"))
    else:
        st.info("Noch nicht genügend Average-Daten vorhanden, um die Team-Entwicklung anzuzeigen.")

    st.write("### Spielerübersicht & Rangliste")
    suche = st.text_input("Spieler suchen...", "", key="search_kader_input")
    
    table_rows = []
    for p in kader:
        m = stats[p]["Matches"]
        s = stats[p]["Siege"]
        n = stats[p]["Niederlagen"]
        lw = stats[p]["Legs_Won"]
        lv = stats[p]["Legs_Lost"]
        t180 = stats[p]["180er"]
        acount = stats[p]["Avg_Count"]
        avg_val = f"{(stats[p]['Avg_Sum'] / acount):.1f}" if acount > 0 else "–"
        quote = f"{(s / m * 100):.0f}%" if m > 0 else "0%"
        table_rows.append({
            "Spieler": p,
            "Matches": m,
            "Siege": s,
            "Niederlagen": n,
            "Siegquote": quote,
            "Legs Gewonnen": lw,
            "Legs Verloren": lv,
            "🎯 180er": t180,
            "📊 Ø Average": avg_val
        })
        
    df_kader = pd.DataFrame(table_rows)
    if suche:
        df_kader = df_kader[df_kader["Spieler"].str.contains(suche, case=False)]
    st.dataframe(df_kader, use_container_width=True, hide_index=True)

with tab_session:
    st.subheader("Up & Down Sessions & Verlauf")
    st.write("Übersicht aller absolvierten Trainingsabende und Spielabläufe.")
    
    total_sessions_cnt = len(st.session_state.sessions_list)
    total_attendance = sum(len(s.get("spieler", [])) for s in st.session_state.sessions_list)
    avg_attendance_val = round(total_attendance / total_sessions_cnt, 1) if total_sessions_cnt > 0 else 0

    kaiser_win_counts = {}
    for sess in st.session_state.sessions_list:
        res = sess.get("results", {})
        total_rounds = sess.get("total_rounds", 4)
        final_round = total_rounds
        m_info = res.get((final_round, "Kaiser B1"))
        if m_info and m_info.get("winner"):
            winner = m_info.get("winner")
            if " & " not in winner:
                kaiser_win_counts[winner] = kaiser_win_counts.get(winner, 0) + 1
    
    if kaiser_win_counts:
        top_kaiser = max(kaiser_win_counts, key=kaiser_win_counts.get)
        top_kaiser_display = f"{top_kaiser} ({kaiser_win_counts[top_kaiser]}x)"
    else:
        top_kaiser_display = "–"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Gespielte Abende", value=str(total_sessions_cnt), delta="Sessions")
    with col2:
        st.metric(label="ø Anwesende Spieler", value=str(avg_attendance_val), delta="pro Abend")
    with col3:
        st.metric(label="Rekord-Kaiser 👑", value=top_kaiser_display, delta="meiste Board 1 Siege")
        
    if st.button("➕ Neue Session starten", use_container_width=True, key="tab_session_new_btn"):
        open_new_session_dialog()

    st.write("### Bisherige Sessions")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden. Starte über den Button oben eine neue Session.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container(border=True):
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                status_text = " ✅ **[Abgeschlossen]**" if is_session_completed(sess) else " ⏳ **[Aktiv]**"
                total_rounds = sess.get("total_rounds", 4)
                st.markdown(f"**{sess['id']}** — **{sess['datum']}** (*{sess['modus']} · {sess['boards']} · {total_rounds} Runden · {sess['modus_leg']}*{gaeste_text}){status_text}")
                
                if st.button("📊 Spielablauf ansehen", key=f"s_view_unique_{idx}", use_container_width=True):
                    open_session_archive_dialog(idx)

with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    st.write("Hier kannst du vergangene Sessions nachtragen oder ältere Ergebnisse einsehen, bearbeiten und verwalten.")
    
    col_arc1, col_arc2 = st.columns(2)
    with col_arc1:
        if st.button("➕ Vergangene Session nachtragen", type="primary", use_container_width=True, key="retro_session_btn"):
            open_new_session_dialog()
    with col_arc2:
        active_sessions_for_arc = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
        if active_sessions_for_arc:
            if st.button("⚙️ Aktive Session bearbeiten", use_container_width=True, key="archiv_edit_active_btn"):
                open_edit_session_dialog(st.session_state.sessions_list.index(active_sessions_for_arc[0]))
        else:
            latest_session_idx = 0 if st.session_state.sessions_list else None
            if latest_session_idx is not None:
                if st.button("⚙️ Letzte Session bearbeiten", use_container_width=True, key="archiv_edit_latest_btn"):
                    open_edit_session_dialog(latest_session_idx)
            else:
                st.button("⚙️ Aktive Session bearbeiten", use_container_width=True, disabled=True, key="archiv_edit_active_disabled_btn")
        
    st.write("")
    if not st.session_state.sessions_list:
        st.info("Keine Sessions im Archiv vorhanden.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container(border=True):
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                total_rounds = sess.get("total_rounds", 4)
                st.markdown(f"**{sess['id']}** — {sess['datum']} (*{sess['modus']} · {sess['boards']} · {total_rounds} Runden*{gaeste_text})")
                
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    if st.button("📊 Spielablauf", key=f"arch_view_btn_{idx}", use_container_width=True):
                        open_session_archive_dialog(idx)
                with col_b2:
                    if st.button("⚡ Schnelldurchlauf", key=f"arch_quick_btn_{idx}", use_container_width=True):
                        open_quick_entry_dialog(idx)
                with col_b3:
                    if st.button("🗑️ Löschen", key=f"arch_del_btn_{idx}", use_container_width=True):
                        open_delete_dialog(idx)

with tab_bdv:
    st.subheader("Leitfaden Ligabetrieb BDV – Bezirk Schwaben")
    st.markdown("""
# **Leitfaden Ligabetrieb BDV – Bezirk Schwaben**
1. Mannschaft & Meldung
2. Spielmodus & Ablauf (Liga und Pokal)
3. Spielbericht & Online-Meldung
4. Mannschaftsvorstellung (Kader)

### 1. Mannschaft & Meldung
- **Mannschaftsmeldung:** Erledigt.
- **Spielerkader:** Besteht aus 10 Spielern. Die namentliche Meldung erfolgt bis zum 31. August in der Online-Software (nuLiga).

### 2. Spielmodus & Ablauf (Liga und Pokal)
- **Heimspieltag ist Dienstag**
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
  Die Heimmannschaft schreibt und beginnt auf Board 1.  
  Die Gastmannschaft schreibt und beginnt auf Board 2.  
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
- Andrino Czombera
- Dennis Güttner
- Marco Eser
- Maximilian Zientner
- Michael Kummer
- Michael Mak
- Michael Neumeier
- Thomas Schaudt
- Wolfgang Scheider
    """)
