# Antigravity Instruments

This repository/folder serves as a centralized hub for all **Skills**, **MCP Servers**, and **Utility Scripts** across your various Antigravity projects.

## Structure
- `skills/`: Collected Antigravity skills (`.md` files) from neighboring projects.
- `mcp/`: Collected MCP server configurations and scripts.
- `scripts/`: Assorted utility scripts (e.g. build, deployment, test scripts).
- `agents/`: Agent prompts, roles, and definitions.
- `collector.py`: The Python script used to harvest these files from neighboring projects.

## How to Collect
The `collector.py` script automatically scans all folders in `K:\Мой диск\AI Projects\Antigravity\`, looks for directories named `skills/`, `mcp/`, or `scripts/`, and copies them here.

### Manual Run
Just run the script via Python:
```powershell
python collector.py
```

### Automated Regular Collection (Proposed Solutions)

If you want this to happen regularly, here are the best ways to automate it:

**Option 1: Windows Task Scheduler (Recommended for Local Workstation)**
Since this folder lives on your local Workstation / Google Drive, you can create a Windows Task to run this script daily or on login.
1. Open Task Scheduler.
2. Create Basic Task -> "Sync Antigravity Instruments".
3. Trigger: "Daily" or "When I log on".
4. Action: Start a program.
   - Program/script: `python`
   - Add arguments: `collector.py`
   - Start in: `K:\Мой диск\AI Projects\Antigravity\Instruments`

**Option 2: Antigravity Scheduled Agent**
You can use the `/schedule` slash command inside Antigravity to tell an agent to run this script automatically.
Example prompt to agent: 
> "Every day at 10:00 AM, run `python K:\Мой диск\AI Projects\Antigravity\Instruments\collector.py` and report if there are any new files."

**Option 3: Watchdog Script (Real-time sync)**
We can write a Python `watchdog` script that runs in the background and listens for changes in `skills/` or `mcp/` across your projects, and immediately syncs them here. Let me know if you want to implement real-time synchronization.
