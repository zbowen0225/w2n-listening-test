#!/usr/bin/env python
"""Aggregate listening-test answers: results/*.json + key.json -> results/summary.md
   conda run -n diffusers python listening_test/analyze.py
Per system: N-MOS (naturalness), I-MOS (intelligibility), S-MOS (same-speaker), mean ± 95% CI
(CI over per-stimulus means, t-distribution), broken down by gender / accent / register group,
plus paired Wilcoxon signed-rank on per-stimulus means for the pairs that matter.
"""
import glob, json, os, sys
from collections import defaultdict
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = json.load(open(f"{HERE}/key.json"))
CFG = json.load(open(next(p for p in (f"{HERE}/web/config.json", f"{HERE}/../config.json") if os.path.exists(p))))
items = {k["id"]: k for k in KEY["items"]}
SPK = CFG["speakers"]
PAIRS = [("v9", "whispervc"), ("v9", "quickvc"), ("v9", "wesper"), ("v9", "abshz"), ("v9", "nopitch"), ("abshz", "nopitch")]
METRICS = [("nat", "Naturalness 自然度 (N-MOS)"), ("intel", "Intelligibility 可懂度 (I-MOS)"), ("sim", "Speaker similarity 相似度 (S-MOS)")]


def ci(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return (x.mean() if len(x) else np.nan), np.nan
    return x.mean(), stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def pull(url):
    import urllib.request
    os.makedirs(f"{HERE}/results", exist_ok=True)
    data = json.load(urllib.request.urlopen(url))
    if isinstance(data, dict) and not data.get("ok", True):
        sys.exit(f"collector refused: {data}")
    for row in data:
        d = row["data"]
        fn = f"{HERE}/results/{str(d.get('listener','anon')).replace('/','_')}_{row['received'].replace(':','').replace('-','')[:15]}.json"
        json.dump(d, open(fn, "w"))
    print(f"pulled {len(data)} submissions into {HERE}/results/")


def load_any(f):
    """results/*.json (full page state) or results/*.txt (compact text pasted from a chat message)."""
    if f.endswith(".json"):
        return json.load(open(f))
    txt = open(f, encoding="utf-8").read()
    i = txt.find("LT1 ")
    if i < 0:
        return None
    lines = [l.strip() for l in txt[i:].splitlines() if l.strip()]
    hdr = dict(kv.split("=", 1) for kv in lines[0].split()[1:] if "=" in kv)
    d = dict(listener=hdr.get("id", os.path.basename(f)), group=hdr.get("g"), started=hdr.get("start"),
             finished=hdr.get("end"), done=True, ratings=[], source=f)
    for l in lines[1:]:
        p = l.split()
        if len(p) < 3 or p[0] not in ("1", "2"):
            continue
        if p[0] == "1":
            d["ratings"].append(dict(part=1, id=p[1], nat=int(p[2]), intel=int(p[3]) if len(p) > 3 else None, plays=int(p[4]) if len(p) > 4 else 0))
        else:
            d["ratings"].append(dict(part=2, id=p[1], sim=int(p[2]), plays=int(p[3]) if len(p) > 3 else 0, plays_ref=int(p[4]) if len(p) > 4 else 0))
    return d


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--pull":
        pull(sys.argv[2])
    files = sorted(glob.glob(f"{HERE}/results/*.json") + glob.glob(f"{HERE}/results/*.txt"))
    if not files:
        sys.exit("no results/*.json or *.txt")
    # keep the latest file per listener
    latest = {}
    for f in files:  # chronological by filename; a complete submission beats a later partial one
        d = load_any(f)
        if d is None:
            print(f"skip {f}: no 'LT1' header found"); continue
        prev = latest.get(d["listener"])
        if prev and prev.get("done", not prev.get("partial")) and d.get("partial"):
            continue
        latest[d["listener"]] = d
    rows = []  # (listener, group, system, spk, uid, metric, value)
    for who, d in latest.items():
        for r in d["ratings"]:
            k = items[r["id"]]
            for m, _ in METRICS:
                if r.get(m) is not None:
                    rows.append((who, d["group"], k["system"], k["spk"], k["uid"], m, r[m]))
    listeners = sorted(latest)
    out = [f"# Listening test summary", f"listeners: {len(listeners)} ({', '.join(listeners)}); ratings: {len(rows)}",
           "groups: " + ", ".join(f"{g}={sum(1 for d in latest.values() if d['group']==g)}" for g in CFG["groups"]), "",
           "Legend: all scores are 1–5, 5 = best. N-MOS = naturalness (Part 1, Q1), I-MOS = ease of understanding (Part 1, Q2),",
           "S-MOS = how similar the voice is to the reference speaker (Part 2). Cell = mean ± 95% CI over stimuli (n stimuli);",
           "a stimulus's score is first averaged over the listeners who rated it. 'gt' = real normal speech (upper anchor),",
           "'whisper' = raw whispered input (lower anchor). Δ in the paired table = first system minus second.", ""]

    # per-stimulus means
    stim = defaultdict(list)
    for who, g, sysn, spk, uid, m, v in rows:
        stim[(sysn, spk, uid, m)].append(v)
    stim_mean = {k: np.mean(v) for k, v in stim.items()}

    def table(title, keep):
        out.append(f"## {title}")
        out.append("| system | " + " | ".join(f"{n} (n stim)" for _, n in METRICS) + " |")
        out.append("|---|" + "---|" * len(METRICS))
        for sysn in KEY["systems"]:
            cells = []
            for m, _ in METRICS:
                xs = [v for (s, spk, uid, mm), v in stim_mean.items() if s == sysn and mm == m and keep(spk)]
                mu, h = ci(xs)
                cells.append("—" if not xs else f"{mu:.2f} ± {h:.2f} ({len(xs)})")
            out.append(f"| {sysn} | " + " | ".join(cells) + " |")
        out.append("")

    table("All speakers", lambda s: True)
    for g in ("F", "M"):
        table(f"Gender {g}", lambda s, g=g: SPK[s]["gender"] == g)
    for a in ("US", "SG"):
        table(f"Accent {a}", lambda s, a=a: SPK[s]["accent"] == a)
    for rg in ("low", "mid", "high"):
        table(f"Register {rg}", lambda s, rg=rg: SPK[s]["register_group"] == rg)

    out.append("## Paired tests (per-stimulus means, Wilcoxon signed-rank; Holm-corrected within metric)")
    out.append("| metric | pair | Δ mean | n | p raw | p Holm |")
    out.append("|---|---|---|---|---|---|")
    for m, name in METRICS:
        res = []
        for a, b in PAIRS:
            xa, xb = [], []
            for (s, spk, uid, mm), v in stim_mean.items():
                if mm != m or s != a:
                    continue
                kb = (b, spk, uid, m)
                if kb in stim_mean:
                    xa.append(v); xb.append(stim_mean[kb])
            if len(xa) < 5:
                continue
            d = np.array(xa) - np.array(xb)
            p = stats.wilcoxon(d).pvalue if np.any(d != 0) else 1.0
            res.append((a, b, d.mean(), len(d), p))
        ps = np.array([r[4] for r in res])
        order = np.argsort(ps); holm = np.empty_like(ps)
        for rank, idx in enumerate(order):
            holm[idx] = min(1.0, ps[idx] * (len(ps) - rank))
        holm = np.maximum.accumulate(holm[order])[np.argsort(order)] if len(ps) else holm
        for (a, b, dm, n, p), ph in zip(res, holm):
            out.append(f"| {name} | {a} − {b} | {dm:+.2f} | {n} | {p:.3g} | {ph:.3g} |")
    out.append("")

    # listener sanity: GT anchors and whisper anchor per listener
    out.append("## Listener sanity (mean rating of anchors)")
    out.append("(sanity: gt should be high, whisper low, wesper similarity low — a listener far off these may be guessing)")
    out.append("")
    out.append("| listener | group | gt naturalness | whisper naturalness | gt similarity | wesper similarity | n ratings |")
    out.append("|---|---|---|---|---|---|---|")
    for who in listeners:
        def mean_of(sysn, m):
            xs = [v for w, g, s, spk, uid, mm, v in rows if w == who and s == sysn and mm == m]
            return f"{np.mean(xs):.2f}" if xs else "—"
        out.append(f"| {who} | {latest[who]['group']} | {mean_of('gt','nat')} | {mean_of('whisper','nat')} | {mean_of('gt','sim')} | {mean_of('wesper','sim')} | {sum(1 for r in rows if r[0]==who)} |")
    txt = "\n".join(out)
    open(f"{HERE}/results/summary.md", "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
