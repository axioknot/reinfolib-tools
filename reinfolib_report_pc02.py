#!/usr/bin/env python3
"""成約価格情報（priceClassification=02）の集計CSVから可視化HTMLと通知文を作る。

pc01（取引価格情報）用の reinfolib_report.py と対になるスクリプト。
対象データは成約価格情報のみで、pc01 の数値を混ぜない。pc01 との比較は
既存の pc01 集計CSVを読み、同じ「都道府県 × 市区町村 × 種別 × 四半期」の
グループ同士で中央値を並べる専用セクションでのみ行う。

成約価格情報の性質（2026-11-27、実データで確認）:
  - 種別は「中古マンション等」「宅地(土地と建物)」の2種のみ
  - UnitPrice（m2単価）は全レコードで空。当方の取得範囲では単価の値が入っていないため、
    価格の指標は成約価格（総額）の中央値を使う

使い方: python3 reinfolib_report_pc02.py 成約集計.csv 取引集計.csv 出力.html 通知文.txt
出典: 国土交通省 不動産情報ライブラリ
API利用規約 第7条のクレジット表示をHTML末尾に入れる。
HTMLの様式は分析基盤の共通レポートテンプレート（analysis-hub）に従う。
通知文はファイルに書くのみで、外部送信はしない。
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

CREDIT = "このサービスは、国土交通省の不動産情報ライブラリのAPI機能を使用していますが、提供情報の最新性、正確性、完全性等が保証されたものではありません"
SOURCE = "出典: 国土交通省 不動産情報ライブラリ（https://www.reinfolib.mlit.go.jp/）"
PROCESSED = "「成約価格情報」（国土交通省）をもとに集計・加工して作成"
PROCESSED_BOTH = "「成約価格情報」「不動産取引価格情報」（国土交通省）をもとに集計・加工して作成"
COLORS = ["#3b6ea5", "#54823F", "#A87A1D"]


def load(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            row["count"] = int(row["count"])
            row["median_trade_price"] = int(row["median_trade_price"]) if row["median_trade_price"] else None
            row["median_unit_price"] = int(row["median_unit_price"]) if row["median_unit_price"] else None
            rows.append(row)
    return rows


def coverage_text(rows):
    """レポートの対象範囲の表記を、集計CSVの実データから組み立てる。

    都道府県数・期間（最初と最後の四半期）・総件数はいずれも入力行から
    数える。都道府県が47すべてそろっている場合だけ「全国」を付ける。
    """
    prefs = {r["prefecture"] for r in rows}
    periods = sorted({r["period"] for r in rows if r["period"] != "unknown"})
    total = sum(r["count"] for r in rows)

    def fmt(p):
        year, q = p.split("Q")
        return "%s年第%s四半期" % (year, q)

    if periods:
        span = fmt(periods[0]) if periods[0] == periods[-1] else "%s〜%s" % (fmt(periods[0]), fmt(periods[-1]))
    else:
        span = "期間不明"
    area = "全国47都道府県" if len(prefs) == 47 else "%d都道府県" % len(prefs)
    return "%s、%s、成約価格情報（priceClassification=02）%s件" % (area, span, format(total, ","))


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


def man(v):
    return format(round(v / 10000), ",")


def comparison(pc02_rows, pc01_rows):
    pc01 = {(r["prefecture"], r["municipality"], r["property_type"], r["period"]): r for r in pc01_rows}
    overlap = []
    for r in pc02_rows:
        k = (r["prefecture"], r["municipality"], r["property_type"], r["period"])
        o = pc01.get(k)
        if o and o["median_trade_price"] and r["median_trade_price"]:
            overlap.append((k, o["median_trade_price"], r["median_trade_price"]))
    ratios = [b / a for _, a, b in overlap if a > 0]
    by_type = defaultdict(list)
    for (k, a, b) in overlap:
        if a > 0:
            by_type[k[2]].append(b / a)
    return overlap, ratios, by_type


def main(src, pc01_src, html_out, notify_out):
    rows = load(src)
    pc01_rows = load(pc01_src) if pc01_src and os.path.exists(pc01_src) else []
    processed = PROCESSED_BOTH if pc01_rows else PROCESSED
    if not rows:
        notify_text = "\n".join([
            "【不動産成約価格・四半期まとめ】",
            "集計データがまだありません。",
            SOURCE,
            processed,
        ])
        body = '<section class="sec"><p>集計データがまだありません。</p></section>'
        foot = "<p>%s</p><p>%s</p><p>%s</p>" % (SOURCE, processed, CREDIT)
        html = render_page("不動産成約価格の集計", "REAL ESTATE CONTRACTED PRICES / QUARTERLY",
                           "不動産成約価格の集計", "", body, foot)
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
    trade_price = {}
    for r in frows:
        period_counts[r["period"]][r["property_type"]] += r["count"]
        if r["median_trade_price"] is not None:
            trade_price[(r["period"], r["property_type"])] = r["median_trade_price"]

    last, prev = periods[-1], periods[-2] if len(periods) > 1 else None
    last_total = sum(period_counts[last][t] for t in types)
    lines = ["【不動産成約価格・四半期まとめ】",
             "対象データ: 成約価格情報（priceClassification=02）",
             "対象: %s%s（成約件数が最多の市区町村）" % focus,
             "直近四半期: %s" % last]
    if prev:
        prev_total = sum(period_counts[prev][t] for t in types)
        d = last_total - prev_total
        sign = "+" if d >= 0 else ""
        lines.append("成約件数: %s件（前四半期 %s件、%s%s件）" % (format(last_total, ","), format(prev_total, ","), sign, format(d, ",")))
    else:
        lines.append("成約件数: %s件" % format(last_total, ","))
    for t in types:
        tp = trade_price.get((last, t))
        if tp is None:
            continue
        seg = "%s: 成約価格中央値 %s万円" % (t, man(tp))
        if prev and trade_price.get((prev, t)):
            dm = (tp - trade_price[(prev, t)]) / 10000.0
            sign = "+" if dm >= 0 else ""
            seg += "（前四半期比 %s%s万円）" % (sign, format(round(dm), ","))
        lines.append(seg)
    lines.append("※ 当方のデータでは m2単価に値が1件も入っていないため、価格は総額の中央値で示す")
    lines.append(SOURCE)
    lines.append(processed)
    notify_text = "\n".join(lines)

    lede = ('<p class="lede">%s。種別は中古マンション等と宅地(土地と建物)の2種のみで、'
            '価格は実際に契約された成約価格（総額）です。m2単価は当方のデータでは値が入っていません。</p>' % coverage_text(rows))

    legend = "、".join("%s=%s" % (COLORS[i % len(COLORS)], t) for i, t in enumerate(types))
    chart = '<div class="chart">%s</div>' % svg_bars(period_counts, periods, types)
    body = section("01", "CHART", "四半期ごとの成約件数 — %s%s" % focus,
                   chart + '<p class="legend">凡例: %s</p>' % legend)

    overlap, ratios, by_type = comparison(rows, pc01_rows)
    if overlap and ratios:
        med_ratio = statistics.median(ratios)
        trs = "".join(
            "<tr><td>%s</td><td>%s</td><td>%.3f</td></tr>" % (t, format(len(rs), ","), statistics.median(rs))
            for t, rs in sorted(by_type.items(), key=lambda kv: -len(kv[1])))
        comp = ('<p>取引価格情報（priceClassification=01、不動産取引のアンケート等に基づく価格）と、'
                '同じ「都道府県 × 市区町村 × 種別 × 四半期」で重なるグループは %s 件ありました'
                '（重なりは取引価格情報の対象期間 2024〜2025年内）。'
                'そのグループ同士で総額中央値を比べると、成約価格 ÷ 取引価格の比の中央値は %.3f で、'
                '大きな開きはありませんでした。</p>'
                '<table><thead><tr><th>種別</th><th>グループ数</th><th>比の中央値（成約 ÷ 取引）</th></tr></thead>'
                '<tbody>%s</tbody></table>'
                '<p>これは同一物件の値引き率ではなく、同じ地域・種別・四半期の中央値同士の比較です。'
                '取引価格情報には宅地(土地)・農地・林地も含まれますが、成約価格情報の種別は2種のみのため、'
                '比較はその2種に限られます。</p>'
                % (format(len(overlap), ","), med_ratio, trs))
    else:
        comp = ('<p>取引価格情報（priceClassification=01）と同じ「都道府県 × 市区町村 × 種別 × 四半期」で'
                '重なるグループは %s 件で、比較に足る重なりがありませんでした。</p>' % format(len(overlap), ","))
    body += section("02", "COMPARISON", "取引価格情報（01）との比較", comp)

    foot = "<p>%s</p><p>%s</p><p>%s</p>" % (SOURCE, processed, CREDIT)
    html = render_page("不動産成約価格の動向（%s%s）" % focus, "REAL ESTATE CONTRACTED PRICES / QUARTERLY",
                       "不動産成約価格の動向 — %s%s（四半期ごとの成約件数）" % focus, lede, body, foot)
    with open(html_out, "w", encoding="utf-8") as f:
        f.write(html)
    with open(notify_out, "w", encoding="utf-8") as f:
        f.write(notify_text + "\n")
    print(notify_text)
    print(f"overlap groups: {len(overlap)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
