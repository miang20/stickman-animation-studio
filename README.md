# Stickman Animation Studio

A free-first, code-based 2D cartoon episode maker. It uses Python, Pillow, NumPy, FFmpeg and eSpeak NG. No paid API, API key, stock footage subscription or generative-video service is required.

## What this version includes

- Reusable character bible with stable IDs, outfit colours, hair and roles.
- Ten hand-drawn environments: safehouse, bank, street, police area, warehouse, rooftop, vault, control room, van and hall.
- Animated walk/run/sneak/point/wave/panic/fall/celebrate/surrender poses, arm and leg cycles, character name labels and facial expressions.
- Original 30-scene, five-minute heist-comedy sample story.
- Scene dialogue / narration from the free local eSpeak NG voice.
- Captions with high-contrast panels and selected red keyword highlights.
- Procedurally generated suspense music, simple action SFX and automatic music ducking under narration.
- 24 fps H.264 MP4 with AAC audio, fast-start metadata, a post-render FFprobe check, and a separate scene-timed SRT caption file.
- Manual-only GitHub Actions workflow and downloadable MP4 artifact retained for seven days.

## Android workflow

1. Open this repository on GitHub and select **Actions**.
2. Select **Render Stickman Episode**.
3. Tap **Run workflow** when you want to create a video.
4. Choose duration. The default is **5 minutes**. Choose **720p** first; 1080p requires more processing.
5. Leave narration set to **on** unless you want a music-only render.
6. After the workflow finishes successfully, open the run and download the **stickman-episode-package** artifact ZIP.
7. Extract the ZIP on your phone to get `stickman-episode.mp4`.

Nothing runs automatically on a push. The workflow has not been run as part of setup, so the first real render still needs to validate runtime speed and output quality.

## Make the next episode

Edit only `scripts/episode.json` for a new story. Keep character IDs stable to reuse the same character designs. Each scene can define:

- `id`: unique scene identifier
- `setting`: one of the named environments above
- `duration`: scene duration in seconds
- `characters`: existing character IDs to show
- `action`: visual action description; it also helps select a matching pose
- `dialogue` or `narration`: spoken line
- `caption`: short on-screen hook or caption
- `motion`: optional explicit pose; use `auto` to infer from the action text

For a five-minute episode, use around 30 scenes at 10 seconds each. For an eight-minute export, the renderer can cycle through the available scenes to fill the requested duration, so add enough unique scenes if you want all eight minutes to have unique story beats. Keep the same IDs in the `characters` array to preserve recurring designs.

## Free limits and honest quality notes

- Rendering is CPU-based and uses free GitHub Actions minutes/runner time where applicable. A 1080p, eight-minute job is much heavier than a 720p, one-minute job.
- eSpeak NG is a free synthetic voice and will sound robotic; it does not require a voice API.
- This is deterministic, code-drawn 2D animation—not full generative animation, hand-keyframed studio animation, or live-action footage. Motion is built from reusable poses and cycles.
- The renderer is designed to reduce repeated background work by caching each setting. Runtime and visual quality must still be confirmed by the first authorized render.
- Temporary render/audio files are written to `.render_tmp` and the MP4 to `output/`. These are not committed by the workflow; only the artifact is uploaded.
- The sample is an original fictional heist comedy. For a series inspired by heist fiction, use original characters, dialogue, scenes and branding rather than copying protected movie scenes or character likenesses.

## Repository layout

- `.github/workflows/render.yml` — manual render, validation and output verification.
- `engine/render.py` — renderer, character acting, backgrounds, audio synthesis, SRT export and validation.
- `scripts/episode.json` — character bible and 30-scene episode script.
- `requirements.txt` — pinned open-source Python dependencies.
