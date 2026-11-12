"""Prepare the explicitly selected persistent or ephemeral DB before serving."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0, str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intranet.settings')
from intranet import settings

path = Path(settings.DATABASES['default']['NAME']).resolve()
if os.getenv('RENDER'):
    if os.getenv('INTRANET_STORAGE_MODE', 'persistent') == 'ephemeral':
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if not path.is_relative_to(temporary_root) or path.parent == temporary_root:
            raise SystemExit('Free demo SQLITE_PATH must be inside a dedicated temporary directory.')
    elif not path.is_relative_to(Path('/var/data').resolve()):
        raise SystemExit('Render SQLITE_PATH must be inside the persistent /var/data volume.')
path.parent.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
if os.getenv('SEED_DEMO', 'false').lower() == 'true':
    subprocess.run([sys.executable, 'manage.py', 'seed_demo'], check=True)
