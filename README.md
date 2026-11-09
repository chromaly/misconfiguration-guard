
# Misconfiguration Guard

Misconfiguration Guard is an AI-assisted security program that investigates security misconfigurations in application source code and configuration files. It specifically focuses on publicly exposed configuration, error information, and diagnostic endpoints without authentication. These three vulnerabilities are part of the OWASP A02:2025 – Security Misconfiguration risk category. We are trying to mitigate the improper or insecure configuration of application servers, frameworks, or default settings that leave systems open to attack.

I chose to investigate security misconfigurations because it's one of the most common cybersecurity mistakes I typically make when creating my own projects. I believe that AI-assisted security programs can help with auditing code and ensuring that vulnerabilities are not pushed to the public, so I would like to begin using this project for my own personal use for building safer applications. 

This project was adapted from an SQL-injection attack focused red-vs-blue starter project to explore different security issues. The current project includes an investigation agent (red), a defense agent (blue) that generates proposed fixes, and a GitHub Actions scanner that reviews pull requests and comments its findings, potentially being useful as a reviewer for other projects.

The simple practice application was also adapted to include intentional vulnerabilities and fake configuration values for local testing. It includes both the SQL injection vulnerabilities it initially contained as well as new security misconfiguration. 
NOTE: The PR scanner performs source-only review. Runtime verification of the new defender’s output has not been completed; findings and generated fixes require review.

Based on [lwu1822/red-vs-blue-starter]
(https://github.com/lwu1822/red-vs-blue-starter).

## How it Works

The project has three separate agent entry points. Each uses `llm.py` to communicate with the language model and `tools.py` to interact with external files and the local practice application. 

### Investigation Agent - Red Team

`agent/attack_agent.py` explores the directory and reads files with line numbers. It looks for exposed configuration, detailed error info, and diagnostic endpoints without authentication.

When the practice application is running locally, the agent can send GET or POST requests to investigate these exposures. This is ONLY possible for local applications: we are not trying to hack into live systems. 

### Defense Agent - Blue Team

`agent/defense_agent.py` reads `app.py` and generates a proposed corrected version in `app_fixed.py` that preserves the original application but fixes any vunerabilities.

The write tool specified in `tools.py` restricts output to that filename and checks for Python syntax. The agent can read the generated file back, but it still doesn't prove that the fix works at run time. Generated code must still be reviewed by someone else and tested separately before proper use. 

Note that this only works for app.py, and is limited in reach so far.

### Pull Request Scanner

Github Actions runs `agent/ci_scan.py` when a same-repository pull request is opened or updated. It reads source files and produces a Markdown report. It posts that report as a PR comment and saves it as an artifact.

This scanner doesn't run the investigation or defense agent loops (Red or Blue team), and only performs source review.

### Agent Loop

Each agent asks the model for one JSON action, validates and dispatches
that action, and returns the tool result to the model. This repeats until
the model submits a report or reaches the step limit.

Repository contents and HTTP responses are treated as untrusted evidence.
The tools provide restrictions independently of the model's instructions,
including directory boundaries, localhost-only HTTP requests without
redirect following, and constrained defense output.

## Setup and usage

Requires Python 3.10 or newer.

```bash
git clone https://github.com/chromaly/misconfiguration-guard.git
cd misconfiguration-guard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For a fresh installation, copy `.env.example` to `.env`. Set
`LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` to your provider's working
configuration. Do not commit `.env` or real credentials.

Start the local practice application:

```bash
python target_app/app.py
```

In another terminal with the virtual environment activated:

```bash
python agent/attack_agent.py target_app
```

Generate a proposed fix:

```bash
python agent/defense_agent.py target_app
```

Review `target_app/app_fixed.py` before executing it, then test it:

```bash
python -m unittest discover -s tests -p test_fixed.py -v
```

Run the complete test suite:

```bash
python -m unittest discover -s tests -v
```

Fixed-application tests are skipped when `app_fixed.py` is absent.
A skipped test does not demonstrate successful remediation.

### GitHub Actions Configuration

Add the repository secret `LLM_API_KEY` and repository variables
`LLM_BASE_URL` and `LLM_MODEL` under Settings → Secrets and variables →
Actions.

Opening or updating a same-repository PR triggers the workflow.
The scanner posts its findings as a PR comment. Fork PRs run tests but
skip the model scan. Manual workflow runs produce a summary and artifact
without posting a PR comment.

## Experiments and results

### Automated Pull Request Review

[View the demonstration pull request](https://github.com/chromaly/misconfiguration-guard/pull/1)

<img width="622" height="319" alt="Screenshot 2026-11-08 at 11 57 51 PM" src="https://github.com/user-attachments/assets/2da7d370-5ee0-4c86-be19-2add94fe7f73" />

The workflow successfully ran the regression tests and source-only scan, then posted these findings on the PR. The reported issues included:

- `/debug/config`: internal demo configuration returned without configuration.
- `/public-config/settings.json`: public access to fake configuration values.

The target intentionally contained these exposures. Passing these workflow checks demonstrates that the automation completed, NOT that the application is secure (it wasn't!)

The model also used a directory-traversal label. Public configuration exposure was supported by the source, but directory traversal was NOT established. This indicates that model findings still need further review.

### External Repository Evaluation

The source-only scanner (Red team) was aso applied to downloaded public projects. These evaluations did not run the external applications or verify exploitation through HTTP, it was just through source code revisions.

| Application | Revision | Scope |
|---|---|---|
| [Flaskr](https://github.com/pallets/flask/tree/main/examples/tutorial) | `49943b5a94413a530761350f04e896f76e8d620e` | `examples/tutorial/flaskr` |
| [DigitalOcean Flask sample](https://github.com/digitalocean/sample-flask) | `3f2269883cf430cf93352a832da80fee4094f159` | Downloaded repository |
| [Render Flask Hello World](https://github.com/render-examples/flask-hello-world) | `facfc73c44b35d00bb1f72e8986f0ea47cab0755` | Downloaded repository |
| [DVWA](https://github.com/digininja/DVWA) | Revision not recorded in this writeup | Discoverable configuration and text files |

These reports were saved locally as `flaskr-findings.md`, `digitalocean-findings.md`, `render-findings.md`, and `dvwa-findings.md`. Model-generated findings are preliminary observations, not confirmed exploits.

#### DVWA Compatibility Result

Testing on the DVWA was meant to be edge case testing, as PHP application files were excluded by the discovery filter. Initially, I was trying to prove that the scanner would not work on all types of files, as it was not told to scan these types of files, yet however the scanner reported `allow_url_fopen = on` and `allow_url_include = on` in `php.ini`. The PHP configuration files were still discoverable, demonstrating partial configuration-review compatibility.

These settings alone do not prove an exploitable vulnerability. Application source analysis and runtime verification were not completed for this test.

## Prevention research

Preventing Security Misconfigurations in applications is one of the most important steps to securing code, especially with the introduction of AI agents and helpers automating code workflows.

### Preventing Application Misconfigurations

OWASP A02:2025 recommends repeatable configuration hardening, removing unnecessary functionality, reviewing security settings, and automatically verifying configurations.

For the issues invested in this project, relevant measures include:

- Keeping sensitive configuration OUTSIDE publicly served directories.
- Removing unnecessary diagnostic routes and enforcing authentication and authentication.
- Disabling production debugging and returning generic public errors, not specific ones.
- Use platform secret management rather than embedding real credentials.
- TESTING blocked exposure and normal application functionality.

All in all, make sure to test your code and inspect it for any type of misconfiguration or leaks! Having multiple types of evaluation techniques (ie. looking through code manually, using AI agents, programs like this one, or other techniques) being used in tandem reduces the chance of misconfigurations.

Source: [OWASP A02:2025 — Security Misconfiguration](https://top10.owasp.org/2025/A02_2025-Security_Misconfiguration/)

### Preventing Prompt Injection Against the Agent

Prompt injection is another concern that technically doesn't involve Security Misconfigurations, but instead this project as a whole. Malicious repository content may try to redirect the scanner rather than merely contain an application bug, which could lead to harmful unintended consequences.

Relevant defenses include:

- Treating repository comments, files, and HTTP responses as UNTRUSTED data. Rule of thumb: most responses should be UNTRUSTED by default.
- Giving each agent ONLY the tools necessary for its task (Principle of Least Privilege)
- Restricting file access and generated output paths.
- Validating actions and reviewing findings against ACTUAL evidence.
- Reviewing generated code before execution.
- Evaluating the agent with adversarial inputs.

This project combines prompt instructions with tool restrictions. It has clear, defined directory boundaries, can only send HTTP requests through localhost programs and cannot redirect following, CI tools are read-only, and defense outputs are restricted to `app_fixed.py`. 

These controls reduce the likelihood and impact of prompt injection, reducing risk which is likelihood * impact, but still does not guarantee that the model will identify every issue or resist every injected instruction. Further defenses should be implemented before public usage.

Source: [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

## Limitations and Next Steps

- The CI still performs source-only review, and does not verify any running applications. This could be implemented in the future to test preliminary projects.
- Findings and cited evidence still require human review to determine where they were successful or not.
- File discovery excludes `.php`, `.js`, and `.ts` application sources. Although PHP was somewhat read by the DVWA test, it's still indecisive and should not be used as a sign of proper integration.
- The defender targets a single Python `app.py`, not entire folders or repositories.
- Runtime verification of newly generated misconfiguration fixes are incomplete.
- The original SQL injection flaws kept in `app.py` remain in the practice application since the model wasn't engineered to fix them, meaning other types of security vulnerabilities will still be present.
- The prompt-injection comparison is still not completed or documented.

In the future, I would like to expand this project to address some or all of the limitations mentioned above and bring it to a state of usefulness in my own code repositories or even as a potential code auditor for larger teams that reviews code workflows and ensures that no security misconfiguration or other type of cybersecurity vulnerability is present in an entire application stack.
