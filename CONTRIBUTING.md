# Contributing to Auto_Jobs_Applier_AIHawk

Thank you for your interest in contributing to Auto_Jobs_Applier_AIHawk. This document provides guidelines for contributing to the project.

## Bug Reports

When submitting a bug report, please include:

- A clear, descriptive title prefixed with [BUG]
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Any error messages or screenshots
- Your environment details (OS, Python version, etc.)

## Feature Requests

For feature requests, please:

- Prefix the title with [FEATURE]
- Include a feature summary
- Provide detailed feature description
- Explain your motivation for the feature
- List any alternatives you've considered

## Pull Request Process

1. Create a feature branch from the latest `main` branch.
2. Keep each pull request focused and use a descriptive branch name, such as `feat/profile-match-filter`, `fix/login-detection`, or `docs/setup-guide`.
3. Write clear commit messages using the Conventional Commits style where practical (for example, `fix: handle missing job descriptions`).
4. Update documentation and add tests for behavior changes.
5. Run the test suite and review `git status` before committing.
6. Submit a pull request with a concise summary, test results, and any relevant screenshots or logs with personal information removed.

Never commit API keys, `.env` files, personal resumes, LinkedIn cookies, browser profiles, job application records, or other private data. Do not use real LinkedIn accounts or submit real applications in automated tests.

## Code Style Guidelines

- Follow PEP 8 standards for Python code
- Include docstrings for new functions and classes
- Add comments for complex logic
- Maintain consistent naming conventions

## Development Setup

1. Clone the repository and create a Python 3.12 virtual environment.
2. Install dependencies from `requirements.txt`.
3. Copy safe templates from `data_folder_example/` into the local, Git-ignored `data_folder/`.
4. Configure a local Ollama model or a cloud provider and keep all credentials in the ignored runtime data folder.

## Issue Labels

The project uses the following labels:

- **bug**: Something isn't working correctly
- **enhancement**: New feature requests
- **good first issue**: Good for newcomers
- **help wanted**: Extra attention needed
- **documentation**: Documentation improvements

## Testing

Before submitting a PR:

- Run `python -m pytest`.
- Add focused regression tests for bug fixes and new behavior.
- Do not make live external applications part of automated tests.

## Communication

- Be respectful and constructive in discussions
- Use clear and concise language
- Reference relevant issues in commits and PRs
- Ask for help when needed

The project maintainers reserve the right to reject any contribution that doesn't meet these guidelines or align with the project's goals.
