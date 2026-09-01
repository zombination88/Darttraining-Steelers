@st.dialog("Board-Eingabe (Runde für Runde)")
def open_board_dialog(board_name, session_idx):
    sess = st.session_state.sessions_list[session_idx]
    
    res = sess.get("results", {})
    completed_rounds = [r for (r, b) in res.keys() if b == board_name]
    current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > 4:
        st.write(f"### {board_name} ist bereits beendet (alle 4 Runden gespielt).")
        if st.button("Schließen"):
            st.rerun()
        return

    st.write(f"### Erfassung für {board_name} — Runde {current_round} von 4")
    
    auto_players = get_board_players(sess, current_round, board_name)
    verfügbare_spieler = sess.get("spieler", kader)
    
    col1, col2 = st.columns(2)
    with col1:
        default_s1_idx = verfügbare_spieler.index(auto_players[0]) if auto_players[0] in verfügbare_spieler else 0
        s1 = st.selectbox("Spieler 1", verfügbare_spieler, index=default_s1_idx, key=f"d_s1_{board_name}_{session_idx}_{current_round}")
    with col2:
        remaining = [p for p in verfügbare_spieler if p != s1]
        default_s2_idx = remaining.index(auto_players[1]) if auto_players[1] in remaining else 0
        s2 = st.selectbox("Spieler 2", remaining, index=default_s2_idx if remaining else 0, key=f"d_s2_{board_name}_{session_idx}_{current_round}")
        
    ergebnis = st.text_input("Ergebnis (z. B. 3:1)", key=f"d_res_{board_name}_{session_idx}_{current_round}")
    
    # Automatische Gewinner-Ermittlung
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
    
    if st.button("Ergebnis speichern", key=f"d_save_{board_name}_{session_idx}_{current_round}"):
        if not winner:
            st.error("Bitte ein gültiges Ergebnis eingeben, damit der Sieger ermittelt werden kann.")
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
            st.success(f"{board_name} (Runde {current_round}): {s1} vs {s2} [{ergebnis}] gespeichert! Sieger: {winner}")
            if st.session_state.board_rounds[board_name] < 4:
                st.session_state.board_rounds[board_name] += 1
            st.rerun()
