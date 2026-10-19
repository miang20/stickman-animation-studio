# Stickman Animation Studio

A free-first, code-based 2D cartoon video renderer. It creates consistent, reusable stickman characters, colourful scenes, simple character motion, cinematic camera-style framing, captions, generated narration (eSpeak NG), a procedural music bed, and an MP4 artifact. No paid AI API or API key is required.

## Current scope

This is deterministic 2D animation, not generative-AI footage. Characters are drawn from reusable code definitions so their core appearance stays consistent across scenes. Motion is intentionally lightweight (walking/running gestures, bobbing, pointing and reactions) and can be expanded over time.

## How to use on Android

1. Open the **Actions** tab in this repository.
2. Select **Render Stickman Episode**.
3. Press **Run workflow** only when you're ready. (Do not run it during initial setup/review.)
4. Choose duration and resolution options, then start the workflow.
5. When it finishes, open the run and download the **stickman-episode-mp4** artifact ZIP. Extract the MP4 on your phone.

## Making a new episode

Edit `scripts/episode.json` on GitHub. Keep the same character IDs to preserve their designs. Each scene has a setting, action, dialogue/narration, and caption. The workflow uses the committed episode script; the run inputs control output duration and resolution.

## Free-tier notes

GitHub Actions usage limits apply. Long episodes at 1080p can take a while; start with 1 minute at 720p to verify the engine before attempting 5–8 minutes. The first setup has **not** been rendered yet. This repository is prepared but should be validated by running the workflow when you choose.

## Repository layout

- `.github/workflows/render.yml` — manual-only render workflow; no automatic runs.
- `engine/render.py` — deterministic animation and MP4 renderer.
- `scripts/episode.json` — editable sample story and character bible.
- `requirements.txt` — Python dependencies.

Only upload content you have rights to use. For a series inspired by heist fiction, use original characters, storylines, dialogue, and branding rather than copying protected scenes or character likenesses.