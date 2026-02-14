import pandas as pd
import sys

csv_path = "data/Test_Batch/10._full-pipeline_press_test_3k-row/3k_translated.csv"
try:
    df = pd.read_csv(csv_path)
    if 'tokenized_zh' not in df.columns:
        print("Adding tokenized_zh column...")
        if 'source_zh' in df.columns:
            df['tokenized_zh'] = df['source_zh']
        else:
            print("Error: source_zh not found either!")
            sys.exit(1)
        df.to_csv(csv_path, index=False)
        print("Done.")
    else:
        print("Column already exists.")
except Exception as e:
    print(f"Error: {e}")
