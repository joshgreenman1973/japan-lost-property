#!/usr/bin/env python3
"""Build the Tokyo lost-property dataset from the Metropolitan Police statistics page,
plus the National Police Agency index of prefectural lost-property portals.

Sources:
  https://www.keishicho.metro.tokyo.lg.jp/about_mpd/jokyo_tokei/kakushu/kaikei.html
  https://www.npa.go.jp/bureau/soumu/ishitsubutsu/otoshimono/todofukenishitubutu.html
Output: out_japan/data.json
Fails loudly if the expected tables are missing.
"""
import re, json, html, os, sys, urllib.request

OUT = "out_japan"
os.makedirs(OUT, exist_ok=True)

TOKYO = "https://www.keishicho.metro.tokyo.lg.jp/about_mpd/jokyo_tokei/kakushu/kaikei.html"
NPA = "https://www.npa.go.jp/bureau/soumu/ishitsubutsu/otoshimono/todofukenishitubutu.html"

# Japanese category and disposition labels, translated. Kept explicit rather than
# machine-translated so the mapping is auditable.
CAT = {
    "証明書類": ("Certificates and documents", "ID cards, licences, passes"),
    "有価証券類": ("Securities and vouchers", "Tickets, gift certificates, prepaid cards"),
    "衣類履物類": ("Clothing and footwear", None),
    "衣類・履物類": ("Clothing and footwear", None),
    "電気製品類": ("Electrical goods", "Earphones, chargers, small appliances"),
    "財布類": ("Wallets and purses", None),
    "かさ類": ("Umbrellas", None),
    "かばん類": ("Bags", None),
    "携帯電話類": ("Mobile phones", None),
    "貴金属類": ("Jewellery and precious metals", None),
    "カメラ眼鏡類": ("Cameras and eyeglasses", None),
    "その他": ("Everything else", None),
}
DISP = {
    "遺失者返還": "Returned to the owner",
    "拾得者引渡": "Given to the finder",
    "都帰属": "Became property of Tokyo",
    "廃棄・任意提出": "Discarded or surrendered",
    "合計": "Total",
}


def norm(s):
    return re.sub(r"[\s　]+", "", html.unescape(re.sub(r"<[^>]*>", "", s)))


def cells(row):
    return [re.sub(r"[\s　]+", " ", html.unescape(re.sub(r"<[^>]*>", "", c))).strip()
            for c in re.findall(r"<t[hd].*?</t[hd]>", row, re.S)]


def tables(h):
    return [[cells(r) for r in re.findall(r"<tr.*?</tr>", t, re.S)]
            for t in re.findall(r"<table.*?</table>", h, re.S)]


def num(s):
    s = re.sub(r"[^\d\-]", "", s or "")
    return int(s) if s not in ("", "-") else None


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def main():
    h = get(TOKYO)
    T = tables(h)
    if len(T) < 10:
        sys.exit("FAIL: expected at least 10 tables on the Tokyo page, found %d" % len(T))

    upd = re.search(r"更新日：(\d{4})年(\d{1,2})月(\d{1,2})日", h)
    updated = "%s-%02d-%02d" % (upd.group(1), int(upd.group(2)), int(upd.group(3))) if upd else None

    # ---- headline totals (found reports / loss reports) ----
    def kv(tbl):
        out = {}
        hdr = tbl[0]
        for row in tbl[1:]:
            if len(row) >= 3:
                out[norm(row[0])] = {"y2025": num(row[1]), "y2024": num(row[2])}
        return out, hdr

    found, _ = kv(T[0])
    lost, _ = kv(T[2])

    # ---- found vs reported-lost, by category (table 5) ----
    t5 = T[5]
    cats = [norm(c) for c in t5[0][1:]]
    found_pts = [num(x) for x in t5[1][1:]]
    lost_pts = [num(x) for x in t5[2][1:]]
    compare = []
    for i, c in enumerate(cats):
        name, note = CAT.get(c, (c, None))
        compare.append({"ja": c, "en": name, "note": note,
                        "found": found_pts[i], "reported_lost": lost_pts[i]})

    # ---- what happened to it, by category (table 9) ----
    t9 = [r for r in T[9] if r]
    hdr = [norm(c) for c in t9[0][1:]]
    disp_cols = [DISP.get(c, c) for c in hdr]
    outcomes = []
    for row in t9[1:]:
        c = norm(row[0])
        if c not in CAT:
            continue
        vals = [num(x) for x in row[1:]]
        name, note = CAT[c]
        rec = {"ja": c, "en": name, "note": note, "total": vals[-1]}
        rec["disposition"] = {disp_cols[i]: vals[i] for i in range(len(vals) - 1)}
        tot = rec["total"] or 0
        ret = rec["disposition"].get("Returned to the owner") or 0
        rec["return_rate"] = round(ret / tot * 100, 1) if tot else None
        outcomes.append(rec)
    if not outcomes:
        sys.exit("FAIL: parsed no per-category outcomes from the Tokyo page")

    # ---- overall disposition (table 8) ----
    t8 = T[8]
    dhdr = [DISP.get(norm(c), norm(c)) for c in t8[0][1:]]
    overall = {}
    for row in t8[1:]:
        key = {"件数（件）": "reports", "現金（円）": "cash_yen", "点数（点）": "items"}.get(
            re.sub(r"[\s　]+", "", row[0]), norm(row[0]))
        overall[key] = {dhdr[i]: num(v) for i, v in enumerate(row[1:])}

    # ---- items held by station operators (tables 6, 7) ----
    held = {}
    for row in T[6][1:]:
        k = {"保管件数": "cases", "保管金額": "cash_yen", "占有者数": "operators"}.get(norm(row[0]))
        if k:
            held[k] = row[1]
    held_cats = []
    if len(T[7]) >= 2:
        hc = [norm(c) for c in T[7][0][1:]]
        hv = [num(x) for x in T[7][1][1:]]
        held_cats = [{"ja": c, "en": CAT.get(c, (c, None))[0], "n": hv[i]} for i, c in enumerate(hc)]

    # ---- NPA prefectural portal index ----
    prefs = []
    try:
        nh = get(NPA)
        keep = re.compile(r"lostproperty\.pcf\.npa\.go\.jp|pref\.[a-z]+\.(lg\.)?jp|keishicho|police\.pref")
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', nh, re.S):
            url = m.group(1).strip()
            name = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", m.group(2))).strip()
            if not name or not keep.search(url):
                continue
            if url.startswith("/"):
                url = "https://www.npa.go.jp" + url
            shared = "lostproperty.pcf.npa.go.jp" in url
            prefs.append({"name": name, "url": url, "shared_portal": shared})
        seen, ded = set(), []
        for p in prefs:
            if p["name"] in seen:
                continue
            seen.add(p["name"])
            ded.append(p)
        prefs = ded
        if len(prefs) < 40:
            print("warning: only %d prefectural links found, expected ~47" % len(prefs),
                  file=sys.stderr)
    except Exception as e:
        print("warning: NPA index fetch failed: %s" % e, file=sys.stderr)

    # ---- exchange rate: calendar-2025 average, to match the data year ----
    fx = None
    try:
        fxj = json.loads(get("https://api.frankfurter.dev/v1/"
                             "2025-01-01..2025-12-31?base=USD&symbols=JPY"))
        vals = [v["JPY"] for v in fxj["rates"].values()]
        if vals:
            fx = {
                "jpy_per_usd": round(sum(vals) / len(vals), 2),
                "basis": "mean of daily ECB reference rates, calendar 2025",
                "observations": len(vals),
                "min": round(min(vals), 2), "max": round(max(vals), 2),
                "source": "European Central Bank via frankfurter.dev",
            }
    except Exception as e:
        print("warning: FX fetch failed: %s" % e, file=sys.stderr)
    if fx is None:
        sys.exit("FAIL: could not fetch an exchange rate; refusing to publish yen "
                 "figures without a documented conversion")

    data = {
        "fx": fx,
        "meta": {
            "source_tokyo": TOKYO,
            "source_npa": NPA,
            "year": 2025, "year_ja": "令和7年",
            "prior_year": 2024, "prior_year_ja": "令和6年",
            "page_updated": updated,
            "built": "2026-08-15",
            "prefecture_links": len(prefs),
        },
        "found": found, "lost": lost,
        "compare": compare, "outcomes": outcomes,
        "overall": overall, "held": held, "held_categories": held_cats,
        "prefectures": prefs,
    }
    p = os.path.join(OUT, "data.json")
    json.dump(data, open(p, "w"), ensure_ascii=False, separators=(",", ":"))
    print("wrote %s  categories=%d  outcomes=%d  prefectures=%d  updated=%s"
          % (p, len(compare), len(outcomes), len(prefs), updated), file=sys.stderr)
    for o in sorted(outcomes, key=lambda x: x["return_rate"] or 0):
        print("  %-32s total %9s  returned %5s%%" % (o["en"], o["total"], o["return_rate"]), file=sys.stderr)


if __name__ == "__main__":
    main()
