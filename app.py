# ... existing code ...
        with col_btn2:
            if st.button("Schließen", use_container_width=True, key=f"d_close_{board_name}_{session_idx}"):
                st.rerun()

@st.dialog("⚠️ Session löschen")
def confirm_delete_session(session_idx):
    sess = st.session_state.sessions_list[session_idx]
    st.warning(f"Möchtest du die Session **{sess['id']} vom {sess['datum']}** wirklich unwiderruflich löschen?")
    pwd = st.text_input("Admin-Passwort", type="password", key=f"del_sess_pwd_{session_idx}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Abbrechen", use_container_width=True, key=f"cancel_del_sess_{session_idx}"):
            st.rerun()
    with col2:
        if st.button("🗑️ Ja, endgültig löschen", type="primary", use_container_width=True, key=f"confirm_del_sess_{session_idx}"):
            if pwd == "1521":
                st.session_state.sessions_list.pop(session_idx)
                smart_sync_and_save(st.session_state.sessions_list)
                st.success("Session gelöscht!")
                st.rerun()
            elif pwd != "":
                st.error("Falsches Passwort!")

with tab_übersicht:
    col_btn1, col_btn2 = st.columns(2)
# ... existing code ...
with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    st.write("Die neueste Session steht hier immer ganz oben.")
    
    if not st.session_state.sessions_list:
# ... existing code ...
            with st.container(border=True):
                status_text = "✅ [Abgeschlossen]" if is_session_completed(sess) else "🔴 [Aktiv]"
                st.markdown(f"**{sess['id']}** — {sess['datum']} {status_text}")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("📊 Ansehen", key=f"arch_view_{idx}", use_container_width=True):
                        open_session_archive_dialog(idx)
                with col_btn2:
                    if st.button("🗑️ Löschen", key=f"arch_del_{idx}", use_container_width=True):
                        confirm_delete_session(idx)
                        
                st.divider()
                
                # --- BLITZEINTRAG & KORREKTUR ---
# ... existing code ...
