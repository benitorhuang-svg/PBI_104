BEGIN READ ONLY;

WITH relation_rows AS (
    SELECT
        c.oid,
        n.nspname AS schema_name,
        c.relname AS relation_name,
        c.relkind,
        CASE c.relkind
            WHEN 'r' THEN 'table'
            WHEN 'p' THEN 'partitioned_table'
            WHEN 'v' THEN 'view'
            WHEN 'm' THEN 'materialized_view'
            WHEN 'f' THEN 'foreign_table'
            ELSE c.relkind::text
        END AS relation_kind
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE (
        n.nspname IN ('bronze', 'silver', 'gold')
        OR (n.nspname LIKE 'fdw_%' AND c.relkind = 'f')
    )
      AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
)
SELECT jsonb_pretty(
    jsonb_build_object(
        'catalogFormatVersion', 1,
        'database', current_database(),
        'serverVersion', current_setting('server_version'),
        'capturedAtUtc', to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
        'schemas', (
            SELECT COALESCE(jsonb_agg(schema_name ORDER BY schema_name), '[]'::jsonb)
            FROM (
                SELECT DISTINCT schema_name FROM relation_rows
            ) AS found_schemas
        ),
        'relations', COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'schema', relation_rows.schema_name,
                    'name', relation_rows.relation_name,
                    'kind', relation_rows.relation_kind,
                    'columns', (
                        SELECT COALESCE(
                            jsonb_agg(
                                jsonb_build_object(
                                    'ordinal', a.attnum,
                                    'name', a.attname,
                                    'type', format_type(a.atttypid, a.atttypmod),
                                    'nullable', NOT a.attnotnull,
                                    'hasDefault', (d.adbin IS NOT NULL),
                                    'identity', a.attidentity,
                                    'generated', a.attgenerated
                                ) ORDER BY a.attnum
                            ),
                            '[]'::jsonb
                        )
                        FROM pg_attribute AS a
                        LEFT JOIN pg_attrdef AS d
                          ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                        WHERE a.attrelid = relation_rows.oid
                          AND a.attnum > 0
                          AND NOT a.attisdropped
                    ),
                    'constraints', (
                        SELECT COALESCE(
                            jsonb_agg(
                                jsonb_build_object(
                                    'name', con.conname,
                                    'kind', con.contype,
                                    'definition', pg_get_constraintdef(con.oid, true)
                                ) ORDER BY con.conname
                            ),
                            '[]'::jsonb
                        )
                        FROM pg_constraint AS con
                        WHERE con.conrelid = relation_rows.oid
                    ),
                    'indexes', (
                        SELECT COALESCE(
                            jsonb_agg(
                                jsonb_build_object(
                                    'name', index_class.relname,
                                    'unique', index_info.indisunique,
                                    'primary', index_info.indisprimary,
                                    'definition', pg_get_indexdef(index_info.indexrelid)
                                ) ORDER BY index_class.relname
                            ),
                            '[]'::jsonb
                        )
                        FROM pg_index AS index_info
                        JOIN pg_class AS index_class ON index_class.oid = index_info.indexrelid
                        WHERE index_info.indrelid = relation_rows.oid
                    ),
                    'viewDefinitionMd5', CASE
                        WHEN relation_rows.relkind IN ('v', 'm')
                        THEN md5(pg_get_viewdef(relation_rows.oid, true))
                        ELSE NULL
                    END
                ) ORDER BY relation_rows.schema_name, relation_rows.relation_name
            ),
            '[]'::jsonb
        )
    )
)
FROM relation_rows;

COMMIT;
