"""Agentic dating pipeline: scraped IG+LinkedIn -> profiles -> agent dates -> rankings.
Uses Gemini (free tier) for all agent reasoning."""
import json, os, time, sys, requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

def load_env():
    env = {}
    for path in (os.path.join(BASE, ".env"), "/tmp/agentic/.env"):
        if os.path.exists(path):
            for line in open(path):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k] = v
    return env

ENV = load_env()
GEMINI_KEY = ENV.get("GEMINI_KEY", "")
MODEL = "gemini-2.5-flash-lite"

def gemini(prompt, retries=4):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json"}}
    for attempt in range(retries):
        try:
            r = requests.post(url, json=body, timeout=90)
            if r.status_code == 200:
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(txt)
        except Exception as e:
            print("gemini retry", attempt, str(e)[:120], flush=True)
        time.sleep(5 + attempt * 7)
    return None

def ig_summary(ig):
    posts = []
    for p in (ig.get("latestPosts") or [])[:12]:
        cap = (p.get("caption") or "")[:280]
        if cap:
            posts.append(cap)
    return {
        "username": ig.get("username"), "full_name": ig.get("fullName"),
        "bio": ig.get("biography") or "", "followers": ig.get("followersCount"),
        "business_category": ig.get("businessCategoryName"),
        "post_captions": posts,
    }

def li_summary(li):
    if not li:
        return {}
    exp = []
    for e in (li.get("experience") or li.get("positions") or [])[:5]:
        if isinstance(e, dict):
            exp.append({k: e.get(k) for k in ("title", "companyName", "company", "description") if e.get(k)})
    return {
        "headline": li.get("headline") or (li.get("basic_info") or {}).get("headline"),
        "about": (li.get("summary") or li.get("about") or "")[:800],
        "experience": exp,
        "location": (li.get("location") or {}).get("linkedinText") if isinstance(li.get("location"), dict) else li.get("location"),
    }

def analyze_person(name, ig, li):
    prompt = f"""You are an analyst agent for an agentic dating platform. Your ONLY sources of truth about this person are their public LinkedIn and public Instagram data below. Infer needs, hobbies, interests and qualities strictly from that evidence.

PERSON: {name}
LINKEDIN DATA: {json.dumps(li_summary(li), ensure_ascii=False)}
INSTAGRAM DATA: {json.dumps(ig_summary(ig), ensure_ascii=False)}

Return strict JSON with keys:
summary (2-3 sentences about who this person is),
needs (array of 4-6 emotional/practical needs in a partner),
hobbies (array of 4-8 hobbies),
interests (array of 4-8 interests),
personality (array of 4-6 traits),
values (array of 3-5 values),
lifestyle (one sentence),
looking_for (2 sentences: what would fit them in a partner),
dealbreakers (array of 2-4),
communication_style (one sentence),
evidence_notes (1-2 sentences citing which specific posts/roles you inferred from)."""
    return gemini(prompt)

def compact_card(p):
    prof = p["profile"]
    return {"id": p["id"], "name": p["name"],
            "summary": prof.get("summary", ""), "hobbies": prof.get("hobbies", []),
            "interests": prof.get("interests", []), "personality": prof.get("personality", []),
            "looking_for": prof.get("looking_for", "")}

def rank_for(person, others):
    prompt = f"""You are the dating agent representing {person['name']}. Based ONLY on your person's analyzed profile and the candidate cards below (each built from their public LinkedIn + Instagram), rank ALL candidates from best to worst romantic fit for your person.

YOUR PERSON: {json.dumps(compact_card(person), ensure_ascii=False)}
CANDIDATES: {json.dumps([compact_card(o) for o in others], ensure_ascii=False)}

Return strict JSON: {{"ranking": [{{"id": <candidate id>, "score": <0-100 integer>, "reason": "<one punchy sentence>"}}]}} with every candidate exactly once, best first."""
    return gemini(prompt)

def run_date(a, b, turns=5):
    convo = []
    last = ""
    for t in range(turns):
        for me, other in ((a, b), (b, a)):
            prompt = f"""You are {me['name']}'s personal dating agent, on a first date conversation with {other['name']}'s agent. You speak FOR {me['name']} in first person, faithfully using only what their profile says (from their public LinkedIn + Instagram). Be warm, witty, specific; reference real details from either profile. Keep each message 1-3 sentences. This is message {t+1} of {turns} from you.

YOUR PERSON: {json.dumps(compact_card(me), ensure_ascii=False)}
THEIR PROFILE: {json.dumps(compact_card(other), ensure_ascii=False)}
CONVERSATION SO FAR: {json.dumps(convo, ensure_ascii=False)}

Return strict JSON: {{"message": "<your next message>"}}"""
            out = gemini(prompt)
            msg = (out or {}).get("message", "...")
            convo.append({"speaker": me["name"], "message": msg})
    verdict = gemini(f"""You are a matchmaker. Two agents just went on this date representing their people (profiles built from public LinkedIn + Instagram).
A: {json.dumps(compact_card(a), ensure_ascii=False)}
B: {json.dumps(compact_card(b), ensure_ascii=False)}
DATE TRANSCRIPT: {json.dumps(convo, ensure_ascii=False)}
Return strict JSON: {{"score": <0-100 compatibility>, "verdict": "<2-3 sentence verdict>", "best_moment": "<one line>"}}""") or {}
    return {"pair": [a["id"], b["id"]], "names": [a["name"], b["name"]],
            "transcript": convo, "verdict": verdict}

def main():
    people = json.load(open(os.path.join(DATA, "people.json")))
    ig_data = json.load(open(os.path.join(DATA, "ig_data.json")))
    li_data = json.load(open(os.path.join(DATA, "li_data.json")))
    ig_by = {i.get("username"): i for i in ig_data}
    def find_li(p):
        slug = p["li"].rstrip("/").split("/in/")[-1]
        for li in li_data:
            if li.get("publicIdentifier") == slug or slug in (li.get("linkedinUrl") or ""):
                return li
        return None
    profiles = []
    if os.path.exists(os.path.join(DATA, "profiles.json")):
        profiles = json.load(open(os.path.join(DATA, "profiles.json")))
    done = {p["id"] for p in profiles}
    for idx, p in enumerate(people):
        pid = f"p{idx+1:02d}"
        if pid in done:
            continue
        ig = ig_by.get(p["ig"])
        li = find_li(p)
        print("analyze", p["name"], flush=True)
        prof = analyze_person(p["name"], ig or {}, li)
        if not prof:
            print("FAILED", p["name"], flush=True); continue
        profiles.append({"id": pid, "name": p["name"], "linkedin": p["li"],
                         "instagram": f"https://www.instagram.com/{p['ig']}/",
                         "photo": (ig or {}).get("profilePicUrlHD") or (ig or {}).get("profilePicUrl"),
                         "followers": (ig or {}).get("followersCount"),
                         "profile": prof})
        json.dump(profiles, open(os.path.join(DATA, "profiles.json"), "w"), ensure_ascii=False, indent=1)
        time.sleep(2)
    # rankings
    rankings = {}
    rp = os.path.join(DATA, "rankings.json")
    if os.path.exists(rp):
        rankings = json.load(open(rp))
    for p in profiles:
        if p["id"] in rankings:
            continue
        others = [o for o in profiles if o["id"] != p["id"]]
        print("rank", p["name"], flush=True)
        out = rank_for(p, others)
        if out and "ranking" in out:
            rankings[p["id"]] = out["ranking"]
            json.dump(rankings, open(rp, "w"), ensure_ascii=False, indent=1)
        time.sleep(2)
    # dates: top mutual pairs
    dates = []
    dp = os.path.join(DATA, "dates.json")
    if os.path.exists(dp):
        dates = json.load(open(dp))
    if not dates:
        score = {}
        for pid, rk in rankings.items():
            for entry in rk[:3]:
                key = tuple(sorted([pid, entry["id"]]))
                score[key] = score.get(key, 0) + entry.get("score", 0)
        top = sorted(score.items(), key=lambda kv: -kv[1])[:8]
        byid = {p["id"]: p for p in profiles}
        for (ida, idb), s in top:
            print("date", byid[ida]["name"], "x", byid[idb]["name"], flush=True)
            dates.append(run_date(byid[ida], byid[idb]))
            json.dump(dates, open(dp, "w"), ensure_ascii=False, indent=1)
            time.sleep(2)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
