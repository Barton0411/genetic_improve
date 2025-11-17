# Repository Guidelines

## Project Structure & Module Organization
`main.py` starts the PyQt6 desktop client, while business logic stays in `core/` (data processors, genetics, PPT builders) and shared helpers live in `utils/`. UI assets and widgets sit inside `gui/` and `templates/`, integrations live in `api/` and `auth/`, and deployment assets are grouped under `docker/`, `deployment/`, and `nginx/`. Keep configuration schemas in `config/`, data samples in `data/`, and route generated installers to `build/` or `dist/` with logs under `logs/`.

## Build, Test, and Development Commands
- `python -m venv venv && source venv/bin/activate` – create a Python 3.9+ environment.
- `pip install -r requirements.txt` – install desktop dependencies (`requirements.linux.txt` for servers).
- `python main.py` – launch the client with live OSS/download flows.
- `bash build_mac.sh` or `pyinstaller genetic_improve.spec` – package installers; artifacts drop into `dist/`.
- `docker compose -f docker-compose.limited.yml up --build` – run the limited API surface used by `api/api_client.py`.
- `python -m pytest test_slide_01.py test_slide_02.py` – regression-test PPT builders before shipping.

## Coding Style & Naming Conventions
Stick to PEP 8 with four-space indentation, descriptive snake_case for functions/modules, and PascalCase for Qt widgets. Prefer type hints on new public APIs, keep docstrings focused on inputs/outputs, and run `black .` before pushing. Store shared constants in JSON under `config/` or `version.py` instead of scattering literals throughout GUI files.

## Testing Guidelines
PyTest is the test harness. Mirror the `test_slide_*.py` pattern for report builders, and colocate small tests next to the module (e.g., `core/ppt_report/tests/`). Use sample spreadsheets in `data/` for deterministic fixtures; route generated files to `test_output/` or a temp directory and clean afterward. Target ~80 % statement coverage for new modules and capture at least one UI smoke test when editing `gui/`.

## Commit & Pull Request Guidelines
Follow the existing conventional prefixes (`fix:`, `chore:`, `Release vX.Y.Z`) and keep subject lines <72 characters. Reference affected modules in the body, update `CHANGELOG.md` plus `version.json` when user-visible behavior changes, and mention scripts (`deploy.sh`, `tasks.py`) touched. PRs must describe motivation, include test evidence (PyTest logs, GUI screenshots, or sample PPT exports), and reference linked issues or checklists.

## Security & Configuration Tips
Leave credentials in the ignored `.genetic_improve/` cache or environment variables loaded through `server_setup_guide.md`; never embed keys in source. Sanitize cattle IDs and farm codes before sharing logs from `logs/`, and wipe `dist/`/`build/` with `rm -rf` before publishing installers so temporary secrets do not leak.
