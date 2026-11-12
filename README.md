# 굿모나의원 직원 인트라넷 · 과제 2

**개선된 달력 접속:** https://goodmona-intranet-calendar-preview.onrender.com/

직원 연차·관리자 연차·차량 예약을 월간 달력으로 개선했습니다. 부서 인원·반차 구분·동시 승인 검사를 추가했으며 기존 데이터 보존 마이그레이션과 71개 로컬 테스트를 통과했습니다. 새 주소에서 신청·승인·인원 제한·차량 충돌을 HTTPS로 확인했습니다. 기존 Free 공개 DB를 보호하기 위해 개선은 `calendar-upgrade-20261112` 브랜치의 별도 무료 서비스로 제공합니다. [원인·화면·시연·검증 상세](docs/calendar-upgrade.md)

Django 5.2 LTS, SQLite, Django 템플릿으로 만든 독립 직원용 인트라넷입니다. 과제 1의 프로젝트·DB·서비스를 참조하지 않습니다. 모든 인물·정책·자료·차량은 가상입니다.

**기존 직원 인트라넷(이전 화면·기존 데이터 보존): https://goodmona-staff-intranet-demo.onrender.com/**

[GitHub 저장소](https://github.com/dlwo8520/goodmona-staff-intranet)의 직원 인트라넷을 별도 **Render Free 서비스**로 배포하고 실제 HTTPS에서 주요 기능을 검증했습니다. 유료 서비스와 영구 디스크는 사용하지 않습니다. 직원·관리자 버튼으로 접속합니다. 진료 사진 앱과 다른 프로젝트·서비스입니다. 로컬 주소는 `http://127.0.0.1:8002/`입니다.

## Windows 실행

현재 작업 폴더에는 Python 3.12 가상환경과 로컬 DB를 준비했습니다. PowerShell에서:

```powershell
cd C:\Users\Administrator\Desktop\work2
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```

브라우저에서 `http://127.0.0.1:8002/`을 엽니다. 종료는 실행한 창에서 `Ctrl+C`입니다. 스크립트의 실행 정책 옵션은 해당 프로세스에만 적용되며 시스템 정책을 변경하지 않습니다.

다른 Windows PC에서 새로 준비할 때는 Python 3.12 이상을 설치한 뒤:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup_local.py
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8002
```

활성화 스크립트 없이 가상환경 Python을 직접 실행할 수 있습니다. `setup_local.py`는 `.env`, `data/`를 처음 한 번만 만들고 기존 값을 변경하지 않습니다. 직접 `.env`를 만들었다면 디렉터리와 Django 비밀 키를 설정하세요. Windows 로컬은 Django 개발 서버를 쓰며 Gunicorn은 Render Linux에서 실행합니다.

## 데모 계정·자료

| 접속 버튼 | 데모 계정 | 사용 화면 |
| --- | --- | --- |
| 직원으로 접속 | `demo_staff` | CS 위키, 자기 연차·예약 |
| 관리자로 접속 | `demo_admin` | 직원 화면과 관리자 업무 |

**아이디나 비밀번호 입력 없이 접속 버튼을 선택합니다.** 선택한 역할의 데모 계정으로 Django 세션을 만들고, 직원·관리자 권한 검사는 서버에서 계속 수행합니다. 화면의 ‘역할 변경’을 누르면 접속 선택 화면으로 돌아갑니다. 버튼으로 누구나 관리자 역할을 선택할 수 있는 가상 시연용 방식입니다. 실제 직원이나 고객 정보는 넣지 마세요.

데이터 생성 명령은 `python manage.py seed_demo` 한 번이며 데모 비밀번호 환경 변수는 필요하지 않습니다. 새 데모 계정은 비밀번호 로그인을 사용할 수 없도록 생성합니다. 재실행 시 기존 계정·권한·문서 개정·공지 수정·연차 처리·예약 취소를 덮어쓰지 않습니다. 기존 `.env`에 남은 `DEMO_STAFF_PASSWORD`, `DEMO_ADMIN_PASSWORD`와 이전 비밀번호 안내 파일은 접속에 사용하지 않습니다. Django 비밀 키·모델 키·SQLite 파일·이전 자격 증명 파일은 `.gitignore`와 소스 ZIP에서 제외됩니다.

생성 내용: 계정 2개, 공지 2건, 논리 문서 8건·버전 9개(현재 발행 6건, 초안·보관본 포함), 직원 12일·관리자 15일 시작 연차, 승인 대기 2건, 차량 2대와 예약 2건입니다. 생성일 기준 다음 날 1호 차량 10:00–11:00, 2호 차량 14:00–15:00 예약을 넣습니다. 모든 시각은 한국 시각입니다. 재실행해도 예약 날짜를 이동시키지 않으므로 시연할 때 화면에 표시된 일정을 확인하세요. 기존 데이터가 오래됐다면 미래 예약을 직접 추가할 수 있습니다.

출처의 `example.com/demo/...`는 가상 자료임을 나타내는 예시 URL이며 실제 의원 문서나 영상이 아닙니다. 근거 원문·제목·개정일은 앱에 저장되어 있습니다. 실제 자료를 사용할 때 관리자가 실제 출처 URL을 입력합니다. 대본 타임스탬프를 저장하며, YouTube 출처라면 서버가 `t=` 링크를 만듭니다.

## 기능과 권한

- 홈은 최근 공지, 본인의 연차 상태와 가까운 차량 예약을 표시합니다. 메뉴는 홈·공지 / CS 위키 / 내 연차 / 차량 예약 / 관리자입니다.
- 직원은 본인 연차·예약만 상세 조회합니다. 차량 점유 목록에는 차량명과 시간만 전달하며 다른 직원의 이름·메모·예약 ID를 전달하지 않습니다. 관리자 메뉴와 모든 관리자 요청은 서버에서 권한을 확인합니다. 데모 관리자는 활성 `is_staff` 계정입니다.
- 위키에서 문서 유형, 제목, 본문 붙여넣기, 출처, 개정일, 담당자, 동의어를 등록합니다. 빈 줄로 문단을 나누고 문단별 응대 허용 여부를 설정합니다. 초안 저장 후 별도 발행합니다. 발행본은 읽기 전용이며 ‘새 버전 초안’에서 개정합니다. 새 버전을 발행할 때 기존 발행본을 한 트랜잭션에서 보관하고 문서당 현재 발행본을 DB 제약으로 하나만 허용합니다.
- 고객 검색은 현재 발행본의 응대 허용 문단만, 내부 검색은 현재 발행본의 모든 문단을 검색합니다. SQLite 제목·본문·등록 키워드 검색과 예약 변경/시간 변경/일정 변경 동의어를 사용합니다. 질문의 추가 조건이 근거에 없으면 초안을 생성하지 않습니다. 검색 정확도는 보수적인 규칙 기반이며 문서가 늘면 검색 품질 평가와 개선이 필요합니다.
- 질문은 POST로 받아 DB나 앱 로그에 별도로 저장하지 않습니다. 검색 화면에서 개인정보 입력 금지를 안내하고 일부 연락처 패턴도 차단합니다. 응답은 `no-store`로 제공하며 앱 요청 로그의 쿼리 문자열도 가립니다. 일반 이름·진료 내용의 자동 탐지는 보장하지 않으므로 데모는 개인정보 없는 질문만 사용합니다.
- 근거가 충분할 때만 선택적으로 OpenAI Responses API를 호출합니다(`store=false`). 서버가 허용 문단을 다시 조회하고 질문·문단 본문·제목만 전달합니다. 직원 전용 문단은 전달하지 않습니다. 출처는 모델 출력에서 만들지 않고 검색한 문단의 저장된 정보로 표시합니다. 모델이 확인 필요를 반환하거나 링크를 생성하면 초안을 표시하지 않습니다.
- 키가 없으면 ‘모델 미연결’, 호출 실패 시 ‘모델 호출 실패’를 검색 상태와 별도로 표시합니다. 두 경우 모두 원문을 볼 수 있습니다. 내부 검색은 모델을 호출하지 않습니다. 모델 응답은 직원이 검토하고 복사합니다.
- 흰 배경, 차콜 텍스트, 회색 선, 짙은 청록 강조색을 사용합니다. 작은 화면에서는 메뉴·검색·신청·근거를 세로로 배치합니다.

## 연차·차량의 데모 가정

연차 잔여일은 관리자가 최초 1회 설정하며 하루·오전 반차·오후 반차로 신청합니다. 과거 날짜와 같은 시간대의 대기·승인 중복을 막습니다. 오전과 오후는 각각 신청할 수 있습니다. 대기 중에는 차감하지 않으며 승인 시 부서 최소 인원과 잔여일을 다시 확인하고 차감합니다. 직원은 대기 신청을 취소할 수 있고 승인 건 취소·복원은 관리자만 수행합니다. 이전 반차는 관리자 확인 전까지 오전·오후를 임의 배정하지 않습니다.

시작값·신청·승인·반려·취소를 처리자, 증감량, 처리 후 잔여일과 함께 기록합니다. 반일 정수 단위로 계산하여 소수점 오차를 피합니다. SQLite `IMMEDIATE` 트랜잭션, 잔여일 조건부 갱신, 상태 검사와 이력 유일성 제약을 사용합니다. 중복 승인·취소는 재차 차감·복원하지 않습니다.

차 관리는 공용 차량 예약으로 가정합니다. 미래 시작·종료 시각과 차량을 검증하고 같은 차량의 유효 예약 충돌을 트랜잭션 안에서 검사합니다. 구간은 `[시작, 종료)`이므로 기존 예약 종료 시각에 시작하는 다음 예약은 허용합니다. 직원은 자기 예약을 취소합니다. 관리자는 차량 이름·가상 번호·사용 가능 상태를 관리합니다.

자동 연차 발생·이월·근속·공휴일·주말·반일 시간대·취소 기한·차량 운영 시간·예약 제한 기간 등은 구현된 의원 정책이 아닙니다. 실제 운영 전 의원 정책을 확인해야 합니다. 이 시스템은 시연 규모의 단일 인스턴스 SQLite 앱입니다.

## Render 배포

소스는 `goodmona-staff-intranet` 저장소에 올리고 Render에서 **과제 2 전용 Free Web Service**를 생성합니다. 과제 1의 진료 사진 서비스와 분리합니다. `.env`나 DB를 업로드하지 마세요. `artifacts/goodmona-intranet-source.zip`은 비밀과 런타임 데이터를 뺀 소스 패키지입니다.

`render.yaml`은 Python 런타임, **`plan: free`**, 단일 인스턴스와 빌드·시작 명령을 선언하며 디스크를 연결하지 않습니다. SQLite는 임시 저장소를 사용합니다. [Render 무료 서비스](https://render.com/docs/free), [Blueprint 규격](https://render.com/docs/blueprint-spec)

| 항목 | 설정 |
| --- | --- |
| 서비스 | `goodmona-staff-intranet-demo` · Python · **Free** · 단일 인스턴스 |
| Build | `bash scripts/build.sh` |
| Start | `bash scripts/start.sh` |
| 영구 디스크 | **없음** |
| SQLite | `/tmp/goodmona-intranet/intranet.sqlite3` |
| 상태 확인 URL | `/healthz/` · DB 연결 상태만 반환. MCP 서비스는 기본 TCP 검사 사용 |
| 서버 | Gunicorn · worker 1개 · thread 4개 · `0.0.0.0:$PORT` |

빌드에서는 의존성 설치와 `collectstatic`만 실행합니다. 실제 서버 **시작 단계**에서 임시 디렉터리 준비 → `migrate` → 멱등 `seed_demo` → Gunicorn 순서로 실행합니다. `INTRANET_STORAGE_MODE=ephemeral`에서는 전용 OS 임시 하위 디렉터리만 허용합니다. 초기화를 반복해도 현재 인스턴스의 문서·신청·승인·예약을 덮어쓰거나 중복 생성하지 않습니다.

### 환경 변수

| 이름 | 값·설명 |
| --- | --- |
| `DJANGO_DEBUG` | 배포는 반드시 `False` |
| `DJANGO_SECRET_KEY` | 32자 이상 무작위 값. Blueprint가 생성한 256비트 비밀값을 지원하며, 50자 미만이면 SHA-512로 안정적으로 변환. 재배포마다 바꾸지 않음 |
| `RENDER_EXTERNAL_HOSTNAME` | Render 자동 제공. 허용 호스트와 HTTPS CSRF origin에 자동 반영 |
| `DJANGO_ALLOWED_HOSTS` | 로컬 기본 `localhost,127.0.0.1`. 커스텀 도메인 사용 시 해당 호스트 추가. `*` 사용 금지 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 커스텀 도메인이 있으면 `https://해당도메인` 추가. 쉼표로 구분 |
| `SQLITE_PATH` | Free 배포 `/tmp/goodmona-intranet/intranet.sqlite3` |
| `INTRANET_STORAGE_MODE` | Free 배포 `ephemeral` |
| `SEED_DEMO` | `true`이면 시작 시 데모를 최초 생성. 이후에도 기존 자료 유지 |
| `OPENAI_API_KEY` | 선택. Render Environment에 Secret로 추가. 없으면 검색·원문만 작동 |
| `OPENAI_MODEL` | 기본 `gpt-4.1-mini`. 계정에서 사용 가능한 모델로 설정 |
| `PYTHON_VERSION` | `3.12.16` |
| `PORT` | Render 자동 제공. 수동 지정 불필요 |

접속 화면의 역할 버튼은 배포 환경에서도 동일하게 작동하므로 데모 비밀번호 입력은 필요하지 않습니다. Django 비밀 키와 모델 API 키는 Render Secret로 관리하세요.

실제 발급된 주소는 **https://goodmona-staff-intranet-demo.onrender.com/** 입니다. HTTPS 프록시 헤더, 보안 쿠키, HSTS, `DEBUG=False`, WhiteNoise 정적 파일 설정을 적용합니다. Render는 기본 도메인의 TLS를 제공합니다. [Render TLS](https://render.com/docs/tls)

같은 실행 인스턴스에서는 새로고침과 재접속 후에도 변경 내용을 유지합니다. **무료 서버 재시작·재배포·절전 후 인스턴스가 교체되면 변경 내용이 사라지고 기본 가상 자료를 다시 생성합니다.** 영구 보존을 보장하는 운영 시스템이 아닌 무료 면접 데모입니다. 15분간 접속이 없으면 절전될 수 있고 다음 접속의 기동에는 약 1분이 걸릴 수 있으므로 면접 직전에 열어 준비하세요.

## 면접 시연 순서

접속 화면에서 ‘직원으로 접속’ 또는 ‘관리자로 접속’을 선택합니다. 한 창에서는 ‘역할 변경’으로 전환할 수 있습니다. 직원은 일반 창, 관리자는 시크릿 창처럼 세션이 분리된 창을 사용하면 두 역할을 동시에 시연하기 편합니다.

1. **CS 위키:** ‘직원으로 접속’ 클릭 → 고객 답변 찾기 → `예약 시간을 변경하려면 어떻게 안내하나요?` → 응대 허용 근거, v2 문서, 개정일과 원문을 확인합니다. 모델 키가 있으면 짧은 초안을 검토하고 복사합니다. 키가 없으면 모델 미연결과 정상 검색을 구분해 설명합니다.
2. `우주여행 보험 가입은 어떻게 하나요?` → **담당자 확인 필요**, 모델 미호출을 확인합니다. `예약 변경 위약금`처럼 일부 주제만 맞는 질문도 확인이 필요합니다.
3. 내부 문서 찾기 → `직원 온보딩` → `INTERNAL-ONLY-482` 원문을 확인합니다. 같은 검색어를 고객 답변 찾기에서 실행하면 해당 원문이 나오지 않고 모델에도 전달되지 않습니다.
4. **연차:** 가상 지원의 잔여 12일 확인 → 달력 2026-11-18 선택 → 오전 반차 신청 → 관리자 / 연차 승인 달력의 같은 날짜에서 승인 → 직원 달력의 자동 갱신으로 11.5일과 승인 완료 확인. 11/19에는 세 번째 신청 차단, 11/20에는 마지막 한 자리의 승인 경쟁을 시연합니다. 새 서버에서는 [실제 생성 날짜](docs/calendar-upgrade.md)를 확인합니다.
5. **차량:** 차량 화면의 1호 기존 예약 시간을 확인 → 같은 날 10:30–11:30처럼 겹치는 시간으로 신청 → **이미 예약된 시간과 겹칩니다** 확인 → 11:00–12:00처럼 인접 시간은 예약 성공을 확인합니다. 날짜는 실제 표시된 미래 예약 기준으로 선택합니다.
6. 관리자에서 위키 개정 초안 → 문단 응대 범위 검토 → 저장·발행하면 새 버전만 검색됨을 보여줄 수 있습니다.

## 검증 결과와 한계

확인일: 2026-11-12, Windows / Python 3.12.16 / Django 5.2.19.

| 검증 | 결과 |
| --- | --- |
| 자동 테스트 | **71개 통과**. 기존 위키·권한·연차·차량 54개와 달력·부서 인원·동시 승인·마이그레이션·시드 보존 17개 |
| 실제 SQLite 동시 요청 | 동시 승인 1회 차감, 동시 중복 예약 1건만 저장 |
| 실제 로컬 HTTP | 8002 포트에서 CSRF 포함 직원·관리자 역할 접속·전환, 보호된 메뉴, 위키 네 가지 검색 흐름 통과 |
| 시작 프로세스 재실행 | 격리된 SQLite에서 문서 편집·연차 승인 잔여일·예약 취소·행 개수 보존 확인 |
| Django 운영 설정 점검 | `DEBUG=False`로 `check --deploy --fail-level WARNING` 통과 |
| 정적 파일·마이그레이션 | `collectstatic`, 마이그레이션 생성·적용 및 누락 검사 통과 |
| 모델 성공·실패·공개 범위 | 모의 API 테스트 통과. **실제 모델 호출은 API 키가 없어 미검증** |
| 브라우저 시각·iPhone Safari | 반응형 CSS 구현. Windows 브라우저 주소 판별 제한으로 자동 검증 중단, **실기기 미검증** |
| 실제 Render Free HTTPS·Gunicorn 실행 | **배포 성공 및 실제 검증 통과**. 직원·관리자 접속, 위키 4가지 검색, 관리자 요청 차단, 연차 신청·중복 승인·취소 복원, 차량 충돌·인접 예약·취소 |
| Free 재시작·재배포의 데이터 보존 | **영구 보존하지 않음**. 새 인스턴스에서는 기본 가상 자료를 자동 생성. 이 직원 서비스의 원격 재시작 실험은 별도 미실시 |

다시 검증하기:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=intranet.test_settings --noinput
.\.venv\Scripts\python.exe scripts/verify_persistence.py
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
$env:DJANGO_DEBUG = 'False'
.\.venv\Scripts\python.exe manage.py check --deploy --fail-level WARNING
Remove-Item Env:DJANGO_DEBUG
```

개발 서버가 켜진 별도 PowerShell에서 `python scripts/http_smoke.py`를 실행하면 실제 HTTP 조회 검증을 재현합니다. 공개 기능 검증은 `python scripts/verify_public.py https://goodmona-staff-intranet-demo.onrender.com`으로 실행합니다. 연차 승인 후 취소로 잔여일을 복원하고 테스트 차량 예약도 취소합니다. `verify_persistence.py`는 같은 임시 DB를 시작 프로세스들이 재사용하는 로컬 검사이며 Free 인스턴스 교체 후 보존을 뜻하지 않습니다. [배포 커밋의 Linux CI](https://github.com/dlwo8520/goodmona-staff-intranet/actions/runs/43207582581)도 통과했습니다. 실제 공개 검증 요약은 [검증 JSON](docs/public-verification.json)에 있습니다.

실제 HTTPS에서 역할 미선택 시 접속 선택 화면 이동 → 직원 검색 → 신청 → 관리자 승인 → 직원 잔여일 → 예약 충돌까지 검증했습니다. PC·아이폰 Safari의 실제 조작은 직접 확인할 수 있습니다. 배포 규칙과 과거 배포 시도는 [배포 메모](docs/deployment-notes.md)에 정리했습니다. API 형식은 [OpenAI Responses 문서](https://platform.openai.com/docs/api-reference/responses/create)를 참고했습니다.
