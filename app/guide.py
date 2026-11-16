"""Plain-language guide for every dashboard tab.

Each tab gets four short answers: what you see, where the data comes from, how to read it,
and what to do with it. Plus a column-by-column guide for its tables. Numbers in {braces}
are filled in from the live data by the dashboard; anything missing shows as "—".
"""

from __future__ import annotations

from collections import defaultdict

import streamlit as st

HEADINGS = {"what": "👀 What you see", "where": "📥 Where the data comes from",
            "read": "🔢 How to read it", "do": "👉 What to do with it"}

# The same "where do these people come from" story is used in more than one tab.
PEOPLE_SOURCES = [
    "We do **not** search all of X. We collect people **by who they talk to**, from 4 places:",
    "1. **Our clients themselves**: all posts by Alex, Michel, Nikola, Kenny and the other clients.",
    "2. **People who engage with our clients**: anyone who replies to or quotes a client's post. "
    "These are the clients' actual audience.",
    "3. **The big accounts in each niche**: well-known B2B, AI and SaaS voices the niche follows and talks to.",
    "4. **People who engage with those big accounts**: anyone who replies to them. They're in the same "
    "world but don't know our clients yet, so they're the *new* audience to reach.",
    "Then each person's **bio and recent posts** are read, and only people who really talk about "
    "B2B, AI or Tech are kept. Everyone else is marked *off-topic* and ignored.",
]

GUIDE: dict[str, dict] = {
    "overview": {
        "what": ["A one-page summary: how much data we have, how many people were sorted into a niche, and "
                 "which steps are finished."],
        "where": PEOPLE_SOURCES[:1] + ["Everything comes from **xplatform** (Thought Pilot's X data store). "
                                       "It is refreshed automatically: every 4 hours, every day at 06:00 UTC and "
                                       "every Sunday."],
        "read": ["**Posts stored**: {posts} posts collected so far.",
                 "**Accounts posting**: {authors} different people wrote those posts.",
                 "**Profiles**: people whose profile (bio, followers) we have.",
                 "**Interactions mapped**: {edges} times someone replied to, quoted or retweeted someone. This "
                 "is how we know *who talks to whom*.",
                 "**Left sidebar**: ✅ finished and checked · 🟡 finished, still being tested · ⬜ not built. "
                 "The coloured box at the bottom says whether the trust checks passed."],
        "do": ["Start here. If the sidebar shows ❌, go to **✅ Proof & trust** first. Otherwise go to "
               "**2 · Engage today** (daily) or **🧠 What it learned** (weekly)."],
        "columns": {},
    },
    "1a": {
        "what": ["Every person we've collected, sorted into **B2B**, **AI**, **Tech** or **off-topic**.",
                 "- **B2B**: people selling to businesses: founders, sales, outbound, cold email, RevOps, "
                 "lead-gen agencies.",
                 "- **AI**: people building with AI: AI agents, Claude/GPT workflows, automation (n8n, Make).",
                 "- **Tech**: SaaS and startup founders: build in public, MRR, churn, indie hackers.",
                 "- **Off-topic**: crypto, giveaways, gaming, politics, stock tips, or too little to judge."],
        "where": PEOPLE_SOURCES + ["So far: **{in_niche}** people are in a niche, out of **{authors}** collected. "
                                   "Most people who reply on X are bots or off-topic, and filtering them out is "
                                   "the point."],
        "read": ["**In-niche vs off-topic**: out of 100 accounts, how many it correctly calls \"ours\" or "
                 "\"not ours\". For example, 93.5% = right about 93 times in 100.",
                 "**Main or 2nd segment right**: for in-niche people, how often the right niche is its first "
                 "*or* second guess (many people are two things, like an AI founder selling to businesses).",
                 "**Exact segment**: how often its *first* guess alone is right. Lower, because of those "
                 "two-niche people.",
                 "**✓ passes 80%**: it beat the quality bar we set before trusting it.",
                 "**Hand labels**: how many accounts people checked by hand to grade it. The model never saw "
                 "these answers while learning, so the score is honest."],
        "do": ["Use the **Account explorer**: pick a niche, slide **Min confidence** up to see only the obvious "
               "ones, read a few bios. If someone is clearly wrong, fix it in **1A · Review**."],
        "columns": {"username / Profile": "the X account (click to open)",
                    "Main": "the niche it belongs to most",
                    "2nd": "a second niche, if it clearly has one",
                    "confidence": "how sure the model is (0 to 1). 0.9 = very sure; 0.4 = borderline",
                    "Posts seen": "how many of their posts the model read",
                    "Followers": "their follower count",
                    "bio": "their X bio"},
    },
    "1a_review": {
        "what": ["A short list of accounts where the model might be wrong, for your team to check."],
        "where": ["Each week the **AI reviewer** (Claude) checks hundreds of accounts. This list shows the ones "
                  "where the **AI and the model disagree** (where mistakes hide), plus a few **random audits** "
                  "where they agree (to check the AI itself is honest)."],
        "read": ["**Model said / Model 2nd**: the model's niche guess.",
                 "**AI said / AI's reason**: the AI reviewer's guess and why.",
                 "**Your agreement with the model**: of the ones you ticked, how often you agreed."],
        "do": ["Open the profile, read the bio and posts, pick the right niche in **Correct segment**, tick "
               "**Reviewed**, then press **Save**. About **30 answers** (around 10 minutes) clears the two "
               "warnings in Proof & trust, and the next weekly run learns from your answers."],
        "columns": {"Why you see it": "\"AI and model disagree\" or \"random audit\"",
                    "Model said": "the model's main niche", "Model 2nd": "the model's second niche",
                    "AI said": "the AI reviewer's niche", "AI's reason": "why the AI chose it",
                    "Correct segment": "**you fill this in**: the right answer",
                    "Reviewed": "**tick** when you've checked it"},
    },
    "1b_core": {
        "what": ["The **hubs** of each niche: the big accounts that B2B, AI or Tech people follow, reply to and "
                 "quote the most."],
        "where": ["From the interactions we collected (who replies to and quotes whom). An account becomes a hub "
                  "when **many in-niche people** engage with it, not just many people."],
        "read": ["**Rank**: 1 = most important hub in this niche.",
                 "Accounts that post engagement bait (\"HOLY F*CK…\", \"goldmine\", \"comment to get\") are "
                 "pushed down, because their crowd is not a real niche audience."],
        "do": ["Nothing to do here day to day. It is the foundation for the **seed map** in the next tab."],
        "columns": {"rank": "1 = most important hub",
                    "niche_p": "how sure we are this hub is in the niche (0 to 1)",
                    "Followers": "their follower count",
                    "Niche engagers": "how many **in-niche** people reply to or quote them",
                    "Niche share": "of everyone engaging with them, the share who are in the niche (0.6 = 60%)",
                    "Bait share": "share of their posts that are engagement bait (lower is better)",
                    "Client": "ticked if it's one of our clients"},
    },
    "1b_seeds": {
        "what": ["The **seed map**: the people each niche actually talks to. These are the people clients should "
                 "reply to and engage with, so X learns the client belongs in that conversation."],
        "where": ["Built from the hubs (previous tab): anyone the hubs reply to, quote or retweet, and anyone who "
                  "replies to the hubs, then kept only if they're in the niche themselves. Giant accounts "
                  "(over 3M followers) are left out because they never reply back."],
        "read": ["**Score**: how strongly they're tied to the niche (more hubs, more two-way talk = higher).",
                 "**Reason** says it in words, e.g. *\"25 core accts (32 from core, 20 to core)\"* = 25 different "
                 "hubs talk with them; hubs engaged with them 32 times, and they engaged with hubs 20 times."],
        "do": ["You don't need to act here. The **2 · Engage today** list is picked from these people "
               "automatically. You can download a map to look through it."],
        "columns": {"rank": "1 = strongest tie to the niche", "score": "the seed score",
                    "Core accts": "how many different hubs they talk with",
                    "Core → them": "times hubs replied to / quoted / retweeted them",
                    "Them → core": "times they replied to / quoted / retweeted hubs",
                    "niche_p": "how sure we are they're in the niche (0 to 1)",
                    "known": "their niche is known from their own bio or posts",
                    "Followers": "their follower count", "reason": "the score explained in words"},
    },
    "clients": {
        "what": ["The test of the seed map: **does it really contain the people who engage with each client?**"],
        "where": ["The seed map was rebuilt **with all client data removed**. Then we took each client's real "
                  "repliers and quoters from the last 60 days and checked how many are in that map, versus "
                  "random accounts."],
        "read": ["**In seed map**: share of the client's real engagers that the map found (e.g. 24%).",
                 "**Baseline**: share of *random* accounts in the map (e.g. 4%).",
                 "**Lift** = in seed map ÷ baseline. **5.7×** = the map is 5.7 times better than random at "
                 "finding Michel's real audience. Above 1× = the map works.",
                 "**Lift range**: where the true lift very likely sits. If even the low end is above 1×, it's "
                 "**proven**. Clients with few engagers get a wide range and are marked weak."],
        "do": ["The \"in seed map\" share is each client's **starting point**. Phase 2 tries to raise it. "
               "The table at the bottom shows which niche each client belongs to."],
        "columns": {"client": "the client", "segments": "the client's niche(s)",
                    "engagers": "how many real engagers we tested with",
                    "in_seed_map": "share of them found in the seed map",
                    "baseline": "share of random accounts found in the map",
                    "lift": "in_seed_map ÷ baseline (1× = no better than random)",
                    "lift_lo / lift_hi": "the likely range of the lift"},
    },
    "1c": {
        "what": ["What kind of posts work **for this client**: format, opening line, topic, length, time and "
                 "day, compared with **their own** usual post."],
        "where": ["The client's own original posts from the last year (replies and retweets left out), with "
                  "likes, replies, quotes, reposts and views from xplatform, refreshed daily. Posts under 48h "
                  "old are skipped because their numbers are still growing."],
        "read": ["Every post gets an **X-score** using X's published weights: replies ×5, quotes ×5, "
                 "reposts ×1, likes ×0.708. It's then compared with the median of the client's previous 20 posts.",
                 "**1.0× = a normal post for this person.** 2.0× = twice as good. 0.5× = half as good.",
                 "**Range** (e.g. 1.7×–5.4×): where the true effect very likely is. A pattern is **proven** only "
                 "when the whole range is above (or below) 1×.",
                 "**Right audience / Niche share**: of the people engaging, the share in the client's niche.",
                 "**Light bars** in the chart = fewer than 5 posts, too few to trust."],
        "do": ["Use the **Simple plan** line (proven patterns only) when writing for this client. ❔ *not proven* "
               "patterns are hints only; don't build on them."],
        "columns": {"vs baseline": "this post vs the client's usual (1.0× = normal)",
                    "Views": "how many times it was seen",
                    "format": "single post, thread, quote post, article…",
                    "hook": "the type of opening line",
                    "topic": "what it's about",
                    "Niche share": "share of its engagers in the client's niche",
                    "text / url": "the post itself"},
    },
    "1d": {
        "what": ["A model that estimates, **before posting**, whether a draft will do better or worse than the "
                 "client's usual post, and why."],
        "where": ["Trained on posts **before 15 Oct 2026** and tested on posts **after** it, so it was graded on "
                  "posts it had never seen. Since then, a **live test** scores each new client post early and "
                  "checks it 48h later."],
        "read": ["It's compared with two simple rules: **A** = \"every post does the client's usual\", **B** = "
                 "usual × X's published rules. The model must beat both.",
                 "**Within-author Spearman**: does it put one client's posts in the right order? 0 = random, "
                 "1 = perfect. Small positive numbers (like 0.18) are normal for social posts; what matters is "
                 "beating A and B.",
                 "**Top-20% hit rate**: of the posts it picks as a client's best fifth, how many really were. "
                 "Random = 20%.",
                 "**Mean abs error (log)**: how far off its estimates are. Lower is better.",
                 "**Expected vs usual** (live test): 1.3× = it expected 30% better than usual."],
        "do": ["Wait for the live verdict (~21 Nov) before relying on it. Until then, use it as a second opinion "
               "on drafts, not a decision."],
        "columns": {"predictor": "the model or a simple rule it's compared with",
                    "within_author_spearman": "ordering skill within one client (0 random, 1 perfect)",
                    "top20_hit_rate": "picks a client's best fifth correctly (random = 20%)",
                    "mae_log": "size of its errors (lower = better)",
                    "authors": "how many accounts it was tested on",
                    "scored_at_age_h": "how old the post was when scored (hours)",
                    "expected_vs_usual": "the model's estimate vs the client's usual"},
    },
    "engage": {
        "what": ["**The daily to-do list**: posts from the right people that each pilot client should reply to "
                 "today. Only for the 3 pilot clients (Alex, Kenny, Nikola)."],
        "where": ["Every morning (06:00 UTC) we collect the newest posts from people in each client's seed map. "
                  "We rank them by how strongly the person is tied to the niche, how fresh the post is, and "
                  "whether it's on a topic the client posts about. Then the **AI reviewer** removes posts not "
                  "worth replying to. One post per person, 20 per client."],
        "read": ["**#**: order to work through (1 first).",
                 "**Why it's on the list**: e.g. *\"in Alex's B2B seed map (#88, talks with 6 niche hubs); posted "
                 "1h ago; on a topic the client posts about; asks a question\"*.",
                 "**Worth replying?** (bottom table): the AI's verdict is pre-ticked; the goal is 80%+ worth it."],
        "do": ["Each day, open each post (**reply ↗**) and write a genuine reply from the client's account. "
               "**Don't** use the list for the comparison clients (Michel, Mai, Vick), or the test breaks. "
               "Spot-check the bottom table and save."],
        "columns": {"#": "work order", "Account": "who wrote the post",
                    "Their post": "the post to reply to",
                    "Why it's on the list": "why this person and post were picked",
                    "Open on X": "opens the post so you can reply",
                    "Worth replying?": "tick if it's genuinely worth replying to",
                    "AI reviewer": "the AI's verdict and reason"},
    },
    "results": {
        "what": ["The Phase 2 experiment: **does replying to the right people make the right people engage back?**"],
        "where": ["3 clients **get the list** (Alex, Kenny, Nikola) and 3 similar clients **don't** (Michel, Mai, "
                  "Vick). Pairs: Alex↔Michel, Kenny↔Mai, Nikola↔Vick. Comparing them separates the list's effect "
                  "from things that hit everyone (a holiday, an X update). Lists started **{p2_start}**."],
        "read": ["**Right-audience share**: of the people who engaged with the client that week, the share in "
                 "the client's niche. That's the number we want to rise.",
                 "**Solid lines** = clients who get the list. **Dashed** = comparison clients. **Grey line** = "
                 "lists started.",
                 "It works if solid lines **rise more than dashed lines** after the grey line.",
                 "**Reply-back**: of accounts a client replied to, the share who replied to or quoted the client "
                 "within 14 days."],
        "do": ["First signal ~14 Nov, verdict ~5 Dec. With 3 vs 3 clients it shows **direction, not proof**, so "
               "don't change the plan on one week's numbers."],
        "columns": {"group": "treatment = gets the list; control = doesn't",
                    "week": "the week (starting Monday)", "engagers": "people who engaged that week",
                    "niche_share": "share of them in the client's niche",
                    "period": "before or after the lists started"},
    },
    "proof": {
        "what": ["The checks that tell you **whether the numbers in this app can be believed**."],
        "where": ["Run automatically after every GitHub run (every 4 hours, daily and weekly), on the same data "
                  "the app shows."],
        "read": ["**Trust checks**: ✅ passed · ⚠️ true but don't lean on it yet · ❌ something is wrong (stop and "
                 "fix). They check that our data matches xplatform, that no future data leaks into tests, that "
                 "data is fresh, and that there's enough data behind each claim.",
                 "**Claims table**: every number the app states, with its **95% range** and **n** (how many posts "
                 "or accounts it rests on).",
                 "**Status**: *proven* = the whole range clears the bar · *measured* = a plain fact with its range "
                 "· *weak* = too little data · *not proven* = the range still includes \"no effect\" · *habit / "
                 "emerging since …* = from the memory tab."],
        "do": ["If you see ❌, tell me and don't act on the affected numbers until it's ✅. ⚠️ needs nothing urgent; "
               "the current ones clear when your team does ~30 reviews in **1A · Review**."],
        "columns": {"step": "which part (1A, 1B, 1C, 1D, 2A, memory)", "client": "which client (blank = all)",
                    "claim": "what is being claimed", "Value": "the number",
                    "95% range": "where the true value very likely is",
                    "Based on (n)": "how many posts or accounts", "Status": "proven / measured / weak / not proven",
                    "method": "how it was measured", "evidence": "the file holding the raw data"},
    },
    "predict": {
        "what": ["Paste a draft and see, **before it goes out**, how many views, likes, replies, reposts, quotes "
                 "and bookmarks it should get, each with a range, compared with the client's usual post.",
                 "Paste two versions to see which one should do better."],
        "where": ["Trained on ~45,000 real X posts from 800+ accounts in our niches (from xplatform), each judged "
                  "against **its own author's usual level**.",
                  "X's open-sourced ranking code (`xai-org/x-algorithm`, pinned commit) supplies the X score weights "
                  "(reply 5, quote 5, repost 1, like 0.708) and rules such as the same-day diversity decay.",
                  "The client's usual level only uses posts that had 48h to finish growing, exactly as it would be "
                  "known in real life."],
        "read": ["**Expected**: the middle estimate. **80% range**: 8 in 10 posts land inside it (checked on posts "
                 "the model never saw). A wide range means the model is honestly unsure.",
                 "**vs usual**: 1.3× = about 30% better than this client's typical post.",
                 "**Why**: the main things pushing this estimate up or down (format, length, time, text…).",
                 "Exact numbers can't be known before posting: the same post can get 5k or 50k views depending on who "
                 "is online. The **Measured accuracy** box shows how far off it usually is."],
        "do": ["Use it to **choose between drafts** and to spot weak ones before they go out. Don't promise a "
               "client an exact number; promise the range."],
        "columns": {"Action": "what X counts", "Expected": "middle estimate", "80% range": "8 in 10 posts land here",
                    "Usual": "the client's typical post (median of recent matured posts)",
                    "vs usual": "expected ÷ usual"},
    },
    "memory": {
        "what": ["What the system has **learned and remembers** about each client's content, week by week, "
                 "like habits."],
        "where": ["Every Sunday it looks at the week's posts (only posts 48h+ old) and records how each pattern "
                  "did. Old weeks are never rewritten. Small clients borrow what works for **all** clients until "
                  "they have enough posts of their own (each client counts equally)."],
        "read": ["🔁 **Habit**: worked **3 weeks in a row**, so it goes into the plan.",
                 "🌱 **Emerging**: worked in 2 of the last 3 weeks; newer, still being confirmed.",
                 "🍂 **Fading**: used to work, not lately. 🗑 **Forgotten**: dropped from the plan.",
                 "**Chart**: the line is the pattern's effect each week; the band is its likely range. When the "
                 "whole band is above the dashed 1.0 line, it worked that week.",
                 "**Surprises**: posts that did 3× better or worse than predicted. After 10 judged posts, the "
                 "client's predictions get corrected."],
        "do": ["Read the **Plan from memory** line for each client and use it when writing. It's the most "
               "reliable content advice in the app."],
        "columns": {"created_at": "when the post went out", "expected_xscore": "what the model expected",
                    "actual": "what really happened (X-score)",
                    "actual_vs_expected": "actual ÷ expected (3 = three times better than expected)"},
    },
}


def tab_guide(key: str, **numbers) -> None:
    """Render the four-part plain-words guide and the column guide for one tab."""
    g = GUIDE[key]
    vals = defaultdict(lambda: "—", {k: (f"{v:,}" if isinstance(v, int) else v) for k, v in numbers.items()})
    with st.expander("🔎 **What this tab means**: what you see, where the data comes from, how to read it",
                     expanded=True):
        for part, title in HEADINGS.items():
            st.markdown(f"**{title}**")
            st.markdown("\n".join(l if l.startswith(("- ", "1.", "2.", "3.", "4."))
                                  else f"- {l}" for l in (x.format_map(vals) for x in g[part])))
    if g["columns"]:
        with st.expander("📋 **What each column means**", expanded=False):
            st.markdown("\n".join(f"- **{c}**: {m}" for c, m in g["columns"].items()))
