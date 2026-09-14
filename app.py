# ... existing code ...
                delete_session(session_id)
                st.success("Session wurde erfolgreich gelöscht!")
                st.rerun()
            else: st.error("Falsches Passwort!")

@st.dialog("📋 Board-Erfassung & Tracking")
def open_board_dialog(board_name, session_id, edit_round=None):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    
    if edit_round:
        current_round = edit_round
    else:
        completed_rounds = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
        current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > total_rounds and not edit_round:
        st.warning(f"{board_name} has completed all rounds.")
        if st.button("Schließen"): st.rerun()
        return

    modus = sess.get("modus", "Up & Down")
# ... existing code ...
                        sc3, sc4 = st.columns([5, 2])
                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                        with sc4:
                            if st.button("🔄", key=f"sub2_{curr_sess['id']}_{b_name}_{next_r}"): open_substitution_dialog(b_name, curr_sess['id'], next_r, 2, p2)
                        
                        st.write("")
                        c_live1, c_live2 = st.columns([4, 1])
                        with c_live1:
                            if st.button("🎯 Eintragen", key=f"live_{curr_sess['id']}_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                                open_board_dialog(b_name, curr_sess['id'])
                        with c_live2:
                            if completed_r:
                                last_r = max(completed_r)
                                if st.button("✏️", key=f"edit_live_{curr_sess['id']}_{b_name}_{last_r}", help=f"Letztes Match (Runde {last_r}) korrigieren", use_container_width=True):
                                    open_board_dialog(b_name, curr_sess['id'], edit_round=last_r)
                    else:
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle Runden beendet</p>", unsafe_allow_html=True)
                        st.success("✅ Abgeschlossen")
                        if completed_r:
                            last_r = max(completed_r)
                            if st.button("✏️ Letztes Match korrigieren", key=f"edit_done_{curr_sess['id']}_{b_name}_{last_r}", use_container_width=True):
                                open_board_dialog(b_name, curr_sess['id'], edit_round=last_r)

    st.write("")
    st.divider()

    st.markdown("### 📊 Allgemeine Statistiken")
# ... existing code ...
```

**Was sich nun ändert:**
1. Neben dem großen Button **"🎯 Eintragen"** erscheint ein kleiner Button **"✏️"**.
2. Er ist nur sichtbar, wenn auf diesem Board bereits mindestens ein Match gespielt wurde.
3. Klickst du darauf, öffnet sich das dir bekannte Eingabefenster exakt für die Vorrunde (inkl. der dort vorab eingetragenen falschen Werte).
4. Du tauschst einfach die Legs (z. B. 0:3 in 3:0), drückst auf Speichern, und die App aktualisiert in Millisekunden die nachfolgenden Ansetzungen.
