"""Run only after the persistent volume is mounted, before serving requests."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0, str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intranet.settings')
from intranet import settings

path = Path(settings.DATABASES['default']['NAME']).resolve()
if os.getenv('RENDER') and not path.is_relative_to(Path('/var/data').resolve()):
    raise SystemExit('Render SQLITE_PATH must be inside the persistent /var/data volume.')
path.parent.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
if os.getenv('SEED_DEMO', 'false').lower() == 'true':
    subprocess.run([sys.executable, 'manage.py', 'seed_demo'], check=True)
