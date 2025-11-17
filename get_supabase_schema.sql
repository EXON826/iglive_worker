-- Run this in Supabase SQL Editor to get complete schema information
SELECT 
    pg_namespace.nspname as schema_name,
    pg_class.relname as table_name,
    pg_attribute.attname as column_name,
    pg_type.typname as data_type,
    pg_attribute.attnotnull as not_null,
    pg_attribute.atthasdef as has_default,
    pg_get_expr(pg_attrdef.adbin, pg_attrdef.adrelid) as default_value
FROM pg_attribute 
JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
JOIN pg_type ON pg_type.oid = pg_attribute.atttypid
LEFT JOIN pg_attrdef ON pg_attrdef.adrelid = pg_class.oid AND pg_attrdef.adnum = pg_attribute.attnum
WHERE 
    pg_namespace.nspname = 'public'
    AND pg_attribute.attnum > 0
    AND NOT pg_attribute.attisdropped
    AND pg_class.relkind = 'r'
    AND pg_class.relname IN (
        'telegram_users', 
        'star_payments', 
        'insta_links',
        'chat_groups',
        'jobs',
        'queue_items'
    )
ORDER BY schema_name, table_name, pg_attribute.attnum;