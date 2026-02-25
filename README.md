# Tdarr Autoscaler

Dynamic Tdarr worker scaling based on Plex activity. 

Automatically scales Tdarr workers down when users are streaming on Plex
and scales them back up when Plex becomes idle.\
Designed to prevent CPU/GPU contention between Plex transcoding and
Tdarr processing --- especially useful on Intel QSV, NVENC, or
limited-resource servers.

Inspired by https://github.com/triw0lf/tdarr-autoscale

------------------------------------------------------------------------

## Overview

`tdarr-autoscaler.py` monitors Plex activity via Tautulli and dynamically
adjusts Tdarr worker limits using the Tdarr API.

It can:

-   Detect active playback sessions
-   Optionally count only active transcodes (ignores Direct Play /
    Direct Stream)
-   Apply different worker limits for:
    -   Idle (day)
    -   Active streaming (day)
    -   Idle (night)
    -   Active streaming (night)

------------------------------------------------------------------------

## Requirements

-   Python 3.8+
-   `requests` library

Install dependency:

``` bash
pip install requests
```

------------------------------------------------------------------------

## Configuration

Edit the `CONFIGURATION` section inside `tdarr-autoscaler.py`:

``` python
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
```

Adjust worker values according to your hardware capacity and desired
behavior.

------------------------------------------------------------------------

## Usage

### Option 1 --- Run as Tautulli Notification Script (Recommended)

1.  Copy `tdarr-autoscaler.py` into your **Tautulli scripts folder**

2.  Edit the configuration section

3.  In Tautulli, go to:

    Settings → Notification Agents

4.  Add a new **Script** notification agent

5.  Select `tdarr-autoscaler.py`

6.  Enable the following triggers:

    -   Playback Start
    -   Playback Stop
    -   Playback Pause
    -   Playback Resume
    -   Transcode Decision Change

7.  Leave **Conditions** and **Arguments** empty

------------------------------------------------------------------------

### Option 2 --- Run Manually

``` bash
chmod +x tdarr-autoscaler.py
./tdarr-autoscaler.py
```

------------------------------------------------------------------------

### Option 3 --- Run via Cron

Example (runs every 5 minutes):

``` bash
*/5 * * * * /path/to/tdarr-autoscaler.py >> /path/to/tdarr-autoscaler.log 2>&1
```

------------------------------------------------------------------------

## How It Works

1.  Queries Tautulli API for current activity
2.  Counts all sessions or only transcoding sessions (if enabled)
3.  Detects whether current time is within configured night window
4.  Sets Tdarr worker limits via Tdarr API
5.  Logs actions with timestamps

------------------------------------------------------------------------

## Recommended Use Cases

-   Single-GPU home servers
-   Intel iGPU (QSV) systems
-   Low-power NAS setups
-   Systems where Plex transcoding must always take priority
-   Mixed Tdarr + Plex workloads on shared hardware

------------------------------------------------------------------------

## License

MIT

