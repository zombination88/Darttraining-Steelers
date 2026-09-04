<!-- ... existing code ... -->
    pdf_out.seek(0)
    return pdf_out

@st.dialog("➕ Neues Freundschaftsspiel starten", width="large")
def open_new_liga_match_dialog():
    st.write("Erstelle hier ein neues Freundschaftsspiel.")
    c1, c2 = st.columns(2)
    session_datum = c1.date_input("Datum des Spiels", date.today())
    heim_team = c2.text_input("Heimmannschaft", value="Wehringer Steelers")
    gast_team = st.text_input("Gastmannschaft", placeholder="z.B. DC Irgendwas")
    
    spiel_typ = st.radio("Welchen Modus möchtet ihr spielen?", [
        "🏆 Standard Liga-Spiel (exakt 4 Spieler, 2 Boards)",
        "⚙️ Freies Spiel auf Liga-Basis (flexible Spieler & Boards)"
    ])

    if "Standard" in spiel_typ:
        team_size = 4
        b_count = 2
        st.info("Klassischer Liga-Modus: 4 Einzel, 4 Kreuz, 2 Doppel auf genau 2 Boards.")
    else:
        c3, c4 = st.columns(2)
        ts_sel = c3.selectbox("Spieler pro Team", ["4 Spieler (4 Einzel, 4 Kreuz, 2 Doppel)", "6 Spieler (6 Einzel, 6 Kreuz, 3 Doppel)"])
        team_size = int(ts_sel.split()[0])
        b_count = c4.selectbox("Anzahl paralleler Boards", [1, 2, 3, 4, 5, 6], index=(1 if team_size==4 else 2))
        st.info(f"Es spielen {team_size} gegen {team_size} Spieler. Die Matches werden auf {b_count} Board(s) aufgeteilt.")
    
    st.write("Wähle die Boards aus (von links nach rechts):")
    board_options = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    selected_boards = []
    cols = st.columns(min(b_count, 4))
    for i in range(b_count):
        with cols[i % len(cols)]:
            default_idx = i if i < len(board_options) else 0
            b_sel = st.selectbox(f"Board {i+1}", board_options, index=default_idx, key=f"liga_b_sel_{i}")
            selected_boards.append(b_sel)
<!-- ... existing code ... -->
            st.session_state.sessions_list.append(new_session)
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("⚙️ Freundschaftsspiel bearbeiten")
def open_edit_liga_session_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"edit_pwd_{session_idx}")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return
    
    sess = liga_sessions[session_idx]
    real_idx = st.session_state.sessions_list.index(sess)
    
    try: curr_date = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except: curr_date = date.today()
    
    session_datum = st.date_input("Datum", curr_date)
    heim_team = st.text_input("Heimmannschaft", value=sess.get("heim_team", ""))
    gast_team = st.text_input("Gastmannschaft", value=sess.get("gast_team", ""))
    
    curr_boards = sess.get("liga_boards", ["Kaiser B1", "Board 2"])
    b_count_curr = sess.get("boards_count", len(curr_boards))
    
    b_count = st.selectbox("Anzahl paralleler Boards", [1, 2, 3, 4, 5, 6], index=max(0, b_count_curr-1))
    
    board_options = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    new_boards = []
    cols = st.columns(min(b_count, 4))
    for i in range(b_count):
        with cols[i % len(cols)]:
            curr_val = curr_boards[i] if i < len(curr_boards) else board_options[i]
            b_sel = st.selectbox(f"Board {i+1}", board_options, index=board_options.index(curr_val) if curr_val in board_options else 0, key=f"edit_liga_b_{session_idx}_{i}")
            new_boards.append(b_sel)
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c_btn2:
        if st.button("Speichern", type="primary", use_container_width=True):
            sess.update({
                "datum": session_datum.strftime("%d.%m.%Y"),
                "heim_team": heim_team.strip(),
                "gast_team": gast_team.strip(),
                "boards_count": b_count,
                "liga_boards": new_boards
            })
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🔒 Einzel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_einzel(session_idx, is_heim):
    sess = liga_sessions[session_idx]
    real_idx = st.session_state.sessions_list.index(sess)
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    t_size = sess.get("team_size", 4)
    st.write(f"### Aufstellung: {team_name}")
    st.info(f"Trage hier die {t_size} Einzelspieler als Text ein.")
    
    inputs = []
    for i in range(t_size):
        inputs.append(st.text_input(f"Position {i+1}", key=f"auf_{is_heim}_{i}"))
        
    if st.button("Speichern", type="primary", use_container_width=True):
        if all(x.strip() for x in inputs):
            update_dict = {}
            for i, val in enumerate(inputs):
                key = f"h{i+1}" if is_heim else f"g{i+1}"
                update_dict[key] = val.strip()
            if is_heim:
                sess["auf_heim"].update(update_dict)
            else:
                sess["auf_gast"].update(update_dict)
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
        else:
            st.error(f"Bitte alle {t_size} Positionen eintragen!")

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_idx, is_heim):
