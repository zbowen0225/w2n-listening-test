# Result collection (no server needed)
1. Open https://script.google.com, create a new project, paste `Code.gs`, change `TOKEN`.
2. Deploy → New deployment → type **Web app**, Execute as **Me**, Who has access **Anyone**. Copy the URL ending in `/exec`.
3. Put that URL into `settings.js` (`submit_url`) and push. Done: every finished test appends one row to a Google Sheet
   named `listening_test_results` in your Drive.
4. Download all answers: `python tools/analyze.py --pull "<exec URL>?token=<TOKEN>"` (writes `results/*.json`, then aggregates).
If `submit_url` is empty or unreachable, listeners get a "download my answers" button and are asked to email the file.
