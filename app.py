<!-- ... existing code ... -->
# LIGA CONSTANTS
LIGA_ROUNDS = [
    [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2")],
    [("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4")],
    [("m5", "Einzel 5 (Kreuz)", "h1", "g2"), ("m6", "Einzel 6 (Kreuz)", "h2", "g1")],
    [("m7", "Einzel 7 (Kreuz)", "h3", "g4"), ("m8", "Einzel 8 (Kreuz)", "h4", "g3")],
    [("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
]
LIGA_MATCH_MAP = [match for round in LIGA_ROUNDS for match in round]

@st.dialog("➕ Neues Liga-Spiel (4. BezLiga)", width="large")
def open_new_liga_match_dialog():
    st.write("Erstelle hier ein neues Ligaspiel. Die Aufstellung erfolgt gleich verdeckt im Live-Modus.")
    c1, c2 = st.columns(2)
    session_datum = c1.date_input("Datum des Ligaspiels", date.today())
    heim_team = c2.text_input("Heimmannschaft", value="Wehringer Steelers")
    gast_team = st.text_input("Gastmannschaft", placeholder="z.B. DC Irgendwas")
    
    st.write("Auf welchen Boards wird gespielt?")
    c3, c4 = st.columns(2)
    b1 = c3.selectbox("Board A", ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"], index=0)
    b2 = c4.selectbox("Board B", ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"], index=1)
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with cb2:
        if st.button("Liga-Spiel erstellen", type="primary", use_container_width=True):
            max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "L-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
            new_session = {
                "id": f"L-{max_id + 1}",
                "datum": session_datum.strftime("%d.%m.%Y"),
                "is_liga": True,
                "heim_team": heim_team,
                "gast_team": gast_team,
                "liga_boards": [b1, b2],
                "auf_heim": {},
                "auf_gast": {},
                "results": {}
            }
            st.session_state.sessions_list.append(new_session)
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🔒 Einzel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_einzel(session_idx, is_heim):
    sess = st.session_state.sessions_list[session_idx]
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    st.write(f"### Aufstellung: {team_name}")
    st.info("Trage hier die 4 Einzelspieler ein. Der Gegner sieht diese Eingabe erst, wenn das Spiel startet.")
    
    if is_heim:
        h1 = st.selectbox("Position 1", kader + ["-"], index=len(kader))
        h2 = st.selectbox("Position 2", kader + ["-"], index=len(kader))
        h3 = st.selectbox("Position 3", kader + ["-"], index=len(kader))
        h4 = st.selectbox("Position 4", kader + ["-"], index=len(kader))
    else:
        h1 = st.text_input("Position 1")
        h2 = st.text_input("Position 2")
        h3 = st.text_input("Position 3")
        h4 = st.text_input("Position 4")
        
    if st.button("Speichern", type="primary", use_container_width=True):
        if is_heim:
            sess["auf_heim"].update({"h1": h1, "h2": h2, "h3": h3, "h4": h4})
        else:
            sess["auf_gast"].update({"g1": h1, "g2": h2, "g3": h3, "g4": h4})
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_idx, is_heim):
    sess = st.session_state.sessions_list[session_idx]
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    st.write(f"### Doppel-Aufstellung: {team_name}")
    
    d1 = st.text_input("Doppel 1 (z.B. Andi & Marco)")
    d2 = st.text_input("Doppel 2")
        
    if st.button("Speichern", type="primary", use_container_width=True):
        if is_heim:
            sess["auf_heim"].update({"hd1": d1, "hd2": d2})
        else:
            sess["auf_gast"].update({"gd1": d1, "gd2": d2})
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🔄 Spieler auswechseln")
def open_liga_sub_dialog(session_idx, p_key, is_heim, curr_name):
    sess = st.session_state.sessions_list[session_idx]
    st.write(f"Neuen Spieler für **{curr_name}** einwechseln:")
    
    if is_heim:
        new_name = st.selectbox("Aus Kader wählen:", kader + ["-"], index=len(kader))
    else:
        new_name = st.text_input("Neuer Gastspieler:")
        
    if st.button("Speichern", type="primary", use_container_width=True):
        if new_name and new_name != "-":
            if is_heim:
                sess["auf_heim"][p_key] = new_name
            else:
                sess["auf_gast"][p_key] = new_name
            smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🎯 Live Board (Liga)")
def open_liga_live_board_dialog(session_idx, m_key, board_name, m_label, p_heim, p_gast):
    sess = st.session_state.sessions_list[session_idx]
    res = sess.setdefault("results", {})
    m_data = res.get(m_key, {})
    
    st.write(f"### {board_name} — {m_label}")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Heim:** `{p_heim}`")
        lh = st.number_input("Legs", 0, 3, m_data.get("lh", 0), key="lh")
    with c2:
        st.markdown(f"**Gast:** `{p_gast}`")
        lg = st.number_input("Legs", 0, 3, m_data.get("lg", 0), key="lg")
        
    with st.expander("➕ Extras (180, HF, SL)", expanded=False):
        ce1, ce2 = st.columns(2)
        with ce1:
            e180_h = st.number_input("180er", 0, 10, m_data.get("180_h", 0), key="180h")
            hf_h = st.text_input("High Finish", m_data.get("hf_h", ""), key="hfh")
            sl_h = st.text_input("Short Leg", m_data.get("sl_h", ""), key="slh")
        with ce2:
            e180_g = st.number_input("180er", 0, 10, m_data.get("180_g", 0), key="180g")
            hf_g = st.text_input("High Finish", m_data.get("hf_g", ""), key="hfg")
            sl_g = st.text_input("Short Leg", m_data.get("sl_g", ""), key="slg")

    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Speichern", type="primary", use_container_width=True):
            if lh == lg:
                st.error("Unentschieden ungültig!")
            else:
                res[m_key] = {
                    "lh": lh, "lg": lg, "played": True,
                    "180_h": e180_h, "hf_h": hf_h, "sl_h": sl_h,
                    "180_g": e180_g, "hf_g": hf_g, "sl_g": sl_g
                }
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()
    with cb2:
        if st.button("Abbrechen", use_container_width=True): st.rerun()

@st.dialog("📝 Offizieller Spielbericht (Korrektur)", width="large")
def open_liga_bericht_dialog(session_idx):
    sess = st.session_state.sessions_list[session_idx]
    auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
    res = sess.setdefault("results", {})
    st.write(f"Hier kannst du bei Bedarf alle Ergebnisse manuell korrigieren.")
    
    for m_key, label, h_key, g_key in LIGA_MATCH_MAP:
        p_heim, p_gast = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
        m_data = res.get(m_key, {})
        with st.expander(f"{label}: {p_heim} vs {p_gast}", expanded=False):
            c_lh, c_vs, c_lg = st.columns([2, 1, 2])
            lh = c_lh.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"blh_{m_key}")
            c_vs.markdown("<div style='text-align: center; padding-top: 30px;'>:</div>", unsafe_allow_html=True)
            lg = c_lg.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"blg_{m_key}")
            res[m_key] = {"lh": lh, "lg": lg, "played": True if (lh>0 or lg>0) else False, "180_h": m_data.get("180_h", 0), "hf_h": m_data.get("hf_h", ""), "sl_h": m_data.get("sl_h", ""), "180_g": m_data.get("180_g", 0), "hf_g": m_data.get("hf_g", ""), "sl_g": m_data.get("sl_g", "")}

    if st.button("💾 Speichern & Schließen", type="primary", use_container_width=True):
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

with tab_liga:
    st.subheader("Liga-Spielbetrieb (4. BezLiga Schwaben)")
    st.write("Eigener Bereich für Ligaspielen. Mit 2-Board Live Tracking und automatischem Überkreuzen.")
    
    if st.button("➕ Neues Liga-Spiel anlegen", type="primary", use_container_width=True):
        open_new_liga_match_dialog()
        
    st.divider()
    
    liga_sessions = [s for s in st.session_state.sessions_list if s.get("is_liga")]
    
    if not liga_sessions:
        st.info("Noch keine Liga-Spiele angelegt.")
    else:
        sorted_liga = sorted(liga_sessions, key=lambda x: int(x["id"].split("-")[1]) if "id" in x and "-" in x["id"] else 0, reverse=True)
        for l_sess in sorted_liga:
            real_idx = st.session_state.sessions_list.index(l_sess)
            heim = l_sess.get("heim_team", "Heim")
            gast = l_sess.get("gast_team", "Gast")
            res = l_sess.setdefault("results", {})
            boards = l_sess.get("liga_boards", ["Kaiser B1", "Board 2"])
            
            # Abwärtskompatibilität für alte Sessions
            if "aufstellung" in l_sess:
                l_sess["auf_heim"] = {k:v for k,v in l_sess["aufstellung"].items() if "h" in k}
                l_sess["auf_gast"] = {k:v for k,v in l_sess["aufstellung"].items() if "g" in k}
                del l_sess["aufstellung"]
                
            auf_h = l_sess.setdefault("auf_heim", {})
            auf_g = l_sess.setdefault("auf_gast", {})
            
            # Live Score berechnen
            sets_heim, sets_gast, legs_heim, legs_gast = 0, 0, 0, 0
            for m_data in res.values():
                if m_data.get("played"):
                    lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
                    legs_heim += lh; legs_gast += lg
                    if lh > lg: sets_heim += 1
                    elif lg > lh: sets_gast += 1
                    
            is_done = len([k for k, v in res.items() if v.get("played")]) == 10
            status = "✅ Abgeschlossen" if is_done else "🔴 Aktiv"
            
            with st.container(border=True):
                st.markdown(f"### {heim} vs. {gast}")
                st.caption(f"{l_sess['datum']} | ID: {l_sess['id']} | Status: {status}")
                st.markdown(f"**Sets:** {sets_heim} : {sets_gast} | **Legs:** {legs_heim} : {legs_gast}")
                
                # Setup Phase Checks
                h_einzel_ok = bool(auf_h.get("h1"))
                g_einzel_ok = bool(auf_g.get("g1"))
                
                if not h_einzel_ok or not g_einzel_ok:
                    st.warning("Phase 1: Einzel-Aufstellungen eintragen (wird verdeckt)")
                    c_h, c_g = st.columns(2)
                    if not h_einzel_ok and c_h.button("🔒 Heim Aufstellen", key=f"h_setup_{l_sess['id']}"):
                        open_liga_aufstellung_einzel(real_idx, True)
                    if not g_einzel_ok and c_g.button("🔒 Gast Aufstellen", key=f"g_setup_{l_sess['id']}"):
                        open_liga_aufstellung_einzel(real_idx, False)
                elif not is_done:
                    # Finde aktive Runde
                    curr_round_idx = 0
                    for r_idx, round_matches in enumerate(LIGA_ROUNDS):
                        if not all(res.get(m[0], {}).get("played") for m in round_matches):
                            curr_round_idx = r_idx
                            break
                            
                    if curr_round_idx == 4: # Doppel Runde erreicht
                        h_doppel_ok = bool(auf_h.get("hd1"))
                        g_doppel_ok = bool(auf_g.get("gd1"))
                        if not h_doppel_ok or not g_doppel_ok:
                            st.warning("Phase 2: Doppel-Aufstellungen eintragen")
                            c_dh, c_dg = st.columns(2)
                            if not h_doppel_ok and c_dh.button("🔒 Heim Doppel", key=f"hd_setup_{l_sess['id']}"):
                                open_liga_aufstellung_doppel(real_idx, True)
                            if not g_doppel_ok and c_dg.button("🔒 Gast Doppel", key=f"gd_setup_{l_sess['id']}"):
                                open_liga_aufstellung_doppel(real_idx, False)
                                
                    # Zeige Live Boards für aktuelle Runde (sofern bereit)
                    if curr_round_idx < 4 or (h_doppel_ok and g_doppel_ok):
                        active_matches = LIGA_ROUNDS[curr_round_idx]
                        st.markdown(f"**Runde {curr_round_idx + 1} läuft:**")
                        for i, (m_key, m_label, h_key, g_key) in enumerate(active_matches):
                            b_name = boards[i % len(boards)]
                            p_heim, p_gast = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
                            is_played = res.get(m_key, {}).get("played", False)
                            
                            with st.container(border=True):
                                st.write(f"*{b_name}* — {m_label}")
                                sc1, sc2 = st.columns([5, 2])
                                sc1.markdown(f"Heim: **{p_heim}**")
                                if not is_played and not "d" in h_key:
                                    if sc2.button("🔄", key=f"sub_h_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(real_idx, h_key, True, p_heim)
                                    
                                sc3, sc4 = st.columns([5, 2])
                                sc3.markdown(f"Gast: **{p_gast}**")
                                if not is_played and not "d" in g_key:
                                    if sc4.button("🔄", key=f"sub_g_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(real_idx, g_key, False, p_gast)
                                
                                if is_played:
                                    st.success(f"Ergebnis: {res[m_key]['lh']}:{res[m_key]['lg']}")
                                else:
                                    if st.button("🎯 Eintragen", key=f"live_{m_key}_{l_sess['id']}", use_container_width=True):
                                        open_liga_live_board_dialog(real_idx, m_key, b_name, m_label, p_heim, p_gast)

                if is_done or (h_einzel_ok and g_einzel_ok):
                    st.divider()
                    if st.button("📝 Gesamten Spielbericht ansehen/korrigieren", key=f"l_ber_{l_sess['id']}", use_container_width=True):
                        open_liga_bericht_dialog(real_idx)

    st.divider()
    
    st.subheader("📈 Liga-Statistiken (Steelers Kader)")
    liga_stats = {p: {"e_spiele": 0, "e_siege": 0, "d_spiele": 0, "d_siege": 0, "180er": 0, "hf": 0, "sl": 999} for p in kader}
    
    def process_liga_player(p_name, is_win, is_doppel, hf, sl, e180):
        if p_name in liga_stats:
            if is_doppel:
                liga_stats[p_name]["d_spiele"] += 1
                if is_win: liga_stats[p_name]["d_siege"] += 1
            else:
                liga_stats[p_name]["e_spiele"] += 1
                if is_win: liga_stats[p_name]["e_siege"] += 1
            liga_stats[p_name]["180er"] += e180
            if hf:
                import re
                nums = [int(n) for n in re.findall(r'\d+', str(hf))]
                if nums and max(nums) > liga_stats[p_name]["hf"]: liga_stats[p_name]["hf"] = max(nums)
            if sl:
                import re
                nums = [int(n) for n in re.findall(r'\d+', str(sl))]
                if nums and min(nums) < liga_stats[p_name]["sl"]: liga_stats[p_name]["sl"] = min(nums)

    for sess in liga_sessions:
        auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
        res = sess.get("results", {})
        is_steelers_heim = "Steelers" in sess.get("heim_team", "")
        
        for m_key, m_name, h_key, g_key in LIGA_MATCH_MAP:
            m_data = res.get(m_key, {})
            if not m_data.get("played"): continue
            lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
            
            is_win_heim = lh > lg
            is_win_gast = lg > lh
            
            p_heim, p_gast = auf_h.get(h_key, ""), auf_g.get(g_key, "")
            is_doppel = "d" in h_key
            
            if is_steelers_heim:
                hf_v, sl_v, e180_v = m_data.get("hf_h", ""), m_data.get("sl_h", ""), m_data.get("180_h", 0)
                targets = str(p_heim).split("&") if is_doppel else [str(p_heim)]
                for p in targets: process_liga_player(p.strip(), is_win_heim, is_doppel, hf_v, sl_v, e180_v)
            else:
                hf_v, sl_v, e180_v = m_data.get("hf_g", ""), m_data.get("sl_g", ""), m_data.get("180_g", 0)
                targets = str(p_gast).split("&") if is_doppel else [str(p_gast)]
                for p in targets: process_liga_player(p.strip(), is_win_gast, is_doppel, hf_v, sl_v, e180_v)

    l_rows = []
    for p in kader:
        stt = liga_stats[p]
        if stt["e_spiele"] > 0 or stt["d_spiele"] > 0:
            l_rows.append({
                "Spieler": p,
                "Einzel (S/M)": f"{stt['e_siege']}/{stt['e_spiele']}",
                "Doppel (S/M)": f"{stt['d_siege']}/{stt['d_spiele']}",
                "180er": stt['180er'],
                "High Finish": stt['hf'] if stt['hf'] > 0 else "-",
                "Short Leg": stt['sl'] if stt['sl'] != 999 else "-"
            })
            
    if l_rows:
        st.dataframe(pd.DataFrame(l_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Noch keine Statistiken für Ligamatches verfügbar.")
<!-- ... existing code ... -->
