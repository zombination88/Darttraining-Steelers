import streamlit as st
import pandas as pd
from datetime import date
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

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

def smart_sync_and_save(updated_sessions):
    fresh_data = load_data()
    if fresh_data:
        existing_ids = {s["id"] for s in fresh_data}
        for sess in updated_sessions:
            if sess["id"] not in existing_ids:
                fresh_data.append(sess)
            else:
                for idx, fs in enumerate(fresh_data):
                    if fs["id"] == sess["id"]:
                        fresh_data[idx] = sess
        save_data(fresh_data)
        st.session_state.sessions_list = fresh_data
    else:
        save_data(updated_sessions)
        st.session_state.sessions_list = updated_sessions

st.markdown("<h1 style='text-align: center; margin: 0; padding-top: 8px; font-size: 1.8rem;'>Wehringer Steelers</h1>", unsafe_allow_html=True)

c_mus, c_sync, c_dummy = st.columns([1, 1, 4])
with c_mus:
    try:
        with st.popover("🎵"):
            st.audio("vereinssong.mp3")
    except Exception:
        pass
with c_sync:
    if st.button("🔄", help="Aktualisieren"):
        st.session_state.sessions_list = load_data()
        st.rerun()

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

tab_übersicht, tab_kader, tab_session, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv", "Modus & Regeln"])

def get_boards_list(session, round_num=None):
    boards_count = session.get("boards_count", 6)
    modus = session.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num is not None and round_num > singles_rounds
    
    if in_coop_phase:
        return ["Kaiser B1", "Board 2"]
        
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_board_players(session, round_num, board_name):
    boards = get_boards_list(session, round_num)
    if board_name not in boards:
        return ["-", "-"]
    b_idx = boards.index(board_name)
    
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session["spieler"].copy()
    
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
        else:
            chrono_s_idx = len(all_sessions) - 1 - s_idx
            if spieler:
                shift = (chrono_s_idx * 2) % len(spieler)
                spieler = spieler[shift:] + spieler[:shift]

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
            
        pairs = []
        coop_boards_cnt = 2
        for i in range(0, min(coop_boards_cnt * 2, len(teams) - len(teams) % 2), 2):
            pairs.append((teams[i], teams[i+1]))
        while len(pairs) <= b_idx:
            t1 = teams[0] if len(teams) > 0 else "-"
            t2 = teams[1] if len(teams) > 1 else "-"
            pairs.append((t1, t2))
        return list(pairs[b_idx])
    else:
        boards_count = session.get("boards_count", 6)
        pairs = []
        if round_num == 1:
            for i in range(0, min(boards_count * 2, len(spieler) - len(spieler) % 2), 2):
                pairs.append((spieler[i], spieler[i+1]))
            while len(pairs) <= b_idx:
                pairs.append((spieler[0] if spieler else "-", spieler[1] if len(spieler) > 1 else "-"))
            
            if len(spieler) % 2 != 0:
                pairs[-1] = (spieler[-1], "-")

            return list(pairs[b_idx])
        
        # Für Folgerunden (> 1): Up & Down Berechnung inklusive Verlierer vom letzten Board kriegt Freilos (-)
        prev_r = round_num - 1
        res = session.get("results", {})
        prev_boards = get_boards_list(session, prev_r)
        
        winners = []
        losers = []
        for pb in prev_boards:
            match_info = res.get((prev_r, pb))
            if match_info:
                w = match_info.get("winner", "-")
                l = match_info.get("loser", "-")
                winners.append(w)
                losers.append(l)
            else:
                p_pair = get_board_players(session, prev_r, pb)
                winners.append(p_pair[0])
                losers.append(p_pair[1])
                
        active_winners = [w for w in winners if w != "-"]
        active_losers = [l for l in losers if l != "-"]
        
        freilos_player = None
        if len(losers) > 0 and losers[-1] != "-":
            freilos_player = losers[-1]
            active_losers = [l for l in losers[:-1] if l != "-"]
            
        combined = active_winners + active_losers
        if freilos_player:
            combined.append(freilos_player)
            
        all_pairs = []
        i = 0
        while i < len(combined):
            p1 = combined[i]
            p2 = combined[i+1] if i + 1 < len(combined) else "-"
            all_pairs.append((p1, p2))
            i += 2
            
        while len(all_pairs) <= b_idx:
            all_pairs.append(("-", "-"))
            
        return list(all_pairs[b_idx])

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
                
            smart_sync_and_save(st.session_state.sessions_list)
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
            if is_standard_training and r > singles_rounds:
                r_display = f"Doppelrunde {r - singles_rounds}/{total_rounds - singles_rounds} (Coop)"
            else:
                r_display = f"Runde {r}/{singles_rounds} (Einzel)" if is_standard_training else f"Runde {r}/{total_rounds}"
                
            st.markdown(f"#### 🎯 {r_display}")
            boards_in_r = get_boards_list(sess, r)
            for b_name in boards_in_r:
                match_info = res.get((r, b_name))
                if match_info:
                    heim = match_info.get("s1", "–")
                    gast = match_info.get("s2", "–")
                    ergebnis = match_info.get("ergebnis", "–")
                    sieger = match_info.get("winner", "-")
                    t180 = f"{match_info.get('180_s1', 0)} / {match_info.get('180_s2', 0)}"
                    avg = f"{match_info.get('avg_s1', 0.0)} / {match_info.get('avg_s2', 0.0)}"
                else:
                    auto_p = get_board_players(sess, r, b_name)
                    heim, gast = auto_p[0], auto_p[1]
                    ergebnis, sieger, t180, avg = "Ausstehend", "–", "–", "–"
            
                with st.container(border=True):
                    st.markdown(f"**{b_name}**")
                    st.caption(f"⚔️ {heim} vs {gast}")
                    st.markdown(f"Ergebnis: **{ergebnis}** | Sieger: **{sieger}**")
                    st.caption(f"🎯 180er: {t180} | 📊 Avg: {avg}")
            
            if is_standard_training and r == singles_rounds:
                st.markdown("##### 🏆 Board-Endstand nach den Einzel-Runden:")
                singles_boards = get_boards_list(sess, singles_rounds)
                for b_name in singles_boards:
                    p_list = get_board_players(sess, singles_rounds, b_name)
                    m_inf = res.get((singles_rounds, b_name))
                    winner_str = m_inf.get("winner", "–") if m_inf else "–"
                    st.write(f"- **{b_name}:** {p_list[0]} vs {p_list[1]} ➔ **Sieger:** {winner_str}")
                st.divider()
                
    if st.button("Schließen", use_container_width=True):
        st.rerun()

@st.dialog("➕ Neue Session starten")
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
        st.info(f"ℹ️ Standard-Training: {singles_rounds} Runden Einzel + {coop_rounds} Runden Doppel (Coop).")
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
            smart_sync_and_save(st.session_state.sessions_list)
            st.success("Session erfolgreich gestartet!")
            st.rerun()

@st.dialog("⚙️ Session bearbeiten")
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
            smart_sync_and_save(st.session_state.sessions_list)
            st.success("Session erfolgreich aktualisiert!")
            st.rerun()

@st.dialog("📋 Board-Erfassung & Tracking")
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
    
    if is_standard_training and current_round > singles_rounds:
        r_display = f"Doppelrunde {current_round - singles_rounds}/{total_rounds - singles_rounds} (Coop)"
    else:
        r_display = f"Runde {current_round}/{singles_rounds} (Einzel)" if is_standard_training else f"Runde {current_round}/{total_rounds}"

    st.write(f"### {board_name} — {r_display}")
    
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
        in_score1 = st.number_input(f"Legs Heim", min_value=0, max_value=5, value=score1, key=f"d_score1_{board_name}_{session_idx}")
        in_180_1 = st.number_input(f"🎯 180er Heim", min_value=0, max_value=20, value=t1_180, key=f"d_180_1_{board_name}_{session_idx}")
        in_avg_1 = st.number_input(f"📊 Avg Heim", min_value=0.0, max_value=180.0, value=avg1, step=0.1, key=f"d_avg_1_{board_name}_{session_idx}")
        
    with col2:
        st.markdown(f"**Gast:** `{current_p2}`")
        in_score2 = st.number_input(f"Legs Gast", min_value=0, max_value=5, value=score2, key=f"d_score2_{board_name}_{session_idx}")
        in_180_2 = st.number_input(f"🎯 180er Gast", min_value=0, max_value=20, value=t2_180, key=f"d_180_2_{board_name}_{session_idx}")
        in_avg_2 = st.number_input(f"📊 Avg Gast", min_value=0.0, max_value=180.0, value=avg2, step=0.1, key=f"d_avg_2_{board_name}_{session_idx}")
        
    ergebnis = f"{in_score1}:{in_score2}"
    winner = current_p1 if in_score1 > in_score2 else (current_p2 if in_score2 > in_score1 else "-")
    loser = current_p2 if winner == current_p1 else (current_p1 if winner == current_p2 else "-")
    
    st.info(f"📊 Ergebnis: **{ergebnis}** | 🏆 Sieger: **{winner if winner != '-' else 'Unentschieden'}**")
    
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
                smart_sync_and_save(st.session_state.sessions_list)
                st.success("Ergebnis und Statistiken erfolgreich gespeichert!")
                st.rerun()
    with col_btn2:
        if st.button("Schließen", use_container_width=True, key=f"d_close_{board_name}_{session_idx}"):
            st.rerun()

with tab_übersicht:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Neue Session", type="primary", use_container_width=True, key="quick_start_btn"):
            open_new_session_dialog()
    with col_btn2:
        active_sessions_for_btn = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
        if active_sessions_for_btn:
            if st.button("⚙️ Bearbeiten", use_container_width=True, key="edit_active_btn"):
                open_edit_session_dialog(st.session_state.sessions_list.index(active_sessions_for_btn[0]))
        else:
            st.button("⚙️ Bearbeiten", use_container_width=True, disabled=True)
            
    st.write("")
    
    # 1. LAUFENDE SESSION GANZ OBEN
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
        active_boards_list = get_boards_list(curr_sess, 1)
        
        for b_name in active_boards_list:
            completed_r_for_board = [r for (r, b), v in res.items() if b == b_name and v.get("winner")]
            next_r_for_board = max(completed_r_for_board) + 1 if completed_r_for_board else 1
            
            with st.container(border=True):
                st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                
                if next_r_for_board <= total_rounds:
                    ready = is_board_ready(curr_sess, b_name, next_r_for_board)
                    ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                    st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                    
                    existing_match = res.get((next_r_for_board, b_name))
                    if existing_match:
                        p1 = existing_match.get("s1", "-")
                        p2 = existing_match.get("s2", "-")
                    else:
                        players_now = get_board_players(curr_sess, next_r_for_board, b_name)
                        p1, p2 = players_now[0], players_now[1]
                    
                    if is_standard_training and next_r_for_board > singles_rounds:
                        r_head_board = f"Doppelrunde {next_r_for_board - singles_rounds}/{total_rounds - singles_rounds} (Coop)"
                    else:
                        r_head_board = f"Runde {next_r_for_board}/{singles_rounds} (Einzel)" if is_standard_training else f"Runde {next_r_for_board}/{total_rounds}"
                    
                    st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>{r_head_board}</p>", unsafe_allow_html=True)
                    
                    sc1, sc2 = st.columns([5, 2])
                    sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p1}</div>", unsafe_allow_html=True)
                    with sc2:
                        if st.button("🔄", key=f"sub1_{b_name}_{next_r_for_board}", help="Wechsel"):
                            open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r_for_board, 1, p1)
                    
                    st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                    
                    sc3, sc4 = st.columns([5, 2])
                    sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                    with sc4:
                        if st.button("🔄", key=f"sub2_{b_name}_{next_r_for_board}", help="Wechsel"):
                            open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r_for_board, 2, p2)
                    
                    st.write("")
                    if st.button("🎯 Eintragen", key=f"live_{b_name}_{next_r_for_board}", use_container_width=True, disabled=not ready):
                        open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess))
                else:
                    st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle Runden beendet</p>", unsafe_allow_html=True)
                    st.success("✅ Abgeschlossen")

    st.write("")
    st.divider()

    # 2. ALLGEMEINE STATISTIKEN DARUNTER
    st.markdown("### 📊 Allgemeine Statistiken")
    
    total_180s = 0
    kaiser_winner_text = "Noch offen"
    anwesende_count = 0
    
    display_sess = None
    for s in st.session_state.sessions_list:
        if is_session_completed(s) or s.get("results"):
            display_sess = s
            break
    if not display_sess and st.session_state.sessions_list:
        display_sess = st.session_state.sessions_list[0]

    for sess in st.session_state.sessions_list:
        for match in sess.get("results", {}).values():
            s1_name = match.get("s1", "")
            s2_name = match.get("s2", "")
            if s1_name and " & " not in s1_name: total_180s += int(match.get("180_s1", 0))
            if s2_name and " & " not in s2_name: total_180s += int(match.get("180_s2", 0))

    if display_sess:
        l_results = display_sess.get("results", {})
        kaiser_matches = [(r, m) for (r, b), m in l_results.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
        if kaiser_matches:
            kaiser_matches.sort(key=lambda x: x[0], reverse=True)
            kaiser_winner_text = kaiser_matches[0][1].get("winner")
        
        anwesende_count = len([p for p in display_sess.get("spieler", []) if p != "-"])

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1: st.metric(label="Sessions", value=str(len(st.session_state.sessions_list)), delta="gesamt")
        with c2: st.metric(label="Team 180er", value=str(total_180s), delta="geworfen")
        st.divider()
        c3, c4 = st.columns(2)
        with c3: st.metric(label="Aktueller Kaiser", value=kaiser_winner_text[:12] + "..." if len(kaiser_winner_text) > 12 else kaiser_winner_text, delta="Board 1")
        with c4: st.metric(label="Anwesende", value=str(anwesende_count), delta="Spieler")
        
    st.write("")
    with st.expander("Letzte Session & Spitzenreiter", expanded=False):
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### Letzte Session")
            if display_sess:
                l_date = display_sess.get('datum', '–')
                count_180s = {}
                match_avgs = []
                for m in display_sess.get('results', {}).values():
                    s1_name = m.get("s1", "")
                    s2_name = m.get("s2", "")
                    if s1_name and " & " not in s1_name:
                        count_180s[s1_name] = count_180s.get(s1_name, 0) + int(m.get("180_s1", 0))
                        if float(m.get("avg_s1", 0)) > 0: match_avgs.append((s1_name, float(m.get("avg_s1", 0))))
                    if s2_name and " & " not in s2_name:
                        count_180s[s2_name] = count_180s.get(s2_name, 0) + int(m.get("180_s2", 0))
                        if float(m.get("avg_s2", 0)) > 0: match_avgs.append((s2_name, float(m.get("avg_s2", 0))))
                
                most_180_text = "Keine"
                if count_180s and max(count_180s.values()) > 0:
                    top_player = max(count_180s, key=count_180s.get)
                    most_180_text = f"{top_player} ({count_180s[top_player]}x)"
                
                best_avg_text = "–"
                if match_avgs:
                    top_avg_player, top_avg_val = max(match_avgs, key=lambda x: x[1])
                    best_avg_text = f"{top_avg_player} ({top_avg_val:.1f})"
                
                st.info(f"**Datum:** {l_date}\n\n**Kaiser B1 (Einzel):** 👑 {kaiser_winner_text}\n\n**Höchster Einzel-Average:** 📊 {best_avg_text}\n\n**Meiste 180er:** 🎯 {most_180_text}")
            else:
                st.info("Keine Daten vorhanden.")

        with col_r:
            st.markdown("### Spitzenreiter")
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

    with st.expander("Zuletzt ausgetragene Board-Matches", expanded=False):
        all_matches = []
        for sess in st.session_state.sessions_list:
            sess_date = sess.get("datum", "")
            for (round_num, board_name), m_info in sess.get("results", {}).items():
                if not m_info.get("winner"): continue
                all_matches.append({
                    "Datum": sess_date, "Runde": round_num, "Board": board_name,
                    "Spieler": f"{m_info['s1']} vs {m_info['s2']}",
                    "Ergebnis": m_info['ergebnis'], "Sieger": m_info['winner']
                })
                
        if all_matches:
            for m in reversed(all_matches):
                with st.container(border=True):
                    st.markdown(f"**{m['Datum']} - {m['Board']}** (Runde {m['Runde']})")
                    st.caption(f"⚔️ {m['Spieler']}")
                    st.markdown(f"Ergebnis: {m['Ergebnis']} | Sieger: **{m['Sieger']}**")
        else:
            st.info("Bisher wurden keine Board-Matches ausgetragen.")

with tab_kader:
    st.subheader("Kader & Spielerbilanz")
    st.write("Live berechnete Bilanz des festen Stammkaders.")
    
    stats = {p: {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0} for p in kader}
    player_matches_played = 0
    total_wins = 0
    total_losses = 0
    
    for sess in st.session_state.sessions_list:
        for match in sess.get("results", {}).values():
            winner = match.get("winner", "")
            loser = match.get("loser", "")
            s1 = match.get("s1", "")
            s2 = match.get("s2", "")
            ergebnis = match.get("ergebnis", "0:0")
            
            try: l1, l2 = map(int, ergebnis.split(":"))
            except ValueError: l1, l2 = 0, 0
                
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
            if s2 in stats and " & " not in s2:
                stats[s2]["180er"] += h2
                stats[s2]["Legs_Won"] += l2
                stats[s2]["Legs_Lost"] += l1
                if a2 > 0:
                    stats[s2]["Avg_Sum"] += a2
                    stats[s2]["Avg_Count"] += 1
            
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

    total_games = total_wins + total_losses
    avg_win_rate = f"{(total_wins / total_games * 100):.0f}%" if total_games > 0 else "0%"

    all_team_avgs = [stats[p]["Avg_Sum"] / stats[p]["Avg_Count"] for p in kader if stats[p]["Avg_Count"] > 0]
    overall_team_avg = f"{(sum(all_team_avgs) / len(all_team_avgs)):.1f}" if all_team_avgs else "–"

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1: st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
        with c2: st.metric(label="Matches", value=str(player_matches_played), delta="aus Sessions")
        st.divider()
        c3, c4 = st.columns(2)
        with c3: st.metric(label="Ø Siegquote", value=avg_win_rate, delta="gesamt")
        with c4: st.metric(label="Team Average", value=overall_team_avg, delta="Ø Gesamt")
        
    st.write("### Spielerübersicht & Rangliste")
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
            "Spieler": p, "Matches": m, "Siege": s, "Niederlagen": n,
            "Siegquote": quote, "Legs Gewonnen": lw, "Legs Verloren": lv,
            "🎯 180er": t180, "📊 Ø Average": avg_val
        })
        
    sorted_rows = sorted(table_rows, key=lambda x: (x["Siege"], x["Legs Gewonnen"]), reverse=True)
    for row in sorted_rows:
        with st.container(border=True):
            st.markdown(f"**{row['Spieler']}** — Quote: **{row['Siegquote']}**")
            st.caption(f"🏆 Siege: {row['Siege']}/{row['Matches']} | 📊 Avg: {row['📊 Ø Average']} | 🎯 180er: {row['🎯 180er']} | Legs: {row['Legs Gewonnen']}:{row['Legs Verloren']}")

    with st.expander("🤝 Doppel-Paarungen (Coop-Statistik)", expanded=False):
        pair_stats = {}
        for sess in st.session_state.sessions_list:
            for match in sess.get("results", {}).values():
                winner = match.get("winner", "")
                s1 = match.get("s1", "")
                s2 = match.get("s2", "")
                try: l1, l2 = map(int, match.get("ergebnis", "0:0").split(":"))
                except: l1, l2 = 0, 0
                
                h1, h2 = int(match.get("180_s1", 0)), int(match.get("180_s2", 0))
                a1, a2 = float(match.get("avg_s1", 0.0)), float(match.get("avg_s2", 0.0))
                
                def process_pair(pair_str, is_won, won_legs, lost_legs, h_count, avg_val):
                    if " & " in pair_str:
                        p_members = sorted([p.strip() for p in pair_str.split("&")])
                        pair_key = " & ".join(p_members)
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

                if " & " in s1: process_pair(s1, (winner == s1), l1, l2, h1, a1)
                if " & " in s2: process_pair(s2, (winner == s2), l2, l1, h2, a2)

        pair_rows = []
        for pair_name, p_data in pair_stats.items():
            m = p_data["Matches"]
            s = p_data["Siege"]
            n = p_data["Niederlagen"]
            quote = f"{(s / m * 100):.0f}%" if m > 0 else "0%"
            acount = p_data["Avg_Count"]
            avg_val = f"{(p_data['Avg_Sum'] / acount):.1f}" if acount > 0 else "–"
            pair_rows.append({
                "Doppel-Team": pair_name, "Matches": m, "Siege": s, "Niederlagen": n,
                "Siegquote": quote, "Legs Gewonnen": p_data["Legs_Won"], "Legs Verloren": p_data["Legs_Lost"],
                "🎯 180er": p_data["180er"], "📊 Ø Average": avg_val
            })
            
        if pair_rows:
            sorted_pairs = sorted(pair_rows, key=lambda x: (x["Siege"], x["Legs Gewonnen"]), reverse=True)
            for row in sorted_pairs:
                with st.container(border=True):
                    st.markdown(f"**{row['Doppel-Team']}** — Quote: **{row['Siegquote']}**")
                    st.caption(f"🏆 Siege: {row['Siege']}/{row['Matches']} | 📊 Avg: {row['📊 Ø Average']} | 🎯 180er: {row['🎯 180er']} | Legs: {row['Legs Gewonnen']}:{row['Legs Verloren']}")
        else:
            st.info("Bisher wurden keine Doppel- oder Koop-Matches ausgetragen.")

with tab_session:
    st.subheader("Up & Down Sessions")
    st.write("Aufstieg Richtung B1 und Abstieg Richtung B6.")
    
    total_anwesende = 0
    for s in st.session_state.sessions_list:
        total_anwesende += len([p for p in s.get("spieler", []) if p != "-"])
    avg_anwesende = f"{(total_anwesende / len(st.session_state.sessions_list)):.1f}" if st.session_state.sessions_list else "0"
    
    kaiser_count = {}
    for sess in st.session_state.sessions_list:
        l_res = sess.get("results", {})
        k_matches = [(r, m) for (r, b), m in l_res.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "")]
        if k_matches:
            k_matches.sort(key=lambda x: x[0], reverse=True)
            w = k_matches[0][1].get("winner")
            if w and w != "-": kaiser_count[w] = kaiser_count.get(w, 0) + 1
            
    rekord_kaiser = max(kaiser_count, key=kaiser_count.get) if kaiser_count else "Noch offen"
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1: st.metric("Gespielte Abende", str(len(st.session_state.sessions_list)))
        with c2: st.metric("Ø Anwesende", avg_anwesende, "Spieler")
        st.divider()
        st.metric("Rekord-Kaiser", rekord_kaiser, "Meiste Board 1 Siege")
        
    if st.button("➕ Neue Session starten", use_container_width=True, key="tab_session_new"):
        open_new_session_dialog()

    st.write("### Bisherige Sessions & Board-Endstände")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container(border=True):
                gaeste_text = f" | Gäste: {', '.join(sess['gaeste'])}" if sess.get('gaeste') else ""
                status_text = " ✅ **[Abgeschlossen]**" if is_session_completed(sess) else ""
                total_rounds = sess.get("total_rounds", 4)
                st.markdown(f"**{sess['datum']}** — *{sess['modus']} · {sess['boards']} · {total_rounds} Runden · {sess['id']}{gaeste_text}*{status_text}")
                
                if st.button("📊 Spielablauf ansehen", key=f"sess_view_{idx}", use_container_width=True):
                    open_session_archive_dialog(idx)

with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    
    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        for idx, sess in enumerate(st.session_state.sessions_list):
            with st.container(border=True):
                status_text = "✅ [Abgeschlossen]" if is_session_completed(sess) else "🔴 [Aktiv]"
                st.markdown(f"**{sess['id']}** — {sess['datum']} {status_text}")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("📊 Ansehen", key=f"arch_view_{idx}", use_container_width=True):
                        open_session_archive_dialog(idx)
                with col_btn2:
                    if st.button("🗑️ Löschen", key=f"arch_del_{idx}", use_container_width=True):
                        st.session_state.sessions_list.pop(idx)
                        smart_sync_and_save(st.session_state.sessions_list)
                        st.success("Session gelöscht!")
                        st.rerun()

with tab_regeln:
    st.subheader("🎯 Modus & Regeln")
    st.write("Hier findet ihr die Anleitung für den Trainingsabend, den Auf- und Abstieg sowie die Board-Verteilung.")
    
    with st.container(border=True):
        st.markdown("### 👑 Das Prinzip: 'Up & Down'")
        st.markdown("""
        * **Kaiser B1 ist das Top-Board:** Wer hier gewinnt, bleibt König (Kaiser) oder steigt auf. Wer verliert, wandert ein Board nach unten.
        * **Das untere Board:** Wer hier gewinnt, steigt ein Board nach oben. Wer verliert, wandert nach ganz unten (Richtung B1).
        """)
        
    with st.container(border=True):
        st.markdown("### 🚦 Die Ampel-Anzeige")
        st.markdown("""
        * 🟢 **Spielbar:** Euer Match steht fest – ihr könnt sofort loslegen und eintragen!
        * 🔴 **Wartet:** Ihr müsst noch kurz warten, bis die Spieler von den Nachbarboards fertig sind (da sich der Auf- und Absteiger erst entscheidet).
        """)

    with st.container(border=True):
        st.markdown("### ⏱️ Der Ablauf an eurem Board")
        st.markdown("""
        1. **Ergebnis eintragen:** Sobald euer Match vorbei ist, tippt am Handy auf **🎯 Eintragen**, tragt das Leg-Ergebnis ein (z. B. 3:1) und speichert ab.
        2. **Automatische Weiterleitung:** Der Gewinner steigt automatisch eine Etage höher (oder bleibt Kaiser auf B1), der Verlierer rutscht eine Etage tiefer.
        3. **Nächste Runde:** Sobald *alle* Boards ihre Ergebnisse eingetragen haben, schaltet die App vollautomatisch in die nächste Runde und setzt die neuen Paarungen zusammen.
        """)

    with st.container(border=True):
        st.markdown("### 👥 Was passiert bei ungerader Spieleranzahl?")
        st.markdown("""
        * Wenn wir z. B. zu neunt auf 4 Boards spielen, bekommt auf dem allerletzten Board (Board 4) der Verlierer in der nächsten Runde die Pause (er landet sozusagen auf dem Abstellgleis / kriegt das `-` als Gegner).
        * Der Spieler, der zuvor in der Pause war / auf den Einsatz gewartet hat, steigt stattdessen auf Board 4 auf und spielt dort gegen den Verlierer von Board 3.
        * Dadurch wechselt sich die Pause von Runde zu Runde automatisch ab, und das System hält exakt die richtige Reihenfolge ein!
        """)

    with st.container(border=True):
        st.markdown("### 📋 Wie werden die Spieler für eine *neue* Session aufgestellt?")
        st.markdown("""
        * **Auswertung der Vorsession:** Für die 1. Runde einer neuen Session schaut das System nach, wie die Spieler am Ende der *letzten* Session platziert waren.
        * **Bottom-to-Top Reihenfolge:** Die Spieler werden anhand des letzten Endstands von unten nach oben eingeteilt (wer am Ende ganz unten war, fängt in Runde 1 oben an, neue Spieler werden vorne einsortiert). 
        * **Vollautomatisch:** Ihr müsst euch um die Aufstellung zu Beginn des Abends keine Gedanken machen – das System setzt sich beim Starten einer neuen Session selbstständig zusammen!
        """)
