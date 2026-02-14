import json
import os
import re

def normalize_price(price_str):
    if not price_str:
        return 0.0
    # Remove '$', spaces, and anything after '/', 
    # e.g. "$ 0.1000 / 1M tokens" -> 0.1000
    # "Suggested price: $ 0.1000 / 1M tokens" -> find the first number after $
    
    # Try to extract numbers
    # Pattern to match dollar amount
    match = re.search(r'\$\s*([\d\.]+)', price_str)
    if match:
        return float(match.group(1))
    return 0.0

def normalize_multiplier(val_str):
    if not val_str or val_str == '-':
        return None
    # "Prompt multiplier: 0.05" -> 0.05
    # "Completion ratio: 10.0000" -> 10.0
    
    # We might have one or two mixed in text.
    # The scraping logic returns raw text like: "Prompt multiplier: 0.05\n Completion ratio: 10.0000"
    # or just "Prompt multiplier: 30"
    
    prompt_mult = 1.0
    completion_ratio = 1.0
    
    pm_match = re.search(r'Prompt multiplier:\s*([\d\.]+)', val_str)
    if pm_match:
        prompt_mult = float(pm_match.group(1))
        
    cr_match = re.search(r'Completion ratio:\s*([\d\.]+)', val_str)
    if cr_match:
        completion_ratio = float(cr_match.group(1))
        
    return {
        "prompt": prompt_mult,
        "completion": completion_ratio
    }

def main():
    base_dir = "C:/Users/bob_c/.gemini/antigravity/auto_Localization/config/"
    files = ["pricing_p1.json", "pricing_p2.json", "pricing_p3.json", "pricing_p4.json", "pricing_p5.json"]
    
    all_data = []
    seen_models = set()
    
    print(f"Merging files from {base_dir}...")
    
    for f_name in files:
        path = os.path.join(base_dir, f_name)
        if not os.path.exists(path):
            print(f"Warning: {path} not found.")
            continue
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            print(f"Loaded {len(data)} items from {f_name}")
            
            for item in data:
                # Normalize keys: the pages had slightly different keys
                # P1/P2: modelName, billingType, suggestedPrice, magnification, tags
                # P4: model, type, price, magnification, grouping (or tags?)
                # P5: model, type, pricing, multiplier, tags
                
                model = item.get('modelName') or item.get('model')
                if not model:
                    continue
                    
                if model in seen_models:
                    continue
                seen_models.add(model)
                
                # Normalize Price
                raw_price = item.get('suggestedPrice') or item.get('price') or item.get('pricing') or ""
                raw_mag = item.get('magnification') or item.get('multiplier') or ""
                
                # Extract clean values
                # We want: model, inputPrice, outputPrice, promptMult, completionRatio
                
                # Parsing logic
                # usually "Suggested price: $ X / ... Completion price: $ Y / ..."
                suggested = 0.0
                completion = 0.0
                
                # Simple split/regex for price
                s_match = re.search(r'Suggested price:\s*\$\s*([\d\.]+)', raw_price)
                if s_match:
                    suggested = float(s_match.group(1))
                
                c_match = re.search(r'Completion price:\s*\$\s*([\d\.]+)', raw_price)
                if c_match:
                    completion = float(c_match.group(1))
                    
                # Fallback for simple "$ X / time" formats (images?)
                if not s_match and not c_match:
                     simple_match = re.search(r'\$\s*([\d\.]+)', raw_price)
                     if simple_match:
                         suggested = float(simple_match.group(1))
                         completion = suggested # Assume symmetric or single price
                
                # Parsing logic for magnification
                mag_data = normalize_multiplier(raw_mag)
                
                entry = {
                    "model": model,
                    "inputPrice": suggested,
                    "outputPrice": completion,
                    # If mag_data is none (e.g. image models), use 1.0 or None
                    "promptMultiplier": mag_data['prompt'] if mag_data else 1.0,
                    "completionRatio": mag_data['completion'] if mag_data else 1.0,
                    "tags": item.get('tags') or [] # P4/P5 might have "grouping" string instead of tags list?
                }
                
                # Fix P4 grouping if string
                grouping = item.get('grouping')
                if grouping and isinstance(grouping, str):
                     entry['tags'] = grouping.split()
                
                all_data.append(entry)
                
        except Exception as e:
            print(f"Error reading {f_name}: {e}")

    print(f"Total unique models merged: {len(all_data)}")
    
    out_path = os.path.join(base_dir, "pricing.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        # Minified output
        json.dump(all_data, f, separators=(',', ':'))
        
    print(f"Saved minified JSON to {out_path}")

if __name__ == "__main__":
    main()
