// Google Apps Script collector for the listening test.
// Deploy: script.google.com -> New project -> paste this -> Deploy -> New deployment -> Web app,
// "Execute as: Me", "Who has access: Anyone" -> copy the /exec URL into settings.js (submit_url).
// Answers go to a Google Sheet created next to the script (one tab "raw", one row per listener).
// Pull them with: python tools/analyze.py --pull "<exec URL>?token=<TOKEN>"
const TOKEN = "change-me-" + "7f3a";   // change this, keep it secret; used only for downloading results
const SHEET_NAME = "listening_test_results";

function sheet_() {
  const p = PropertiesService.getScriptProperties();
  let id = p.getProperty("sheet_id");
  let ss = id ? SpreadsheetApp.openById(id) : null;
  if (!ss) { ss = SpreadsheetApp.create(SHEET_NAME); p.setProperty("sheet_id", ss.getId()); }
  let sh = ss.getSheetByName("raw");
  if (!sh) { sh = ss.insertSheet("raw"); sh.appendRow(["received", "listener", "group", "n_ratings", "json"]); }
  return sh;
}

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    sheet_().appendRow([new Date().toISOString(), String(d.listener || ""), String(d.group || ""),
                        (d.ratings || []).length, e.postData.contents]);
    return ContentService.createTextOutput(JSON.stringify({ ok: true })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  if (!e.parameter.token || e.parameter.token !== TOKEN)
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: "bad token" })).setMimeType(ContentService.MimeType.JSON);
  const rows = sheet_().getDataRange().getValues().slice(1);
  const out = rows.map(r => ({ received: r[0], listener: r[1], group: r[2], n_ratings: r[3], data: JSON.parse(r[4]) }));
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}
