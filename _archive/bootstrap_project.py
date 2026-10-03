import os
import argparse
from pathlib import Path

# Base directory for all AI Projects
BASE_DIR = Path(r"K:\Мой диск\AI Projects\Antigravity")

# The standard directories every new project should have
STANDARD_DIRS = [
    ".antigravity",
    "agents",
    "mcp",
    "skills",
    "scripts",
    "src",
    "docs",
    "tests"
]

DEFAULT_GEMINI_MD = """# Antigravity Workspace: {project_name}

## Overview
Brief description of the project goes here.

## Tech Stack
- **Language/Framework:** 
- **Database:**
- **Deployment:** 

## Working Rules
1. Research before implementation.
2. Follow the GUARDRAILS.md strictly.
3. Keep code modular and testable.
"""

DEFAULT_GUARDRAILS_MD = """# Security & Operational Guardrails

**CRITICAL:** These rules must be strictly followed by all agents.

1. **Critical File Protection:** Do not modify `.env`, `.key`, or deployment scripts without user confirmation.
2. **Execution Constraints:** Never run destructive commands (`rm -rf`, database drops) without explicit approval.
3. **Secret Management:** Do not output API keys or passwords in plaintext.
"""

def init_project(project_name):
    project_path = BASE_DIR / project_name
    
    if project_path.exists():
        print(f"[-] Error: Project '{project_name}' already exists at {project_path}")
        return
        
    print(f"[*] Initializing new project: {project_name}")
    
    # Create directories
    for d in STANDARD_DIRS:
        dir_path = project_path / d
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  -> Created {d}/")
        
    # Create template files
    gemini_path = project_path / ".antigravity" / "GEMINI.md"
    gemini_path.write_text(DEFAULT_GEMINI_MD.format(project_name=project_name), encoding="utf-8")
    print("  -> Created .antigravity/GEMINI.md")
    
    guardrails_path = project_path / ".antigravity" / "GUARDRAILS.md"
    guardrails_path.write_text(DEFAULT_GUARDRAILS_MD, encoding="utf-8")
    print("  -> Created .antigravity/GUARDRAILS.md")
    
    print(f"\n[+] Successfully scaffolded '{project_name}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize a new Antigravity project with the standard architecture.")
    parser.add_argument("project_name", help="Name of the new project")
    args = parser.parse_args()
    
    init_project(args.project_name)
