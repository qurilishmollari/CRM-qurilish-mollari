"""Run database upgrades before accepting web requests on Railway."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    project_root = Path(__file__).resolve().parent.parent
    for command in ('migrate', 'setup_crm'):
        args = [sys.executable, str(project_root / 'manage.py'), command]
        if command == 'migrate':
            args.append('--noinput')
        subprocess.run(args, cwd=project_root, check=True)
    os.chdir(project_root)
    os.execvp(sys.executable, [sys.executable, '-m', 'gunicorn', 'config.wsgi:application', '--bind', f'0.0.0.0:{os.environ.get("PORT", "8000")}', '--workers', os.environ.get('WEB_CONCURRENCY', '2'), '--timeout', '120', '--access-logfile', '-', '--error-logfile', '-'])


if __name__ == '__main__':
    main()
