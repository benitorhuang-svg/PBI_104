# JobWant Schema Registry

此資料夾是各職缺平台來源 schema、PostgreSQL 實際 schema 快照及共用 Gold 契約的索引。新平台或來源欄位更新時，先在此記錄證據和版本，再修改 ETL、migration 或 Power BI；不能只靠程式碼推測 schema。

## 目錄

```text
docs/schema/
  README.md
  registry.json
  catalog_snapshot.sql
  contracts/
    database-schema-contract-v1.md
  platforms/
    _template/source-schema.md
    104/source-schema.md
    yes123/source-schema.md
    yes123/capture-batch-v1.schema.json
  databases/
    <database>/catalog-<UTC timestamp>.json
```

- [共用資料庫契約](contracts/database-schema-contract-v1.md)：Bronze/Silver/Gold 職責、鍵、粒度、型別與 migration 規則。
- [平台登錄表](registry.json)：每個平台的識別碼、adapter、schema 狀態、證據文件和阻擋項目。
- `platforms/<platform>/source-schema.md`：來源契約和 adapter 輸出；逐項標示觀察日期、查詢範圍、資料型別證據及未知項目。
- `platforms/<platform>/*.schema.json`：版本化的 machine-readable adapter/capture schema。它們描述 JobWant 保存格式，不自動代表來源網站的官方 API schema。
- `databases/<database>/catalog-*.json`：只讀匯出的實際 PostgreSQL 關聯、欄位、型別、constraints、indexes 和 view 定義雜湊。按次新增，既有快照不覆寫。
- DDL 和可重播 migration 的實作仍由 `tools/sql/` 管理；此處快照記錄資料庫「實際長相」，不取代 migration。

## 更新規則

1. 每個新來源先複製 `platforms/_template/source-schema.md` 到新的小寫平台 slug 資料夾，填來源證據、觀察範圍、adapter 版本、欄位型別和 `BLOCKED` 項目。
2. API/頁面欄位有變動時，保留舊版 schema，建立新版本檔並更新 `registry.json`；不覆寫舊版，不把單次觀察擴寫成未驗證的全站保證。
3. PostgreSQL migration 前後都可執行 catalog 匯出，將結果存到相應資料庫資料夾。比對實際欄位和 keys，不能只比較 `schema_migrations` 最大版本。
4. Catalog 匯出刻意不保存角色、密碼、FDW user mapping 或連線 options；不把原始職缺列或個人資料放進 schema 文件。
5. 跨平台 Gold 變更須符合共用契約，並同時驗證 TMDL 欄位、資料粒度、鍵唯一性和 bridge 孤兒列。未確認的來源語意以 `BLOCKED` 記錄。

## 產生資料庫快照

在專案根目錄執行：

```powershell
python tools/export_postgres_schema_catalog.py --database jobwant_104 --database jobwant_yes123
```

工具透過 Compose PostgreSQL 執行 `catalog_snapshot.sql` 的唯讀查詢，輸出 UTF-8 JSON 到 `docs/schema/databases/<database>/`。新增資料庫時提供另一個 `--database jobwant_<platform>` 參數。

## 目前導入狀態

`104` 有有限範圍的 API 欄位證據；`yes123` 的 capture JSON 是 adapter 產物，不是官方 API JSON。yes123 使用授權、搜尋代碼映射與跨平台職類/技能對照仍依各平台證據文件管理。資料庫 view 差異見共用契約及 dated catalog，不以資料已存在推論導入閘門已通過。
