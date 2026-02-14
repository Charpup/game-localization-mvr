#!/usr/bin/env python3
import os
import ast
import json
import glob
import yaml
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any

@dataclass
class PromptUsage:
    script_path: str
    function_name: str
    step_name: Optional[str]
    prompt_snippet: Optional[str]
    prompt_source: Optional[str]
    model_role: Optional[str]
    model_config: Optional[Dict[str, Any]] = None # From routing.yaml
    batch_size_info: Optional[str] = None # Extracted from code

def load_routing_config() -> Dict[str, Any]:
    try:
        with open("config/llm_routing.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("routing", {})
    except Exception as e:
        print(f"DEBUG: Failed to load routing config: {e}")
        return {}

class ContextVisitor(ast.NodeVisitor):
    """
    Scans file to build context:
    1. Function definitions (for referencing prompt builders)
    2. Local assignments (to resolve variable -> string/call)
    3. Chat calls
    4. Batch size tracking
    """
    def __init__(self, source_code: str, file_path: str):
        self.source_code = source_code
        self.file_path = file_path
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.scope_assignments: Dict[str, Dict[str, ast.AST]] = {"global": {}}
        self.current_scope = "global"
        self.usages: List[PromptUsage] = []
        
        # Track potential batch sizes found in file
        self.found_batch_sizes: List[str] = []

    def _get_segment(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.source_code, node) or ""

    def visit_FunctionDef(self, node):
        self.functions[node.name] = node
        
        # Check args for batch_size default
        for arg in node.args.args:
            if 'batch' in arg.arg.lower() and 'size' in arg.arg.lower():
                # We can't easily get the default value here without zip, but simple check is enough
                pass
        
        # Check defaults
        defaults = node.args.defaults
        args = node.args.args
        if defaults:
            # Map defaults to args from right to left
            for i, default in enumerate(reversed(defaults)):
                 arg_name = args[-(i+1)].arg
                 if 'batch' in arg_name.lower() and 'size' in arg_name.lower():
                     val = self._resolve_constant(default)
                     if val:
                         self.found_batch_sizes.append(f"{node.name}.{arg_name}={val}")

        parent_scope = self.current_scope
        self.current_scope = node.name
        self.scope_assignments[self.current_scope] = {}
        self.generic_visit(node)
        self.current_scope = parent_scope

    def _resolve_constant(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant):
            return str(node.value)
        return None

    def visit_Assign(self, node):
        # Track assignments: x = ...
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            self.scope_assignments[self.current_scope][var_name] = node.value
            
            # Check for BATCH_SIZE constants
            if 'BATCH_SIZE' in var_name:
                val = self._resolve_constant(node.value)
                if val:
                    self.found_batch_sizes.append(f"{var_name}={val}")
                    
        self.generic_visit(node)

    def _resolve_source(self, node: ast.AST, scope: str) -> str:
        """Trace back the source of a node."""
        if isinstance(node, ast.Constant):
            return str(node.value)
        
        if isinstance(node, ast.JoinedStr):
            return self._get_segment(node)
            
        if isinstance(node, ast.Call):
            # If function call, try to find the function definition
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                if fname in self.functions:
                    return self._get_segment(self.functions[fname])
            return f"Call to: {self._get_segment(node)}"

        if isinstance(node, ast.Name):
            var_name = node.id
            local_vars = self.scope_assignments.get(scope, {})
            if var_name in local_vars:
                return self._resolve_source(local_vars[var_name], scope)
            global_vars = self.scope_assignments.get("global", {})
            if var_name in global_vars:
                return self._resolve_source(global_vars[var_name], "global")
            return f"Variable({var_name}) - Definition not found"

        return self._get_segment(node)

    def visit_Call(self, node):
        # Look for llm_client.chat(...)
        is_chat = False
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'chat':
            is_chat = True
        
        if is_chat:
            step_name = "unknown"
            
            # Extract metadata.step
            for kw in node.keywords:
                if kw.arg == 'metadata' and isinstance(kw.value, ast.Dict):
                    for k, v in zip(kw.value.keys, kw.value.values):
                        if isinstance(k, ast.Constant) and k.value == 'step':
                            if isinstance(v, ast.Constant):
                                step_name = v.value

            # Extract System and User Prompts
            sources = []
            for kw in node.keywords:
                if kw.arg in ['system', 'user']:
                    resolved = self._resolve_source(kw.value, self.current_scope)
                    sources.append(f"--- Argument: {kw.arg} ---\n{resolved}")

            full_source = "\n\n".join(sources)
            
            # Best effort batch size association
            batch_info = "; ".join(set(self.found_batch_sizes)) if self.found_batch_sizes else "Not found in static analysis"

            self.usages.append(PromptUsage(
                script_path=self.file_path,
                function_name="chat",
                step_name=step_name,
                prompt_snippet=full_source[:100].replace('\n', ' ') + "...",
                prompt_source=full_source,
                model_role=step_name,
                model_config=None, # Will inject later
                batch_size_info=batch_info
            ))
            
        self.generic_visit(node)

def extract_prompts(file_path: str) -> List[PromptUsage]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        visitor = ContextVisitor(source, file_path)
        visitor.visit(tree)
        return visitor.usages
    except Exception as e:
        print(f"⚠️ Error parsing {file_path}: {e}")
        return []

def main():
    import yaml
    
    root_dir = "scripts"
    all_usages = []
    
    routing_config = load_routing_config()
    print("🔍 Scanning scripts for LLM usage (Source + Models + Batch)...")
    
    for file_path in glob.glob(f"{root_dir}/*.py"):
        usages = extract_prompts(file_path)
        if usages:
            print(f"  Found {len(usages)} in {file_path}")
            # Inject routing info
            for u in usages:
                if u.step_name and u.step_name in routing_config:
                    u.model_config = routing_config[u.step_name]
                elif "_default" in routing_config:
                    u.model_config = routing_config["_default"]
                    u.model_config["note"] = "Used _default fallback"
                
            all_usages.extend(usages)
            
    output_path = "artifacts/llm_prompt_inventory.json"
    os.makedirs("artifacts", exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump([asdict(u) for u in all_usages], f, indent=2, ensure_ascii=False)
        
    print(f"✅ Saved enriched inventory to {output_path}")

if __name__ == "__main__":
    main()
