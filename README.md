<img width="620" height="319" alt="Screenshot 2026-11-08 at 11 57 35 PM" src="https://github.com/user-attachments/assets/634d12f9-909c-4031-9740-1126923fa751" />
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
<img width="602" height="320" alt="Screenshot 2026-11-08 at 11 53 30 PM" src="https://github.com/user-attachments/assets/00ea1abd-369a-4862-95d7-77fd98afa8b6" />

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

[View the demonstration pull request](https://github.com/chromaly/misconfiguration-guard/pull/1)

<img width="622" height="319" alt="Screenshot 2026-11-08 at 11 57 51 PM" src="https://github.com/user-attachments/assets/2da7d370-5ee0-4c86-be19-2add94fe7f73" />

### Agent Loop

Each agent asks the model for one JSON action, validates and dispatches
that action, and returns the tool result to the model. This repeats until
the model submits a report or reaches the step limit.

Repository contents and HTTP responses are treated as untrusted evidence.
The tools provide restrictions independently of the model's instructions,
including directory boundaries, localhost-only HTTP requests without
redirect following, and constrained defense output.

## How it works

## Setup and usage

## Experiments and results

## Prevention research

## Limitations and next steps


## Pull request scanning demonstration

[Demo pull request with automated findings](https://github.com/chromaly/misconfiguration-guard/pull/1)

Opening and updating this PR triggered the regression tests and source-only
security scanner. Both checks passed, and the scanner posted findings about
public configuration exposure and an unauthenticated diagnostic route.
Runtime verification was not performed by the CI scanner.

## External Application Testings
1. Flaskr from pallets/flask
Revision: 49943b5a94413a530761350f04e896f76e8d620e
Scanned directory: examples/tutorial/flaskr

2. digitalocean
Revision: 3f2269883cf430cf93352a832da80fee4094f159
Scanned directory: 

3. render's flask hello world
Revision: facfc73c44b35d00bb1f72e8986f0ea47cab0755

4. DVWA compatibility experiment: 
