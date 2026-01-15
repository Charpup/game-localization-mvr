#!/usr/bin/env python3
import sys
import os
import csv
import argparse
import pandas as pd
from typing import Optional

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column headers to standard schema."""
    # Case-insensitive mapping
    column_map = {}
    
    for col in df.columns:
        c_lower = str(col).lower().strip()
        
        # ID Priority
        if c_lower in ['id', 'string_id', 'stringid', 'key', 'uid']:
            column_map[col] = 'string_id'
            
        # Source Priority
        elif c_lower in ['source', 'zh', 'source_zh', 'zh-cn', 'text', 'original']:
            column_map[col] = 'source_zh'
            
        # Target Priority (if present in input)
        elif c_lower in ['target', 'ru', 'target_ru', 'ru-ru', 'translation']:
            column_map[col] = 'target_ru'
            
        # Context
        elif c_lower in ['context', 'desc', 'description', 'comment', 'memo']:
            column_map[col] = 'context'

    # Apply mapping
    if column_map:
        print(f"  Mapping columns: {column_map}")
        df = df.rename(columns=column_map)
        
    return df

def ingest_file(input_path: str, output_path: str):
    print(f"Processing {input_path}...")
    
    ext = os.path.splitext(input_path)[1].lower()
    
    try:
        if ext == '.xlsx':
            df = pd.read_excel(input_path, engine='openpyxl', dtype=str)
        elif ext == '.csv':
            df = pd.read_csv(input_path, dtype=str)
        else:
            print(f"[Error] Unsupported format: {ext}")
            return False
            
        # Normalize Headers
        df = normalize_headers(df)
        
        # Validation
        if 'string_id' not in df.columns or 'source_zh' not in df.columns:
            print(f"[Error] Missing required columns (string_id, source_zh). Found: {list(df.columns)}")
            return False
            
        # Fill NaN
        df = df.fillna('')
        
        # Output Schema Enforce
        required_cols = ['string_id', 'source_zh']
        opt_cols = ['context', 'source_locale']
        
        # Add missing optional columns
        for c in opt_cols:
            if c not in df.columns:
                df[c] = ''
                
        # Select and write
        final_cols = required_cols + [c for c in opt_cols if c in df.columns]
        # Keep other columns? For now, stick to standard schema + context
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df[final_cols].to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"  Saved to {output_path} ({len(df)} rows)")
        return True
        
    except Exception as e:
        print(f"[Error] Ingest failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Ingest CSV/XLSX and normalize to source_raw.csv")
    parser.add_argument("--input", required=True, help="Input file path")
    parser.add_argument("--output", default="data/source_raw.csv", help="Output CSV path")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"File not found: {args.input}")
        sys.exit(1)
        
    success = ingest_file(args.input, args.output)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
