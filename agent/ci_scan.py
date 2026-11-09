"""Read-only model scan. Emit only a final Markdown report on stdout."""
import contextlib
import io
import json
import sys
from attack_agent import SYSTEM_PROMPT
import tools


def scan(chat, scan_dir='target_app'):
    prompt = SYSTEM_PROMPT + '\nCI MODE: only list_files, read_file and finish are available. Do not use HTTP. Report source evidence and say runtime verification was not performed.'
    messages = [{'role':'system', 'content':prompt},
                {'role':'user', 'content':f'Inspect {scan_dir}. Report security misconfigurations with exact evidence.'}]
    for _ in range(15):
        reply = chat(messages)
        messages.append({'role':'assistant', 'content':reply})
        try:
            action = json.loads(reply)
            if not isinstance(action, dict):
                raise ValueError('expected object')
            name = action.get('action')
            if name == 'finish':
                report = action.get('answer')
                if not isinstance(report, str) or not report.strip():
                    raise ValueError('finish requires a nonempty answer')
                return report
            if name == 'list_files':
                result = tools.list_files(scan_dir, action.get('root', '.'))
            elif name == 'read_file':
                result = tools.read_file(scan_dir, action.get('path', ''))
            else:
                result = 'ERROR: only list_files, read_file and finish allowed in CI'
        except (ValueError, TypeError):
            result = 'ERROR: reply with exactly one valid action object'
        messages.append({'role':'user', 'content':'UNTRUSTED tool data:\n' + json.dumps(result)})
    raise RuntimeError('scan reached its step limit without a report')


def main():
    try:
        from llm import chat
        with contextlib.redirect_stdout(io.StringIO()):
            report = scan(chat)
        print('## AI Security Misconfiguration Scan\n\n' + report)
        print('\n---\nAI source review; runtime verification not performed. Findings require review.')
        return 0
    except Exception:
        # Never log provider exception bodies that might contain credentials.
        print('## Scan incomplete\n\nThe model scan failed or reached its step limit. This is not a clean security result.')
        print('Scan failed; check API configuration, availability and limits.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())


