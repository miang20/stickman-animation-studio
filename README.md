# Stickman Animation Studio

A free-first, code-based 2D cartoon episode maker. It uses Python, Pillow, NumPy, FFmpeg and **Kokoro neural text-to-speech**. No paid API, API key, voice subscription, stock-footage subscription or generative-video service is required.

## What this version includes

- Reusable character bible with stable IDs, fixed dark round heads, expressive white eyes, outfit details, hair and roles.
- **Workflow colour picker**: choose blue, cyan, red, green, purple, orange, yellow, pink, white or black; the selected main colour is applied consistently to every recurring character in that episode.
- Ten hand-drawn environments: safehouse, bank, street, police area, warehouse, rooftop, vault, control room, van and hall.
- Reusable walk/run/sneak/point/wave/panic/fall/celebrate/surrender poses, arm and leg cycles, character name labels and facial expressions.
- Original 30-scene, five-minute heist-comedy sample story.
- **Kokoro neural narration**, with `af_heart` as the default voice.
- Captions with high-contrast panels and selected red keyword highlights.
- Procedurally generated suspense music, simple action sound effects and automatic music ducking under narration.
- 24 fps H.264 MP4 with AAC audio, fast-start metadata, a post-render FFprobe check, and a separate scene-timed SRT caption file.
- Manual-only GitHub Actions workflow and downloadable package artifact retained for seven days.

## Voice system (Kokoro)

The renderer uses the open-weight Kokoro TTS model through its Python `KPipeline` interface. English narration is generated on the GitHub Actions runner; no hosted voice API or API key is used.

Available workflow voices:

| Voice ID | Description |
|---|---|
| `af_heart` | Default American English female voice |
| `af_bella` | American English female voice |
| `af_nova` | American English female voice |
| `af_alloy` | American English female voice |
| `am_adam` | American English male voice |
| `am_michael` | American English male voice |

The workflow's **voice** input turns narration on or off; **voice_name** selects the voice. Default is `af_heart`. The current renderer uses a speech speed of `1.04`. Voice style and pronunciation can vary by line, and the actual output should be listened to after the first successful render.

### Runtime setup

You do not need to install Python packages on your phone. When a workflow is manually started, GitHub Actions:

1. Installs FFmpeg, eSpeak NG (used by the phonemization stack) and DejaVu fonts.
2. Sets up Python 3.11.
3. Installs CPU-only PyTorch `2.6.0+cpu`.
4. Installs the pinned packages from `requirements.txt`, including `kokoro==0.9.4`.
5. Imports the Kokoro engine and validates the episode JSON before rendering.

If Kokoro cannot initialize or fails to produce audio, the render stops with an error; it does **not** silently switch to eSpeak narration. The eSpeak NG system package is present for Kokoro's phonemization requirements, not as the narration voice.

## Android workflow

1. Open this repository on GitHub and select **Actions**.
2. Select **Render Stickman Episode**.
3. Tap **Run workflow** when you want to create a video.
4. Choose duration (1, 2, 3, 5 or 8 minutes). Default is **5 minutes**.
5. Choose **720p** first; 1080p requires more processing.
6. Keep narration **on** and choose a voice under **voice_name**; `af_heart` is the default.
7. Select **character_color** to recolour the recurring characters for that video (blue is the default).
8. After the workflow finishes successfully, open the run and download the **stickman-episode-package** artifact ZIP.
9. Extract the ZIP on your phone to get `stickman-episode.mp4` and `captions.srt`.

Nothing runs automatically on a push. The workflow has not been run as part of setup, so the first real render still needs to validate installation, runtime speed, voice output, audio sync and visual quality.

## Make the next episode

Edit `scripts/episode.json` for a new story. Keep character IDs stable to reuse the same character designs. Each scene can define:

- `id`: unique scene identifier
- `setting`: one of the named environments above
- `duration`: scene duration in seconds
- `characters`: existing character IDs to show
- `action`: visual action description; it also helps select a matching pose
- `dialogue` or `narration`: spoken line
- `caption`: short on-screen hook or caption
- `motion`: optional explicit pose; use `auto` to infer from the action text

For a five-minute episode, use around 30 scenes at 10 seconds each. For an eight-minute export, the renderer can cycle through available scenes to fill the requested duration, so add enough unique scenes if you want all eight minutes to have unique story beats. Keep the same IDs in the `characters` array to preserve recurring designs.

## Free limits and honest quality notes

- Rendering is CPU-based and uses free GitHub Actions minutes/runner time where applicable. A 1080p, eight-minute job is much heavier than a 720p, one-minute job.
- Kokoro is an open-weight neural voice model; the model and required packages must download during setup. It is not a zero-download or instant first-run process.
- This is deterministic, code-drawn 2D animation—not full generative animation, hand-keyframed studio animation, or live-action footage. The character style now uses a high-contrast dark round head, expressive eyes and selectable shared outfit colour; motion is built from reusable poses and cycles. It aims at the reference's illustrated look but is not a frame-for-frame copy.
- The renderer caches each setting's background to reduce repeated work. Runtime and visual quality must still be confirmed by the first authorized render.
- Temporary render/audio files are written to `.render_tmp` and cleaned up after a successful render. The MP4 and SRT are written to `output/`; the workflow uploads them as the artifact.
- The sample is an original fictional heist comedy. For a series inspired by heist fiction, use original characters, dialogue, scenes and branding rather than copying protected movie scenes or character likenesses.

## Repository layout

- `.github/workflows/render.yml` — manual render, validation and output verification; duration, resolution and voice selectors.
- `engine/render.py` — renderer, character acting, backgrounds, Kokoro narration, audio synthesis, SRT export and validation.
- `scripts/episode.json` — character bible and sample episode script.
- `requirements.txt` — pinned open-source Python dependencies.
