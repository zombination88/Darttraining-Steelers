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

tab_übersicht, tab_kader, tab_session, tab_archiv = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv"])

def get_boards_list(session, round_num=None):
    boards_count = session.get("boards_count", 4)
    modus = session.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
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
    
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session.get("spieler", []).copy()
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
        else:
            chrono_s_idx = len(all_sessions) - 1 - s_idx
            if active_spieler:
                shift = (chrono_s_idx * 2) % len(active_spieler)
                active_spieler = active_spieler[shift:] + active_spieler[:shift]

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
        boards_count = len(boards)
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
        if st.button("Abbrechen", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Änderung speichern", type="primary", use_container_width=True):
            final_name = new_txt.strip() if new_txt.strip() else new_sel
            if "results" not in sess:
                sess["results"] = {}
            if (round_num, board_name) not in sess["results"]:
                auto_p = get_board_players(sess, round_num, board_name)
                sess["results"][(round_num, board_name)] = {
                    "s1": auto_p[0], "s2": auto_p[1], "ergebnis": "0:0", "winner": "", "loser": "", "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0
                }
            if slot_num == 1:
                sess["results"][(round_num, board_name)]["s1"] = final_name
            else:
                sess["results"][(round_num, board_name)]["s2"] = final_name
                
            save_data(st.session_state.sessions_list)
            st.success("Spieler gewechselt!")
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
    if st.button("Schließen", use_container_width=True):
        st.rerun()

@st.dialog("➕ Neue Session starten (Passwortgeschützt)")
def open_new_session_dialog():
    pwd = st.text_input("Passwort eingeben", type="password")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return

    session_datum = st.date_input("Datum", date.today())
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
    spielmodus = st.selectbox("Spielmodus", ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)"])
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=3)
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 5)), index=1)
        total_rounds = singles_rounds + coop_rounds
    else:
        singles_rounds = 0
        coop_rounds = 0
        total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=3)
        
    anzahl_boards = st.selectbox("Anzahl der Boards (für Einzel)", ["4 Boards", "6 Boards", "5 Boards", "3 Boards", "2 Boards", "1 Board"], index=0)
    
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
                
    st.write("### Gastspieler (optional)")
    g1 = st.text_input("Gastspieler 1")
    g2 = st.text_input("Gastspieler 2")
    g3 = st.text_input("Gastspieler 3")
    g4 = st.text_input("Gastspieler 4")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with col_b2:
        if st.button("Session starten", type="primary", use_container_width=True):
            gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
            aktive_spieler = anwesende + gaeste
            new_id = f"S-{len(st.session_state.sessions_list) + 1}"
            boards_cnt = int(anzahl_boards.split()[0])
            
            new_session = {
                "id": new_id, "datum": session_datum.strftime("%d.%m.%Y"), "modus": spielmodus,
                "boards_count": boards_cnt, "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds,
                "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus,
                "spieler": aktive_spieler, "gaeste": gaeste, "results": {}
            }
            st.session_state.sessions_list.insert(0, new_session)
            save_data(st.session_state.sessions_list)
            st.success("Gestartet!")
            st.rerun()

@st.dialog("⚙️ Session bearbeiten (Passwortgeschützt)")
def open_edit_session_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"edit_pwd_{session_idx}")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return

    sess = st.session_state.sessions_list[session_idx]
    try:
        curr_date = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except:
        curr_date = date.today()

    session_datum = st.date_input("Datum", curr_date, key=f"edit_date_{session_idx}")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with col_b2:
        if st.button("Speichern", type="primary", use_container_width=True):
            sess["datum"] = session_datum.strftime("%d.%m.%Y")
            st.session_state.sessions_list[session_idx] = sess
            save_data(st.session_state.sessions_list)
            st.success("Aktualisiert!")
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
        if st.button("Schließen", use_container_width=True): st.rerun()
        return

    st.write(f"### {board_name} (Session {sess['id']}) — Runde {current_round} von {total_rounds}")
    
    existing_match = res.get((current_round, board_name))
    if existing_match:
        current_p1, current_p2 = existing_match.get("s1", "Offen"), existing_match.get("s2", "Offen")
        try:
            score1, score2 = map(int, existing_match.get("ergebnis", "0:0").split(":"))
        except:
            score1, score2 = 0, 0
        t1_180, t2_180 = int(existing_match.get("180_s1", 0)), int(existing_match.get("180_s2", 0))
        avg1, avg2 = float(existing_match.get("avg_s1", 0.0)), float(existing_match.get("avg_s2", 0.0))
    else:
        auto_players = get_board_players(sess, current_round, board_name)
        current_p1, current_p2 = auto_players[0], auto_players[1]
        score1, score2, t1_180, t2_180, avg1, avg2 = 0, 0, 0, 0, 0.0, 0.0

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Heim:** `{current_p1}`")
        in_score1 = st.number_input(f"Legs Heim", 0, 5, score1, key=f"d_s1_{board_name}_{session_idx}")
        in_180_1 = st.number_input(f"🎯 180er", 0, 20, t1_180, key=f"d_1801_{board_name}_{session_idx}")
        in_avg_1 = st.number_input(f"📊 Average", 0.0, 180.0, avg1, step=0.1, key=f"d_avg1_{board_name}_{session_idx}")
    with col2:
        st.markdown(f"**Gast:** `{current_p2}`")
        in_score2 = st.number_input(f"Legs Gast", 0, 5, score2, key=f"d_s2_{board_name}_{session_idx}")
        in_180_2 = st.number_input(f"🎯 180er", 0, 20, t2_180, key=f"d_1802_{board_name}_{session_idx}")
        in_avg_2 = st.number_input(f"📊 Average", 0.0, 180.0, avg2, step=0.1, key=f"d_avg2_{board_name}_{session_idx}")
        
    ergebnis = f"{in_score1}:{in_score2}"
    winner = current_p1 if in_score1 > in_score2 else (current_p2 if in_score2 > in_score1 else None)
    loser = current_p2 if winner == current_p1 else (current_p1 if winner == current_p2 else None)
    
    st.info(f"📊 Ergebnis: **{ergebnis}** | 🏆 Sieger: **{winner if winner else 'Unentschieden'}**")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Ergebnis abschließen", type="primary", use_container_width=True):
            if in_score1 == in_score2:
                st.error("Kein Unentschieden möglich.")
            else:
                if "results" not in sess: sess["results"] = {}
                sess["results"][(current_round, board_name)] = {
                    "s1": current_p1, "s2": current_p2, "ergebnis": ergebnis, "winner": winner, "loser": loser,
                    "180_s1": in_180_1, "180_s2": in_180_2, "avg_s1": in_avg_1, "avg_s2": in_avg_2
                }
                save_data(st.session_state.sessions_list)
                st.success("Gespeichert!")
                st.rerun()
    with col_btn2:
        if st.button("Schließen", use_container_width=True): st.rerun()

@st.dialog("⚡ Schnelldurchlauf (Passwortgeschützt)")
def open_quick_entry_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"qe_pwd_{session_idx}")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
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
            
    selected_r_tuple = st.selectbox("Wähle Runde aus:", r_options, format_func=lambda x: x[1], key=f"qe_sel_{session_idx}")
    chosen_r = selected_r_tuple[0]
    is_coop_round = is_standard_training and chosen_r > singles_rounds
    
    boards_in_r = get_boards_list(sess, chosen_r)
    available_players = sess.get("spieler", kader) + ["Offen"]
    
    if "results" not in sess: sess["results"] = {}
        
    for b_name in boards_in_r:
        st.markdown(f"##### **{b_name}**")
        current_m = sess["results"].get((chosen_r, b_name), {"s1": "Offen", "s2": "Offen", "ergebnis": "0:0", "180_s1": 0, "180_s2": 0})
        curr_s1, curr_s2 = current_m.get("s1", "Offen"), current_m.get("s2", "Offen")
        try:
            s_l1, s_l2 = map(int, current_m.get("ergebnis", "0:0").split(":"))
        except:
            s_l1, s_l2 = 0, 0
        c1_180, c2_180 = int(current_m.get("180_s1", 0)), int(current_m.get("180_s2", 0))
        
        if is_coop_round or modus == "Koop 2vs2 (Up & Down)":
            parts1 = [p.strip() for p in curr_s1.split("&")] if " & " in curr_s1 else [curr_s1, "Offen"]
            parts2 = [p.strip() for p in curr_s2.split("&")] if " & " in curr_s2 else [curr_s2, "Offen"]
            p1_a, p1_b = parts1[0] if len(parts1)>0 else "Offen", parts1[1] if len(parts1)>1 else "Offen"
            p2_a, p2_b = parts2[0] if len(parts2)>0 else "Offen", parts2[1] if len(parts2)>1 else "Offen"
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                idx1 = available_players.index(p1_a) if p1_a in available_players else 0
                sel_p1a = st.selectbox(f"Heim S1 ({b_name})", available_players, index=idx1, key=f"qe_p1a_{b_name}_{chosen_r}")
                idx2 = available_players.index(p1_b) if p1_b in available_players else 0
                sel_p1b = st.selectbox(f"Heim S2 ({b_name})", available_players, index=idx2, key=f"qe_p1b_{b_name}_{chosen_r}")
                final_s1 = f"{sel_p1a} & {sel_p1b}"
                in_l1 = st.number_input(f"Legs Heim ({b_name})", 0, 5, s_l1, key=f"qe_l1_{b_name}_{chosen_r}")
                in_180_1 = st.number_input(f"180er Heim", 0, 20, c1_180, key=f"qe_181_{b_name}_{chosen_r}")
            with col_t2:
                idx3 = available_players.index(p2_a) if p2_a in available_players else 0
                sel_p2a = st.selectbox(f"Gast S1 ({b_name})", available_players, index=idx3, key=f"qe_p2a_{b_name}_{chosen_r}")
                idx4 = available_players.index(p2_b) if p2_b in available_players else 0
                sel_p2b = st.selectbox(f"Gast S2 ({b_name})", available_players, index=idx4, key=f"qe_p2b_{b_name}_{chosen_r}")
                final_s2 = f"{sel_p2a} & {sel_p2b}"
                in_l2 = st.number_input(f"Legs Gast ({b_name})", 0, 5, s_l2, key=f"qe_l2_{b_name}_{chosen_r}")
                in_180_2 = st.number_input(f"180er Gast", 0, 20, c2_180, key=f"qe_182_{b_name}_{chosen_r}")
        else:
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                idx_s1 = available_players.index(curr_s1) if curr_s1 in available_players else 0
                final_s1 = st.selectbox(f"Heim ({b_name})", available_players, index=idx_s1, key=f"qe_s1_{b_name}_{chosen_r}")
                in_l1 = st.number_input(f"Legs Heim", 0, 5, s_l1, key=f"qe_l1_{b_name}_{chosen_r}")
                in_180_1 = st.number_input(f"180er Heim", 0, 20, c1_180, key=f"qe_181_{b_name}_{chosen_r}")
            with col_p2:
                idx_s2 = available_players.index(curr_s2) if curr_s2 in available_players else 0
                final_s2 = st.selectbox(f"Gast ({b_name})", available_players, index=idx_s2, key=f"qe_s2_{b_name}_{chosen_r}")
                in_l2 = st.number_input(f"Legs Gast", 0, 5, s_l2, key=f"qe_l2_{b_name}_{chosen_r}")
                in_180_2 = st.number_input(f"180er Gast", 0, 20, c2_180, key=f"qe_182_{b_name}_{chosen_r}")
                
        winner = final_s1 if in_l1 > in_l2 else (final_s2 if in_l2 > in_l1 else "")
        loser = final_s2 if winner == final_s1 else (final_s1 if winner == final_s2 else "")
        
        sess["results"][(chosen_r, b_name)] = {
            "s1": final_s1, "s2": final_s2, "ergebnis": f"{in_l1}:{in_l2}", "winner": winner, "loser": loser,
            "180_s1": in_180_1, "180_s2": in_180_2, "avg_s1": current_m.get("avg_s1", 0.0), "avg_s2": current_m.get("avg_s2", 0.0)
        }
        st.divider()
        
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with col_b2:
        if st.button("Speichern", type="primary", use_container_width=True):
            save_data(st.session_state.sessions_list)
            st.success("Gespeichert!")
            st.rerun()

@st.dialog("🗑️ Session löschen (Passwortgeschützt)")
def open_delete_dialog(session_idx):
    if session_idx >= len(st.session_state.sessions_list): return
    sess = st.session_state.sessions_list[session_idx]
    st.warning(f"Soll Session **{sess['id']}** vom **{sess['datum']}** gelöscht werden?")
    pwd = st.text_input("Passwort zur Bestätigung", type="password", key=f"del_pwd_{session_idx}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with col2:
        if st.button("Unwiderruflich löschen", type="primary", use_container_width=True):
            if pwd == "1521":
                st.session_state.sessions_list.pop(session_idx)
                save_data(st.session_state.sessions_list)
                st.success("Gelöscht!")
                st.rerun()
            elif pwd != "":
                st.error("Falsches Passwort!")

with tab_übersicht:
    st.subheader("Übersicht & Live-Status")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Neue Session starten", type="primary", use_container_width=True, key="start_sess_btn"):
            open_new_session_dialog()
    with col_btn2:
        if st.session_state.sessions_list:
            if st.button("⚙️ Letzte Session bearbeiten", use_container_width=True, key="edit_sess_btn"):
                open_edit_session_dialog(0)
        else:
            st.button("⚙️ Letzte Session bearbeiten", use_container_width=True, disabled=True)
            
    st.write("")
    
    total_180s = sum(int(m.get("180_s1", 0)) + int(m.get("180_s2", 0)) for s in st.session_state.sessions_list for m in s.get("results", {}).values())
    
    current_kaiser = "Noch offen"
    if st.session_state.sessions_list:
        l_res = st.session_state.sessions_list[0].get("results", {})
        k_matches = [(r, m) for (r, b), m in l_res.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
        if k_matches:
            k_matches.sort(key=lambda x: x[0], reverse=True)
            current_kaiser = k_matches[0][1].get("winner")
            
    active_p_count = len(st.session_state.sessions_list[0].get("spieler", [])) if st.session_state.sessions_list else len(kader)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Trainingsabende", str(len(st.session_state.sessions_list)), "gesamt")
    with c2:
        st.metric("Team 180er 🎯", str(total_180s), "geworfen")
    with c3:
        st.metric("Aktueller Kaiser 👑", current_kaiser, "Board 1")
    with c4:
        st.metric("Anwesende Spieler", str(active_p_count), "im Training")
        
    st.write("")
    
    active_sessions = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
    
    if not active_sessions:
        st.markdown("### 🔴 Laufende Session")
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um hier live die Ergebnisse einzutragen.")
    else:
        curr_sess = active_sessions[0]
        st.markdown("### 🔴 Laufende Session")
        st.caption(f"Session-ID: **{curr_sess['id']}** vom {curr_sess['datum']} ({curr_sess['modus']})")
        
        total_rounds = curr_sess.get("total_rounds", 4)
        modus_s = curr_sess.get("modus", "Up & Down")
        is_std = (modus_s == "Standard-Training (Einzel + Coop)")
        singles_r = curr_sess.get("singles_rounds", total_rounds - 2 if is_std and total_rounds > 2 else total_rounds)
        
        res = curr_sess.get("results", {})
        current_active_round = 1
        for r_check in range(1, total_rounds + 1):
            boards_in_r = get_boards_list(curr_sess, r_check)
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
                    
        active_boards_list = get_boards_list(curr_sess, current_active_round)
        
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
                            
                            ready = is_board_ready(curr_sess, b_name, next_r)
                            ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                            st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                            
                            existing_match = res.get((next_r, b_name))
                            if existing_match:
                                p1, p2 = existing_match.get("s1", "Offen"), existing_match.get("s2", "Offen")
                            else:
                                players_now = get_board_players(curr_sess, next_r, b_name)
                                p1, p2 = players_now[0], players_now[1]
                            
                            r_label = f"Runde {next_r}/{total_rounds}" if not (is_std and next_r > singles_r) else f"Doppelrunde {next_r-singles_r}/{total_rounds-singles_r}"
                            st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>{r_label}</p>", unsafe_allow_html=True)
                            
                            if p1 in ["-", "Offen"]:
                                st.markdown(f"<div style='text-align: center; font-weight: bold; color: gray; margin: 8px 0;'>-</div>", unsafe_allow_html=True)
                            else:
                                sc1, sc2 = st.columns([5, 2])
                                sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p1}</div>", unsafe_allow_html=True)
                                with sc2:
                                    if st.button("🔄", key=f"sub1_{b_name}_{next_r}", help="Spieler ändern"):
                                        open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r, 1, p1)
                            
                            st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                            
                            if p2 in ["-", "Offen"]:
                                st.markdown(f"<div style='text-align: center; font-weight: bold; color: gray; margin: 8px 0;'>-</div>", unsafe_allow_html=True)
                            else:
                                sc3, sc4 = st.columns([5, 2])
                                sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                                with sc4:
                                    if st.button("🔄", key=f"sub2_{b_name}_{next_r}", help="Spieler ändern"):
                                        open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r, 2, p2)
                            
                            st.write("")
                            if st.button("🎯 Ergebnis eintragen", key=f"lbtn_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                                open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess))

    st.write("")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("### Letzte Session")
        display_sess = None
        for s in st.session_state.sessions_list:
            if is_session_completed(s) or s.get("results"):
                display_sess = s
                break
        if not display_sess and st.session_state.sessions_list:
            display_sess = st.session_state.sessions_list[0]
            
        if display_sess:
            l_date = display_sess.get('datum', '–')
            l_results = display_sess.get('results', {})
            kaiser_winner = "Noch offen"
            k_matches = [(r, m) for (r, b), m in l_results.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
            if k_matches:
                k_matches.sort(key=lambda x: x[0], reverse=True)
                kaiser_winner = k_matches[0][1].get("winner")
            
            count_180s = {}
            match_avgs = []
            for m in l_results.values():
                s1_n, s2_n = m.get("s1", ""), m.get("s2", "")
                c1, c2 = int(m.get("180_s1", 0)), int(m.get("180_s2", 0))
                a1, a2 = float(m.get("avg_s1", 0.0)), float(m.get("avg_s2", 0.0))
                
                if s1_n and " & " not in s1_n: count_180s[s1_n] = count_180s.get(s1_n, 0) + c1
                if s2_n and " & " not in s2_n: count_180s[s2_n] = count_180s.get(s2_n, 0) + c2
                if s1_n and " & " not in s1_n and a1 > 0: match_avgs.append((s1_n, a1))
                if s2_n and " & " not in s2_n and a2 > 0: match_avgs.append((s2_n, a2))
            
            most_180_text = "Keine"
            if count_180s:
                top_player = max(count_180s, key=count_180s.get)
                if count_180s[top_player] > 0: most_180_text = f"{top_player} ({count_180s[top_player]}x)"
            
            best_avg_text = "–"
            if match_avgs:
                top_avg_player, top_avg_val = max(match_avgs, key=lambda x: x[1])
                best_avg_text = f"{top_avg_player} ({top_avg_val:.1f})"
            
            st.info(f"**Datum:** {l_date}\n\n**Kaiser B1 (Einzel):** 👑 {kaiser_winner}\n\n**Höchster Einzel-Average:** 📊 {best_avg_text}\n\n**Meiste 180er:** 🎯 {most_180_text}")
        else:
            st.info("**Datum:** –\n\n**Kaiser B1 (Einzel):** Noch offen\n\n**Höchster Einzel-Average:** –\n\n**Meiste 180er:** –")

    with col_r:
        st.markdown("### Spitzenreiter & Formkurve")
        st.caption("Sortiert nach Siegquote und absolvierten Matches")
        
        stats_temp = {p: {"Matches": 0, "Siege": 0} for p in kader}
        for sess in st.session_state.sessions_list:
            for match in sess.get("results", {}).values():
                winner, loser = match.get("winner", ""), match.get("loser", "")
                if winner and " & " not in winner:
                    for p in winner.split(" & "):
                        if p in stats_temp:
                            stats_temp[p]["Matches"] += 1
                            stats_temp[p]["Siege"] += 1
                if loser and " & " not in loser:
                    for p in loser.split(" & "):
                        if p in stats_temp: stats_temp[p]["Matches"] += 1

        best_p, best_q, best_m = "Keiner", 0.0, 0
        for p in kader:
            m = stats_temp[p]["Matches"]
            if m > 0:
                q = stats_temp[p]["Siege"] / m
                if q > best_q or (q == best_q and m > best_m):
                    best_q, best_m, best_p = q, m, p

        st.markdown(f"**{best_p}** (Siegquote: {(best_q*100):.0f}% bei {best_m} Matches)")
        st.progress(best_q)

    st.write("### Zuletzt ausgetragene Board-Matches")
    st.caption("Best of 5 und Gewinner für die Statistik")
    
    all_matches = []
    for sess in st.session_state.sessions_list:
        sess_date = sess.get("datum", "")
        for (round_num, board_name), m_info in sess.get("results", {}).items():
            if not m_info.get("winner"): continue
            all_matches.append({
                "Datum": sess_date, "Runde": round_num, "Board": board_name,
                "Spieler": f"{m_info['s1']} vs {m_info['s2']}", "Ergebnis": m_info['ergebnis'],
                "Sieger": m_info['winner']
            })
    if all_matches:
        st.dataframe(pd.DataFrame(all_matches), use_container_width=True, hide_index=True)
    else:
        st.info("Bisher wurden keine Board-Matches ausgetragen.")

with tab_kader:
    st.subheader("Kader & Spielerbilanz")
    st.write("Live berechnete Bilanz des festen Stammkaders (exklusive Gastspieler) inklusive Legs, 180er und Averages.")
    
    stats = {p: {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0} for p in kader}
    player_matches_played, total_wins, total_losses = 0, 0, 0
    team_session_avgs = []
    
    for sess in st.session_state.sessions_list:
        sess_avgs = []
        for match in sess.get("results", {}).values():
            winner, loser = match.get("winner", ""), match.get("loser", "")
            s1, s2 = match.get("s1", ""), match.get("s2", "")
            try:
                l1, l2 = map(int, match.get("ergebnis", "0:0").split(":"))
            except:
                l1, l2 = 0, 0
            h1, h2 = int(match.get("180_s1", 0)), int(match.get("180_s2", 0))
            a1, a2 = float(match.get("avg_s1", 0.0)), float(match.get("avg_s2", 0.0))
            
            if s1 in stats and " & " not in s1:
                stats[s1]["180er"] += h1; stats[s1]["Legs_Won"] += l1; stats[s1]["Legs_Lost"] += l2
                if a1 > 0: stats[s1]["Avg_Sum"] += a1; stats[s1]["Avg_Count"] += 1; sess_avgs.append(a1)
            if s2 in stats and " & " not in s2:
                stats[s2]["180er"] += h2; stats[s2]["Legs_Won"] += l2; stats[s2]["Legs_Lost"] += l1
                if a2 > 0: stats[s2]["Avg_Sum"] += a2; stats[s2]["Avg_Count"] += 1; sess_avgs.append(a2)
            
            if winner and " & " not in winner:
                for p in winner.split(" & "):
                    if p in stats:
                        stats[p]["Matches"] += 1; stats[p]["Siege"] += 1; player_matches_played += 1; total_wins += 1
            if loser and " & " not in loser:
                for p in loser.split(" & "):
                    if p in stats:
                        stats[p]["Matches"] += 1; stats[p]["Niederlagen"] += 1; player_matches_played += 1; total_losses += 1

        if sess_avgs:
            team_session_avgs.append({"Datum": sess.get("datum", "Unbekannt"), "Team-Average": round(sum(sess_avgs) / len(sess_avgs), 1)})

    best_wr, best_wr_player = 0.0, "–"
    for p in kader:
        if stats[p]["Matches"] >= 2:
            wr = stats[p]["Siege"] / stats[p]["Matches"]
            if wr > best_wr: best_wr, best_wr_player = wr, p
    best_wr_str = f"{(best_wr * 100):.0f}%" if best_wr > 0 else "–"

    all_team_avgs = [stats[p]["Avg_Sum"] / stats[p]["Avg_Count"] for p in kader if stats[p]["Avg_Count"] > 0]
    overall_team_avg = f"{(sum(all_team_avgs) / len(all_team_avgs)):.1f}" if all_team_avgs else "–"

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Aktive Spieler", len(kader), "im Kader")
    with col2: st.metric("Absolvierte Matches", str(player_matches_played), "aus Sessions")
    with col3: st.metric("Beste Siegquote", best_wr_str, best_wr_player)
    with col4: st.metric("Team-Gesamtschnitt", overall_team_avg, "Ø Average")
        
    st.write("")
    st.markdown("### 📈 Team-Entwicklung (Gesamt-Average über Sessions)")
    if team_session_avgs:
        st.line_chart(pd.DataFrame(team_session_avgs).set_index("Datum"))
    else:
        st.info("Noch nicht genügend Average-Daten vorhanden.")

    st.write("### Spielerübersicht & Rangliste")
    suche = st.text_input("Spieler suchen...", "")
    
    table_rows = []
    for p in kader:
        m, s, n = stats[p]["Matches"], stats[p]["Siege"], stats[p]["Niederlagen"]
        acount = stats[p]["Avg_Count"]
        table_rows.append({
            "Spieler": p, "Matches": m, "Siege": s, "Niederlagen": n,
            "Siegquote": f"{(s / m * 100):.0f}%" if m > 0 else "0%",
            "Legs Gewonnen": stats[p]["Legs_Won"], "Legs Verloren": stats[p]["Legs_Lost"],
            "🎯 180er": stats[p]["180er"], "📊 Ø Average": f"{(stats[p]['Avg_Sum'] / acount):.1f}" if acount > 0 else "–"
        })
        
    df_kader = pd.DataFrame(table_rows)
    if suche: df_kader = df_kader[df_kader["Spieler"].str.contains(suche, case=False)]
    st.dataframe(df_kader, use_container_width=True, hide_index=True)

    st.write("")
    st.markdown("### 🤝 Doppel-Paarungen (Coop-Statistik für die Liga)")
    pair_stats = {}
    for sess in st.session_state.sessions_list:
        for match in sess.get("results", {}).values():
            winner, s1, s2 = match.get("winner", ""), match.get("s1", ""), match.get("s2", "")
            try:
                l1, l2 = map(int, match.get("ergebnis", "0:0").split(":"))
            except:
                l1, l2 = 0, 0
            h1, h2 = int(match.get("180_s1", 0)), int(match.get("180_s2", 0))
            a1, a2 = float(match.get("avg_s1", 0.0)), float(match.get("avg_s2", 0.0))
            
            def process_pair(pair_str, is_won, won_legs, lost_legs, h_count, avg_val):
                if " & " in pair_str:
                    pair_key = " & ".join(sorted([p.strip() for p in pair_str.split("&")]))
                    if pair_key not in pair_stats:
                        pair_stats[pair_key] = {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0}
                    pair_stats[pair_key]["Matches"] += 1
                    if is_won: pair_stats[pair_key]["Siege"] += 1
                    else: pair_stats[pair_key]["Niederlagen"] += 1
                    pair_stats[pair_key]["Legs_Won"] += won_legs
                    pair_stats[pair_key]["Legs_Lost"] += lost_legs
                    pair_stats[pair_key]["180er"] += h_count
                    if avg_val > 0:
                        pair_stats[pair_key]["Avg_Sum"] += avg_val
                        pair_stats[pair_key]["Avg_Count"] += 1

            if " & " in s1: process_pair(s1, winner == s1, l1, l2, h1, a1)
            if " & " in s2: process_pair(s2, winner == s2, l2, l1, h2, a2)

    pair_rows = []
    for pair_name, p_data in pair_stats.items():
        m, s, n, acount = p_data["Matches"], p_data["Siege"], p_data["Niederlagen"], p_data["Avg_Count"]
        pair_rows.append({
            "Doppel-Team": pair_name, "Matches": m, "Siege": s, "Niederlagen": n,
            "Siegquote": f"{(s / m * 100):.0f}%" if m > 0 else "0%",
            "Legs Gewonnen": p_data["Legs_Won"], "Legs Verloren": p_data["Legs_Lost"],
            "🎯 180er": p_data["180er"], "📊 Ø Average": f"{(p_data['Avg_Sum'] / acount):.1f}" if acount > 0 else "–"
        })
        
    if pair_rows:
        st.dataframe(pd.DataFrame(pair_rows).sort_values(by=["Siege", "Legs Gewonnen"], ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Bisher wurden keine Doppel- oder Koop-Matches ausgetragen.")

with tab_session:
    st.subheader("Up & Down Sessions")
    
    total_sessions_cnt = len(st.session_state.sessions_list)
    total_attendance = sum(len(s.get("spieler", [])) for s in st.session_state.sessions_list)
    avg_attendance_val = round(total_attendance / total_sessions_cnt, 1) if total_sessions_cnt > 0 else 0

    kaiser_win_counts = {}
    for sess in st.session_state.sessions_list:
        res = sess.get("results", {})
        total_r = sess.get("total_rounds", 4)
        m_info = res.get((total_r, "Kaiser B1"))
        if m_info and m_info.get("winner"):
            winner = m_info.get("winner")
            if " & " not in winner:
                kaiser_win_counts[winner] = kaiser_win_counts.get(winner, 0) + 1
    
    top_kaiser_display = f"{max(kaiser_win_counts, key=kaiser_win_counts.get)} ({max(kaiser_win_counts.values())}x)" if kaiser_win_counts else "–"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gespielte Abende", str(total_sessions_cnt), "Sessions")
    with col2:
        st.metric("Ø Anwesende Spieler", str(avg_attendance_val), "pro Abend")
    with col3:
        st.metric("Rekord-Kaiser 👑", top_kaiser_display, "meiste Board 1 Siege")
        
    st.write("### Bisherige Sessions & Board-Endstände")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container():
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                status_text = " ✅ **[Abgeschlossen]**" if is_session_completed(sess) else ""
                total_rounds = sess.get("total_rounds", 4)
                st.markdown(f"**{sess['datum']}** — *{sess['modus']} · {sess['boards']} · {total_rounds} Runden · {sess['modus_leg']} · {sess['id']}{gaeste_text}*{status_text}")
                
                active_boards_list = get_boards_list(sess, 1)
                b_cols = st.columns(len(active_boards_list))
                for b_i, b_name in enumerate(active_boards_list):
                    with b_cols[b_i]:
                        res = sess.get("results", {})
                        completed = [r for (r, b), v in res.items() if b == b_name and v.get("winner")]
                        next_r = max(completed) + 1 if completed else 1
                        label_btn = f"🎯 {b_name}\nRunde {next_r}/{total_rounds}" if next_r <= total_rounds else f"🏆 {b_name}\nBeendet"
                        if st.button(label_btn, use_container_width=True, key=f"sbtn_{b_name}_{idx}"):
                            open_session_archive_dialog(idx)
                st.divider()

with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container(border=True):
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                st.markdown(f"**{sess['id']}** — {sess['datum']} (*{sess['modus']} · {sess['boards']} · {sess.get('total_rounds', 4)} Runden*{gaeste_text})")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("📊 Spielablauf", key=f"arch_view_{idx}", use_container_width=True):
                        open_session_archive_dialog(idx)
                with c2:
                    if st.button("⚡ Schnelldurchlauf", key=f"arch_quick_{idx}", use_container_width=True):
                        open_quick_entry_dialog(idx)
                with c3:
                    if st.button("🗑️ Löschen", key=f"arch_del_{idx}", use_container_width=True):
                        open_delete_dialog(idx)
