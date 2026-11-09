import argparse
import json

from llm import chat
import tools

# How many steps the agent is allowed before we stop it. This is a safety net
# so a confused agent can't loop forever (and burn through your API credits).
MAX_STEPS = 12

# Which folder to scan if the user doesn't pass one on the command line. This
# is the vulnerable practice app. The value is interpreted by tools.list_files,
# which anchors it to the repo root and refuses anything outside the repo.
DEFAULT_SCAN_DIR = "target_app"

SYSTEM_PROMPT = """
You are a security code-scanning agent tasked with identifying security misconfigurations in a local practice application.

Your goals are to:
Explore the application's source code and configuration files and
Identify insecure configurations, verify the impact through the local application if possible, and report findings.

Focus on identifying these types of security misconfigurations:
Exposed Configuration Files:
Look for configuration files like .env files, JSON configuration files, or other files containing sensitive settings or credentials that may be publicly accessible.
Debugging Information Exposure:
Look for enabled debugging modes, detailed and exposed error messages, stack traces, or other internal application information that may be exposed to users unintentionally.
Unauthenticated Diagnostic Routes:
Look for diagnostic, testing, or administrative endpoints that expose sensitive application information without appropriate authentication or authorization.

Do NOT assume a vulnerability exists because a configuration file, debug setting, or diagnostic route exists. First, you should determine whether it creates an actual security risk.

To examine the source code, here are the tools you have at your disposal:
list_files:
{“action”: “list_files”, “root”: “<folder>”}
You use this to explore directories inside the project and find relevant configuration files, server initialization code, and application routes.
read_file:
{“action”: “read_file”, “root”: “<folder>”, “path”: “<file>”}
You use this to inspect configurations and source code for insecure settings, like debug mode, exposed endpoints, default credentials, and improperly configured security controls. Read above for more instructions about inspecting source code.
send_request:
{“action”: “send_request”, “method”: “GET”|”POST”, “path”: “<route>”, “data”: {}}
You use this to test suspected misconfigurations against the local practice application.
finish:
{“action”: “finish”, “answer”: “<your final report>”}
You use this to submit your findings after investigating and testing any vulnerabilities.

RULES:
Every turn (your response when I prompt you something), you should respond with EXACTLY one valid JSON object per turn. Do not include markdown, backticks, or additional explanations alongside this JSON object.
Use ONLY the four available actions listed above.
Do not invent file contents, line numbers, or HTTP responses. Every source of information you pull from must be real and not hallucinated.

HIGH-LEVEL INSTRUCTIONS:
Explore the application's directory structure and inspect relevant source and configuration files. Prioritize server configuration, environment files, debugging settings, and diagnostic routes.
Look for exposed configuration files, debugging information, and unauthenticated diagnostic endpoints.  Read above for more instructions about inspecting source code.
Identify the EXACT path and line number for a suspected security misconfiguration. Save those metadatas.
Determine whether the vulnerability can be verified through static source code inspection or requires local application testing.
If HTTP verification is possible for the vulnerability, use the send_request command to test the relevant endpoint.
Examine the response and verify whether the suspected misconfiguration exposes sensitive information or functionality. Don’t assume ANYTHING: you must check the response to prove the injection worked.
Once confirmed, use finish to report the exact file, line number, and evidence supporting the security misconfiguration through the application’s source code.

NOTE: If testing doesn't confirm the vulnerability's existence, report it as unconfirmed rather than claiming success. NEVER make up data or results that you don’t explicitly have.

EXAMPLE RESPONSES:
{“action”: “list_files”, “root”: “.”}

{“action”: “read_file”, “root”: “.”, “path”: “src/auth/auth.py”}

{“action”: “send_request”, “method”: “GET”, “path”: “/debug/config”, “data”: {}}

{“action”: “finish”, “answer”: “Security misconfiguration confirmed in app.py at line 50. The /debug/config endpoint is accessible without authentication, which exposes sensitive configuration information.”}
"""

def run_tool(action, scan_dir):
    """
    Look at the parsed JSON `action` and run the matching tool.

    `scan_dir` is the directory chosen on the command line. It is passed into
    every file tool as the HARD BOUNDARY, so the model can only ever read or
    walk inside it -- even if it asks for ".." or "." or an absolute path.

    Returns a string describing the result, which we hand back to the model.
    This part is DONE -- it simply connects the model's chosen action to the
    real functions in tools.py.
    """
    name = action.get("action")

    if name == "list_files":
        # The model may name a sub-folder with "root"; it defaults to "." (the
        # scan directory itself). Either way it stays inside scan_dir.
        files = tools.list_files(scan_dir, action.get("root", "."))
        # list_files returns a list on success, or an error STRING if the path
        # is outside the scan directory. Pass the error through as-is.
        if isinstance(files, str):
            return files
        return "Files found:\n" + "\n".join(files)

    if name == "read_file":
        return tools.read_file(scan_dir, action.get("path", ""))

    if name == "send_request":
        result = tools.send_request(
            action.get("method", "GET"),
            action.get("path", "/"),
            action.get("data"),
        )
        return json.dumps(result)

    return "ERROR: unknown action '" + str(name) + "'."


def main(scan_dir):
    # Tell the student which directory this run is scanning.
    print("Scanning: " + scan_dir)

    # The conversation starts with the system prompt, then a first user message
    # that kicks the agent off.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Begin. Scan the '" + scan_dir + "' directory. Find the SQL "
                "injection vulnerability, report the exact file and line, and "
                "confirm it works."
            ),
        },
    ]

    for step in range(1, MAX_STEPS + 1):
        print("\n" + "=" * 60)
        print("STEP " + str(step))
        print("=" * 60)

        # 1) Ask the model what to do next.
        reply = chat(messages)
        print("Agent says:\n" + reply)

        # Record the model's reply so it remembers its own train of thought.
        messages.append({"role": "assistant", "content": reply})

        # 2) Parse ONE JSON action out of the reply.
        try:
            action = json.loads(reply)
        except json.JSONDecodeError:
            # The model didn't give us clean JSON. Tell it so it can fix itself.
            feedback = (
                "Your last reply was not valid JSON. Reply with exactly one "
                "JSON object describing a single action, and nothing else."
            )
            print("\n[parser] " + feedback)
            messages.append({"role": "user", "content": feedback})
            continue

        # 3) If the model is finished, print its final answer and stop.
        if action.get("action") == "finish":
            print("\n" + "*" * 60)
            print("FINAL REPORT:")
            print(action.get("answer", "(no answer provided)"))
            print("*" * 60)
            return

        # 4) Otherwise run the chosen tool and feed the result back.
        result = run_tool(action, scan_dir)
        print("\nTool result:\n" + result)
        messages.append(
            {"role": "user", "content": "Tool result:\n" + result}
        )

    # If we fall out of the loop, the agent used up all its steps.
    print("\nReached the step limit (" + str(MAX_STEPS) + ") without finishing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Run the attack agent against a directory of the practice app. "
            "The directory is resolved relative to the repo root; anything "
            "outside the repo is refused."
        )
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=DEFAULT_SCAN_DIR,
        help="Folder to scan, relative to the repo root (default: target_app).",
    )
    args = parser.parse_args()
    main(args.directory)
