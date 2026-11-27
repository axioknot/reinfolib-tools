#!/usr/bin/env python3
"""不動産情報ライブラリ（国土交通省）の XIT001 API で不動産価格
（取引価格・成約価格）情報を取得し、生JSONのまま保存する。

仕様は公式APIマニュアル（XIT001）に基づく:
  エンドポイント: https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001
  APIキーはリクエストヘッダー Ocp-Apim-Subscription-Key で渡す。
  year（必須）, quarter（1-4）, area（都道府県コード2桁）, city, station の
  いずれかが必要。出力は gzip でエンコードされる場合がある。
  取引価格情報は2005年第3四半期以降、成約価格情報は2021年以降を指定可能。

APIキーは環境変数 REINFOLIB_API_KEY から読む。キーの発行には
不動産情報ライブラリの「API利用申請ページ」からの申請と審査が必要
（API利用規約 第3条・第5条・第13条: 氏名、メールアドレス、利用目的等を登録し、
承認後にキーがメールで通知される）。

利用条件: 公共データ利用規約（第1.0版）。出典の記載が必要。
「不動産情報ライブラリ」の名称を製品名に使うことはできない（利用規約 第3条（7））。

使い方:
  python3 reinfolib_collect.py 出力先ディレクトリ \
      [--area 13] [--from-year 2024] [--to-year 2025] [--price-classification 01]
  --area はカンマ区切りで複数指定可（例: 13,14）。既定は 13（東京都）。
  --price-classification: 01=取引価格情報のみ, 02=成約価格情報のみ,
  all=両方（API のパラメータ自体を送らない。API の仕様では未指定時に両方が返る）。
  未指定時の既定は 01。
"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001"
UA = "reinfolib-tools/0.1 (public data accumulation; contact: accounts@axioknot.com)"


def fetch_one(key, params):
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Ocp-Apim-Subscription-Key": key,
        "Accept-Encoding": "gzip",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    out_dir = args[0]

    def opt(name, default=None):
        if name in args:
            return args[args.index(name) + 1]
        return default

    areas = [a.strip().zfill(2) for a in opt("--area", "13").split(",") if a.strip()]
    from_year = int(opt("--from-year", "2024"))
    to_year = int(opt("--to-year", "2025"))
    pc = opt("--price-classification", "01")
    if pc and pc.lower() == "all":
        pc = None

    key = os.environ.get("REINFOLIB_API_KEY")
    if not key:
        print("ERROR: 環境変数 REINFOLIB_API_KEY が未設定です。", file=sys.stderr)
        print("不動産情報ライブラリのAPI利用申請（無料・審査あり）でキーを取得してください。", file=sys.stderr)
        sys.exit(2)

    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "runs.jsonl")
    total = 0
    for area in areas:
        for year in range(from_year, to_year + 1):
            for quarter in (1, 2, 3, 4):
                params = {"year": year, "quarter": quarter, "area": area}
                if pc:
                    params["priceClassification"] = pc
                try:
                    payload = fetch_one(key, params)
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8", "ignore")[:300]
                    print(f"HTTP {e.code} area={area} {year}Q{quarter}: {body}", file=sys.stderr)
                    sys.exit(1)
                if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                    records = [payload]
                    n_records = len(payload["data"])
                elif isinstance(payload, list):
                    records = payload
                    n_records = len(payload)
                else:
                    records = [payload]
                    n_records = 1
                fname = f"xit001_area{area}_{year}q{quarter}_pc{pc or 'all'}.json"
                path = os.path.join(out_dir, fname)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(records, f, ensure_ascii=False)
                rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "params": params,
                       "records": n_records, "file": fname}
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"area={area} {year}Q{quarter}: {n_records} records -> {fname}")
                total += n_records
                time.sleep(1)
    print(f"total records: {total}")


if __name__ == "__main__":
    main()
