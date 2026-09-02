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

def get_boards_list(boards_count):
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_board_players(session, round_num, board_name):
    boards_count = session.get("boards_count", 6)
    boards = get_boards_list(boards_count)
    if board_name not in boards:
        return ["Offen", "Offen"]
    b_idx = boards.index(board_name)
    
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session["spieler"].copy()
    
    # Automatische Rotation über Trainingstage für Einzel-Startboards
    if round_num == 1 and not in_coop_phase:
        all_sessions = st.session_state.sessions_list
        try:
            s_idx = all_sessions.index(session)
        except:
            s_idx = 0
        if spieler:
            shift = s_idx % len(spieler)
            spieler = spieler[shift:] + spieler[:shift]

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
            teams.append(f"{spieler[-1]} & Offen")
            
        for i in range(0, min(boards_count * 2, len(teams) - len(teams) % 2), 2):
            pairs.append((teams[i], teams[i+1]))
        while len(pairs) <= b_idx:
            t1 = teams[0] if len(teams) > 0 else "Offen"
            t2 = teams[1] if len(teams) > 1 else "Offen"
            pairs.append((t1, t2))
        return list(pairs[b_idx])
    else:
        if round_num == 1:
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
            if match_info and match_info.get("winner"):
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
    
    modus = session.get("modus", "Up & Down")
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = total_rounds - 2 if modus == "Standard-Training (Einzel + Coop)" and total_rounds > 2 else total_rounds
    
    if modus == "Standard-Training (Einzel + Coop)" and next_r == singles_rounds + 1:
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
        for (r, b), v in res.items():
            if r == prev_r and b == rb and v.get("winner"):
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
        completed = [r for (r, b), v in res.items() if b == b_name and v.get("winner")]
        max_r = max(completed) if completed else 0
        if max_r < total_rounds:
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
        total_rounds = 6
        st.info("ℹ️ Standard-Training: 4 Runden Up & Down Einzel + 2 Runden Koop (Hin- und Rückrunde) mit automatischer Partner- und Board-Rotation.")
    else:
        total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=3)
        
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
    
    modi_list = ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)", "Liga (4er-Team)"]
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

    st.write(f"### {board_name} (Session {sess['id']}) — Runde {current_round} von {total_rounds}")
    
    existing_match = res.get((current_round, board_name))
    
    if existing_match:
        current_p1 = existing_match.get("s1", "Offen")
        current_p2 = existing_match.get("s2", "Offen")
        try:
            score1 = int(existing_match.get("ergebnis", "3:0").split(":")[0])
            score2 = int(existing_match.get("ergebnis", "3:0").split(":")[1])
        except:
            score1, score2 = 3, 0
        t1_180 = int(existing_match.get("180_s1", 0))
        t2_180 = int(existing_match.get("180_s2", 0))
        avg1 = float(existing_match.get("avg_s1", 0.0))
        avg2 = float(existing_match.get("avg_s2", 0.0))
    else:
        auto_players = get_board_players(sess, current_round, board_name)
        current_p1, current_p2 = auto_players[0], auto_players[1]
        score1, score2 = 3, 0
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
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="Training")
        
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
            if not match.get("winner"):
                continue
            
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
                            completed_rounds = [r for (r, b), v in res.items() if b == b_name and v.get("winner")]
                            next_r = max(completed_rounds) + 1 if completed_rounds else 1
                            
                            st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                            
                            if next_r <= total_rounds:
                                ready = is_board_ready(curr_sess, b_name, next_r)
                                ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                                st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                                
                                existing_match = res.get((next_r, b_name))
                                if existing_match:
                                    p1 = existing_match.get("s1", "Offen")
                                    p2 = existing_match.get("s2", "Offen")
                                else:
                                    players_now = get_board_players(curr_sess, min(next_r, total_rounds), b_name)
                                    p1, p2 = players_now[0], players_now[1]
                                
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Runde {next_r}/{total_rounds}</p>", unsafe_allow_html=True)
                                
                                sc1, sc2 = st.columns([5, 2])
                                sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p1}</div>", unsafe_allow_html=True)
                                with sc2:
                                    if st.button("🔄 Ändern", key=f"sub_btn1_{b_name}_{next_r}", help="Spieler 1 auswechseln"):
                                        open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r, 1, p1)
                                
                                st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                                
                                sc3, sc4 = st.columns([5, 2])
                                sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                                with sc4:
                                    if st.button("🔄 Ändern", key=f"sub_btn2_{b_name}_{next_r}", help="Spieler 2 auswechseln"):
                                        open_substitution_dialog(b_name, st.session_state.sessions_list.index(curr_sess), next_r, 2, p2)
                                
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
        last_s = st.session_state.sessions_list[0] if st.session_state.sessions_list else None
        
        if last_s:
            l_date = last_s.get('datum', '–')
            l_results = last_s.get('results', {})
            
            kaiser_winner = "Noch offen"
            kaiser_matches = [(r, m) for (r, b), m in l_results.items() if b == "Kaiser B1" and m.get("winner")]
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
                
                if s1_name: count_180s[s1_name] = count_180s.get(s1_name, 0) + c1
                if s2_name: count_180s[s2_name] = count_180s.get(s2_name, 0) + c2
                if a1 > 0: match_avgs.append((s1_name, a1))
                if a2 > 0: match_avgs.append((s2_name, a2))
            
            most_180_text = "Keine"
            if count_180s:
                top_player = max(count_180s, key=count_180s.get)
                if count_180s[top_player] > 0:
                    most_180_text = f"{top_player} ({count_180s[top_player]}x)"
            
            best_avg_text = "–"
            if match_avgs:
                top_avg_player, top_avg_val = max(match_avgs, key=lambda x: x[1])
                best_avg_text = f"{top_avg_player} ({top_avg_val:.1f})"
            
            st.info(f"**Datum:** {l_date}\n\n**Kaiser B1:** 👑 {kaiser_winner}\n\n**Höchster Match-Average:** 📊 {best_avg_text}\n\n**Meiste 180er:** 🎯 {most_180_text}\n\n**Fahrstuhl-Award:** Offen")
        else:
            st.info("**Datum:** –\n\n**Kaiser B1:** Noch offen\n\n**Höchster Match-Average:** –\n\n**Meiste 180er:** –\n\n**Fahrstuhl-Award:** Offen")

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
            
            if s1 in stats:
                stats[s1]["180er"] += h1
                stats[s1]["Legs_Won"] += l1
                stats[s1]["Legs_Lost"] += l2
                if a1 > 0:
                    stats[s1]["Avg_Sum"] += a1
                    stats[s1]["Avg_Count"] += 1
                    sess_avgs.append(a1)
            if s2 in stats:
                stats[s2]["180er"] += h2
                stats[s2]["Legs_Won"] += l2
                stats[s2]["Legs_Lost"] += l1
                if a2 > 0:
                    stats[s2]["Avg_Sum"] += a2
                    stats[s2]["Avg_Count"] += 1
                    sess_avgs.append(a2)
            
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

        if sess_avgs:
            t_avg = sum(sess_avgs) / len(sess_avgs)
            team_session_avgs.append({"Datum": sess.get("datum", "Unbekannt"), "Team-Average": round(t_avg, 1)})

    total_games = total_wins + total_losses
    avg_win_rate = f"{(total_wins / total_games * 100):.0f}%" if total_games > 0 else "0%"

    all_team_avgs = [stats[p]["Avg_Sum"] / stats[p]["Avg_Count"] for p in kader if stats[p]["Avg_Count"] > 0]
    overall_team_avg = f"{(sum(all_team_avgs) / len(all_team_avgs)):.1f}" if all_team_avgs else "–"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
    with col2:
        st.metric(label="Absolvierte Matches", value=str(player_matches_played), delta="aus Sessions")
    with col3:
        st.metric(label="Ø Siegquote", value=avg_win_rate, delta="gesamt")
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

with tab_session:
    st.subheader("Up & Down Sessions")
    st.write("Aufstieg Richtung B1 und Abstieg Richtung B6.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Gespielte Abende", value=str(len(st.session_state.sessions_list)), delta="gefilterte Sessions")
    with col2:
        st.metric(label="Ø Teilnehmer je Session", value="8", delta="aus der Mehrfachauswahl")
    with col3:
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="Training")
        
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
                        completed = [r for (r, b), v in res.items() if b == b_name and v.get("winner")]
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
