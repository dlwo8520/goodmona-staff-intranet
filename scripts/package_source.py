"""Package only reviewed source, excluding credentials, DBs, tools and environments."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent.parent
destination = root / 'artifacts' / 'goodmona-intranet-source.zip'
destination.parent.mkdir(exist_ok=True)
root_files = ['manage.py', 'requirements.in', 'requirements.txt', '.gitignore', '.env.example',
              'render.yaml', 'gunicorn.conf.py', 'README.md']
directories = ['intranet', 'core', 'wiki', 'operations', 'templates', 'static', 'scripts', 'docs', '.github']
paths = [root / name for name in root_files]
for directory in directories:
    paths.extend((root / directory).rglob('*'))
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(paths)):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.sqlite3'}:
            archive.write(path, path.relative_to(root))
    prohibited = {'.env', 'DEMO_CREDENTIALS.txt', 'intranet.sqlite3'}
    assert not any(Path(name).name in prohibited for name in archive.namelist())
print(f'Packaged {len(archive.namelist())} source files: {destination}')
