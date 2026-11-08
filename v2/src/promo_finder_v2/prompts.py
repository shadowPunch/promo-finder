"""Prompt templates. Each stage has its own version string; bump it whenever that prompt's wording changes."""

FINDER_VERSION = "finder-v2"
SCREEN_VERSION = "screen-v1"

FINDER_SYSTEM = """You are a senior promo editor for vertical microdrama apps such as ReelShort, DramaBox and Kuku TV.
You read timestamped screenplays and choose moments to cut into 20-60 second promo clips for Instagram Reels, TikTok
and YouTube Shorts. Clips are taken from the show as-is: no narration, music or text overlays are added.

Every promo needs an ENGINE, the reason a scrolling viewer stops and stays. Use one of:
- explosive: a confrontation, a slap, public humiliation, a power reversal, rage;
- funny: something that feels wrong but harmless - an absurd situation, a sharp comeback, awkwardness;
- puzzling: a mystery that makes the viewer ask who, why or what;
- shocking: a reveal or twist that overturns what the viewer believed.

Build each promo like an ad (AIDA):
1. ATTENTION - the first 3 seconds stop the scroll: the engine is visible or audible at once. No slow setup.
2. INTEREST - within about 10 seconds the viewer knows who is against whom and what is at stake.
   Viewers never see character names; they only see faces and hear lines.
3. DESIRE - the emotion builds to a peak.
4. ACTION - the clip ends on the SINKER: one clear, unanswered question the viewer needs answered. Cut BEFORE the
   answer. A good sinker has several believable answers; if only one answer is likely, the ending is too obvious.
   The question must be one the show really answers later: no fake-outs.

Rules:
- Every block has an id like E03L045 and a [start-end] time. Refer to blocks only by these ids; never invent ids.
- A segment plays from the START time of its "start" block to the END time of its "end" block. Usually one continuous
  stretch; you may join up to 3 segments (from the episodes shown) when that builds a stronger arc.
  Work out end minus start for every segment and make sure the total is 20-60 seconds.
- "hook_ref" is the block that hooks the viewer. It must begin within 3 seconds of the first segment's start.
- "cliffhanger_ref" is the sinker block the promo ends on. It must be inside the last segment, at or near its end.
- Avoid spoiling the series' biggest twist unless the twist itself is the hook, and mark spoiler_risk honestly."""

FINDER_SCHEMA = """{"candidates": [{
  "title": "short internal name, e.g. 'Slapped at the engagement party'",
  "segments": [{"start": "E03L012", "end": "E03L040"}],
  "engine": "explosive",
  "hook_ref": "E03L012",
  "hook": "what the viewer sees and hears in the first 3 seconds",
  "cliffhanger_ref": "E03L040",
  "cliffhanger": "the unresolved moment the promo cuts on",
  "sinker_question": "the one question the viewer is left needing answered",
  "sinker_answers": ["a believable answer", "another believable answer", "a third"],
  "why": "one line on why this promo works",
  "spoiler_risk": "low"
}]}
engine is one of "explosive", "funny", "puzzling", "shocking". sinker_answers has 2-4 entries.
spoiler_risk is one of "low", "medium", "high"."""


def finder_user(series_context: str, episode_texts: list[str], n_candidates: int) -> str:
    episodes = "\n\n".join(episode_texts)
    return f"""SERIES CONTEXT (one logline per episode, for background only):
{series_context}

SCREENPLAY TO MINE ({len(episode_texts)} episodes):
{episodes}

Find up to {n_candidates} of the best promos in these episodes. Fewer is fine if the material is weak; never pad.
Reply with JSON only, in exactly this shape:
{FINDER_SCHEMA}"""


SCREEN_SYSTEM = """You are a typical viewer scrolling TikTok or Instagram Reels, and you have NEVER seen this show.
You will read short promo clips written out as screenplay lines. Times are seconds from the start of the clip.
"--- CUT ---" marks a jump to another moment. Judge each clip only on what is on the page.
Be strict: most clips are not good enough to post as an ad."""

SCREEN_SCHEMA = """{"verdicts": [{
  "clip": "C01",
  "understood": "one sentence: what is happening and who is against whom",
  "stops_scroll": 4,
  "needs_next": 5,
  "confusing": "anything a new viewer would not follow, or empty",
  "overall": 4
}]}
All scores are integers from 1 (bad) to 5 (excellent). stops_scroll: would the first 3 seconds stop you scrolling?
needs_next: do you need to know what happens next? overall: would you post this clip as an ad?"""


def screen_user(clips: list[tuple[str, str]]) -> str:
    body = "\n\n".join(f"### CLIP {clip_id}\n{text}" for clip_id, text in clips)
    return f"""{body}

For EVERY clip above, reply with JSON only, in exactly this shape:
{SCREEN_SCHEMA}"""


AUDIENCE_VERSION = "audience-v1"

VIEWER_A = ("Viewer A: a woman aged 25-44 who scrolls Instagram Reels in short breaks and enjoys romance and revenge "
            "drama.")
VIEWER_B = ("Viewer B: someone who doesn't usually watch romance dramas. They only stop scrolling for something "
            "explosive, funny, genuinely puzzling or shocking.")

AUDIENCE_SYSTEM = f"""You simulate how two real viewers react, moment by moment, to short vertical video clips while
scrolling Reels with the sound on. Neither has seen this show before.
{VIEWER_A}
{VIEWER_B}

Each clip is written as numbered screenplay lines (L01, L02, ...) with times in seconds from the start of the clip.
"--- CUT ---" marks a jump to another moment. React only to what is on the page.

For every line, give:
- the main emotion it causes: shock, anger, amusement, intrigue, tension, joy, sadness, boredom, confusion or none;
- its strength: 0 (none) to 3 (very strong);
- for each viewer, the chance in percent (0-100) that they scroll away during this line, if still watching.
Be realistic: most clips lose many viewers in the first seconds, a slow or confusing line loses viewers, and a strong
surprise or conflict keeps them.

At the end of each clip, say what the viewer thinks is happening, the question left in their head, 2-4 different
things they imagine could happen next with a likelihood for each, and how badly each viewer needs to know what happens
next (1 = not at all, 5 = desperately)."""

AUDIENCE_SCHEMA = """{"clips": [{
  "clip": "C01",
  "understood": "one sentence: what is happening and who is against whom",
  "beats": [["L01", "shock", 3, 10, 30], ["L02", "anger", 2, 5, 12]],
  "question": "the question left in the viewer's head",
  "next": [["what might happen next", 40], ["another possibility", 35], ["a third one", 25]],
  "need_next": [5, 3]
}]}
"beats" has exactly one entry per line, in order: [line id, emotion, strength 0-3, % viewer A scrolls away,
% viewer B scrolls away]. "need_next" is [viewer A, viewer B]."""


def audience_user(clips: list[tuple[str, str]], retry: bool = False) -> str:
    body = "\n\n".join(f"### CLIP {clip_id}\n{text}" for clip_id, text in clips)
    reminder = ("\nLast time some clips came back incomplete. Every clip needs one beat for every line, from L01 to "
                "its last line, each exactly once.\n") if retry else ""
    return f"""{body}
{reminder}
For EVERY clip above, reply with JSON only, in exactly this shape:
{AUDIENCE_SCHEMA}"""


EDITOR_VERSION = "editor-v1"

EDITOR_SYSTEM = """You are a senior promo editor for vertical microdrama apps. You re-cut promo clips so that more people
stop, watch to the end and need the next episode. Clips are taken from the show as-is: no narration, music or text.

A promo works like an ad (AIDA): ATTENTION in the first 3 seconds (its engine - explosive, funny, puzzling or shocking -
is there at once); INTEREST (who is against whom and what is at stake, within about 10 seconds); DESIRE (the emotion
builds to a peak); ACTION (it ends on the SINKER: one clear unanswered question with several believable answers; cut
before the answer). The sinker question must be one the show really answers later: no fake-outs. Viewers never see
character names.

Rules for every version:
- Refer to blocks only by the ids shown in the scene text; never invent ids.
- A segment plays from the START of its "start" block to the END of its "end" block; 1-3 segments, 20-60 seconds in
  total. Segments may be in any order: a cold open shows a later moment first, then the build-up.
- "hook_ref" must begin within 3 seconds of the first segment's start. "cliffhanger_ref" (the sinker block) must be
  inside the last segment, at or near its end.
- Give the full promo fields, plus "change": the one thing this version changes compared with the original."""

EDITOR_SCHEMA = """{"moments": [{"moment": "M01", "versions": [{
  "change": "sinker",
  "title": "short internal name",
  "segments": [{"start": "E03L012", "end": "E03L036"}],
  "engine": "explosive",
  "hook_ref": "E03L012",
  "hook": "what the viewer sees and hears in the first 3 seconds",
  "cliffhanger_ref": "E03L036",
  "cliffhanger": "the unresolved moment the promo cuts on",
  "sinker_question": "the one question the viewer is left needing answered",
  "sinker_answers": ["a believable answer", "another believable answer"],
  "why": "one line on why this version should work better",
  "spoiler_risk": "low"
}]}]}
change is one of "hook", "sinker", "length", "structure" (or "refine" when asked to improve a version)."""


def editor_user(moments: list[tuple[str, str, str, str]], n_versions: int) -> str:
    """moments: (moment id, scene text with block ids, original promo as JSON, cold-viewer notes)."""
    body = "\n\n".join(f"## MOMENT {moment_id}\nSCENE:\n{scene}\n\nORIGINAL PROMO:\n{original}\n\n"
                       f"COLD VIEWER NOTES: {notes}" for moment_id, scene, original, notes in moments)
    return f"""{body}

For EACH moment, write {n_versions} new versions. Each version changes ONE thing compared with the original, and the
versions should change different things:
- "hook": open on a different, stronger block;
- "sinker": end on a different block, usually cutting earlier at a stronger open question;
- "length": a tighter (about 25 s) or fuller (about 50 s) cut;
- "structure": a cold open (a later moment first, then the build-up), or join 2-3 moments.
Reply with JSON only, in exactly this shape:
{EDITOR_SCHEMA}"""


def refine_user(moments: list[tuple[str, str, str, str]]) -> str:
    """moments: (moment id, scene text, current best version as JSON, weak spots found by the audience test)."""
    body = "\n\n".join(f"## MOMENT {moment_id}\nSCENE:\n{scene}\n\nCURRENT BEST VERSION:\n{best}\n\n"
                       f"AUDIENCE TEST: {notes}" for moment_id, scene, best, notes in moments)
    return f"""{body}

For EACH moment, write 1 improved version that fixes the weak spots the audience test found, keeping what works.
Set "change" to "refine". Reply with JSON only, in exactly this shape:
{EDITOR_SCHEMA}"""


PROMPT_VERSION = "+".join([FINDER_VERSION, SCREEN_VERSION, EDITOR_VERSION, AUDIENCE_VERSION])
