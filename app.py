<!-- ... existing code ... -->
                for b_name in singles_boards:
                    p_list = get_board_players(sess, singles_rounds, b_name)
                    m_inf = res.get((singles_rounds, b_name))
                    winner_str = m_inf.get("winner", "–") if m_inf else "–"
                    st.write(f"- **{b_name}:** {p_list[0]} vs {p_list[1]} ➔ **Sieger:** {winner_str}")
                st.divider()
                
    if st.button("Schließen", use_container_width=True):
        st.rerun()

@st.dialog("🏆 Endstand (Zusammenfassung)")
def open_session_summary_dialog(session_idx):
    sess = st.session_state.sessions_list[session_idx]
    st.write(f"### Endstand: Session {sess['id']} vom {sess['datum']}")
    
    res = sess.get("results", {})
    if not res:
        st.info("Für diese Session wurden noch keine Matches erfasst.")
        if st.button("Schließen", use_container_width=True):
            st.rerun()
        return
        
    completed_rounds = [r for (r, b) in res.keys()]
    last_round = max(completed_rounds) if completed_rounds else 1
    
    modus = sess.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    singles_rounds = sess.get("singles_rounds", sess.get("total_rounds", 4))
    
    target_round = last_round
    if is_standard_training and last_round >= singles_rounds:
        st.caption(f"Endstand nach den Einzel-Runden (Runde {singles_rounds}):")
        target_round = singles_rounds
    else:
        st.caption(f"Stand nach der zuletzt gespielten Runde ({target_round}):")
        
    boards_in_r = get_boards_list(sess, target_round)
    for b_name in boards_in_r:
        match_info = res.get((target_round, b_name))
        if match_info and match_info.get("winner") and match_info.get("winner") != "-":
            p1 = match_info.get("winner")
            p2 = match_info.get("loser")
        elif match_info:
            p1 = match_info.get("s1", "-")
            p2 = match_info.get("s2", "-")
        else:
            auto_p = get_board_players(sess, target_round, b_name)
            p1, p2 = auto_p[0], auto_p[1]
            
        with st.container(border=True):
            st.markdown(f"#### {b_name}")
            st.markdown(f"🥇 1. Platz: **{p1}**")
            st.markdown(f"🥈 2. Platz: **{p2}**")
            
    if st.button("Schließen", use_container_width=True):
        st.rerun()

@st.dialog("➕ Neue Session starten")
def open_new_session_dialog():
<!-- ... existing code ... -->
            for idx in sorted_indices:
                sess = st.session_state.sessions_list[idx]
                with st.container(border=True):
                    status_text = "✅ [Abgeschlossen]" if is_session_completed(sess) else "🔴 [Aktiv]"
                    st.markdown(f"**{sess['id']}** — {sess['datum']} {status_text}")
                    
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    with col_btn1:
                        if st.button("📊 Ansehen", key=f"arch_view_{idx}", use_container_width=True):
                            open_session_summary_dialog(idx)
                    with col_btn2:
                        if st.button("⚙️ Bearbeiten", key=f"arch_edit_{idx}", use_container_width=True):
                            open_edit_session_dialog(idx)
                    with col_btn3:
<!-- ... existing code ... -->
