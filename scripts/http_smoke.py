"""Read-only real-HTTP smoke check using the two demo role buttons."""
import os
import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

base = os.getenv('SMOKE_BASE_URL', 'http://127.0.0.1:8002').rstrip('/')
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

def get(path):
    with client.open(base + path, timeout=15) as response:
        return response.geturl(), response.read().decode('utf-8'), response.headers

def post(path, values, html):
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    if not token:
        raise AssertionError('CSRF token missing')
    values = dict(values, csrfmiddlewaretoken=token.group(1))
    request = urllib.request.Request(base + path, data=urllib.parse.urlencode(values).encode(),
                                     headers={'Referer': base + path})
    with client.open(request, timeout=25) as response:
        return response.geturl(), response.read().decode('utf-8'), response.headers

url, html, _ = get('/')
assert '/login/' in url
assert '직원으로 접속' in html and '관리자로 접속' in html
url, html, headers = post('/login/', {'role': 'staff'}, html)
assert '안녕하세요' in html and '/login/' not in url
assert 'no-store' in headers.get('Cache-Control', '')
assert '/manage/">' not in html
for path in ('/wiki/', '/leave/', '/vehicles/'):
    _, body, _ = get(path)
    assert '<main' in body
_, html, _ = get('/wiki/')
_, positive, _ = post('/wiki/', {'mode': 'customer', 'question': '예약 시간을 변경하려면 어떻게 안내하나요?'}, html)
assert '응대 허용 근거 확인' in positive and '예약 시간 변경 안내' in positive
assert 'LEGACY-ARCHIVED-210' not in positive and 'INTERNAL-BOOKING-731' not in positive
_, missing, _ = post('/wiki/', {'mode': 'customer', 'question': '우주여행 보험 가입은 어떻게 하나요?'}, positive)
assert '담당자 확인 필요' in missing
_, internal, _ = post('/wiki/', {'mode': 'internal', 'question': '직원 온보딩'}, missing)
assert 'INTERNAL-ONLY-482' in internal and '내부 검색 · 모델 호출 안 함' in internal
_, private, _ = post('/wiki/', {'mode': 'customer', 'question': '직원 온보딩'}, internal)
assert 'INTERNAL-ONLY-482' not in private and '담당자 확인 필요' in private
_, login, _ = post('/logout/', {}, private)
_, admin, _ = post('/login/', {'role': 'admin'}, login)
for path in ('/manage/', '/wiki/manage/', '/manage/leave/', '/manage/balances/', '/manage/vehicles/', '/manage/announcements/'):
    _, body, _ = get(path)
    assert '<main' in body
print('PASS: real HTTP + CSRF role entry, staff/admin pages, 4 wiki cases, private cache policy. No demo state was changed.')
