@st.dialog("Neue Session starten")
def open_new_session_dialog():
    st.write("Einmalig die Rahmenbedingungen festlegen. Die Match-Eingaben nutzen diese Angaben automatisch.")
    
    st.write("### Grunddaten")
    col1, col2 = st.columns(2)
    with col1:
        session_datum = st.date_input("Datum", date.today())
        leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
    with col2:
        spielmodus = st.selectbox("Spielmodus", ["Up & Down", "Liga (4er-Team)"])
        anzahl_boards = st.selectbox("Anzahl der Boards", ["4 Boards", "2 Boards", "3 Boards", "1 Board"])
        
    st.write("### Anwesende Spieler")
    st.caption("Mehrfachauswahl aus dem Kader.")
    
    anwesende = []
    col_a, col_b = st.columns(2)
    half = len(kader) // 2
    with col_a:
        for spieler in kader[:half]:
            if st.checkbox(spieler, value=True, key=f"kader_{spieler}"):
                anwesende.append(spieler)
    with col_b:
        for spieler in kader[half:]:
            if st.checkbox(spieler, value=True, key=f"kader_{spieler}"):
                anwesende.append(spieler)
                
    st.write("### Gastspieler (optional, max. 4)")
    g1 = st.text_input("Gastspieler 1", key="gast_1")
    g2 = st.text_input("Gastspieler 2", key="gast_2")
    g3 = st.text_input("Gastspieler 3", key="gast_3")
    g4 = st.text_input("Gastspieler 4", key="gast_4")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Abbrechen", use_container_width=True):
            st.rerun()
    with col_btn2:
        if st.button("Neue Session starten", type="primary", use_container_width=True):
            gaeste = [x for x in [g1, g2, g3, g4] if x.strip() != ""]
            aktive_spieler_dieser_session = anwesende + gaeste
            
            new_id = f"S-{len(st.session_state.sessions_list) + 1}"
            st.session_state.sessions_list.append({
                "id": new_id,
                "datum": session_datum.strftime("%d.%m.%Y"),
                "modus": spielmodus,
                "boards": anzahl_boards,
                "modus_leg": leg_modus,
                "spieler": aktive_spieler_dieser_session,
                "gaeste": gaeste
            })
            st.success(f"Session für den {session_datum} gestartet!")
            st.rerun()

@st.dialog("Board-Eingabe (Runde für Runde)")
def open_board_dialog(board_name, session_idx):
    current_round = st.session_state.board_rounds[board_name]
    st.write(f"### Erfassung für {board_name} — Runde {current_round} von 4")
    
    # Nutzt nur die Spieler, die für genau diese Session ausgewählt wurden
    verfügbare_spieler = st.session_state.sessions_list[session_idx]["spieler"]
    
    col1, col2 = st.columns(2)
    with col1:
        s1 = st.selectbox("Spieler 1", verfügbare_spieler, key=f"s1_{board_name}_{session_idx}")
    with col2:
        s2 = st.selectbox("Spieler 2", [p for p in verfügbare_spieler if p != s1], key=f"s2_{board_name}_{session_idx}")
        
    ergebnis = st.text_input("Ergebnis (z. B. 3:1)", key=f"res_{board_name}_{session_idx}")
    
    if st.button("Ergebnis speichern", key=f"save_{board_name}_{session_idx}"):
        st.success(f"{board_name} (Runde {current_round}): {s1} vs {s2} [{ergebnis}] gespeichert!")
        if st.session_state.board_rounds[board_name] < 4:
            st.session_state.board_rounds[board_name] += 1
        st.rerun()
