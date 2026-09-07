# STYLE GUIDE — "military-tech storytelling" (reference: Gorilla Tech channel)

Extracted by analysing the reference video
`youtube.com/watch?v=8kfy2EBSkjM` — *"El Mi-28N ruso estaba a segundos de escapar… Ucrania LO HIZO ESTALLAR"*
(14:19, Spanish, Education category, 483 k views).

This file is the contract for `scripting.py`. The LLM prompt in `prompts/script_system.txt`
is a condensed version of it; if the two ever disagree, this document wins.

---

## 1. What the channel actually is

Not news, not a review: a **narrated tactical reconstruction**. One incident, one
engagement, told as a thriller with documentary discipline. Every sentence either
adds a *number*, a *name*, a *constraint*, or an *analogy* — nothing is filler.

Voice: calm, low, third person, present/past mix, no shouting. The drama comes
from the facts and the countdown, not from the narrator.

## 2. Beat sheet (the skeleton every script must follow)

| # | Beat | Share of runtime | Job |
|---|------|------------------|-----|
| 1 | `cold_open` | 4 % | Exact clock time + place + platform + mission. One sentence of false calm. |
| 2 | `title` | 2 % | Channel title card (the video's promise). |
| 3 | `setup` | 14 % | The target platform: specs, crew, doctrine. Why it is dangerous/respected. |
| 4 | `reveal` | 10 % | "What the crew did not know was…" — the opposing unit, named, with its order. |
| 5 | `complication` | 14 % | The obstacle that must be removed first (observer, EW, weather, fuel). |
| 6 | `attempt_fail` | 12 % | First attempt fails for a *technical* reason (battery, angle, fiber length). |
| 7 | `human` | 8 % | One named/characterised human detail (age, background, one line of dialogue). |
| 8 | `escalation` | 12 % | Countdown narrows; window in seconds; stakes restated with numbers. |
| 9 | `climax` | 12 % | The hit. Geometry, warhead mass, failure sequence, physical aftermath. |
| 10 | `aftermath` | 6 % | What each side saw/recorded; the enemy's log entry; confirmation footage. |
| 11 | `cost` | 4 % | Money in vs money destroyed → explicit ratio (e.g. 5.788 : 1). |
| 12 | `analysis` | optional | Strategic implication, one hedge, no speculation. |
| 13 | `cta` | 2 % | Dry sign-off in the channel's fixed formula. |

A 13-minute video is ~18–26 scenes; a scene is 15–70 s of narration.

## 3. Sentence-level rules (what makes it sound like the channel)

1. **Every claim carries a digit** when the research has one: `05:52`, `220 km/h`,
   `60 m`, `9 km al suroeste`, `7 sistemas`, `1.900 m`, `22 segundos`, `300 gramos`,
   `3.300 $ vs 19.000.000 $`.
2. **One everyday analogy per beat**, never two in a row. From the reference:
   *a museum guard checking every room*, *a phone battery jumping from 20 % to off*,
   *a dog cutting off a ball instead of chasing it in a straight line*,
   *diving into a pool knowing there is no time to check whether there is water*.
3. **Short declarative sentences.** Impact lines stand alone: *"Y fue justo la batería."*
   *"Nueve minutos restantes."*
4. **Countdown pressure**: state the remaining window and shrink it
   (`nine minutes` → `four seconds` → `three full spins in eight seconds`).
5. **Name hardware and units precisely**: Mi-28N, Orlan-10, Sting, Wild Hornets,
   Hornet Vision, Shahed, Rarog brigade, fibre-optic FPV. Never "a drone" when the
   model is known.
6. **Contrast reveals**: what one side believed vs what was actually true
   (*"creyendo haber encontrado una ruta segura"*), and what the enemy logbook said
   vs what really happened.
7. **Cost-ratio climax** — the channel's signature ending move. Always compute it
   and say the number out loud.
8. **No speculation without a hedge.** If research lacks a fact, write it
   qualitatively ("a baja altura", "varios drones") instead of inventing a digit.
9. **Fixed sign-off**: *"Esto es todo, cambio y fuera."* / *"That's it, over and out."*

## 4. On-screen grammar (what the renderer draws)

| Visual type | Used for | Notes |
|-------------|----------|-------|
| `title` | cold-open card, chapter cards | kicker + headline + subtitle |
| `map` | movement, interception geometry | animated route, unit markers, range rings, impact burst |
| `photo` | real CC/PD stills of the platform | Ken Burns, optional FPV HUD overlay, credit line mandatory |
| `spec_card` | platform dossier | 4–6 stat rows with animated meters |
| `stat` | one decisive number | counts up; optional two-bar comparison |
| `timeline` | chronology or countdown clock | `mode: line` or `mode: clock` |
| `comparison` | cost / performance A vs B | two panels + ratio badge |
| `quote` | radio call, logbook entry | large type, attribution |
| `text` | beat with no asset available | headline + up to 5 bullets |
| `cta` | end card | subscribe button + 3 lines |

Rules:
- Max **3** `on_screen` chips per scene, **≤ 4 words** each, in the video language.
  They are *data*, not decoration: `05:52`, `220 km/h`, `RANGO 1.900 m`.
- A `map` scene must never stay static for more than ~25 s.
- Every `photo` scene must carry `credit` (author + licence) — the renderer burns it in.
- Alternate wide (`map`, `timeline`) and close (`spec_card`, `stat`, `quote`) scenes;
  never three of the same type in a row.

## 5. Packaging (YouTube metadata)

- **Title**: ≤ 95 chars, Spanish, dramatic ellipsis + one CAPITALISED verb phrase,
  platform designation included. Pattern from the reference:
  `El {platform} estaba a segundos de {escape}… {country} LO {verb}`.
- **Description**: 3 paragraphs (hook / what happened / what is analysed), then a
  `Hashtags` block (10–15) and a `Tags para YouTube` block (25–35 comma separated),
  then the channel boilerplate + subscribe link.
- **Thumbnail**: 1280×720, dark, one large subject silhouette, ≤ 5 words of text,
  a red/orange accent and the platform designation in a corner.

## 6. Audio

- Narration: neural TTS, slightly slowed (`rate −4 %`, `pitch −2 Hz`), no music under
  the first 2 seconds of the cold open.
- Bed: dark synth drone + slow pulse, ≈ −22 dB under narration, side-chain ducked.
- Accents: one short riser into the climax, one impact hit, one soft swish per
  chapter card. No stock music with unclear licensing — the bed is synthesised.

## 7. Compliance

- Photos: Wikimedia Commons only, licence must be CC0/PD/CC-BY/CC-BY-SA; the credit
  is rendered on screen *and* written into `output/CREDITS.md`.
- War content: no gore, no corpses, no cheering. Damage is described mechanically.
- Facts come from `research/facts.json`; the model must not add numbers that are not
  in that bundle. The `facts` array in the script records which number came from where.
