# ... existing code ...
@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    t_size = sess.get("team_size", 4)
    num_doubles = 3 if t_size == 6 else 2
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    st.write(f"### Doppel-Aufstellung: {team_name}")
    st.info("⚠️ Wichtig: Jeder Spieler darf in den Doppeln insgesamt nur 1x antreten!")
    
    auf_dict = sess.get("auf_heim", {}) if is_heim else sess.get("auf_gast", {})
# ... existing code ...
        doubles_data.append((p1.strip() if p1 else "", p2.strip() if p2 else ""))
        
    if st.button("Speichern", type="primary", use_container_width=True):
        all_selected = []
        for p1, p2 in doubles_data: all_selected.extend([p1, p2])
        
        import collections
        dupes = [item for item, count in collections.Counter(all_selected).items() if count > 1 and item != ""]
        
        if any(not x for x in all_selected): st.error("🚨 Bitte alle Spieler ausfüllen!")
        elif dupes: st.error(f"🚨 Fehler: Der Spieler '{dupes[0]}' steht in mehreren Feldern! Jeder darf nur 1x spielen.")
        else:
            update_dict = {}
            for d_idx, (p1, p2) in enumerate(doubles_data):
# ... existing code ...
```

Und hier ist die Anpassung für die Sichtbarkeit der Auswechsel-Buttons im Freundschaftsspiele-Reiter:

```python:Wehringer Steelers - App:app.py
# ... existing code ...
                                    if i % 2 == 1:
                                        st.markdown(f"Gast (links): **{p_gast}**")
                                        if not is_played and "Kreuz" in m_label:
                                            if st.button("🔄", key=f"sub_g_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_gast)
                                        st.markdown(f"Heim: **{p_heim}**")
                                        if not is_played and "Kreuz" in m_label:
                                            if st.button("🔄", key=f"sub_h_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_heim)
                                    else:
                                        st.markdown(f"Heim (links): **{p_heim}**")
                                        if not is_played and "Kreuz" in m_label:
                                            if st.button("🔄", key=f"sub_h_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_heim)
                                        st.markdown(f"Gast: **{p_gast}**")
                                        if not is_played and "Kreuz" in m_label:
                                            if st.button("🔄", key=f"sub_g_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_gast)
                                    
                                    if is_played:
# ... existing code ...
                        if curr_round_idx + 1 < len(rounds_list):
                            next_matches = rounds_list[curr_round_idx + 1]
                            with st.expander("👀 Vorschau nächste Runde (Auswechslungen vorbereiten)", expanded=False):
                                for ni, (nm_key, nm_label, nh_key, ng_key) in enumerate(next_matches):
                                    np_h, np_g = auf_h.get(nh_key, "-"), auf_g.get(ng_key, "-")
                                    col_nv1, col_nv2 = st.columns([4, 1])
                                    col_nv1.markdown(f"**{nm_label}**: {np_h} vs {np_g}")
                                    if "Kreuz" in nm_label and col_nv2.button("🔄 H", key=f"next_sub_h_{nm_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], nh_key, True, np_h)

                if is_done or (h_einzel_ok and g_einzel_ok):
# ... existing code ...
```

Die App ist technisch gesehen nicht in der Lage, Optionen live aus dem Dropdown verschwinden zu lassen, während du tippst. Mit dem verbesserten Code fängt sie deinen Fehler aber mit der namentlichen Fehlermeldung ab, bevor etwas Falsches in die Datenbank wandert!
