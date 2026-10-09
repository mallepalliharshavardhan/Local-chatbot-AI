# Local-chatbot-AI

[![Python CI](https://github.com/mallepalliharshavardhan/Local-chatbot-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/mallepalliharshavardhan/Local-chatbot-AI/actions/workflows/ci.yml)

A local-first assistant for searching LinkedIn jobs and handling supported Easy Apply applications. Search settings, profile information, and application tracking are managed on your machine. Ollama can be used for local language-model inference.

> **Important:** This is experimental browser automation. LinkedIn's interface and policies can change. Review your profile, answers, search settings, and every generated application before use. The software does not bypass sign-in verification, CAPTCHAs, or other security checks and cannot guarantee that an application is submitted.

## What it does

- Searches using the titles, locations, dates, experience levels, and job types in your local YAML configuration.
- Restricts automated submissions to supported LinkedIn Easy Apply flows.
- Can score a job against your profile and skip jobs below the configured match threshold.
- Tracks results in local JSON files and an Excel workbook.
- Supports a supplied PDF resume or the project's resume-generation flow.
- Supports Ollama for local model inference; cloud model providers may also be configured.

Automation may stop for LinkedIn verification, unsupported application questions, missing job details, or other conditions that require your attention. Do not use generated answers without checking that they are accurate and truthful.

## Requirements

- Windows, macOS, or Linux
- Python 3.12
- Google Chrome
- Git
- Ollama and a compatible downloaded model when using the local provider

## Install

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/mallepalliharshavardhan/Local-chatbot-AI.git
cd Local-chatbot-AI
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

On macOS or Linux, create and use the environment with:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

## Configure

Create the runtime data folder from the safe example files. The checked-in examples contain placeholders only:

```powershell
New-Item -ItemType Directory -Force .\data_folder
Copy-Item .\data_folder_example\config.yaml .\data_folder\config.yaml
Copy-Item .\data_folder_example\plain_text_resume.yaml.example .\data_folder\plain_text_resume.yaml
Copy-Item .\data_folder_example\secrets.yaml.example .\data_folder\secrets.yaml
```

For macOS or Linux, use:

```bash
mkdir -p data_folder
cp data_folder_example/config.yaml data_folder/config.yaml
cp data_folder_example/plain_text_resume.yaml.example data_folder/plain_text_resume.yaml
cp data_folder_example/secrets.yaml.example data_folder/secrets.yaml
```

1. Edit `data_folder/plain_text_resume.yaml` with your accurate profile information. Do not leave placeholder information in an application profile.
2. Edit `data_folder/config.yaml` with your job titles, locations, and search filters. `minimum_profile_match_score` defaults to `60`; `max_pages_per_search` defaults to `1`. Increase the page limit cautiously.
3. The example selects Ollama with `qwen2.5:3b`. Install Ollama from its official site, start its local service if needed, then download the model:

   ```bash
   ollama pull qwen2.5:3b
   ```

   Confirm the model is available with `ollama list`. Ollama does not require an API key in `secrets.yaml`. If you select a cloud provider instead, put its valid key in the local `data_folder/secrets.yaml`; never commit or share that file.
4. Review any authorization, work-preference, and self-identification answers in your profile. They must reflect your own situation.

## Run

On Windows, pass a PDF resume using an absolute path:

```powershell
.\.venv\Scripts\python.exe .\main.py --resume "C:\path\to\your\resume.pdf"
```

On macOS or Linux:

```bash
./.venv/bin/python main.py --resume "/path/to/your/resume.pdf"
```

Without `--resume`, the application uses its resume-generation flow. To inspect options:

```bash
./.venv/bin/python main.py --help
```

On Windows, use `.\.venv\Scripts\python.exe .\main.py --help`.

The first run opens the bot's dedicated Chrome profile at `chrome_profile/linkedin_profile`. Sign in there and complete any LinkedIn verification yourself. A login in your regular Chrome profile is separate. The bot must reach LinkedIn's authenticated feed before it proceeds.

`--collect` gathers job data without submitting applications:

On Windows:

```powershell
.\.venv\Scripts\python.exe .\main.py --collect
```

On macOS or Linux:

```bash
./.venv/bin/python main.py --collect
```

## Local outputs and privacy

Application records and browser session data can contain personal information. Keep them on your machine:

- `data_folder/` contains your profile, secrets, and generated application records.
- `chrome_profile/` contains your browser session and authentication cookies.
- PDF resumes placed in the repository root are excluded from Git.
- Local virtual environments, logs, caches, and test artifacts are also excluded.

The repository's `.gitignore` excludes these local paths. Check `git status` before every commit and never force-add credentials, browser data, resumes, or output workbooks. Ollama prompts are processed by your local Ollama service; cloud-provider prompts are sent to that provider. LinkedIn receives the information you submit in an application.

## Tests

Run the test suite from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

```bash
./.venv/bin/python -m pytest
```

The GitHub Actions workflow runs the same tests with Python 3.12.

## Repository layout

```text
.
├── data_folder_example/   Safe configuration and profile templates
├── docs/                  User and workflow documentation
├── src/                   Search, authentication, LLM, and application modules
├── tests/                 Automated tests
├── main.py                Command-line entry point
├── requirements.txt       Python dependencies
└── .github/workflows/     Continuous integration
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Create a short-lived branch from `main`, use a descriptive prefix such as `feat/`, `fix/`, `docs/`, or `chore/`, run tests, and open a pull request. Do not include personal job-search data, secrets, or browser state in issues or pull requests.

## License

See [LICENSE](LICENSE) before using or redistributing this project. It contains project-specific restrictions; this repository does not claim to be MIT-licensed. Retain the license and attribution when sharing the source.

This project is derived from [Auto_Jobs_Applier_AIHawk](https://github.com/feder-cr/Auto_Jobs_Applier_AIHawk). Refer to the upstream project and the included license for original project attribution and terms.
