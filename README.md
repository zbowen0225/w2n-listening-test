# Whisper-to-normal speech listening test

Static web page for a subjective evaluation (naturalness, intelligibility, speaker similarity) of whisper-to-normal
speech conversion systems. Served with GitHub Pages. At the end each participant downloads a JSON file with their answers and sends it to the experimenter (an optional Google Apps Script collector is in `collector/`).

- `index.html`, `settings.js` — the test. Participant IDs are generated automatically (5 chars) and appear in the answer file name. `?g=A` or `?g=B` forces a listener group, `?id=XYZ` forces an ID.
- `config.json`, `stimuli/` — trial list and loudness-normalised 16 kHz clips under opaque ids. The system identity of
  each clip is **not** in this repository (held privately in `key.json` by the experimenter).
- `tools/analyze.py` — aggregates answers (needs the private `key.json` next to it).

Audio clips are short sentences from the wTIMIT corpus, used for research evaluation only.
