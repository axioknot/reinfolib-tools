#!/usr/bin/env python3
"""XIT001 の生JSON群から「都道府県 × 市区町村 × 物件種別 × 四半期」の
件数と価格中央値を集計する。

入力ディレクトリ内の xit001_*.json（JSON配列）をすべて読む。
使う項目は公式マニュアルの出力定義に基づく:
  Prefecture（都道府県名）, Municipality（市区町村名）, Type（取引の種類）,
  Period（取引時点。例: "2025年第1四半期"）,
  TradePrice（取引価格・総額）, UnitPrice（取引価格・平方メートル単価）
価格が空文字・数値化できないレコードは、件数には数え、中央値からは除く。

使い方: python3 reinfolib_aggregate.py 入力ディレクトリ 出力.csv
出典: 国土交通省 不動産情報ライブラリ（国土交通省）をもとに作成
"""
import csv
import glob
import json
import os
import re
import statistics
import sys
from collections import defaultdict

PERIOD_RE = re.compile(r"(\d{4})年第(\d)四半期")


def to_number(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def main(src_dir, dst):
    groups = defaultdict(lambda: {"count": 0, "trade": [], "unit": []})
    files = sorted(glob.glob(os.path.join(src_dir, "xit001_*.json")))
    total = 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]
        records = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("data"), list):
                records.extend(item["data"])
            else:
                records.append(item)
        for r in records:
            total += 1
            m = PERIOD_RE.search(str(r.get("Period", "")))
            period = f"{m.group(1)}Q{m.group(2)}" if m else "unknown"
            key = (r.get("Prefecture", ""), r.get("Municipality", ""), r.get("Type", ""), period)
            g = groups[key]
            g["count"] += 1
            tp = to_number(r.get("TradePrice"))
            if tp is not None:
                g["trade"].append(tp)
            up = to_number(r.get("UnitPrice"))
            if up is not None:
                g["unit"].append(up)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["prefecture", "municipality", "property_type", "period",
                    "count", "median_trade_price", "median_unit_price"])
        for (pref, muni, ptype, period), g in sorted(groups.items()):
            med_t = int(statistics.median(g["trade"])) if g["trade"] else ""
            med_u = int(statistics.median(g["unit"])) if g["unit"] else ""
            w.writerow([pref, muni, ptype, period, g["count"], med_t, med_u])
    print(f"files: {len(files)}, records: {total}, groups: {len(groups)} -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
