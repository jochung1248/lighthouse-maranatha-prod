from fastapi import FastAPI, BackgroundTasks
import os
import threading
import time
from subprocess import Popen

app = FastAPI(title="ppt_agent HTTP wrapper")

@app.get("/health")
async def health():
    return {"status": "ok"}

def start_agent_in_background():
    # Example: run the agent module as a subprocess.
    # Adjust the command if your agent requires args or env setup.
    cmd = ["python", "-m", "ppt_agent.agent"]
    Popen(cmd)  # fire-and-forget; logs go to container stdout/stderr

@app.on_event("startup")
async def on_startup():
    # If you want the agent to start when container starts, uncomment:
    # threading.Thread(target=start_agent_in_background, daemon=True).start()
    pass

@app.post("/run")
async def run_agent(background_tasks: BackgroundTasks):
    # Trigger the agent once, without blocking the request
    background_tasks.add_task(start_agent_in_background)
    return {"status": "started"}