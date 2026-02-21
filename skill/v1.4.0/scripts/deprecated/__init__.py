"""
Deprecated scripts

These scripts are preserved for reference but should not be used:
- run_destructive_batch_v*: Old destructive batch versions
- temp_*: Temporary scripts
- *_v1.py: Superseded versions

Migrate to:
- repair_loop_v2 instead of run_destructive_batch_*
- core scripts instead of temp scripts
"""

__all__ = [
    'run_destructive_batch_v1',
    'run_destructive_batch_v2',
    'run_destructive_batch_v3',
    'temp_check_lock',
    'temp_ckpt_check',
    'prepare_destructive_assets',
    'prepare_long_text_assets_v1',
    'fix_progress_logs',
    'combine_repair_tasks',
    'merge_repair_outputs',
]
