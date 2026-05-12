# Dewey

Dewey is a CLI instructional planning partner for K-12 teachers. It uses Anthropic models plus a small local memory store to help with lesson planning, standards lookup, and WIDA-informed differentiation.

## Requirements

- Python 3.11+
- An `ANTHROPIC_API_KEY`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

## Run

Start the CLI from the repository root:

```bash
python3 agent.py
```

Useful options:

- `python3 agent.py --help`
- `python3 agent.py --reset`

You can also install the CLI in editable mode:

```bash
pip install -e .
dewey
```

In-app commands:

- `/help`: show available commands
- `/save [title]`: save Dewey's last response as a lesson plan
- `/plans`: list saved lesson plans
- `/profile`: show remembered teacher profile notes
- `/forget profile`: delete remembered profile notes
- `/forget all`: delete all local memory

## Dashboard

Run the local dashboard from the repository root:

```bash
python3 dashboard_server.py
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

If you installed the package with `pip install -e .`, you can also run:

```bash
dewey-dashboard
```

To reach it from another trusted device on your Tailscale network, bind to all
interfaces and open `http://<this-device-tailscale-ip>:8765`:

```bash
python3 dashboard_server.py --host 0.0.0.0 --port 8765
```

The dashboard currently includes:

- Lesson Library: browse saved lesson plans
- Teacher Profile: review and clear remembered profile notes
- Standards: search Virginia SOLs and WIDA descriptors
- Save Plan: save markdown lesson plans with grade and subject metadata

Lesson plans are saved under [plans](/Users/m3studio/projects/TeachingAgent/dewey/plans). Local memory is stored under [db](/Users/m3studio/projects/TeachingAgent/dewey/db).

## Tests

Run the test suite from the repository root:

```bash
python3 -m pytest -q
```

## Project Layout

- [agent.py](/Users/m3studio/projects/TeachingAgent/dewey/agent.py): main CLI loop
- [onboarding.py](/Users/m3studio/projects/TeachingAgent/dewey/onboarding.py): first-run profile capture
- [memory.py](/Users/m3studio/projects/TeachingAgent/dewey/memory.py): SQLite-backed memory
- [dashboard_server.py](/Users/m3studio/projects/TeachingAgent/dewey/dashboard_server.py): local dashboard server and JSON API
- [dashboard](/Users/m3studio/projects/TeachingAgent/dewey/dashboard): dashboard frontend assets
- [tools/standards.py](/Users/m3studio/projects/TeachingAgent/dewey/tools/standards.py): standards and WIDA lookup
- [data/va_sols.json](/Users/m3studio/projects/TeachingAgent/dewey/data/va_sols.json): SOL reference data
- [data/wida_descriptors.json](/Users/m3studio/projects/TeachingAgent/dewey/data/wida_descriptors.json): WIDA reference data
