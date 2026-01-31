#!/usr/bin/env python3
"""验证 Bug 5 修复: Docker ENV 注入"""
import subprocess
import os
import sys

def verify_fix():
    print("=== Bug 5 验证: Docker ENV 注入 ===\n")
    
    # 检查 Docker 运行模板脚本是否存在
    print("1. 检查 Docker 运行模板脚本...")
    ps1_script = 'scripts/docker_run.ps1'
    sh_script = 'scripts/docker_run.sh'
    
    if not os.path.exists(ps1_script):
        print(f"❌ PowerShell 脚本不存在: {ps1_script}")
        return False
    
    if not os.path.exists(sh_script):
        print(f"❌ Bash 脚本不存在: {sh_script}")
        return False
    
    print(f"   ✓ PowerShell 脚本: {ps1_script}")
    print(f"   ✓ Bash 脚本: {sh_script}")
    
    # 检查脚本内容是否包含正确的 ENV 注入
    print("\n2. 检查脚本内容...")
    with open(ps1_script, 'r', encoding='utf-8') as f:
        ps1_content = f.read()
        
        if 'LLM_API_KEY' not in ps1_content:
            print("❌ PowerShell 脚本缺少 LLM_API_KEY 注入")
            return False
        
        if '-e' not in ps1_content or 'LLM_API_KEY=' not in ps1_content:
            print("❌ PowerShell 脚本缺少正确的 -e 参数格式")
            return False
    
    with open(sh_script, 'r', encoding='utf-8') as f:
        sh_content = f.read()
        
        if 'LLM_API_KEY' not in sh_content:
            print("❌ Bash 脚本缺少 LLM_API_KEY 注入")
            return False
        
        if '-e LLM_API_KEY' not in sh_content:
            print("❌ Bash 脚本缺少正确的 -e 参数格式")
            return False
    
    print("   ✓ PowerShell 脚本包含正确的 ENV 注入逻辑")
    print("   ✓ Bash 脚本包含正确的 ENV 注入逻辑")
    
    # 检查 .env.example 是否更新
    print("\n3. 检查 .env.example...")
    env_example = '.env.example'
    
    if not os.path.exists(env_example):
        print(f"❌ 文件不存在: {env_example}")
        return False
    
    with open(env_example, 'r', encoding='utf-8') as f:
        env_content = f.read()
        
        if 'LLM_API_KEY' not in env_content:
            print("❌ .env.example 缺少 LLM_API_KEY")
            return False
        
        if 'LLM_BASE_URL' not in env_content:
            print("❌ .env.example 缺少 LLM_BASE_URL")
            return False
    
    print(f"   ✓ .env.example 包含正确的环境变量名")
    
    # 检查 docker-compose.yml 是否与 .env.example 一致
    print("\n4. 检查 docker-compose.yml 一致性...")
    compose_file = 'docker-compose.yml'
    
    if os.path.exists(compose_file):
        with open(compose_file, 'r', encoding='utf-8') as f:
            compose_content = f.read()
            
            if 'LLM_API_KEY' in compose_content:
                print("   ✓ docker-compose.yml 使用 LLM_API_KEY")
            else:
                print("   ⚠️  docker-compose.yml 未使用 LLM_API_KEY")
    
    print("\n✅ Bug 5 修复验证通过: Docker ENV 注入机制已修复")
    print("\n使用方法:")
    print("  Windows (PowerShell):")
    print('    $env:LLM_API_KEY="your_key_here"')
    print('    .\\scripts\\docker_run.ps1 python scripts/translate_llm.py --input data/input.csv --output data/output.csv')
    print("\n  Linux/Mac (Bash):")
    print('    export LLM_API_KEY="your_key_here"')
    print('    ./scripts/docker_run.sh python scripts/translate_llm.py --input data/input.csv --output data/output.csv')
    
    return True

if __name__ == '__main__':
    sys.exit(0 if verify_fix() else 1)
