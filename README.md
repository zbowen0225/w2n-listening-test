# Whisper-to-normal speech listening test

Static web page for a subjective evaluation (naturalness, intelligibility, speaker similarity) of whisper-to-normal
speech conversion systems. Served with GitHub Pages; answers are collected by a Google Apps Script (see `collector/`).

- `index.html`, `settings.js` — the test. Open `?g=A` or `?g=B` to force a listener group; otherwise random.
- `config.json`, `stimuli/` — trial list and loudness-normalised 16 kHz clips under opaque ids. The system identity of
  each clip is **not** in this repository (held privately in `key.json` by the experimenter).
- `tools/analyze.py` — aggregates answers (needs the private `key.json` next to it).

Audio clips are short sentences from the wTIMIT corpus, used for research evaluation only.
