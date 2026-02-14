import json
import re
import os

def load_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def save_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

def format_model_block(name, p_mult, c_mult, in_price, out_price):
    # Determine correct formatting
    # Try to align with existing style: 2 spaces indent for model, 4 for props
    lines = []
    lines.append(f"  {name}:")
    lines.append(f"    prompt_mult: {p_mult}")
    lines.append(f"    completion_mult: {c_mult}")
    lines.append(f"    input_per_1M: {in_price}")
    lines.append(f"    output_per_1M: {out_price}")
    return "\n".join(lines)

def update_yaml():
    yaml_path = "config/pricing.yaml"
    json_path = "config/pricing_scraped_dump.json"
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    yaml_content = load_text(yaml_path)
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    # Normalize JSON data into a dict
    scraped_models = {}
    for item in json_data:
        model = item.get('model')
        if not model: continue
        scraped_models[model] = {
            'prompt_mult': item.get('promptMultiplier', 1.0),
            'completion_mult': item.get('completionRatio', 1.0),
            'input_per_1M': item.get('inputPrice', 0.0),
            'output_per_1M': item.get('outputPrice', 0.0)
        }

    # Identify where 'models:' starts
    models_start_match = re.search(r'^models:', yaml_content, re.MULTILINE)
    if not models_start_match:
        print("Error: Could not find 'models:' section in YAML.")
        return

    # Split content into parts to safer insertion/append
    # But wait, we want to update IN PLACE if exists.
    
    updated_content = yaml_content
    
    # 1. Update existing models
    # Find all models defined in YAML:   model_name:
    # Regex: ^  ([\w\-\.]+):
    
    # We will build a list of existing models in the YAML to decide what to append
    existing_models_in_yaml = set()
    
    # Iterate over scraped models
    new_blocks = []
    
    # We scan the YAML to find existing keys
    # To cover partial matching, we can use a callback or iterative regex
    
    for model_name, data in scraped_models.items():
        # strict regex for the model key indentation
        pattern = re.compile(rf"^  {re.escape(model_name)}:", re.MULTILINE)
        match = pattern.search(updated_content)
        
        if match:
            existing_models_in_yaml.add(model_name)
            # Update values
            # We look for the next lines until prompt_mult etc are found or next model starts
            # This is complex with regex. simpler:
            # If exists, we skip overwriting for now OR we overwrite. 
            # User said "incremental update" (增量更新). Usually implies adding new ones, 
            # but maybe updating old ones with new prices? 
            # Let's assume we overwrite values if they changed, or just report.
            # Given the difficulty of robustly editing YAML text without a parser, 
            # and the user's focus on "incremental", checking for NEW models is priority.
            # But let's try to update logic: 
            # If I find the block, I can try to replace the specific lines inside it.
            
            # For simplicity and safety against corruption, I will only ADD NEW models
            # unless I'm sure about updating.
            pass 
        else:
            # Model not in YAML, prepare to append
            block = format_model_block(
                model_name, 
                data['prompt_mult'], 
                data['completion_mult'], 
                data['input_per_1M'], 
                data['output_per_1M']
            )
            new_blocks.append(block)

    if not new_blocks:
        print("No new models to add.")
        # We should still probably update existing ones if prices changed, but let's stick to adding first.
        return

    print(f"Adding {len(new_blocks)} new models.")
    
    # Insert new models before 'surcharges:' or at the end of 'models:' section
    # Find insertion point
    surcharges_match = re.search(r'^surcharges:', updated_content, re.MULTILINE)
    
    insertion_text = "\n  # === New Scraped Models ===\n" + "\n".join(new_blocks) + "\n\n"
    
    if surcharges_match:
        start_idx = surcharges_match.start()
        updated_content = updated_content[:start_idx] + insertion_text + updated_content[start_idx:]
    else:
        # Append to end
        updated_content += "\n" + insertion_text

    save_text(yaml_path, updated_content)
    print("Successfully updated pricing.yaml")

if __name__ == "__main__":
    update_yaml()
