#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
loc-mVR v1.4.0 - Game Localization Pipeline CLI

Usage:
    python -m scripts.cli translate --input data/input.csv --output data/output.csv
    python -m scripts.cli qa --input data/translated.csv --report qa_report.json
    python -m scripts.cli repair --input data/translated.csv --tasks repair_tasks.jsonl
    python -m scripts.cli glossary --input data/terms.csv --output data/glossary.yaml
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_translate(args):
    """Run translation pipeline."""
    from scripts.core.batch_runtime import main as batch_main
    # Transform args for batch_runtime
    sys.argv = [
        'batch_runtime.py',
        '--input', args.input,
        '--output', args.output,
        '--config', args.config or 'workflow/config.yaml'
    ]
    if args.glossary:
        sys.argv.extend(['--glossary', args.glossary])
    batch_main()


def cmd_qa(args):
    """Run QA pipeline."""
    from scripts.core.soft_qa_llm import main as qa_main
    sys.argv = [
        'soft_qa_llm.py',
        args.input,
        args.style_guide or 'workflow/style_guide.md',
        args.glossary or 'data/glossary.yaml',
        args.rubric or 'workflow/soft_qa_rubric.yaml',
        '--out_report', args.report,
        '--out_tasks', args.tasks
    ]
    qa_main()


def cmd_repair(args):
    """Run repair loop."""
    from scripts.core.repair_loop_v2 import main as repair_main
    sys.argv = [
        'repair_loop_v2.py',
        '--input', args.input,
        '--tasks', args.tasks,
        '--output', args.output
    ]
    repair_main()


def cmd_glossary(args):
    """Run glossary translation."""
    from scripts.core.glossary_translate_llm import main as glossary_main
    sys.argv = [
        'glossary_translate_llm.py',
        '--input', args.input,
        '--output', args.output
    ]
    glossary_main()


def main():
    parser = argparse.ArgumentParser(
        prog='loc-mvr',
        description='Game Localization Pipeline CLI v1.4.0'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Translate command
    translate_parser = subparsers.add_parser('translate', help='Run translation pipeline')
    translate_parser.add_argument('-i', '--input', required=True, help='Input CSV file')
    translate_parser.add_argument('-o', '--output', required=True, help='Output CSV file')
    translate_parser.add_argument('-c', '--config', help='Config YAML file')
    translate_parser.add_argument('-g', '--glossary', help='Glossary YAML file')
    translate_parser.set_defaults(func=cmd_translate)
    
    # QA command
    qa_parser = subparsers.add_parser('qa', help='Run QA pipeline')
    qa_parser.add_argument('-i', '--input', required=True, help='Input translated CSV')
    qa_parser.add_argument('-r', '--report', default='data/qa_report.json', help='QA report output')
    qa_parser.add_argument('-t', '--tasks', default='data/repair_tasks.jsonl', help='Repair tasks output')
    qa_parser.add_argument('--style-guide', help='Style guide markdown')
    qa_parser.add_argument('--glossary', help='Glossary YAML')
    qa_parser.add_argument('--rubric', help='QA rubric YAML')
    qa_parser.set_defaults(func=cmd_qa)
    
    # Repair command
    repair_parser = subparsers.add_parser('repair', help='Run repair loop')
    repair_parser.add_argument('-i', '--input', required=True, help='Input CSV')
    repair_parser.add_argument('--tasks', required=True, help='Repair tasks JSONL')
    repair_parser.add_argument('-o', '--output', required=True, help='Output CSV')
    repair_parser.set_defaults(func=cmd_repair)
    
    # Glossary command
    glossary_parser = subparsers.add_parser('glossary', help='Translate glossary')
    glossary_parser.add_argument('-i', '--input', required=True, help='Input terms CSV')
    glossary_parser.add_argument('-o', '--output', required=True, help='Output glossary YAML')
    glossary_parser.set_defaults(func=cmd_glossary)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
