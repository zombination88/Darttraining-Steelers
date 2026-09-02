import streamlit as st
import pandas as pd
from datetime import date, timedelta
import json
import gspread
from google.oauth2.service_account import Credentials
import base64

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
    
    with st.popover("🎵", use_container_width=True):
        try:
            st.audio("vereinssong.mp3")
        except Exception:
            st.info("vereinssong.mp3 nicht gefunden.")

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
    K = session.get("boards_count", 4)
    has_resting = (len(spieler) % 2 != 0) or (len(spieler) > 2 * K)
    if not has_resting:
        return None
        
    if round_num == 1:
        return spieler[2 * K] if len(spieler) > 2 * K else (spieler[-1] if len(spieler) % 2 != 0 else None)
        
    prev_r = round_num - 1
    boards = get_boards_list(session, prev_r)
    if not boards:
        return "-"
    last_board = boards[-1]
    res = session.get("results", {})
    match_info = res.get((prev_r, last_board))
    if match_info and match_info.get("loser"):
        return match_info["loser"]
    else:
        def_players = get_board_players(session, prev_r, last_board)
        return def_players[1] if len(def_players) > 1 else "-"

def get_board_players(session, round_num, board_name):
    boards = get_boards_list(session, round_num)
    if board_name not in boards:
        return ["-", "-"]
    b_idx = boards.index(board_name)
    
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session["spieler"].copy()
    K = session.get("boards_count", len(boards))
    has_resting = (len(spieler) % 2 != 0) or (len(spieler) > 2 * K)
    
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
                p1, p2 = "-", "-"
                if match_inf:
                    p1 = match_inf.get("s1", "-")
                    p2 = match_inf.get("s2", "-")
                else:
                    p_pair = get_board_players(prev_sess, target_r, pb)
                    p1, p2 = p_pair[0], p_pair[1]
                if p2 != "-" and p2 not in prev_players_bottom_to_top:
                    prev_players_bottom_to_top.append(p2)
                if p1 != "-" and p1 not in prev_players_bottom_to_top:
                    prev_players_bottom_to_top.append(p1)
            
            returning_players = [p for p in prev_players_bottom_to_top if p in spieler]
            new_players = [p for p in spieler if p not in prev_players_bottom_to_top]
            
            ordered_players = new_players + returning_players
            for p in spieler:
                if p not in ordered_players:
                    ordered_players.append(p)
            spieler = ordered_players[:len(spieler)]

    pairs = []
    
    if is_2v2 or in_coop_phase:
        teams = []
        all_sessions = st.session_state.sessions_list
        try:
            s_idx = all_sessions.index(session)
        except:
            s_idx = 0
            
        if in_coop_phase:
            coop_shift = (s_idx + (round_num - singles_rounds)) % len(spieler)
            spieler = spieler[coop_shift:] + spieler[:coop_shift]
            
        for i in range(0, len(spieler)-1, 2):
            teams.append(f"{spieler[i]} & {spieler[i+1]}")
        if len(spieler) % 2 != 0:
            teams.append(f"{spieler[-1]} & -")
            
        coop_boards_cnt = 2
        for i in range(0, min(coop_boards_cnt * 2, len(teams) - len(teams) % 2), 2):
            pairs.append((teams[i], teams[i+1]))
        while len(pairs) <= b_idx:
            t1 = teams[0] if len(teams) > 0 else "-"
            t2 = teams[1] if len(teams) > 1 else "-"
            pairs.append((t1, t2))
        return list(pairs[b_idx])
    else:
        boards_count = session.get("boards_count", len(boards))
        if round_num == 1:
            active_spielern = spieler[:2 * boards_count] if has_resting else spieler[:2 * boards_count]
            for i in range(0, min(boards_count * 2, len(active_spielern) - len(active_spielern) % 2), 2):
                pairs.append((active_spielern[i], active_spielern[i+1]))
            while len(pairs) <= b_idx:
                pairs.append((spieler[0] if spieler else "-", spieler[1] if len(spieler) > 1 else "-"))
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
            p1 = w.get(boards[0], "-")
            p2 = w.get(boards[1], "-") if len(boards) > 1 else "-"
            return [p1, p2]
        
        if b_idx < len(boards) - 1:
            prev_board = boards[b_idx - 1]
            next_board = boards[b_idx + 1]
            loser_from_above = l.get(prev_board, "-")
            winner_from_below = w.get(next_board, "-")
            return [loser_from_above, winner_from_below]
            
        if b_idx == len(boards) - 1:
            prev_board = boards[b_idx - 1]
            loser_from_above = l.get(prev_board, "-")
            if has_resting:
                resting_p_prev = get_resting_player(session, round_num - 1)
                return [loser_from_above, resting_p_prev if resting_p_prev else "-"]
            else:
                loser_from_last = l.get(boards[b_idx], "-")
                return [loser_from_above, loser_from_last]

    return ["-", "-"]

def is_board_ready(session, board_name, next_r):
    if next_r == 1:
        return True
    
    modus = session.get("modus", "Up & Down")
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if modus == "Standard-Training (Einzel + Coop)" and total_rounds > 2 else total_rounds)
    
    if modus == "Standard-Training (Einzel + Coop)" and next_r == singles_rounds + 1:
        res = session.get("results", {})
        singles_boards = get_boards_list(session, singles_rounds)
        for r in range(1, singles_rounds + 1):
            for b in singles_boards:
                if not res.get((r, b), {}).get("winner"):
                    return False
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
    elif b_idx < len(boards) - 1:
        req_boards.append(boards[b_idx - 1])
        req_boards.append(boards[b_idx + 1])
    else:
        req_boards.append(boards[b_idx - 1])
        req_boards.append(boards[b_idx])
            
    for rb in req_boards:
        match_inf = res.get((prev_r, rb))
        if not match_inf or not match_inf.get("winner"):
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
    if "-" not in alle_spieler:
        alle_spieler.append("-")
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
            if is_standard_training:
                if r <= singles_rounds:
                    r_title = f"Runde {r}/{singles_rounds} (Einzel)"
                else:
                    r_title = f"Doppelrunde {r - singles_rounds}/{total_rounds - singles_rounds} (Coop)"
            else:
                r_title = f"Runde {r}/{total_rounds}"
                
            st.markdown(f"#### 🎯 {r_title}")
            boards_in_r = get_boards_list(sess, r)
            r_matches = []
            for b_name in boards_in_r:
                match_info = res.get((r, b_name))
                if match_info:
                    r_matches.append({
                        "Board": b_name,
                        "Heim": match_info.get("s1", "–"),
                        "Gast": match_info.get("s2", "–"),
                        "Ergebnis": match_info.get("ergebnis", "–"),
                        "Sieger": match_info.get("winner", "Offen"),
                        "180er (H/G)": f"{match_info.get('180_s1', 0)} / {match_info.get('180_s2', 0)}",
                        "Average (H/G)": f"{match_info.get('avg_s1', 0.0)} / {match_info.get('avg_s2', 0.0)}"
                    })
                else:
                    auto_p = get_board_players(sess, r, b_name)
                    r_matches.append({
                        "Board": b_name,
                        "Heim": auto_p[0],
                        "Gast": auto_p[1],
                        "Ergebnis": "Ausstehend",
                        "Sieger": "–",
                        "180er (H/G)": "–",
                        "Average (H/G)": "–"
                    })
            if r_matches:
                df_r = pd.DataFrame(r_matches)
                st.dataframe(df_r, use_container_width=True, hide_index=True)
            
            if is_standard_training and r == singles_rounds:
                st.markdown("##### 🏆 Board-Endstand nach den Einzel-Runden:")
                standings_rows = []
                singles_boards = get_boards_list(sess, singles_rounds)
                for b_name in singles_boards:
                    p_list = get_board_players(sess, singles_rounds, b_name)
                    m_inf = res.get((singles_rounds, b_name))
                    winner_str = m_inf.get("winner", "–") if m_inf else "–"
                    standings_rows.append({
                        "Board": b_name,
                        "Spieler 1 (Heim)": p_list[0],
                        "Spieler 2 (Gast)": p_list[1],
                        "Sieger des Matches": winner_str
                    })
                if standings_rows:
                    df_standings = pd.DataFrame(standings_rows)
                    st.dataframe(df_standings, use_container_width=True, hide_index=True)
                
            st.divider()
            
    if st.button("Schließen", use_container_width=True):
        st.rerun()

@st.dialog("⚡ Schnelldurchlauf Ergebnisse (Passwortgeschützt)")
def open_quick_entry_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"qe_pwd_input_{session_idx}")
    if pwd != "1521":
        if pwd != "":
            st.error("Falsches Passwort!")
        return

    sess = st.session_state.sessions_list[session_idx]
    total_rounds = sess.get("total_rounds", 4)
    modus = sess.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    st.caption("Trage hier rundenweise die Ergebnisse ein und passe Spieler an.")
    
    round_options = []
    for r in range(1, total_rounds + 1):
        if is_standard_training:
            if r <= singles_rounds:
                round_options.append((r, f"Runde {r} / {singles_rounds} (Einzel)"))
            else:
                round_options.append((r, f"Doppelrunde {r - singles_rounds} / {total_rounds - singles_rounds} (Coop)"))
        else:
            round_options.append((r, f"Runde {r} / {total_rounds}"))
            
    selected_r_tuple = st.selectbox("Wähle Runde aus:", round_options, format_func=lambda x: x[1], key=f"qe_round_sel_{session_idx}")
    current_round = selected_r_tuple[0]
    
    boards_in_round = get_boards_list(sess, current_round)
    res = sess.get("results", {})
    
    st.markdown(f"#### 🎯 Partien & Spieler für {selected_r_tuple[1]}")
    
    if "results" not in sess:
        sess["results"] = {}
        
    alle_mögliche_spieler = list(set(sess.get("spieler", kader)))
    if "-" not in alle_mögliche_spieler:
        alle_mögliche_spieler.append("-")
    alle_mögliche_spieler.sort()
    
    in_coop_phase_qe = is_standard_training and current_round > singles_rounds
    is_coop_round_qe = is_2v2 or in_coop_phase_qe
    
    for b_name in boards_in_round:
        st.markdown(f"**{b_name}**")
        auto_p = get_board_players(sess, current_round, b_name)
        match_key = (current_round, b_name)
        existing_match = res.get(match_key, {})
        
        p1_default = existing_match.get("s1", auto_p[0])
        p2_default = existing_match.get("s2", auto_p[1])
        if not p1_default: p1_default = auto_p[0]
        if not p2_default: p2_default = auto_p[1]
        
        if is_coop_round_qe:
            h_parts = [p.strip() for p in p1_default.split("&")] if "&" in p1_default else [p1_default, "-"]
            g_parts = [p.strip() for p in p2_default.split("&")] if "&" in p2_default else [p2_default, "-"]
            
            h1_def = h_parts[0] if len(h_parts) > 0 else "-"
            h2_def = h_parts[1] if len(h_parts) > 1 else "-"
            g1_def = g_parts[0] if len(g_parts) > 0 else "-"
            g2_def = g_parts[1] if len(g_parts) > 1 else "-"
            
            for p_check in [h1_def, h2_def, g1_def, g2_def]:
                if p_check not in alle_mögliche_spieler:
                    alle_mögliche_spieler.append(p_check)
            alle_mögliche_spieler.sort()
            
            st.markdown(f"**Heim-Team ({b_name})**")
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                idx_h1 = alle_mögliche_spieler.index(h1_def) if h1_def in alle_mögliche_spieler else 0
                sel_h1 = st.selectbox(f"Heim S1 ({b_name})", alle_mögliche_spieler, index=idx_h1, key=f"qe_h1_{session_idx}_{current_round}_{b_name}")
            with col_h2:
                idx_h2 = alle_mögliche_spieler.index(h2_def) if h2_def in alle_mögliche_spieler else 0
                sel_h2 = st.selectbox(f"Heim S2 ({b_name})", alle_mögliche_spieler, index=idx_h2, key=f"qe_h2_{session_idx}_{current_round}_{b_name}")
                
            st.markdown(f"**Gast-Team ({b_name})**")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                idx_g1 = alle_mögliche_spieler.index(g1_def) if g1_def in alle_mögliche_spieler else 0
                sel_g1 = st.selectbox(f"Gast S1 ({b_name})", alle_mögliche_spieler, index=idx_g1, key=f"qe_g1_{session_idx}_{current_round}_{b_name}")
            with col_g2:
                idx_g2 = alle_mögliche_spieler.index(g2_def) if g2_def in alle_mögliche_spieler else 0
                sel_g2 = st.selectbox(f"Gast S2 ({b_name})", alle_mögliche_spieler, index=idx_g2, key=f"qe_g2_{session_idx}_{current_round}_{b_name}")
                
            sel_p1 = f"{sel_h1} & {sel_h2}"
            sel_p2 = f"{sel_g1} & {sel_g2}"
        else:
            if p1_default not in alle_mögliche_spieler: alle_mögliche_spieler.append(p1_default)
            if p2_default not in alle_mögliche_spieler: alle_mögliche_spieler.append(p2_default)
            alle_mögliche_spieler.sort()
            
            c_p1, c_vs, c_p2 = st.columns([3, 1, 3])
            with c_p1:
                idx1 = alle_mögliche_spieler.index(p1_default) if p1_default in alle_mögliche_spieler else 0
                sel_p1 = st.selectbox(f"Heim ({b_name})", alle_mögliche_spieler, index=idx1, key=f"qe_p1_{session_idx}_{current_round}_{b_name}")
            with c_vs:
                st.markdown("<div style='text-align: center; color: #ff4b4b; padding-top: 30px; font-weight: bold;'>VS</div>", unsafe_allow_html=True)
            with c_p2:
                idx2 = alle_mögliche_spieler.index(p2_default) if p2_default in alle_mögliche_spieler else 0
                sel_p2 = st.selectbox(f"Gast ({b_name})", alle_mögliche_spieler, index=idx2, key=f"qe_p2_{session_idx}_{current_round}_{b_name}")
        
        try:
            default_score1 = int(existing_match.get("ergebnis", "0:0").split(":")[0])
            default_score2 = int(existing_match.get("ergebnis", "0:0").split(":")[1])
        except:
            default_score1, default_score2 = 0, 0
            
        def_180_1 = int(existing_match.get("180_s1", 0))
        def_180_2 = int(existing_match.get("180_s2", 0))
        def_avg_1 = float(existing_match.get("avg_s1", 0.0))
        def_avg_2 = float(existing_match.get("avg_s2", 0.0))
        
        sc1, sc2, t180_1, t180_2 = st.columns(4)
        with sc1:
            s1_val = st.number_input("Legs Heim", min_value=0, max_value=5, value=default_score1, key=f"qe_sc1_{session_idx}_{current_round}_{b_name}")
        with sc2:
            s2_val = st.number_input("Legs Gast", min_value=0, max_value=5, value=default_score2, key=f"qe_sc2_{session_idx}_{current_round}_{b_name}")
        with t180_1:
            t180_1_val = st.number_input("180er Heim", min_value=0, max_value=10, value=def_180_1, key=f"qe_180_1_{session_idx}_{current_round}_{b_name}")
        with t180_2:
            t180_2_val = st.number_input("180er Gast", min_value=0, max_value=10, value=def_180_2, key=f"qe_180_2_{session_idx}_{current_round}_{b_name}")
            
        ergebnis_str = f"{s1_val}:{s2_val}"
        winner = sel_p1 if s1_val > s2_val else (sel_p2 if s2_val > s1_val else None)
        loser = sel_p2 if winner == sel_p1 else (sel_p1 if winner == sel_p2 else None)
        
        sess["results"][match_key] = {
            "s1": sel_p1,
            "s2": sel_p2,
            "ergebnis": ergebnis_str,
            "winner": winner if winner else "",
            "loser": loser if loser else "",
            "180_s1": t180_1_val,
            "180_s2": t180_2_val,
            "avg_s1": def_avg_1,
            "avg_s2": def_avg_2
        }
        st.divider()
        
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Schließen", use_container_width=True, key=f"qe_close_{session_idx}"):
            st.rerun()
    with col_b2:
        if st.button("💾 Ergebnisse speichern", type="primary", use_container_width=True, key=f"qe_save_{session_idx}"):
            save_data(st.session_state.sessions_list)
            st.success("Ergebnisse und Spieler erfolgreich gespeichert!")
            st.rerun()

@st.dialog("➕ Neue Session starten (Passwortgeschützt)")
def open_new_session_dialog():
    pwd = st.text_input("Passwort eingeben", type="password", key="dialog_pwd_input")
    if pwd != "1521":
        if pwd != "":
            st.error("Falsches Passwort!")
        return

    session_datum = st.date_input("Datum", date.today())
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
    spielmodus = st.selectbox("Spielmodus", ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)", "Liga (4er-Team)"])
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        st.write("### Runden-Aufteilung")
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=3)
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 5)), index=1)
        total_rounds = singles_rounds + coop_rounds
        st.info(f"ℹ️ Standard-Training: {singles_rounds} Runden Einzel (auf gewählten Boards) + {coop_rounds} Runden Doppel/Koop (auf exakt 2 Boards).")
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

@st.dialog("➕ Vergangene Session nachtragen (Passwortgeschützt)")
def open_retroactive_session_dialog():
    pwd = st.text_input("Passwort eingeben", type="password", key="retro_pwd_input")
    if pwd != "1521":
        if pwd != "":
            st.error("Falsches Passwort!")
        return

    yesterday = date.today() - timedelta(days=1)
    session_datum = st.date_input("Datum der Session", yesterday, key="retro_date_input")
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"], key="retro_leg_input")
    spielmodus = st.selectbox("Spielmodus", ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)", "Liga (4er-Team)"], key="retro_mod_input")
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        st.write("### Runden-Aufteilung")
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=3, key="retro_singles_input")
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 5)), index=1, key="retro_coop_input")
        total_rounds = singles_rounds + coop_rounds
    else:
        singles_rounds = 0
        coop_rounds = 0
        total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=3, key="retro_rounds_input")
        
    anzahl_boards = st.selectbox("Anzahl der Boards", ["4 Boards", "6 Boards", "5 Boards", "3 Boards", "2 Boards", "1 Board"], index=0, key="retro_boards_input")
    
    st.write("### Anwesende Spieler")
    anwesende = []
    cols = st.columns(2)
    half = len(kader) // 2
    with cols[0]:
        for spieler in kader[:half]:
            if st.checkbox(spieler, value=True, key=f"retro_kader_{spieler}"):
                anwesende.append(spieler)
    with cols[1]:
        for spieler in kader[half:]:
            if st.checkbox(spieler, value=True, key=f"retro_kader_{spieler}"):
                anwesende.append(spieler)
                
    st.write("### Gastspieler (optional, max. 4)")
    g1 = st.text_input("Gastspieler 1", key="retro_gast_1")
    g2 = st.text_input("Gastspieler 2", key="retro_gast_2")
    g3 = st.text_input("Gastspieler 3", key="retro_gast_3")
    g4 = st.text_input("Gastspieler 4", key="retro_gast_4")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True, key="retro_cancel_btn"):
            st.rerun()
    with col_b2:
        if st.button("Nachtrag speichern", type="primary", use_container_width=True, key="retro_save_btn"):
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
            st.success("Session erfolgreich nachträglich angelegt!")
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
    
    modi_list = ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)", "Liga (4er-Team)"]
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
        if st.button("Schließen", use_container_width=True):
            st.rerun()
        return

    modus = sess.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    if is_standard_training:
        if current_round <= singles_rounds:
            round_title_str = f"Runde {current_round}/{singles_rounds} (Einzel)"
        else:
            round_title_str = f"Doppelrunde {current_round - singles_rounds}/{total_rounds - singles_rounds} (Coop)"
    else:
        round_title_str = f"Runde {current_round}/{total_rounds}"

    st.write(f"### {board_name} (Session {sess['id']}) — {round_title_str}")
    
    existing_match = res.get((current_round, board_name))
    
    if existing_match:
        current_p1 = existing_match.get("s1", "-")
        current_p2 = existing_match.get("s2", "-")
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
        in_score1 = st.number_input("Legs Heim", min_value=0, max_value=5, value=score1, key=f"d_score1_{board_name}_{session_idx}")
        in_180_1 = st.number_input(f"🎯 180er von {current_p1}", min_value=0, max_value=20, value=t1_180, key=f"d_180_1_{board_name}_{session_idx}")
        in_avg_1 = st.number_input(f"📊 Match-Average {current_p1}", min_value=0.0, max_value=180.0, value=avg1, step=0.1, key=f"d_avg_1_{board_name}_{session_idx}")
        
    with col2:
        st.markdown(f"**Gast:** `{current_p2}`")
        in_score2 = st.number_input("Legs Gast", min_value=0, max_value=5, value=score2, key=f"d_score2_{board_name}_{session_idx}")
        in_180_2 = st.number_input(f"🎯 180er von {current_p2}", min_value=0, max_value=20, value=t2_180, key=f"d_180_2_{board_name}_{session_idx}")
        in_avg_2 = st.number_input(f"📊 Match-Average {current_p2}", min_value=0.0, max_value=180.0, value=avg2, step=0.1, key=f"d_avg_2_{board_name}_{session_idx}")
        
    ergebnis = f"{in_score1}:{in_score2}"
    winner = current_p1 if in_score1 > in_score2 else (current_p2 if in_score2 > in_score1 else (current_p1 if in_score1 >= in_score2 else current_p2))
    loser = current_p2 if winner == current_p1 else current_p1
    
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
    
    total_sessions_count = len(st.session_state.sessions_list)
    total_180s_count = 0
    active_kaiser_name = "Noch offen"
    
    target_sess_for_metrics = active_sessions_for_btn[0] if active_sessions_for_btn else (st.session_state.sessions_list[0] if st.session_state.sessions_list else None)
    if target_sess_for_metrics:
        res_m = target_sess_for_metrics.get("results", {})
        completed_kaiser = [(r, m) for (r, b), m in res_m.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
        if completed_kaiser:
            completed_kaiser.sort(key=lambda x: x[0], reverse=True)
            active_kaiser_name = completed_kaiser[0][1].get("winner", "Noch offen")
            
    for sess in st.session_state.sessions_list:
        for m_inf in sess.get("results", {}).values():
            total_180s_count += int(m_inf.get("180_s1", 0)) + int(m_inf.get("180_s2", 0))
            
    current_active_players_count = len(target_sess_for_metrics.get("spieler", kader)) if target_sess_for_metrics else len(kader)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Trainingsabende", value=str(total_sessions_count), delta="Gesamt")
    with col2:
        st.metric(label="Team 180er", value=str(total_180s_count), delta="geworfen 🎯")
    with col3:
        st.metric(label="Anwesende Spieler", value=str(current_active_players_count), delta="heute" if active_sessions_for_btn else "im Kader")
    with col4:
        st.metric(label="Aktueller Kaiser 👑", value=active_kaiser_name, delta="Board 1")
        
    st.write("")
    
    st.markdown("### 🔴 Laufende Session")
    if not active_sessions_for_btn:
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Übersicht zu sehen.")
    else:
        curr_sess = active_sessions_for_btn[0]
        st.caption(f"Session-ID: **{curr_sess['id']}** vom {curr_sess['datum']} ({curr_sess['modus']})")
        
        total_rounds = curr_sess.get("total_rounds", 4)
        modus = curr_sess.get("modus", "Up & Down")
        is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
        singles_rounds = curr_sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
        
        res = curr_sess.get("results", {})
        boards_count = curr_sess.get("boards_count", 4)
        all_possible_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"][:boards_count]
        
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
                    
        curr_waiting = get_resting_player(curr_sess, current_active_round)
        if curr_waiting and curr_waiting != "-":
            st.info(f"☕ **Pause in dieser Runde:** `{curr_waiting}` (Wartet auf das Ende des letzten Boards)")

        if is_standard_training:
            if current_active_round <= singles_rounds:
                round_title_str = f"Runde {current_active_round} von {singles_rounds} (Einzel)"
            else:
                round_title_str = f"Doppelrunde {current_active_round - singles_rounds} von {total_rounds - singles_rounds} (Coop)"
        else:
            round_title_str = f"Runde {current_active_round} von {total_rounds}"

        st.markdown(f"#### {round_title_str} ({len(all_possible_boards)} Boards aktiv)")
        
        cols_per_row = 3
        for i in range(0, len(all_possible_boards), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(all_possible_boards):
                    b_name = all_possible_boards[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            board_active_round = 1
                            for r_chk in range(1, total_rounds + 1):
                                session_boards_at_r = get_boards_list(curr_sess, r_chk)
                                if b_name not in session_boards_at_r:
                                    continue
                                match_info = res.get((r_chk, b_name))
                                if not match_info or not match_info.get("winner"):
                                    board_active_round = r_chk
                                    break
                                else:
                                    if r_chk == total_rounds:
                                        board_active_round = total_rounds + 1
                                        
                            next_r = board_active_round
                            
                            st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                            
                            if next_r <= total_rounds:
                                session_boards_at_r = get_boards_list(curr_sess, next_r)
                                if b_name not in session_boards_at_r:
                                    st.markdown("<p style='text-align: center; color: gray; font-size: 0.85em;'>Nicht in dieser Phase</p>", unsafe_allow_html=True)
                                else:
                                    ready = is_board_ready(curr_sess, b_name, next_r)
                                    ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                                    st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                                    
                                    existing_match = res.get((next_r, b_name))
                                    if existing_match:
                                        p1 = existing_match.get("s1", "-")
                                        p2 = existing_match.get("s2", "-")
                                    else:
                                        if ready:
                                            players_now = get_board_players(curr_sess, next_r, b_name)
                                            p1, p2 = players_now[0], players_now[1]
                                        else:
                                            p1, p2 = "-", "-"
                                            
                                    if is_standard_training:
                                        if next_r <= singles_rounds:
                                            round_sub_str = f"Runde {next_r}/{singles_rounds}"
                                        else:
                                            round_sub_str = f"Doppelrunde {next_r - singles_rounds}/{total_rounds - singles_rounds}"
                                    else:
                                        round_sub_str = f"Runde {next_r}/{total_rounds}"
                                        
                                    st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>{round_sub_str}</p>", unsafe_allow_html=True)
                                    
                                    if ready and p1 != "-" and p1 != "Offen":
                                        sc1, sc2 = st.columns([5, 2])
                                        sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p1}</div>", unsafe_allow_html=True)
                                        with sc2:
                                            if st.button("🔄 Ändern", key=f"sub_btn1_{b_name}_{next_r}", help="Spieler 1 auswechseln"):
                                                open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r, 1, p1)
                                    else:
                                        st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 0.95em; margin: 12px 0;'>{p1}</div>", unsafe_allow_html=True)
                                    
                                    st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                                    
                                    if ready and p2 != "-" and p2 != "Offen":
                                        sc3, sc4 = st.columns([5, 2])
                                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                                        with sc4:
                                            if st.button("🔄 Ändern", key=f"sub_btn2_{b_name}_{next_r}", help="Spieler 2 auswechseln"):
                                                open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r, 2, p2)
                                    else:
                                        st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 0.95em; margin: 12px 0;'>{p2}</div>", unsafe_allow_html=True)
                                    
                                    st.write("")
                                    if st.button("🎯 Ergebnis eintragen", key=f"live_btn_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                                        open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess))
                            else:
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle {total_rounds} Runden beendet</p>", unsafe_allow_html=True)
                                st.success("✅ Board abgeschlossen")

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
            kaiser_matches = [(r, m) for (r, b), m in l_results.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
            if kaiser_matches:
                kaiser_matches.sort(key=lambda x: x[0], reverse=True)
                kaiser_winner = kaiser_matches[0][1].get("winner")
            
            count_180s = {}
            match_avgs = []
            for m in l_results.values():
                s1_name = m.get("s1", "")
                s2_name = m.get("s2", "")
                c1 = int(m.get("180_s1", 0))
                c2 = int(m.get("180_s2", 0))
                a1 = float(m.get("avg_s1", 0.0))
                a2 = float(m.get("avg_s2", 0.0))
                
                if s1_name and " & " not in s1_name: count_180s[s1_name] = count_180s.get(s1_name, 0) + c1
                if s2_name and " & " not in s2_name: count_180s[s2_name] = count_180s.get(s2_name, 0) + c2
                
                if s1_name and " & " not in s1_name and a1 > 0: match_avgs.append((s1_name, a1))
                if s2_name and " & " not in s2_name and a2 > 0: match_avgs.append((s2_name, a2))
            
            most_180_text = "Keine"
            if count_180s:
                top_player = max(count_180s, key=count_180s.get)
                if count_180s[top_player] > 0:
                    most_180_text = f"{top_player} ({count_180s[top_player]}x)"
            
            best_avg_text = "–"
            if match_avgs:
                top_avg_player, top_avg_val = max(match_avgs, key=lambda x: x[1])
                best_avg_text = f"{top_avg_player} ({top_avg_val:.1f})"
            
            st.info(f"**Datum:** {l_date}\n\n**Kaiser B1 (Einzel):** 👑 {kaiser_winner}\n\n**Höchster Einzel-Average:** 📊 {best_avg_text}\n\n**Meiste 180er:** 🎯 {most_180_text}\n\n**Fahrstuhl-Award:** Offen")
        else:
            st.info("**Datum:** –\n\n**Kaiser B1 (Einzel):** Noch offen\n\n**Höchster Einzel-Average:** –\n\n**Meiste 180er:** –\n\n**Fahrstuhl-Award:** Offen")

    with col_r:
        st.markdown("### Spitzenreiter & Formkurve")
        st.caption("Sortiert nach Siegquote und absolvierten Matches")
        
        stats_temp = {p: {"Matches": 0, "Siege": 0} for p in kader}
        for sess in st.session_state.sessions_list:
            for match in sess.get("results", {}).values():
                winner = match.get("winner", "")
                loser = match.get("loser", "")
                if winner and " & " not in winner:
                    for p in winner.split(" & "):
                        if p in stats_temp:
                            stats_temp[p]["Matches"] += 1
                            stats_temp[p]["Siege"] += 1
                if loser and " & " not in loser:
                    for p in loser.split(" & "):
                        if p in stats_temp:
                            stats_temp[p]["Matches"] += 1

        best_p = "Keiner"
        best_q = 0.0
        best_m = 0
        for p in kader:
            m = stats_temp[p]["Matches"]
            s = stats_temp[p]["Siege"]
            if m > 0:
                q = s / m
                if q > best_q or (q == best_q and m > best_m):
                    best_q = q
                    best_m = m
                    best_p = p

        st.markdown(f"**{best_p}** (Siegquote: {(best_q*100):.0f}% bei {best_m} Matches)")
        st.progress(best_q)

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
    total_wins = 0
    total_losses = 0
    
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
                        total_wins += 1
            if loser and " & " not in loser:
                for p in loser.split(" & "):
                    if p in stats:
                        stats[p]["Matches"] += 1
                        stats[p]["Niederlagen"] += 1
                        player_matches_played += 1
                        total_losses += 1

        if sess_avgs:
            t_avg = sum(sess_avgs) / len(sess_avgs)
            team_session_avgs.append({"Datum": sess.get("datum", "Unbekannt"), "Team-Average": round(t_avg, 1)})

    # Beste Siegquote berechnen (ab min 2 Matches)
    best_player_name = "-"
    best_player_rate = 0.0
    for p in kader:
        m = stats[p]["Matches"]
        s = stats[p]["Siege"]
        if m >= 2:
            q = s / m
            if q > best_player_rate:
                best_player_rate = q
                best_player_name = p
    best_quote_str = f"{(best_player_rate * 100):.0f}%" if best_player_name != "-" else "–"
    delta_quote = f"Top: {best_player_name}" if best_player_name != "-" else "ab 2 Matches"

    all_team_avgs = [stats[p]["Avg_Sum"] / stats[p]["Avg_Count"] for p in kader if stats[p]["Avg_Count"] > 0]
    overall_team_avg = f"{(sum(all_team_avgs) / len(all_team_avgs)):.1f}" if all_team_avgs else "–"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
    with col2:
        st.metric(label="Absolvierte Matches", value=str(player_matches_played), delta="aus Sessions")
    with col3:
        st.metric(label="Beste Siegquote", value=best_quote_str, delta=delta_quote)
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
    suche = st.text_input("Spieler suchen...", "")
    
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

    # DOPPEL-PAARUNGEN / COOP-STATISTIK FÜR DIE LIGA
    st.write("")
    st.markdown("### 🤝 Doppel-Paarungen (Coop-Statistik für die Liga)")
    st.caption("Auswertung aller Doppel- und Koop-Matches zur Findung der perfekten Ligapaarungen.")
    
    pair_stats = {}
    for sess in st.session_state.sessions_list:
        for match in sess.get("results", {}).values():
            winner = match.get("winner", "")
            s1 = match.get("s1", "")
            s2 = match.get("s2", "")
            ergebnis = match.get("ergebnis", "0:0")
            
            try:
                l1, l2 = map(int, ergebnis.split(":"))
            except:
                l1, l2 = 0, 0
                
            h1 = int(match.get("180_s1", 0))
            h2 = int(match.get("180_s2", 0))
            a1 = float(match.get("avg_s1", 0.0))
            a2 = float(match.get("avg_s2", 0.0))
            
            def process_pair(pair_str, is_won, won_legs, lost_legs, h_count, avg_val):
                if " & " in pair_str:
                    p_members = sorted([p.strip() for p in pair_str.split("&")])
                    pair_key = " & ".join(p_members)
                    if pair_key not in pair_stats:
                        pair_stats[pair_key] = {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0}
                    pair_stats[pair_key]["Matches"] += 1
                    if is_won:
                        pair_stats[pair_key]["Siege"] += 1
                    else:
                        pair_stats[pair_key]["Niederlagen"] += 1
                    pair_stats[pair_key]["Legs_Won"] += won_legs
                    pair_stats[pair_key]["Legs_Lost"] += lost_legs
                    pair_stats[pair_key]["180er"] += h_count
                    if avg_val > 0:
                        pair_stats[pair_key]["Avg_Sum"] += avg_val
                        pair_stats[pair_key]["Avg_Count"] += 1

            if " & " in s1:
                is_s1_win = (winner == s1)
                process_pair(s1, is_s1_win, l1, l2, h1, a1)
            if " & " in s2:
                is_s2_win = (winner == s2)
                process_pair(s2, is_s2_win, l2, l1, h2, a2)

    pair_rows = []
    for pair_name, p_data in pair_stats.items():
        m = p_data["Matches"]
        s = p_data["Siege"]
        n = p_data["Niederlagen"]
        quote = f"{(s / m * 100):.0f}%" if m > 0 else "0%"
        acount = p_data["Avg_Count"]
        avg_val = f"{(p_data['Avg_Sum'] / acount):.1f}" if acount > 0 else "–"
        pair_rows.append({
            "Doppel-Team": pair_name,
            "Matches": m,
            "Siege": s,
            "Niederlagen": n,
            "Siegquote": quote,
            "Legs Gewonnen": p_data["Legs_Won"],
            "Legs Verloren": p_data["Legs_Lost"],
            "🎯 180er": p_data["180er"],
            "📊 Ø Average": avg_val
        })
        
    if pair_rows:
        df_pairs = pd.DataFrame(pair_rows)
        df_pairs = df_pairs.sort_values(by=["Siege", "Legs Gewonnen"], ascending=False)
        st.dataframe(df_pairs, use_container_width=True, hide_index=True)
    else:
        st.info("Bisher wurden keine Doppel- oder Koop-Matches ausgetragen.")

with tab_session:
    st.subheader("Up & Down Sessions")
    st.write("Aufstieg Richtung B1 und Abstieg Richtung B6.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Gespielte Abende", value=str(len(st.session_state.sessions_list)), delta="gefilterte Sessions")
    with col2:
        st.metric(label="Ø Teilnehmer je Session", value="8", delta="aus Kader")
    with col3:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="Training")
        
    if st.button("➕ Neue Session starten", use_container_width=True, key="tab_session_new"):
        open_new_session_dialog()

    st.write("### Bisherige Sessions & Board-Endstände")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden. Starte über den Button oben eine neue Session.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container(border=True):
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                status_text = " ✅ **[Abgeschlossen]**" if is_session_completed(sess) else ""
                modus_txt = sess.get("modus", "Up & Down")
                boards_txt = sess.get("boards", "4 Boards")
                total_rounds = sess.get("total_rounds", 4)
                
                st.markdown(f"**{sess['id']}** — **{sess['datum']}** (*{modus_txt} · {boards_txt} · {total_rounds} Runden*{gaeste_text}){status_text}")
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("📊 Detaillierter Spielablauf", key=f"sess_arch_{idx}", use_container_width=True):
                        open_session_archive_dialog(idx)
                with col_b2:
                    if not is_session_completed(sess):
                        active_boards_list = get_boards_list(sess, 1)
                        if st.button("🎯 Board-Erfassung öffnen", key=f"sess_board_open_{idx}", use_container_width=True):
                            open_board_dialog(active_boards_list[0], idx)
                st.divider()

with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    st.write("Klicke auf eine Session, um den detaillierten Spielablauf aller Runden einzusehen, oder verwalte/lösche sie bei Bedarf.")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if st.button("➕ Vergangene Session nachtragen", type="primary", use_container_width=True, key="retro_session_main_btn"):
            open_retroactive_session_dialog()
            
    st.write("")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container(border=True):
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                modus_txt = sess.get("modus", "Up & Down")
                boards_txt = sess.get("boards", "4 Boards")
                total_rounds = sess.get("total_rounds", 4)
                st.markdown(f"**{sess['id']}** — {sess['datum']} (*{modus_txt} · {boards_txt} · {total_rounds} Runden*{gaeste_text})")
                
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("📊 Spielablauf ansehen", key=f"arch_view_btn_{idx}", use_container_width=True):
                        open_session_archive_dialog(idx)
                with col_btn2:
                    if st.button("⚡ Schnelldurchlauf", key=f"arch_quick_btn_{idx}", use_container_width=True):
                        open_quick_entry_dialog(idx)
                with col_btn3:
                    if st.button("🗑️ Session löschen", key=f"arch_del_btn_{idx}", use_container_width=True):
                        open_delete_dialog(idx)
                st.divider()
