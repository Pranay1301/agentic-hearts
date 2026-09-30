import json, os, time, requests, streamlit as st

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

st.set_page_config(page_title="Agentic Hearts", page_icon="💘", layout="wide")

st.markdown("""<style>
.big {font-size:2.2rem; font-weight:800}
.card {background:#111826; border:1px solid #2a3550; border-radius:14px; padding:16px; margin-bottom:10px}
.msg-a {background:#1d2b45; border-radius:12px; padding:10px 14px; margin:6px 0}
.msg-b {background:#2b1d45; border-radius:12px; padding:10px 14px; margin:6px 0}
.tag {display:inline-block; background:#233252; color:#bcd3ff; border-radius:20px; padding:3px 12px; margin:3px; font-size:0.85rem}
.score {font-size:1.6rem; font-weight:800; color:#ff5c8a}
</style>""", unsafe_allow_html=True)

def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default

def secret(k):
    try: return st.secrets[k]
    except Exception: return os.environ.get(k, "")

def gemini(prompt):
    key = secret("GEMINI_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json"}}
    for _ in range(3):
        try:
            r = requests.post(url, json=body, timeout=60)
            if r.status_code == 200:
                return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except Exception:
            pass
        time.sleep(4)
    return None

def apify_sync(actor, payload):
    tok = secret("APIFY_TOKEN")
    r = requests.post(f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={tok}",
                      json=payload, timeout=300)
    return r.json() if r.status_code in (200, 201) else []

people = load("people.json", [])
profiles = load("profiles.json", [])
rankings = load("rankings.json", {})
dates = load("dates.json", [])
byid = {p["id"]: p for p in profiles}

st.sidebar.markdown('<p class="big">💘 Agentic Hearts</p>', unsafe_allow_html=True)
st.sidebar.caption("Every person is an agent. The agents date for them.")
page = st.sidebar.radio("Go to", ["🏠 Home & Live Agent", "👥 People", "🧬 Profile pages", "💬 Agent dates", "🏆 Rankings"])

if page == "🏠 Home & Live Agent":
    st.markdown('<p class="big">Agents that date on your behalf</p>', unsafe_allow_html=True)
    st.write("Each person is represented by an agent. The agent reads exactly two sources - the person's public LinkedIn and public Instagram - builds a dating profile, dates other agents, and ranks who fits their person best.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("People", len(profiles)); c2.metric("Profile pages", len(profiles))
    c3.metric("Rankings", len(rankings)); c4.metric("Agent dates", len(dates))
    st.divider()
    st.subheader("Try it: add a real person")
    st.caption("Paste two official links - a LinkedIn profile and a public Instagram profile. The agent reads both, analyzes the person, and opens their profile page. Then watch it date.")
    li = st.text_input("LinkedIn profile URL", placeholder="https://www.linkedin.com/in/...")
    ig = st.text_input("Public Instagram URL", placeholder="https://www.instagram.com/username/")
    if st.button("Send the agent in 🚀", type="primary"):
        if not li or not ig:
            st.error("Both links are needed - those are the agent's only two sources.")
        else:
            handle = ig.rstrip("/").split("/")[-1].split("?")[0]
            with st.status("Agent working...", expanded=True) as s:
                st.write("Reading Instagram (public posts & bio)...")
                igd = apify_sync("apify~instagram-profile-scraper", {"usernames": [handle]})
                if not igd or igd[0].get("error"):
                    s.update(state="error"); st.error("Couldn't read that Instagram profile. It must be public.")
                    st.stop()
                st.write("Reading LinkedIn (public profile)...")
                lid = apify_sync("harvestapi~linkedin-profile-scraper", {"urls": [li]})
                lid = [x for x in lid if isinstance(x, dict) and not x.get("error")]
                st.write("Analyzing the person...")
                ig0 = igd[0]
                li0 = lid[0] if lid else {}
                caps = [(p.get("caption") or "")[:280] for p in (ig0.get("latestPosts") or [])[:12]]
                caps = [c for c in caps if c]
                prompt = f"""You are an analyst agent for an agentic dating platform. ONLY sources: this person's public LinkedIn and Instagram data.
LINKEDIN: {json.dumps({"headline": li0.get("headline"), "about": (li0.get("about") or li0.get("summary") or "")[:800], "experience": (li0.get("experience") or [])[:5]}, ensure_ascii=False)}
INSTAGRAM: {json.dumps({"full_name": ig0.get("fullName"), "bio": ig0.get("biography") or "", "followers": ig0.get("followersCount"), "captions": caps}, ensure_ascii=False)}
Return strict JSON: summary, needs (4-6), hobbies (4-8), interests (4-8), personality (4-6), values (3-5), lifestyle, looking_for, dealbreakers (2-4), communication_style, evidence_notes."""
                prof = gemini(prompt)
                if not prof:
                    s.update(state="error"); st.error("The analyst agent is busy - try again in a minute.")
                    st.stop()
                newp = {"id": f"live{int(time.time())}", "name": ig0.get("fullName") or handle,
                        "linkedin": li, "instagram": ig,
                        "photo": ig0.get("profilePicUrlHD") or ig0.get("profilePicUrl"),
                        "followers": ig0.get("followersCount"), "profile": prof}
                st.session_state["live_person"] = newp
                s.update(label="Profile built!", state="complete")
            st.success(f"Agent profile built for {newp['name']}")
    lp = st.session_state.get("live_person")
    if lp:
        prof = lp["profile"]
        st.subheader(f"🧬 {lp['name']} - agent profile")
        cc = st.columns([1, 3])
        with cc[0]:
            if lp.get("photo"): st.image(lp["photo"], width=160)
        with cc[1]:
            st.write(prof.get("summary", ""))
            st.caption(prof.get("evidence_notes", ""))
        st.markdown("**Needs**"); st.markdown("".join(f'<span class="tag">{n}</span>' for n in prof.get("needs", [])), unsafe_allow_html=True)
        st.markdown("**Hobbies**"); st.markdown("".join(f'<span class="tag">{h}</span>' for h in prof.get("hobbies", [])), unsafe_allow_html=True)
        st.markdown("**Interests**"); st.markdown("".join(f'<span class="tag">{i}</span>' for i in prof.get("interests", [])), unsafe_allow_html=True)
        st.info("💘 Looking for: " + prof.get("looking_for", ""))
        if profiles:
            st.divider()
            st.subheader("Send their agent on a date")
            pick = st.selectbox("Date with", [p["name"] for p in profiles])
            if st.button("Start the date 💬"):
                other = next(p for p in profiles if p["name"] == pick)
                def card(p):
                    pr = p["profile"]
                    return {"name": p["name"], "summary": pr.get("summary",""), "hobbies": pr.get("hobbies",[]),
                            "interests": pr.get("interests",[]), "personality": pr.get("personality",[]), "looking_for": pr.get("looking_for","")}
                convo = []
                with st.status("The agents are on their date...", expanded=True):
                    for t in range(4):
                        for me, other2 in ((lp, other), (other, lp)):
                            out = gemini(f"""You are {me['name']}'s personal dating agent on a first date with {other2['name']}'s agent. Speak FOR {me['name']} in first person using only their profile (from public LinkedIn + Instagram). Warm, witty, specific. 1-3 sentences.
YOUR PERSON: {json.dumps(card(me), ensure_ascii=False)}
THEM: {json.dumps(card(other2), ensure_ascii=False)}
SO FAR: {json.dumps(convo, ensure_ascii=False)}
Return strict JSON: {{"message": "..."}}""")
                            convo.append({"speaker": me["name"], "message": (out or {}).get("message", "...")})
                            st.write(f"**{me['name']}:** {convo[-1]['message']}")
                    verdict = gemini(f"""Matchmaker verdict for this date. A: {json.dumps(card(lp))} B: {json.dumps(card(other))} TRANSCRIPT: {json.dumps(convo)}
Return strict JSON: {{"score": <0-100>, "verdict": "<2 sentences>"}}""") or {}
                st.markdown(f'<p class="score">Compatibility: {verdict.get("score","?")}/100</p>', unsafe_allow_html=True)
                st.write(verdict.get("verdict", ""))

elif page == "👥 People":
    st.markdown('<p class="big">The 25 people</p>', unsafe_allow_html=True)
    st.caption("Real people found on the public web. Each one is two official links: LinkedIn + public Instagram.")
    cols = st.columns(4)
    for i, p in enumerate(profiles):
        with cols[i % 4]:
            if p.get("photo"): st.image(p["photo"], use_container_width=True)
            st.markdown(f"**{p['name']}**")
            st.caption(f"{(p.get('followers') or 0):,} IG followers")
            st.markdown(f"[LinkedIn]({p['linkedin']}) · [Instagram]({p['instagram']})")

elif page == "🧬 Profile pages":
    st.markdown('<p class="big">Profile pages</p>', unsafe_allow_html=True)
    st.caption("What each agent learned from its person's two sources.")
    if not profiles:
        st.warning("Profiles are being generated.")
    else:
        sel = st.selectbox("Person", [p["name"] for p in profiles])
        p = next(x for x in profiles if x["name"] == sel)
        prof = p["profile"]
        cc = st.columns([1, 3])
        with cc[0]:
            if p.get("photo"): st.image(p["photo"], use_container_width=True)
            st.markdown(f"[LinkedIn]({p['linkedin']}) · [Instagram]({p['instagram']})")
        with cc[1]:
            st.subheader(p["name"])
            st.write(prof.get("summary", ""))
            st.caption("🔍 " + prof.get("evidence_notes", ""))
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Needs**"); st.markdown("".join(f'<span class="tag">{n}</span>' for n in prof.get("needs", [])), unsafe_allow_html=True)
            st.markdown("**Values**"); st.markdown("".join(f'<span class="tag">{v}</span>' for v in prof.get("values", [])), unsafe_allow_html=True)
        with c2:
            st.markdown("**Hobbies**"); st.markdown("".join(f'<span class="tag">{h}</span>' for h in prof.get("hobbies", [])), unsafe_allow_html=True)
            st.markdown("**Personality**"); st.markdown("".join(f'<span class="tag">{t}</span>' for t in prof.get("personality", [])), unsafe_allow_html=True)
        with c3:
            st.markdown("**Interests**"); st.markdown("".join(f'<span class="tag">{i}</span>' for i in prof.get("interests", [])), unsafe_allow_html=True)
            st.markdown("**Dealbreakers**"); st.markdown("".join(f'<span class="tag">{d}</span>' for d in prof.get("dealbreakers", [])), unsafe_allow_html=True)
        st.info("💘 Looking for: " + prof.get("looking_for", ""))
        st.caption("Lifestyle: " + prof.get("lifestyle", "") + " · Communication: " + prof.get("communication_style", ""))

elif page == "💬 Agent dates":
    st.markdown('<p class="big">The agents, actually dating</p>', unsafe_allow_html=True)
    if not dates:
        st.warning("Dates are being generated.")
    else:
        labels = [f"{d['names'][0]} 💞 {d['names'][1]} - {d.get('verdict',{}).get('score','?')}/100" for d in dates]
        i = st.selectbox("Pick a date", range(len(dates)), format_func=lambda x: labels[x])
        d = dates[i]
        v = d.get("verdict", {})
        st.markdown(f'<p class="score">{v.get("score","?")}/100</p>', unsafe_allow_html=True)
        st.write(v.get("verdict", ""))
        if v.get("best_moment"): st.caption("✨ Best moment: " + v["best_moment"])
        st.divider()
        for m in d["transcript"]:
            cls = "msg-a" if m["speaker"] == d["names"][0] else "msg-b"
            st.markdown(f'<div class="{cls}"><b>{m["speaker"]}</b><br>{m["message"]}</div>', unsafe_allow_html=True)

elif page == "🏆 Rankings":
    st.markdown('<p class="big">Who fits each person best</p>', unsafe_allow_html=True)
    if not rankings:
        st.warning("Rankings are being generated.")
    else:
        sel = st.selectbox("Person", [p["name"] for p in profiles if p["id"] in rankings])
        pid = next(p["id"] for p in profiles if p["name"] == sel)
        st.subheader(f"Best matches for {sel}")
        for rank, entry in enumerate(rankings.get(pid, [])[:10], 1):
            o = byid.get(entry["id"])
            if not o: continue
            c1, c2 = st.columns([1, 5])
            with c1:
                st.markdown(f"**#{rank}**")
                st.markdown(f'<span class="score">{entry.get("score","?")}</span>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{o['name']}**")
                st.caption(entry.get("reason", ""))
