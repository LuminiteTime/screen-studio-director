# From brief to storyboard

## Contents

- [Read the brief like a contract](#read-the-brief-like-a-contract)
- [Shape of a demo](#shape-of-a-demo)
- [Beats](#beats)
- [Caption copy](#caption-copy)
- [Length and format by destination](#length-and-format-by-destination)
- [Show the product, not the edit](#show-the-product-not-the-edit)
- [Iterating with the user](#iterating-with-the-user)

## Read the brief like a contract

Pull out every requirement and write it down before planning: what to show, what to skip, length,
language of captions, tone ("light", "premium", "fun"), music, destination, aspect ratio, branding,
deadline, whether to send drafts. Anything ambiguous with a sensible default: pick the default and say
which one you picked. Re-read the list before delivering; the user will judge the video against it.

## Shape of a demo

A product demo answers three questions in order: what is this, why should I care, how does it feel to
use it. The usual shape:

1. **Hook** (2-4 s): title card or the most striking moment. What it is in one line.
2. **Problem or promise** (optional, 3-5 s): one caption over the opening screen.
3. **Core flow** (most of the time): the main job done start to finish, in the product, with real data.
4. **Proof or differentiator**: the feature nobody else has, shown working.
5. **Breadth** (optional): one or two quick secondary features or a second surface (phone).
6. **Close** (3-5 s): name, one-line value, call to action (URL, store, "try it").

One continuous product story beats a feature tour. If there are two surfaces (web and phone), make it
one video that cuts between them where the story moves, not two videos.

## Beats

Plan the scenario as a table before writing code:

| # | Caption | Action on screen | Hold |
|---|---|---|---|
| 1 | Describe the hotel in your own words | click search, type the query | 1.5 s after typing |
| 2 | Each condition is checked against open data | hover the evidence chips | 2.5 s |
| 3 | Compare two hotels side by side | select two, click Compare | 3 s |

Rules of thumb:

- One idea per beat, one caption per beat.
- Every caption is proven by what is on screen at that moment.
- Real, plausible data. Empty states and lorem ipsum read as unfinished.
- Do the slow parts off camera (loading data, logging in) or speed them up in the project.
- 4-8 beats for a 60-90 s video.

## Caption copy

- Short: 3-8 words, at most two lines. The viewer is also watching the product.
- Benefit or action, in the user's words: "Find a quiet room near the beach", not "Semantic search
  module".
- Present tense, no exclamation marks, no "simply", "just", "seamlessly", "revolutionary".
- Same language as the product UI unless the brief says otherwise.
- The caption appears with the action, not after it.

## Length and format by destination

| Destination | Length | Aspect | Notes |
|---|---|---|---|
| Landing page hero | 20-60 s, loops | 16:9 | often muted: captions carry everything |
| Product Hunt / launch | 45-90 s | 16:9 | |
| YouTube | 1-3 min | 16:9 | |
| X / LinkedIn feed | 20-60 s | 16:9 or 1:1 | muted autoplay |
| Reels / Shorts / TikTok | 15-45 s | 9:16 | captions in the middle third, away from UI overlays |
| Hackathon / pitch | 60-120 s | 16:9 | judges watch once: story over features |
| Telegram / Slack share | any | any | bot upload limit 50 MB |

Make the 16:9 master first, then derive other aspects from the same takes with another timeline.

## Show the product, not the edit

Motion design supports the product, it never competes with it. Use soft crossfades (0.5-0.7 s),
captions that glide in with ease-out and fade quickly, light ambient music around -24 dB. Avoid
spins, zoom punches, glitch transitions, whooshes, text that animates letter by letter, and anything
that moves while the viewer is trying to read the product.

## Iterating with the user

- Send the first rough cut as soon as it exists, then improve. A wrong direction found at minute 10
  is cheap; at minute 60 it is a reshoot.
- When the user says something "looks off", pull stills at that moment and compare with what they
  describe before changing anything. "Touches are higher than the objects" was a capture bug, not
  an animation problem.
- Keep every take and export: re-cutting is cheap, reshooting is not.
