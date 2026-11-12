"""Create local secrets once, without resetting existing demo users or data."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
(root / 'data').mkdir(exist_ok=True)
env = root / '.env'
if env.exists():
    print('.env already exists; no settings were changed.')
else:
    env.write_text('\n'.join([
        'DJANGO_DEBUG=True', f'DJANGO_SECRET_KEY={secrets.token_urlsafe(60)}',
        'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        'DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8002,http://127.0.0.1:8002',
        'SQLITE_PATH=data/intranet.sqlite3', 'OPENAI_API_KEY=',
        'OPENAI_MODEL=gpt-4.1-mini', '',
    ]), encoding='utf-8')
    print('Created .env (excluded from Git). Choose Staff or Admin on the demo entry page.')
