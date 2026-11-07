"""Plain-language explanations for every dashboard section, generated from the data.

Nothing here is hand-written per client: the same rules turn whatever the pipeline produced
into "do more / do less / simple plan" text, so the words stay true when the numbers change.
"""

from __future__ import annotations

import pandas as pd

MIN_POSTS = 5          # fewer posts than this in a group: not trusted, never recommended
GOOD, BAD = 1.15, 0.80  # median vs own usual level
FEW_POSTS_CLIENT = 100  # below this, the whole client gets an "early hints" warning

DIM_ORDER = ["hook", "format", "topic", "length", "hour_block", "day_slot"]

FORMAT_TEXT = {"article": "Articles", "thread": "Threads", "quote post": "Quote posts",
               "long-form post": "Long-form posts", "short + media": "Short posts with an image/video",
               "short text": "Short text posts"}
HOOK_TEXT = {"giveaway / comment-to-get": 'Giveaways ("comment X and I\'ll send it")',
             "number / result": 'Opening with numbers or results ("$1M ARR…")',
             "story": 'Story openers ("I…", "Last year we…")', "contrarian": 'Strong-opinion openers ("Stop…", "…is dead")',
             "how-to / list": 'How-to / list openers ("Here\'s how…", "5 steps…")',
             "question": "Opening with a question", "announcement": 'Announcements ("Introducing…")',
             "statement": "Plain statement openers", "media only": "Image/video with no text"}
HOOK_PLAN = {"giveaway / comment-to-get": "giveaways", "number / result": "numbers or results", "story": "a story",
             "contrarian": "a strong opinion", "how-to / list": "a how-to or list", "question": "a question",
             "announcement": "an announcement", "statement": "a plain statement", "media only": "just an image"}
LENGTH_TEXT = {"<100 chars": "Very short posts (under 100 characters)", "100-280": "Medium posts (100–280 characters)",
               "281-1,000": "Longer posts (281–1,000 characters)", "1,000+": "Long posts (1,000+ characters)"}
DAY_TEXT = {"1st post of day": "The 1st post of the day", "2nd": "A 2nd post in the same day",
            "3rd+": "A 3rd post in the same day"}


def label(dim: str, value: str) -> str:
    value = str(value)
    if dim == "format":
        return FORMAT_TEXT.get(value, value)
    if dim == "hook":
        return HOOK_TEXT.get(value, value)
    if dim == "length":
        return LENGTH_TEXT.get(value, value)
    if dim == "day_slot":
        return DAY_TEXT.get(value, value)
    if dim == "hour_block":
        return f"Posting at {value.replace('-', '–')}"
    if dim == "topic":
        words = []
        for part in value.split(" / "):
            for w in part.split():
                if w not in words:
                    words.append(w)
        return f'Posts about {", ".join(words[:3])}'
    if dim == "weekday":
        return f"Posting on {value}"
    return value


def groups(posts: pd.DataFrame, dim: str) -> pd.DataFrame:
    rows = []
    for key, g in posts.groupby(dim):
        r = g.rel_perf.dropna()
        rows.append({"dim": dim, "value": key, "posts": len(g),
                     "rel": r.median() if len(r) else float("nan"),
                     "niche": g.niche_share.mean()})
    return pd.DataFrame(rows)


def client_findings(posts: pd.DataFrame) -> dict:
    """Do-more / do-less items, reach-vs-niche flags and a one-line plan for one client."""
    avg_niche = posts.niche_share.mean()
    allg = pd.concat([groups(posts, d) for d in DIM_ORDER], ignore_index=True)
    ok = allg[(allg.posts >= MIN_POSTS) & allg.rel.notna()]

    def note(r) -> str:
        if pd.isna(r.niche) or pd.isna(avg_niche):
            return ""
        if r.rel >= 1.5 and r.niche <= avg_niche - 0.10:
            return f"big reach, but only {r.niche:.0%} of engagers are the right audience (usual {avg_niche:.0%}): use for reach, not for building the niche"
        if r.niche >= avg_niche + 0.15:
            return f"{r.niche:.0%} of engagers are the right audience (usual {avg_niche:.0%}): builds the niche"
        if r.niche <= 0.05 and r.posts >= MIN_POSTS:
            return "almost none of the engagers are the right audience"
        return ""

    more = ok[ok.rel >= GOOD].sort_values("rel", ascending=False)
    less = ok[ok.rel <= BAD].sort_values("rel")
    # right-audience builders even when reach is only average: worth keeping
    builders = ok[(ok.rel > BAD) & (ok.rel < GOOD) & ok.niche.notna() & (ok.niche >= avg_niche + 0.15)]
    fmt = lambda df: [{"text": label(r.dim, r.value), "rel": r.rel, "posts": int(r.posts), "note": note(r)}
                      for r in df.itertuples()]

    # The plan aims at the RIGHT audience: items that win only on reach (flagged above) are not
    # recommended as the default; they get their own "now and then, for reach" line instead.
    reach_only = lambda r: "use for reach" in note(r) or "almost none" in note(r)
    builds = lambda r: "builds the niche" in note(r)
    plan = []
    for dim in ["format", "hook", "topic", "hour_block"]:
        cand = [r for r in more[more.dim == dim].itertuples() if not reach_only(r)]
        if cand:
            t = label(dim, cand[0].value)
            plan.append(t if dim == "format" else ("open with " + HOOK_PLAN.get(str(cand[0].value), t.lower())
                                                   if dim == "hook" else t[0].lower() + t[1:]))
    for r in builders.itertuples():
        if r.dim in ("topic", "format", "hook"):
            plan.append(f"keep {label(r.dim, r.value)[0].lower() + label(r.dim, r.value)[1:]} going (right audience)")
            break
    third = ok[(ok.dim == "day_slot") & (ok.value == "3rd+")]
    second = ok[(ok.dim == "day_slot") & (ok.value == "2nd")]
    if len(third) and third.rel.iloc[0] <= BAD:
        plan.append("max 2 posts a day")
    elif len(second) and second.rel.iloc[0] <= BAD:
        plan.append("1 post a day")
    for r in less[less.dim.isin(["format", "hook"])].itertuples():
        t = label(r.dim, r.value)
        what = f"posts that open with {HOOK_PLAN.get(str(r.value), t.lower())}" if r.dim == "hook" else t[0].lower() + t[1:]
        plan.append(f"fewer {what}" + (" (low reach, though they do reach the right people)" if builds(r) else ""))
        break
    reach = [r for r in more.itertuples() if reach_only(r) and r.dim in ("hook", "format")]
    if reach:
        r0 = reach[0]
        what = HOOK_PLAN.get(str(r0.value)) if r0.dim == "hook" else label(r0.dim, r0.value).lower()
        plan.append(f"{what} only now and then, for reach")
    reach_rows = more[[reach_only(r) for r in more.itertuples()]] if len(more) else more
    good_rows = more[[not reach_only(r) for r in more.itertuples()]] if len(more) else more
    return {"n_posts": len(posts), "avg_niche": avg_niche, "few_posts": len(posts) < FEW_POSTS_CLIENT,
            "do_more": fmt(good_rows.head(6)), "reach_only": fmt(reach_rows.head(3)),
            "do_less": fmt(less.head(6)), "builders": fmt(builders.head(3)), "plan": plan}


def shared_lessons(perf: pd.DataFrame) -> list[str]:
    """Patterns that point the same way for every client with enough posts in that group."""
    out = []
    clients = perf.client.unique()
    for dim in ["format", "hook", "day_slot", "length"]:
        per = {c: groups(perf[perf.client == c], dim) for c in clients}
        values = set().union(*[set(g.value) for g in per.values()])
        for v in sorted(values):
            rels = [g.loc[(g.value == v) & (g.posts >= MIN_POSTS), "rel"] for g in per.values()]
            rels = [r.iloc[0] for r in rels if len(r)]
            if len(rels) >= 2 and len(rels) == len(clients) and all(r <= BAD for r in rels):
                out.append(f"**{label(dim, v)}** underperform for every client "
                           f"({', '.join(f'{r:.2f}×' for r in rels)}).")
            elif len(rels) >= 2 and len(rels) == len(clients) and all(r >= GOOD for r in rels):
                out.append(f"**{label(dim, v)}** work for every client ({', '.join(f'{r:.2f}×' for r in rels)}).")
    # reach vs right audience, across clients
    hook = perf.groupby("hook").agg(rel=("rel_perf", "median"), niche=("niche_share", "mean"), n=("hook", "size"))
    avg = perf.niche_share.mean()
    g = hook.loc["giveaway / comment-to-get"] if "giveaway / comment-to-get" in hook.index else None
    if g is not None and g.n >= MIN_POSTS and pd.notna(g.niche) and g.rel >= 1.5 and g.niche < avg:
        out.append(f"**Giveaways get more people, not the right people:** {g.rel:.1f}× reach, but only "
                   f"{g.niche:.0%} of engagers are in the niche (all posts: {avg:.0%}).")
    return out


def rel_words(x: float) -> str:
    if pd.isna(x):
        return "not enough data"
    if x >= 2:
        return f"{x:.1f}× (about {x:.0f}× as good as usual)"
    if x >= 1.05:
        return f"{x:.2f}× ({(x - 1):.0%} better than usual)"
    if x > 0.95:
        return f"{x:.2f}× (about normal)"
    return f"{x:.2f}× ({(1 - x):.0%} worse than usual)"


def holdout_sentence(r) -> str:
    small = r.engagers < 30
    s = (f"**@{r.client}:** of {r.engagers:,} people who really replied to or quoted them, **{r.in_seed_map:.0%}** are in "
         f"the seed map, against **{r.baseline:.0%}** of random accounts, so the map finds their real audience "
         f"**{r.lift:.1f}× better than chance**.")
    return s + (" ⚠ Only a few engagers, so this is weak evidence." if small else "")


def accuracy_sentence(m) -> list[str]:
    return [
        f"Out of 100 accounts, it correctly says **in our niche or not** about **{m.in_niche_accuracy * 100:.0f}** times.",
        f"It puts the account in the **right niche** (main or second choice) about **{m.segment_main_or_second * 100:.0f}** "
        f"times out of 100. Many people genuinely belong to two niches (an AI founder selling to businesses), so a "
        f"second choice is allowed.",
        f"Tested on accounts the model **never saw while learning** ({int(m.n_labels)} hand-checked accounts), so this "
        f"is an honest score, not homework it graded itself.",
    ]


def backtest_sentences(b: pd.DataFrame) -> list[str]:
    a, rules, m = b.iloc[0], b.iloc[1], b.iloc[2]
    best_base = max(a.within_author_spearman, rules.within_author_spearman)
    verdict = ("better than simple rules, but only modestly" if m.within_author_spearman - best_base < 0.3
               else "clearly better than simple rules")
    return [
        f"The model was trained on older posts and tested on **later posts it had never seen**.",
        f"**Ranking a client's posts in the right order** (0 = random, 1 = perfect): guessing \"same as usual\" "
        f"scores **{a.within_author_spearman:.2f}**, \"usual + X's published rules\" scores "
        f"**{rules.within_author_spearman:.2f}**, the model scores **{m.within_author_spearman:.2f}**.",
        f"**Picking the best fifth of posts:** the model gets **{m.top20_hit_rate:.0%}** right (random guessing gets 20%).",
        f"**What that means:** the model is {verdict}. Use it to **compare drafts and catch weak ones** before they go "
        f"out. It is **not** accurate enough to promise a client a number of views.",
    ]


def engage_sentences(client: str, n_listed: int, list_date, cov: pd.DataFrame) -> list[str]:
    """Plain words for the 'Engage today' tab. `cov` = engage_coverage rows for this client."""
    lines = [
        f"**What this is:** {n_listed} fresh posts (from the last 24 hours) by people in @{client}'s seed map: the "
        "audience we want X to connect @" + client + " with.",
        "**Why reply to these:** when the right people see the client in *their* conversations, and some reply "
        "back, X learns to show the client's own posts to that audience. A reply between two accounts that "
        "follow each other counts extra in X's published ranking.",
        "**How:** open the post, reply **in the client's own voice** with something real (add a point, a number, "
        "a short story, a question). No \"great post!\". About **10 good replies a day** beats 20 rushed ones.",
        "**Order:** the best mix of *who* (how central the person is in the niche), *how fresh* the post is, and "
        "*how open* it is to a reply (questions and opinions first). One post per person.",
    ]
    done = (cov[pd.to_datetime(cov.list_date) < pd.Timestamp(list_date).normalize().tz_localize(None)]
            if not cov.empty else cov)
    if len(done):
        listed, replied = int(done.listed.sum()), int(done.replied.sum())
        lines.append(f"**So far:** @{client} replied to **{replied} of {listed}** listed posts on earlier days "
                     f"({replied / listed:.0%}). Goal for week 1: at least half.")
    else:
        lines.append("**So far:** this is the first list. From tomorrow this shows how many listed posts the "
                     "client actually replied to, detected automatically from their real replies.")
    return lines


def tracking_sentences(weekly: pd.DataFrame, start, replies: pd.DataFrame, rb: pd.DataFrame) -> list[str]:
    """Plain words for the Phase 2 results tab."""
    lines = ["**The question:** does replying to the right people (the daily list) make the right people engage "
             "back? Three clients get the list, three similar clients don't (the comparison group), so we can "
             "tell the list apart from things that hit everyone (a holiday week, an X update)."]
    after = weekly[weekly.period == "after"] if len(weekly) else weekly
    if after.empty:
        lines.append(f"**Status:** lists started {pd.Timestamp(start):%d %b}. Before/after numbers need at least "
                     "one full week of lists; the plan judges this after about 4 weeks.")
    if len(weekly):
        before = weekly[weekly.period == "before"]
        for client, g in before.groupby("client"):
            grp = g.group.iloc[0]
            lines.append(f"**@{client}** ({'gets the list' if grp == 'treatment' else 'comparison'}): in the 4 weeks "
                         f"before, on average **{g.niche_share.mean():.0%}** of the people engaging were the right "
                         f"audience ({int(g.engagers.sum())} engagers).")
    if len(replies):
        r = replies[replies.period == "after"]
        if len(r):
            for client, g in r.groupby("client"):
                tot = int(g.replies.sum())
                lst = int(g.loc[g.tag == "listed", "replies"].sum())
                seed = int(g.loc[g.tag == "seed", "replies"].sum())
                lines.append(f"**@{client} since the start:** {tot} replies to others: {lst} to listed posts, "
                             f"{seed} to other seed-map people, {tot - lst - seed} to anyone else.")
    if len(rb) and rb.engaged_back.notna().any():
        done = rb.dropna(subset=["engaged_back"])
        lines.append(f"**Reply-back so far:** of {len(done)} accounts a client replied to (14+ days ago), "
                     f"{done.engaged_back.mean():.0%} replied to or quoted the client within 14 days.")
    lines.append("*With 3 vs 3 clients over a few weeks, the result shows direction, not proof.*")
    return lines
