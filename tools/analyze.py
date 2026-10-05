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
METRICS = [("nat", "N-MOS"), ("intel", "I-MOS"), ("sim", "S-MOS")]


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


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--pull":
        pull(sys.argv[2])
    files = sorted(glob.glob(f"{HERE}/results/*.json"))
    if not files:
        sys.exit("no results/*.json")
    # keep the latest file per listener
    latest = {}
    for f in files:
        d = json.load(open(f))
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
           "groups: " + ", ".join(f"{g}={sum(1 for d in latest.values() if d['group']==g)}" for g in CFG["groups"]), ""]

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
    out.append("| listener | group | gt N-MOS | whisper N-MOS | gt S-MOS | wesper S-MOS | n ratings |")
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
