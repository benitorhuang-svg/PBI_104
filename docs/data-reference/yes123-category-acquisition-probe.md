# yes123 職務分類目錄與取得方式盤點

> 本文件的網站與條款觀察是 2026-10-09 的查核快照。文件下方的「JobWant 現況」原始盤點也記錄了當時尚未建立 adapter 的基準；之後已新增 yes123 adapter、capture schema、測試批次及本機資料庫。這些新增工作不會解除資料授權或代碼映射閘門，現況請同時參考 [yes123 source schema](../schema/platforms/yes123/source-schema.md) 與 [schema registry](../schema/README.md)。

## 查核範圍

- 查核日期：2026-10-09（Asia/Taipei）
- 本次只讀公開頁面、JSON 目錄、robots.txt、網站條款與兩個工作樹中的 acquisition 程式；未呼叫登入功能、未擷取職缺批次、未修改外部 crawler 工作樹、`data/104/` 或模型。
- 導入狀態：**進行中**；職缺批次擷取維持 **BLOCKED**，直到資料使用授權與分類代碼對應確認。

## 已核實的公開入口

| 項目 | 本次觀察 | 限制 |
|---|---|---|
| 職缺搜尋頁 | [`SingleIndex`](https://m.yes123.com.tw/memmvc/jobsearch/SingleIndex?os=WEB) 可匿名 HTTP 200 開啟，回傳 HTML，頁面標題為「工作機會查詢」。 | 原始 HTML 未呈現可直接盤點的完整分類樹；頁面引用多個前端腳本。 |
| 行動站職務選單（單筆驗證，2026-10-09） | 透過公開選單選取「資訊軟體系統 → 軟體／工程 → 軟體工程師」，[單筆搜尋網址](https://m.yes123.com.tw/memmvc/jobsearch/SingleListPage?apikey=&WcodeList=2_1011_0001_0005&workType=00000&keyword=)帶出 `WcodeList=2_1011_0001_0005`。 | 這是單筆 UI 證據，不代表完整代碼目錄。結果頁回傳 ASP.NET `IndexOutOfRangeException`，因此沒有驗證結果筆數或分頁。 |
| 分類搜尋路徑 | 一個公開搜尋結果使用 `JcodeList=3_1010_0003_0001` 與 `page=0`，頁面匿名 HTTP 200 回傳 HTML。 | 只觀察到單一樣本；不得據此推定代碼各段意義、層級、完整目錄或頁碼起始規則。 |
| 候選 JSON 目錄 | [`/json_file/work_mode.json`](https://www.yes123.com.tw/json_file/work_mode.json) 匿名 HTTP 200，`application/json`，UTF-8 BOM；本次回應含 44 個根群組與 574 個唯一子代碼。 | 根節點只有 `level_1_name`、`list_2`，沒有根代碼；本次 JSON 的子代碼集合不含上列 `JcodeList` 樣本。尚未證明兩者是同一套職務分類。 |
| 行動站 robots.txt | [`m.yes123.com.tw/robots.txt`](https://m.yes123.com.tw/robots.txt) 列出 `/WEBAPI`、`/api`、`/scheduleAPI`、`/js` 等 Disallow 規則。 | 不呼叫這些禁止路徑；robots 規則也不構成資料授權。 |
| 主站 robots.txt | [`www.yes123.com.tw/robots.txt`](https://www.yes123.com.tw/robots.txt) 列有 `/commonAPI/`、`/WEBAPI/` 等 Disallow 規則。 | 主站與行動站是不同 host，兩份規則分別適用。 |

上述分類搜尋頁的原始 HTML 中沒有找到 `currentPage`、`lastPage`、`total` 等同名欄位；這只表示本次觀察的 HTML 沒有這些字串，**不表示**網站沒有分頁總數或其他分頁契約。

## 各平台的擷取代碼邊界

- 每個平台由自己的 adapter 建立搜尋條件：104 使用官方 `jobcat`；yes123 公開網址曾觀察到 `JcodeList`，本次行動站 UI 單筆搜尋則帶出 `WcodeList`。這兩種 yes123 參數是否等價仍未確認。擷取代碼不跨平台共用，也不因數值或字串相似而視為同一分類。
- 保存代碼時使用複合身份 `(source_platform, code_kind, native_code)`，其中 `native_code` 一律保留原始字串。這避免 yes123 的底線分段代碼被轉成整數，也避免 104 與 yes123 發生代碼碰撞。
- 「分類目錄代碼」與「搜尋請求代碼」是兩種不同 `code_kind`。104 目前已證實其搜尋條件使用 `jobcat`；yes123 的 `work_mode.json` 子代碼尚未證明等於搜尋頁 `JcodeList` 或本次觀察到的 `WcodeList`，而 `JcodeList` 與 `WcodeList` 彼此的映射也未確認，因此保持分開，對照狀態為 **BLOCKED**。
- 若日後建立跨平台分類分析，新增可追溯、可人工覆核的 crosswalk；來源原碼與每次批次實際使用的搜尋代碼仍需原樣保存。
- 公開搜尋頁的互動選單至少觀察到三層職務瀏覽路徑（例如「資訊軟體系統 → 軟體／工程 → 軟體工程師」），並提示最多選 10 種職務。這說明兩層 JSON 候選目錄不能直接被當成完整的搜尋選單或代碼表。

## 權利與取得方式

- [yes123 授權條款](https://www.yes123.com.tw/admin/campaign/stickyjob/legal.asp)說明網站文字、圖形、程式、畫面安排及資料編輯等內容受智慧財產權保護，未經授權不得複製、改作、編輯、散布或公開傳輸。
- [求職規約](https://www.yes123.com.tw/admin/integrate/memberrights.asp)列有求職者瀏覽及儲存職缺服務。依目前可見文字，這不等於授權本專案建立批次資料集或再利用網站內容；此處為風險判讀，仍需 yes123 書面確認。
- 因此 yes123 導入已開始，但在取得書面授權或官方資料/API 使用條款前，分類目錄與職缺內容的批量保存及擷取維持 **BLOCKED**。JSON 路徑可匿名讀取，只證明技術上可達，不代表授權或保證該檔供本專案批量再利用。

## JobWant 導入基準與可沿用範圍（查核當時）

- 初始查核時 Git 工作目錄乾淨，HEAD 為 `3290b6c`；當時的 `docs/`、`tools/`、`data/` 尚無 yes123 專用實作或資料。其後已建立獨立 adapter 與 capture 契約，但仍未取得批量保存/分析/展示授權，也尚未完成中央 Gold 導入。
- `tools/acquisition/platforms/jobwant_104/capture/category_catalog.py` 固定使用 104 `JobCat.json` URL，並依 `no`、`des`、`eng`、`n` 欄位解析；`tools/capture_category_matrix.py` 是其穩定命令入口，使用 104 搜尋 API 與 `jobcat` 查詢。這些來源契約不能直接當成 yes123 解析器。
- 可沿用的是資料取得原則：保存原始來源證據、checksum、來源版本與批次狀態，並以來源回報總量驗證完整性。yes123 的分頁大小、限制、排序和重複職缺規則都尚未驗證。
- yes123 導入期間，來源代碼必須與 104 `jobcat` 分開保存；取得書面使用授權並確認代碼映射後，才將 yes123 批次接入 Silver/Gold。跨平台分類對照另建可人工覆核的關聯，不覆寫任何來源原始代碼。

## 外部 crawler 專案中的既有實作

- `C:\Users\benit\Desktop\crawler_system_v3_JSON_LD\core\categories\fetch_categories_yes123.py` 已請求上述 JSON，並正確用 `utf-8-sig` 處理 BOM。該檔目前在外部 Git 工作樹中有未提交修改；本次只讀檢視，沒有執行或改寫。
- 本次實際解析的回應有 44 個根群組、574 個唯一子代碼，沒有重複子代碼。根節點沒有 `code` 欄位，但目前程式用 `item.get("code", "")` 當 `layer_1_id`，會讓這批資料的父層 ID 全空。
- JSON 實際只有根群組加 `list_2` 子項兩層；現有程式把子代碼同時填入 `layer_2_id` 與 `layer_3_id`。這符合該專案三層資料表的欄位形狀，卻不保留來源真實層級。
- 本次 JSON 子代碼範例為 `2_1001_0001_0001`；先前公開搜尋路徑樣本為 `3_1010_0003_0001`，在這份 JSON 中找不到。這是待查的分類代碼對應問題，不足以斷言它們一定是不同分類系統。
- `fetch_categories_all.py` 會並行執行多個平台匯入器，且各匯入器會寫入資料庫；不要為了確認 yes123 而執行全平台總控。

## 進入 PoC 前必須補齊的證據

1. yes123 書面確認可取得的資料範圍、保存期限、內部分析與對外呈現權限。
2. yes123 確認候選 `work_mode.json` 可供本專案批次使用，或提供核准的 API／匯出來源；路徑及使用方式須符合網站條款與對應 host 的 robots.txt。
3. 官方確認分類樹欄位、穩定 ID、父子關係和層級，並說明 `JcodeList`、`WcodeList` 與 JSON 子代碼的對應方式。
4. 官方分頁／終止條件、總量欄位、速率限制、分類更新與停用語意，以及資料變動時的完整性判定方式。

以上證據是啟用持久化擷取的閘門。架構工作已開始：yes123 必須以獨立來源代碼與來源職缺鍵進入 Bronze/Silver，確認跨來源自然鍵與分類對照後，才接入 Gold；本階段不變更 Power Query、TMDL 或 PBIR。
