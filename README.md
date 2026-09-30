# Agentic Hearts 💘

An agentic dating site. Every person is represented by an agent. The agents date on their behalf.

## How it works

1. **You find the people.** 25 real people, each one exactly two official links: their LinkedIn and their public Instagram.
2. **Each agent reads its person.** An analyst agent reads ONLY those two sources (scraped via Apify) and infers needs, hobbies, interests, personality, values, lifestyle, dealbreakers - shown on a profile page per person.
3. **The agents date.** Agent-to-agent first-date conversations, each agent speaking for its person from their profile only.
4. **Rankings.** Every person's agent ranks all the others by romantic fit, with a score and a reason.

## Live features

- Paste your own LinkedIn + public Instagram links: the agent scrapes, analyzes and builds a profile page on the spot, then can go on a live date with anyone in the dataset.
- Pre-run demo: 25 profiles, rankings for all, and full date transcripts for the top-matched pairs.

## Tech stack

- **Scraping**: Apify actors - `apify/instagram-profile-scraper` (public IG profiles + latest post captions) and `harvestapi/linkedin-profile-scraper` (public LinkedIn profiles, no cookies/login). Free tier, REST API.
- **Agents**: Google Gemini (2.5-flash / flash-lite) via REST - analyst agent, dating agents, matchmaker, ranker. JSON-mode outputs.
- **App**: Python + Streamlit (dark theme, 5 pages: Home/Live Agent, People, Profile pages, Agent dates, Rankings).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Secrets (for the live "add a person" feature): `APIFY_TOKEN`, `GEMINI_KEY` in `.streamlit/secrets.toml` or env.
The pre-run demo data in `data/` works with no keys.
