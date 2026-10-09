# yes123 來源與 Adapter Schema 記錄

## 識別與狀態

- 平台 slug：`yes123`
- Adapter：`tools/acquisition/platforms/yes123/`
- Schema 狀態：`ADAPTER_CAPTURE_OBSERVED`; onboarding gate: `BLOCKED`
- 最近觀察：2026-10-09（Asia/Taipei）
- Capture format：[`capture-batch-v1.schema.json`](capture-batch-v1.schema.json)
- 核對批次：`data/yes123/series/48626f7911f1c1443cec/20261009T100639Z-d498dc6bd2e6.json`

## 來源範圍與證據邊界

目前 adapter 請求 `https://www.yes123.com.tw/admin/job_refer_list.asp`，解析 HTML 職缺卡片後輸出 JobWant 的 JSON capture batch。JSON schema 描述的是這個 adapter/capture 版本，**不是 yes123 官方 JSON API schema**。該批次使用 `category_code=2_1006_0002_0003`，manifest 的 `codeKind` 為 `YES123_WORK_MODE`；單一完整批次不能證明其他代碼、查詢條件或未來頁面都遵守相同 shape。

提供的批次標示 `COMPLETE`，manifest 回報 25 筆、保存 25 個 `jobs`；同系列 10:08 的快照有相同 25 個 `source_job_key`。欄位名稱/型別證據僅限這兩次 capture 和目前 adapter 程式碼。

## Adapter 職缺輸出欄位

`jobs[]` 目前輸出：`source_platform`、`source_job_key`、`source_company_key`、`native_job_id`、`native_company_id`、`job_title`、`company_name`、`raw_salary`、`salary_observations[]`、`raw_area`、`standardized_address`、`appear_date_raw`、`job_url`。來源 ID 與代碼保留為文字；raw 欄位和正規化欄位分開保存。

`salary_observations[]` 的 capture 輸出欄位記在 JSON Schema。金額 parser 的 decimal 在此 JSON 格式中會序列化為文字或 null；PostgreSQL Silver 的 numeric 型別是另一個資料庫契約，兩者不可混為同一 schema。

## 待確認與阻擋

- 網站資料保存、分析和展示授權仍是導入閘門；匿名可取回不等於授權。
- `WcodeList`、`JcodeList` 和候選 `work_mode.json` 代碼之間的對應尚未確認；來源搜尋碼須以字串、含 `code_kind` 保存。
- 這份職缺列表 capture 沒有技能欄位證據；不可從職稱或描述猜測技能橋接。
- 分頁、總數語意、排序穩定性和其他代碼的完整性需有各自 evidence 才能升級 schema 狀態。

## 更新方式

adapter/capture shape 改變時，保留 v1 schema，新建 `capture-batch-v2.schema.json` 並更新 `registry.json`。更新需要 sanitized fixture、觀察範圍、欄位差異與 hash；未確認的上游語意仍標 `BLOCKED`。
