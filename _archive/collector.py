import os
import shutil
from pathlib import Path

# Base directories
BASE_DIR = Path(r"K:\Мой диск\AI Projects\Antigravity")
INSTRUMENTS_DIR = BASE_DIR / "Instruments"
GLOBAL_CONFIG_DIR = Path(r"C:\Users\Артем Ганжа\.gemini\config")

# Target categories to collect
CATEGORIES = ["skills", "mcp", "scripts", "agents"]

def setup_instrument_dirs():
    """Ensure the base instrument directories exist."""
    for category in CATEGORIES:
        (INSTRUMENTS_DIR / category).mkdir(parents=True, exist_ok=True)

def sync_skills_globally():
    """Sync collected skills to the global Antigravity config directory."""
    global_skills_dir = GLOBAL_CONFIG_DIR / "skills"
    global_skills_dir.mkdir(parents=True, exist_ok=True)
    
    local_skills_dir = INSTRUMENTS_DIR / "skills"
    
    if local_skills_dir.exists():
        print(f"\n[*] Syncing skills to Global Antigravity Config ({global_skills_dir})...")
        # We copy all subdirectories from Instruments/skills to global skills
        for project_skill_dir in local_skills_dir.iterdir():
            if project_skill_dir.is_dir():
                dest = global_skills_dir / project_skill_dir.name
                shutil.copytree(project_skill_dir, dest, dirs_exist_ok=True)
                print(f"  -> Synced skills from {project_skill_dir.name} globally")

def collect_instruments():
    """Scan neighboring projects and collect skills, mcp, and scripts."""
    setup_instrument_dirs()
    
    print(f"[*] Starting collection from {BASE_DIR}")
    
    # Iterate over all directories in the base folder
    for project_dir in BASE_DIR.iterdir():
        if not project_dir.is_dir() or project_dir.name == "Instruments" or project_dir.name.startswith(".") or project_dir.name == ".system_generated":
            continue
            
        print(f"  -> Scanning project: {project_dir.name}")
        
        for category in CATEGORIES:
            source_path = project_dir / category
            
            if source_path.exists() and source_path.is_dir():
                # Destination will look like: Instruments/skills/ProjectName
                dest_path = INSTRUMENTS_DIR / category / project_dir.name
                
                # print(f"      + Found {category}/ -> copying to {dest_path.relative_to(BASE_DIR)}")
                
                # Copy the directory tree
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
                
    print("[*] Local collection complete!")
    
    # After local collection, sync to global config
    sync_skills_globally()
    
    print("\n[+] All done!")

if __name__ == "__main__":
    collect_instruments()
