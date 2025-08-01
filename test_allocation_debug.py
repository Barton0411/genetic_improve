"""
Debug the allocation issue
"""

import pandas as pd
import json
from pathlib import Path

# Load recommendations
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
recommendations_file = project_path / "analysis_results" / "individual_mating_report.xlsx"

df = pd.read_excel(recommendations_file)

# Check a sample row
sample_row = df.iloc[0]
print("Sample cow:", sample_row['cow_id'])
print("Group:", sample_row['group'])

# Parse valid bulls
valid_bulls_str = sample_row['常规_valid_bulls']
print("\nRaw valid_bulls string (first 500 chars):")
print(repr(valid_bulls_str[:500]))

if isinstance(valid_bulls_str, str):
    try:
        # Use ast.literal_eval for Python literal evaluation
        import ast
        valid_bulls = ast.literal_eval(valid_bulls_str)
    except:
        print("Failed to parse valid_bulls")
        valid_bulls = []
    print(f"\nFound {len(valid_bulls)} valid regular bulls:")
    for i, bull in enumerate(valid_bulls[:3]):
        print(f"  Bull {i+1}: {bull['bull_id']}")
        print(f"    - Score: {bull.get('offspring_score', 0)}")
        print(f"    - Inbreeding: {bull.get('inbreeding_coeff', 0)}")
        print(f"    - Gene status: {bull.get('gene_status', 'Unknown')}")
        print(f"    - Meets constraints: {bull.get('meets_constraints', False)}")
        print(f"    - Semen count in JSON: {bull.get('semen_count', 0)}")