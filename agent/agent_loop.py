"""
agent_loop.py  --  build-your-own agent loop.  >>> THIS TIME YOU WRITE THE CODE. <<<

In the earlier exercises the loop was written FOR you and you only wrote the
prompt. Here it's the other way around: the SYSTEM_PROMPT below is complete
and working -- YOU write the two missing pieces of code.

The model replies in a NEW format (so you can't paste in an old loop):

    {"tool": "<name>", "args": {<arguments>}}

with these tools:

    list_files    args {}                            list the .py files in your directory
    read_file     args {"path": ...}                 read a file (line numbers included)
    send_request  args {"method", "path", "data"}    HTTP request to the local app
    done          args {"report": ...}               stop and give the final report

Your two jobs (the only TODOs in this file):
    TODO #1: run_tool(action, scan_dir) -- take one parsed action and call the
             matching function in tools.py.
    TODO #2: the main loop -- talk to the model, parse its JSON, run the tool,
             stop at "done", enforce the step limit.

Run the target app first (see the README), then run this file.
"""

import argparse
import json

from llm import chat
import tools

# How many steps the agent is allowed before we stop it. This is a safety net
# so a confused agent can't loop forever (and burn through your API credits).
MAX_STEPS = 12

# Which folder to scan if the user doesn't pass one on the command line. This
# directory is the HARD BOUNDARY: every file tool is confined to it, so the
# model can only read inside the folder it was given.
DEFAULT_SCAN_DIR = "target_app"


# The system prompt is COMPLETE -- you do not need to change it. It describes
# the {"tool", "args"} reply format and the job (find the SQL injection,
# confirm it live, report the exact file and line).
SYSTEM_PROMPT = """
You are an automated security code-scanning agent. Your job: find the SQL
injection in the practice web app, PROVE it works with a real request, and
report the exact file and line.

You may only look inside the directory you were given. Do not try to access
parent folders or other directories.

On EVERY turn, reply with EXACTLY ONE JSON object and NOTHING else -- no
markdown, no code fences, no words around it. A strict program parses your
reply. The shape is always:

    {"tool": "<name>", "args": {<arguments>}}

The tools:

  {"tool": "list_files", "args": {}}
      List the .py files in your directory.

  {"tool": "read_file", "args": {"path": "app.py"}}
      Read a file with line numbers. Paths are relative to your directory --
      use "app.py", never ".." or absolute paths (those are refused).

  {"tool": "send_request", "args": {"method": "POST", "path": "/login",
                                    "data": {"username": "x", "password": "y"}}}
      Send an HTTP request to the local app at http://127.0.0.1:5000.
      "method" is "GET" or "POST". "data" is the JSON body (use {} for GET).

  {"tool": "done", "args": {"report": "<your final report>"}}
      Stop and give your final report.

Plan:
  1. list_files to see the code in your directory.
  2. read_file "app.py" and locate the query where user input is concatenated
     straight into the SQL string. Note the exact line number.
  3. Confirm the bug live: send_request POST /login with any username and the
     password  ' OR '1'='1  -- a 200 response with "ok": true proves the
     injection bypassed the password check.
  4. done, with a report that names the exact file and line number, why it is
     vulnerable, the request you sent, and what the response proved.
"""


def run_tool(action, scan_dir):
    """
    Take ONE parsed action from the model and run the matching tool.

    `action` looks like {"tool": "read_file", "args": {"path": "app.py"}}.
    `scan_dir` is the directory chosen on the command line -- it is the HARD
    BOUNDARY, so it must be handed to the file tools on every call.

    Returns a STRING describing the result (it gets printed and fed back to
    the model as the next message).
    """
    # -----------------------------------------------------------------------
    # TODO #1 -- TOOL DISPATCH
    #
    # `action` is the parsed JSON from the model, e.g.
    #     {"tool": "read_file", "args": {"path": "app.py"}}
    # `scan_dir` is the directory passed on the command line. It is the HARD
    # BOUNDARY -- always give it to the file tools so the model can't escape.
    #
    # Guide:
    #   * Pull out the tool name (action["tool"]) and its arguments
    #     (action["args"] -- it may be missing, so default it to {}).
    #   * "list_files": call tools.list_files(scan_dir, "."). It returns a
    #     LIST of filenames -- or an error STRING if something is outside the
    #     boundary. Turn a list into a readable string ("Files found:" then
    #     one name per line) and pass an error string through unchanged.
    #   * "read_file": call tools.read_file(scan_dir, <the "path" arg>).
    #     tools.read_file already returns a string -- just return it.
    #   * "send_request": call tools.send_request(<the "method" arg>,
    #     <the "path" arg>, <the "data" arg>). It returns a dict, so turn it
    #     into a string with json.dumps(...).
    #   * Any other tool name: return "ERROR: unknown tool ..." so the model
    #     can correct itself on the next turn.
    #   * Whatever branch you take, return a STRING.
    # -----------------------------------------------------------------------
    tool = action["tool"]
    arguments = action.get("args", {})

    if tool == "list_files":
        output = tools.list_files(scan_dir, ".")

        if isinstance(output, list):
            return "Files found:\n" + "\n".join(output)
        return output
    elif tool == "read_file":
        output = tools.read_file(scan_dir, arguments["path"])
        return output
    elif tool == "send_request":
        output = tools.send_request(
            arguments["method"],
            arguments["path"],
            arguments.get("data"),
        )
        return json.dumps(output)
    else:
        return f"ERROR: unknwon tool {tool}"



def main(scan_dir):
    # Tell the student which directory this run is scanning.
    print("Scanning: " + scan_dir)

    # The conversation starts with the system prompt, then a first user message
    # that kicks the agent off. (These are given -- don't change them.)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Begin. Find the SQL injection in the '" + scan_dir + "' "
                "directory, confirm it with a live request, then report the "
                "exact file and line."
            ),
        },
    ]

    # -----------------------------------------------------------------------
    # TODO #2 -- THE AGENT LOOP
    #
    # This is the heart of the exercise. Repeat at most MAX_STEPS times:
    #
    #   1. Ask the model for its next move: reply = chat(messages).
    #   2. Print the reply so you can watch it think (a "STEP n" banner each
    #      iteration helps), and append it to messages as an
    #      {"role": "assistant", "content": reply} entry so the model
    #      remembers what it said.
    #   3. Parse the reply with json.loads(...). If it isn't valid JSON, do
    #      NOT crash: append a user message telling the model to reply with
    #      exactly one JSON object like {"tool": "...", "args": {...}}, then
    #      continue to the next step so it can try again.
    #   4. If the tool is "done": print the report from its args
    #      (action["args"]["report"]) and stop -- the agent is finished.
    #   5. Otherwise: result = run_tool(action, scan_dir), print the result,
    #      and append it to messages as a user message so the model sees what
    #      happened. Then loop again.
    #
    # If the loop finishes all MAX_STEPS without a "done", print a line saying
    # the step limit was reached.
    # -----------------------------------------------------------------------
    for i in range(MAX_STEPS):
        reply = chat(messages)
        print(f"\n STEP {i+1} ")
        print(reply)

        messages.append({"role": "assistant", "content": reply})

        try:
            action = json.loads(reply)
        except json.JSONDecodeError:
            messages.append({
                "role": "user",
                "content": (
                    'Reply with exactly one JSON object like '
                    '{"tool": "...", "args": {...}}.'
                ),
            })
            continue

        # Valid JSON could still be a list, string, or invalid action.
        if (
            not isinstance(action, dict)
            or not isinstance(action.get("tool"), str)
            or not isinstance(action.get("args", {}), dict)
        ):
            messages.append({
                "role": "user",
                "content": (
                    'Expected one JSON object with a "tool" string '
                    'and an optional "args" object.'
                ),
            })
            continue

        if action["tool"] == "done":
            args = action.get("args", {})

            if not isinstance(args.get("report"), str):
                messages.append({
                    "role": "user",
                    "content": 'The "done" tool requires args.report as a string.',
                })
                continue

            print("\n--- REPORT ---")
            print(args["report"])
            break

        result = run_tool(action, scan_dir)
        print(result)

        messages.append({"role": "user", "content": result})

    else:
        print("Step limit reached.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Run your hand-built agent loop against a directory of the "
            "practice app. The directory is a hard boundary; the agent can "
            "only read inside it."
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
