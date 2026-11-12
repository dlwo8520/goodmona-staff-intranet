# Render 배포 확인 메모

## GitHub 업로드 및 배포 시도 · 2026-11-12

소스를 `https://github.com/dlwo8520/goodmona-staff-intranet`에 업로드하고 Linux GitHub Actions 검사가 성공했음을 확인했습니다. 사용자가 `My Workspace`를 배포 대상으로 선택했습니다. Render Blueprint 생성 후 최초 계획은 `services[0]: need_payment_info` 오류로 실패했으며, 아직 웹 서비스·영구 디스크는 생성되지 않았습니다. 실패한 계획은 승인하지 않았습니다. 결제 정보 등록 후 같은 Blueprint의 계획을 재실행하고, 성공한 계획을 검토·승인한 뒤 배포해야 합니다. HTTPS 주소와 원격 데이터 보존은 아직 검증하지 못했습니다.

## 추가 연결 확인 · 2026-11-12

Render 플러그인 설치 후 계정 연결을 다시 확인했습니다. 워크스페이스 조회가 성공했고 `My Workspace`가 표시되었습니다. 현재 선택된 워크스페이스는 없으며 사용자 선택 후 해당 워크스페이스 ID를 요청에 전달해야 합니다. 아직 GitHub 저장소와 Git 원격 주소가 없어 배포는 시작하지 않았습니다. 아래 ‘현재 세션의 검증 범위’는 최초 구현 시점의 조사 기록입니다.

확인일: 2026-11-12 (Asia/Seoul). 이 문서는 공식 문서와 현재 세션의 연결 상태를 조사한 결과다. 실제 배포 성공 기록이 아니다.

## 확인된 배포 규칙

- 과제 1과 별도인 Python 웹 서비스와 별도 디스크를 만든다. 현재 최소 유료 웹 서비스 플랜 ID는 `0.5c-512mb`이며 예전 이름은 `starter`다. 실제 비용은 서비스 생성 화면에서 확인한다. [Render Compute Plans](https://render.com/docs/compute-plans)
- SQLite 파일은 영구 디스크 마운트 경로 아래에 둔다. 예: `/var/data/intranet.sqlite3`. Blueprint 디스크는 `name`, `mountPath`, `sizeGB`로 선언한다. [Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- 영구 디스크는 유료 서비스에서만 사용할 수 있으며, 빌드·pre-deploy·one-off 작업에서는 접근할 수 없다. 따라서 빌드에서는 의존성 설치와 `collectstatic`만 수행하고, 디스크가 연결된 **시작 단계에서** 마이그레이션과 선택적 데모 데이터 생성을 수행한 다음 Gunicorn을 실행한다. [Persistent Disks](https://render.com/docs/disks), [Deploys](https://render.com/docs/deploys)
- 디스크는 하나의 서비스 인스턴스만 사용할 수 있다. 디스크가 있는 서비스의 재배포는 짧은 중단을 동반한다. SQLite를 사용하는 이 시연에서는 인스턴스 하나와 Gunicorn worker 하나를 사용하고 데이터 변경을 짧은 트랜잭션으로 처리한다. LLM 네트워크 호출은 트랜잭션 밖에서 수행한다. [Persistent Disks](https://render.com/docs/disks), [Django SQLite notes](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes)
- 서버는 `0.0.0.0:$PORT`에 바인딩한다. Render 웹 서비스 기본 포트는 `10000`이다. [Web Services](https://render.com/docs/web-services)
- Render는 `.onrender.com` 주소에 TLS 인증서를 제공하며 HTTP 요청을 HTTPS로 이동시킨다. Django의 HTTPS 프록시 헤더 신뢰 설정, 보안 쿠키, `DEBUG=False`, 허용 호스트를 함께 설정한다. [TLS](https://render.com/docs/tls), [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- Render의 일반 Django 튜토리얼은 PostgreSQL을 가정한다. 그 문서의 빌드 단계 마이그레이션 예시는 SQLite 영구 디스크 구성에 그대로 적용하지 않는다. [Deploy Django](https://render.com/docs/deploy-django)

## 현재 세션의 검증 범위

- Render 플러그인은 검색되지만 연결되어 있지 않았다. 이미 추천된 이력이 있어 중복 추천하지 않았다.
- 환경 변수 **이름만** 확인했으며 Render 배포 인증 변수가 없었다.
- 브라우저 연결 호스트가 없었고, Windows 브라우저의 URL을 충분한 신뢰도로 판별하지 못해 Computer Use가 중단되었다. 이 때문에 기존 Render 로그인 세션 여부는 확인하지 못했다.
- 실제 Render 서비스 생성, HTTPS 접속, 공개 환경 로그인·검색·연차 신청·승인, 재시작·재배포 후 데이터 보존은 **미검증**이다. 최종 README에는 로컬 테스트 결과와 구분해서 기록한다.
- 모델 API 실제 호출 결과도 별도로 검증해야 한다. 키가 없는 검색·원문 표시와 모의 API 테스트는 실제 모델 호출 검증을 대신하지 않는다.

## 배포 후 반드시 확인할 흐름

1. Render가 발급한 실제 HTTPS 주소로 접속해 비로그인 사용자가 로그인 화면으로 이동하는지 확인한다.
2. 직원 계정으로 CS 위키의 근거 있는 질문·없는 질문·내부 문서 검색을 확인한다.
3. 직원 연차 신청 후 관리자 계정으로 승인하고 직원 잔여일 변화를 확인한다.
4. 같은 차량의 겹치는 예약을 요청해 거절되는지, 끝나는 시각과 다음 시작 시각이 같으면 허용되는지 확인한다.
5. 문서 개정·승인·예약 상태를 기록한 뒤 서비스를 재시작하고 재배포하여 값이 유지되는지 확인한다.
