# reinfolib-tools

国土交通省の不動産情報ライブラリが提供する API（不動産価格（取引価格・成約価格）情報取得 API、XIT001）から不動産の取引価格情報を取得して、都道府県 × 市区町村 × 物件種別 × 四半期の件数と価格中央値に集計し、グラフと通知文を作る道具です。Python の標準ライブラリだけで動きます。データの取得には API キー（無料・申請制）が必要です。

## ファイル

- `reinfolib_collect.py`：都道府県と期間を指定して XIT001 を呼び、返ってきた JSON をそのままファイルに保存します
- `reinfolib_aggregate.py`：保存した JSON 群から、都道府県 × 市区町村 × 物件種別 × 四半期ごとの件数と、取引価格（総額）と平方メートル単価の中央値を CSV に集計します
- `reinfolib_report.py`：集計 CSV から、取引件数が最多の市区町村について、四半期ごとの件数を主要な物件種別（上位3種）で積み上げた棒グラフの HTML と、直近四半期の件数と、主要な物件種別ごとの平方メートル単価中央値を前四半期と比べた通知文を作ります。環境変数 `DISCORD_WEBHOOK_URL` が設定されていれば、通知文を Discord にも送ります
- `sample/xit001_sample.json`：API キーが無くても集計とレポートの動きを試せる、公式マニュアルの出力項目に沿ったサンプルデータです

## API キーの取得

キーは不動産情報ライブラリの API 利用申請ページ（https://www.reinfolib.mlit.go.jp/api/request/）から申請します。氏名、メールアドレス、利用目的などを登録し、審査が通るとキーがメールで届きます。料金はかかりません。

取得したキーは環境変数 `REINFOLIB_API_KEY` に設定して使います。キー自体をファイルに書く必要はありません。

```sh
export REINFOLIB_API_KEY="取得したキー"
```

## 使い方

```sh
# 1. 取引価格情報を取得する（既定は東京都・2024〜2025年・取引価格情報のみ）
python3 reinfolib_collect.py data/

# 都道府県（--area、カンマ区切りで複数可）と期間、価格情報の種別を指定する場合
python3 reinfolib_collect.py data/ --area 13,14 --from-year 2023 --to-year 2025 --price-classification 01
# --price-classification: 01=取引価格情報のみ、02=成約価格情報のみ、all=両方（既定は 01）

# 2. 集計する
python3 reinfolib_aggregate.py data/ reinfolib_quarterly_summary.csv

# 3. グラフと通知文を作る
python3 reinfolib_report.py reinfolib_quarterly_summary.csv reinfolib_report.html reinfolib_notify.txt
```

API キーが無い状態で動きだけ見たい場合は、サンプルデータで 2 と 3 を試せます。

```sh
python3 reinfolib_aggregate.py sample/ reinfolib_quarterly_summary.csv
python3 reinfolib_report.py reinfolib_quarterly_summary.csv reinfolib_report.html reinfolib_notify.txt
```

## 集計の読み方

取引価格情報は、実際の取引を対象に行われたアンケート調査に基づく価格です。売出時の希望価格ではありません。成約価格情報は、指定流通機構（レインズ）に登録された物件の成約事例に基づく価格です。集計では両者を区別せず、取得したレコード全体を対象に数えます。

集計は、取引時点（例:「2025年第1四半期」）を四半期にそろえ、都道府県・市区町村・物件種別（宅地（土地）、中古マンション等、など）ごとに件数を数え、取引価格の総額と平方メートル単価の中央値を出します。価格が入っていない、または数値として読めないレコードは、件数には数えますが中央値の計算からは除きます。

取得できる期間は、取引価格情報が2005年第3四半期以降、成約価格情報が2021年以降です。

## データの出典と利用条件

出典: 国土交通省 不動産情報ライブラリ（https://www.reinfolib.mlit.go.jp/）をもとに作成。

データの利用条件は、公共データ利用規約（第1.0版）に準拠します。利用の際は出典の記載が必要です。編集・加工して利用する場合は、出典とは別に、もとのコンテンツの名称と、編集・加工した旨を記載してください。この道具が出力するレポートと通知文には、「出典: 国土交通省 不動産情報ライブラリ（https://www.reinfolib.mlit.go.jp/）をもとに作成」と表示しています。

API の利用には API 利用規約が別にあります。本 API 機能を利用したサービスを提供する場合は、利用規約第7条のクレジット表示を、利用者が参照できる場所に表示する必要があります。この道具が作るレポート HTML には、クレジット表示の文言を末尾に入れています。また、「不動産情報ライブラリ」という名称は、国土交通省が認めた場合を除き、製品やサービスの名前に使うことはできません（不動産情報ライブラリ利用規約 第3条（7））。

## ライセンス

MIT License です。詳しくは LICENSE を見てください。
