CREATE OR REPLACE VIEW vw_quality_exceptions AS
SELECT
    pipeline_run_id,
    batch_id AS source_snapshot_id,
    entity,
    business_key_type,
    business_key,
    exception_cause,
    source_file,
    source_row_number,
    load_date,
    source_batch_id
FROM src_quality_exceptions;
