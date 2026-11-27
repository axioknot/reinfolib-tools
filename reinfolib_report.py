#!/usr/bin/env python3
"""集計CSVから可視化HTMLと通知文を作る。

可視化は、取引件数が最多の市区町村を対象に、四半期ごとの取引件数を
主要な物件種別（上位3種）の積み上げ棒グラフ（SVG）で示す。
通知文は、直近四半期の件数と主要種別の平方メートル単価中央値を
前四半期と比較して示す。

使い方: python3 reinfolib_report.py 集計.csv 出力.html 通知文.txt
出典: 国土交通省 不動産情報ライブラリ
API利用規約 第7条のクレジット表示をHTML末尾に入れる。
HTMLの様式は分析基盤の共通レポートテンプレート（analysis-hub）に従う。
"""
import csv
import json
import os
import sys
import urllib.request
from collections import defaultdict

CREDIT = "このサービスは、国土交通省の不動産情報ライブラリのAPI機能を使用していますが、提供情報の最新性、正確性、完全性等が保証されたものではありません"
SOURCE = "出典: 国土交通省 不動産情報ライブラリ（https://www.reinfolib.mlit.go.jp/）"
PROCESSED = "「不動産取引価格情報」（国土交通省）をもとに集計・加工して作成"
COLORS = ["#3b6ea5", "#54823F", "#A87A1D"]


def load(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            row["count"] = int(row["count"])
            row["median_unit_price"] = int(row["median_unit_price"]) if row["median_unit_price"] else None
            rows.append(row)
    return rows


def svg_bars(period_counts, periods, types):
    w, h, pad = 960, 320, 44
    top = max((sum(period_counts[p][t] for t in types) for p in periods), default=1)
    bw = (w - pad * 2) / max(len(periods), 1)
    parts = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" role="img">' % (w, h)]
    parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#8A877C"/>' % (pad, h - pad, w - pad, h - pad))
    for i, p in enumerate(periods):
        x = pad + i * bw
        y0 = h - pad
        for j, t in enumerate(types):
            v = period_counts[p][t]
            if not v:
                continue
            bh = (h - pad * 2) * v / top
            y0 -= bh
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"><title>%s %s: %s件</title></rect>' % (x + 1, y0, bw - 2, bh, COLORS[j % len(COLORS)], p, t, format(v, ",")))
        parts.append('<text x="%.1f" y="%d" font-size="12" text-anchor="middle" fill="#55534E">%s</text>' % (x + bw / 2, h - pad + 16, p))
    parts.append("</svg>")
    return "".join(parts)


def render_page(title, kicker, h1, lede, body, foot):
    """共通レポートテンプレート（analysis-hub）でページを組み立てる。

    テンプレートが見つからない環境（パーツ単体での利用）では、
    最小限の埋め込み様式にフォールバックする。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    tpl_path = os.path.join(here, "..", "analysis-hub", "report_template.html")
    try:
        with open(tpl_path, encoding="utf-8") as f:
            tpl = f.read()
    except OSError:
        tpl = None
    if tpl is None:
        return ("<!DOCTYPE html>\n<html lang=\"ja\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>%s</title></head><body><h1>%s</h1>%s%s<footer>%s</footer></body></html>"
                % (title, h1, lede, body, foot))
    page = tpl
    for key, val in (("{{TITLE}}", title), ("{{KICKER}}", kicker), ("{{H1}}", h1),
                     ("{{LEDE}}", lede), ("{{BODY}}", body), ("{{FOOT}}", foot)):
        page = page.replace(key, val)
    return page


def section(no, label, title, inner):
    return ('<section class="sec"><div class="sec-head">'
            '<span class="sec-no">%s</span><span class="sec-label">%s</span><h2>%s</h2>'
            '</div>%s</section>' % (no, label, title, inner))


def main(src, html_out, notify_out):
    rows = load(src)
    if not rows:
        notify_text = "\n".join([
            "【不動産取引価格・四半期まとめ】",
            "集計データがまだありません。APIキーの発行と収集の実行が前提です。",
            SOURCE,
            PROCESSED,
        ])
        body = '<section class="sec"><p>集計データがまだありません。</p></section>'
        foot = "<p>%s</p><p>%s</p><p>%s</p>" % (SOURCE, PROCESSED, CREDIT)
        html = render_page("不動産取引価格の集計", "REAL ESTATE TRANSACTIONS / QUARTERLY",
                           "不動産取引価格の集計", "", body, foot)
        with open(html_out, "w", encoding="utf-8") as f:
            f.write(html)
        with open(notify_out, "w", encoding="utf-8") as f:
            f.write(notify_text + "\n")
        print(notify_text)
        return

    muni_totals = defaultdict(int)
    for r in rows:
        muni_totals[(r["prefecture"], r["municipality"])] += r["count"]
    focus = max(muni_totals, key=muni_totals.get)
    frows = [r for r in rows if (r["prefecture"], r["municipality"]) == focus]
    type_totals = defaultdict(int)
    for r in frows:
        type_totals[r["property_type"]] += r["count"]
    types = [t for t, _ in sorted(type_totals.items(), key=lambda kv: -kv[1])[:3]]
    periods = sorted({r["period"] for r in frows if r["period"] != "unknown"})
    period_counts = defaultdict(lambda: defaultdict(int))
    unit_price = {}
    for r in frows:
        period_counts[r["period"]][r["property_type"]] += r["count"]
        if r["median_unit_price"] is not None:
            unit_price[(r["period"], r["property_type"])] = r["median_unit_price"]

    last, prev = periods[-1], periods[-2] if len(periods) > 1 else None
    last_total = sum(period_counts[last][t] for t in types)
    lines = ["【不動産取引価格・四半期まとめ】",
             "対象: %s%s（取引件数が最多の市区町村）" % focus,
             "直近四半期: %s" % last]
    if prev:
        prev_total = sum(period_counts[prev][t] for t in types)
        d = last_total - prev_total
        sign = "+" if d >= 0 else ""
        lines.append("取引件数: %s件（前四半期 %s件、%s%s件）" % (format(last_total, ","), format(prev_total, ","), sign, format(d, ",")))
    else:
        lines.append("取引件数: %s件" % format(last_total, ","))
    for t in types:
        up = unit_price.get((last, t))
        if up is None:
            continue
        man = up / 10000.0
        seg = "%s: m2単価中央値 %.1f万円" % (t, man)
        if prev and unit_price.get((prev, t)):
            dm = (up - unit_price[(prev, t)]) / 10000.0
            sign = "+" if dm >= 0 else ""
            seg += "（前四半期比 %s%.1f万円）" % (sign, dm)
        lines.append(seg)
    lines.append(SOURCE)
    lines.append(PROCESSED)
    notify_text = "\n".join(lines)

    legend = "、".join("%s=%s" % (COLORS[i % len(COLORS)], t) for i, t in enumerate(types))
    chart = '<div class="chart">%s</div>' % svg_bars(period_counts, periods, types)
    body = section("01", "CHART", "四半期ごとの取引件数",
                   chart + '<p class="legend">凡例: %s</p>' % legend)
    foot = "<p>%s</p><p>%s</p><p>%s</p>" % (SOURCE, PROCESSED, CREDIT)
    html = render_page("不動産取引価格の動向（%s%s）" % focus, "REAL ESTATE TRANSACTIONS / QUARTERLY",
                       "不動産取引価格の動向 — %s%s（四半期ごとの取引件数）" % focus, "", body, foot)
    with open(html_out, "w", encoding="utf-8") as f:
        f.write(html)
    with open(notify_out, "w", encoding="utf-8") as f:
        f.write(notify_text + "\n")
    print(notify_text)

    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if url:
        req = urllib.request.Request(url, data=json.dumps({"content": notify_text}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "reinfolib-tools/0.1"})
        urllib.request.urlopen(req, timeout=30)
        print("notified: discord webhook")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
