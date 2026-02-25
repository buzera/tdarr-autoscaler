#!/usr/bin/env python3
"""
Tdarr Autoscaler - Dynamic worker scaling based on Plex activity

Automatically scales Tdarr workers down when people are streaming and back up when Plex is idle. 

Requirements:
  - Python 3.8+
  - requests

Run as Tautulli notification script:
  - Copy tdarr-autoscaler.py into Tautulli scripts folder
  - Edit the CONFIGURATION section below to match your infrastructure settings
  - Add a new Script notification agent in Tautulli -> Settings -> Notification Agents and select tdarr-autoscaler.py from the scripts folder
  - Configure the triggers for the notification script: Playback Start, Playback Stop, Playback Pause, Playback Resume and Transcode Decision Change
  - Leave empty the Conditions and Arguments config

OR

Run manually (or cronjob):
  chmod +x tdarr-autoscaler.py
  ./tdarr-autoscaler.py

  - Cron example:
  */5 * * * * /path/to/tdarr-autoscaler.py >> /path/to/tdarr-autoscaler.log 2>&1
"""

import datetime as _dt
import json as _json
from typing import List

import requests


#######################
# CONFIGURATION
#######################

# Tdarr settings
TDARR_URL = "http://tdarr-ip:port"

# Worker type - what does your Tdarr use for transcoding?
# Options: "GPU" (Intel QSV, NVENC, etc.), "CPU" (software encoding), or "BOTH"
WORKER_TYPE = "GPU"

# Tautulli settings
TAUTULLI_URL = "http://tautulli-ip:port"
TAUTULLI_API_KEY = ""  # Settings > Web Interface > API Key

# Do not count Direct Play / Direct Stream since they are very easy on CPU/GPU
COUNT_TRANSCODES_ONLY = True

# Worker limits - adjust to your hardware capability
WORKERS_IDLE = 1          # No one watching (daytime)
WORKERS_ACTIVE = 0        # Someone is streaming
WORKERS_NIGHT = 1         # No one watching (night)
WORKERS_NIGHT_ACTIVE = 0  # Streaming during night

# Night mode hours (24h format)
NIGHT_START = 0   # Midnight
NIGHT_END = 5     # 5 AM

#######################
# SCRIPT - no edits needed below
#######################

def _now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _error_exit(msg: str, code: int = 1) -> None:
    print(f"[{_now_stamp()}] ERROR: {msg}")
    raise SystemExit(code)


def _get_json(url: str, timeout: int = 10) -> dict:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _error_exit(f"HTTP/JSON error fetching {url}: {e}")


def _post_json(url: str, payload: dict, timeout: int = 10) -> None:
    try:
        r = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=_json.dumps(payload),
            timeout=timeout,
        )
        r.raise_for_status()
    except Exception as e:
        _error_exit(f"HTTP error POST {url}: {e}")


def _worker_types_from_friendly(name: str) -> List[str]:
    if name == "GPU":
        return ["transcodegpu"]
    if name == "CPU":
        return ["transcodecpu"]
    if name == "BOTH":
        return ["transcodegpu", "transcodecpu"]
    _error_exit("Invalid WORKER_TYPE. Use 'GPU', 'CPU', or 'BOTH'")


def _get_first_node_id(tdarr_url: str) -> str:
    nodes = _get_json(f"{tdarr_url}/api/v2/get-nodes")
    if not isinstance(nodes, dict) or not nodes:
        return ""
    return next(iter(nodes.keys()), "")


def _is_night(hour: int, night_start: int, night_end: int) -> bool:
    if night_start < night_end:
        return (hour >= night_start) and (hour < night_end)
    else:
        return (hour >= night_start) or (hour < night_end)


def _get_streams_tautulli(tautulli_url: str, api_key: str) -> int:
    data = _get_json(f"{tautulli_url}/api/v2?apikey={api_key}&cmd=get_activity")
    try:
        streams = (
            data.get("response", {})
            .get("data", {})
            .get("stream_count", 0)
        )
    except Exception:
        streams = 0

    if streams is None:
        return 0
    try:
        return int(streams)
    except Exception:
        return 0

def _get_transcodes_tautulli (tautulli_url: str, api_key: str) -> int:
    data = _get_json(f"{tautulli_url}/api/v2?apikey={api_key}&cmd=get_activity")
    try:
        sessions = (
        data.get("response", {})
        .get("data", {})
        .get("sessions", [])
    )
    except Exception:
        return 0

    if not isinstance(sessions, list):
        return 0

    return sum(
        1
        for s in sessions
        if isinstance(s, dict) and s.get("video_decision") == "transcode"
    )

def _get_current_worker_limit(tdarr_url: str, node_id: str, worker_type: str) -> int:
    nodes = _get_json(f"{tdarr_url}/api/v2/get-nodes")
    try:
        val = nodes[node_id]["workerLimits"][worker_type]
    except Exception:
        val = 0

    if val is None:
        return 0
    try:
        return int(val)
    except Exception:
        return 0


def _alter_worker_limit(tdarr_url: str, node_id: str, worker_type: str, process: str) -> None:
    payload = {"data": {"nodeID": node_id, "workerType": worker_type, "process": process}}
    _post_json(f"{tdarr_url}/api/v2/alter-worker-limit", payload)


def main() -> None:
    worker_types = _worker_types_from_friendly(WORKER_TYPE)

    node_id = _get_first_node_id(TDARR_URL)
    if not node_id or node_id == "null":
        _error_exit("Could not get Tdarr node ID")

    hour = int(_dt.datetime.now().strftime("%H"))

    is_night = _is_night(hour, NIGHT_START, NIGHT_END)
    time_mode = "Night" if is_night else "Day"

    if COUNT_TRANSCODES_ONLY:
        streams = _get_transcodes_tautulli(TAUTULLI_URL, TAUTULLI_API_KEY)
        stream_type = "Transcodes"
    else:
        streams = _get_streams_tautulli(TAUTULLI_URL, TAUTULLI_API_KEY)
        stream_type = "Streams"

    if streams is None:
        streams = 0
    try:
        streams = int(streams)
    except Exception:
        streams = 0

    if is_night:
        if streams == 0:
            target_workers = WORKERS_NIGHT
        else:
            target_workers = WORKERS_NIGHT_ACTIVE
    else:
        if streams == 0:
            target_workers = WORKERS_IDLE
        else:
            target_workers = WORKERS_ACTIVE

    output = ""
    for tdarr_worker_type in worker_types:
        if tdarr_worker_type == "transcodegpu":
            type_label = "GPU Workers"
        else:
            type_label = "CPU Workers"

        current = _get_current_worker_limit(TDARR_URL, node_id, tdarr_worker_type)

        if current != target_workers:
            original = current
            if current < target_workers:
                while current < target_workers:
                    _alter_worker_limit(TDARR_URL, node_id, tdarr_worker_type, "increase")
                    current += 1
                diff = f"+{target_workers - original}"
            else:
                while current > target_workers:
                    _alter_worker_limit(TDARR_URL, node_id, tdarr_worker_type, "decrease")
                    current -= 1
                diff = f"-{original - target_workers}"
            output += f" | {type_label}: {target_workers} ({diff})"
        else:
            output += f" | {type_label}: {target_workers} (no change)"

    print(f"[{_now_stamp()}] {stream_type}: {streams} | Mode: {time_mode}{output}")


if __name__ == "__main__":
    main()
