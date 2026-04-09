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

Lesson plans are saved under [plans](/Users/mattmacmini/projects/TeachingAgent/dewey/plans). Local memory is stored under [db](/Users/mattmacmini/projects/TeachingAgent/dewey/db).

## Tests

Run the test suite from the repository root:

```bash
python3 -m pytest -q
```

## Project Layout

- [agent.py](/Users/mattmacmini/projects/TeachingAgent/dewey/agent.py): main CLI loop
- [onboarding.py](/Users/mattmacmini/projects/TeachingAgent/dewey/onboarding.py): first-run profile capture
- [memory.py](/Users/mattmacmini/projects/TeachingAgent/dewey/memory.py): SQLite-backed memory
- [tools/standards.py](/Users/mattmacmini/projects/TeachingAgent/dewey/tools/standards.py): standards and WIDA lookup
- [data/va_sols.json](/Users/mattmacmini/projects/TeachingAgent/dewey/data/va_sols.json): SOL reference data
- [data/wida_descriptors.json](/Users/mattmacmini/projects/TeachingAgent/dewey/data/wida_descriptors.json): WIDA reference data
