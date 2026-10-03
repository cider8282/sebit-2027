# 처음 배포하기

선생님의 컴퓨터에 Python·Node.js·Git을 설치하지 않고 GitHub Actions에서 배포하는 방법입니다. 처음 한 번 GitHub와 Firebase 설정이 필요합니다. 현재 파일은 실제 계정에 배포되지 않았습니다.

## 1. 테스트 전용 Firebase 프로젝트 준비

1. https://console.firebase.google.com 에서 **새 프로젝트**를 만듭니다. 기존 학생들이 사용하는 프로젝트를 선택하지 마세요.
2. 프로젝트 설정에서 **프로젝트 ID**를 확인합니다. 표시 이름과 다릅니다.
3. Cloud Functions 사용을 위해 Blaze 요금제로 변경하고 결제 수단을 연결합니다. 이 단계는 계정 소유자가 비용 조건을 확인한 뒤 진행합니다.
4. Firestore Database에서 **Standard / Native mode의 `(default)` 데이터베이스**를 만듭니다. 위치는 가능하면 서울 `asia-northeast3`를 선택합니다. 서버 함수도 서울로 지정되어 있습니다. Production mode로 시작합니다.
5. Google Cloud 결제에서 예산 알림을 설정합니다. 알림만으로 서비스 사용이나 비용 발생이 자동 중지되지는 않습니다.

## 2. GitHub 저장소 준비

1. 새 저장소를 만듭니다. 예: `sebit-test`.
2. ZIP을 압축 해제합니다. `SEBIT-GitHub-Firebase` **폴더 안의 내용**을 저장소 맨 위에 업로드합니다.
3. 저장소 맨 위에 `site`, `functions`, `firebase.json`, `.github`가 보이는지 확인합니다. ZIP 파일 자체를 올리는 방식이 아닙니다.
4. 특히 `.github/workflows/deploy.yml`이 들어 있어야 Actions 실행 메뉴가 생깁니다. 빠졌다면 GitHub의 Add file → Create new file에서 같은 경로로 추가합니다.
5. Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 선택합니다.

완성 주소는 보통 `https://깃허브아이디.github.io/sebit-test/` 형태입니다. 공개 저장소에는 코드와 그림만 들어가고 학생 기록은 Firestore에 저장됩니다.

## 3. Firebase 배포용 계정 연결

GitHub가 Firebase에 배포하려면 전용 Google 서비스 계정의 권한이 필요합니다. 이 단계는 Firebase/Google Cloud 관리자 설정입니다.

1. 새 프로젝트의 Google Cloud Console → IAM 및 관리자 → 서비스 계정에서 배포용 계정을 만듭니다. 예: `sebit-deployer`.
2. 프로젝트 내에서 함수·규칙·예약 작업·비밀 코드를 배포할 수 있도록 아래 역할을 설정합니다. 조직 정책에 따라 관리자의 승인이 필요할 수 있습니다.

| 용도 | Google Cloud 역할 ID |
|---|---|
| Functions 배포 | `roles/cloudfunctions.admin` |
| HTTP 함수 공개 호출 설정 | `roles/run.admin` |
| 실행 서비스 계정 사용 | `roles/iam.serviceAccountUser` |
| 예약 만기 처리 작업 배포 | `roles/cloudscheduler.admin` |
| Firestore 보안 규칙 배포 | `roles/firebaserules.admin` |
| Firestore 인덱스·TTL 설정 | `roles/datastore.indexAdmin` |
| 개설 코드 Secret 생성·설정 | `roles/secretmanager.admin` |
| Firebase API 활성화·사용 | `roles/serviceusage.serviceUsageAdmin` |
| Firebase 프로젝트 확인 | `roles/firebase.viewer` |

3. 함수의 실행 계정(별도 지정하지 않았다면 `프로젝트번호-compute@developer.gserviceaccount.com`)에는 Firestore 접근을 위한 `roles/datastore.user`가 필요합니다. 최신 조직 정책에서 기본 권한이 없으면 명시적으로 부여합니다. Secret 접근 권한은 Firebase CLI가 배포 때 설정합니다.
4. 배포 계정의 Keys에서 JSON 키를 생성합니다. **이 파일은 저장소·웹 파일·이 대화에 올리지 마세요.** 다음 단계에서 GitHub의 전용 Secret 입력란에만 넣습니다. 키 생성을 금지한 조직은 관리자에게 Workload Identity Federation 연결을 요청해야 합니다. 현재 워크플로는 JSON 키 방식입니다.

첫 Functions 배포 시 Cloud Build·Artifact Registry 등 API가 활성화됩니다. 조직의 API/서비스 계정 정책에 따라 빌드 계정 권한을 추가 설정해야 할 수 있습니다. 실패한 Actions 단계의 오류에 따라 권한을 확인하세요. 권한을 우회하도록 전체 Owner 권한을 부여하지 마세요.

## 4. GitHub 설정값 4개 입력

저장소 → Settings → Secrets and variables → Actions에서 설정합니다.

**Variables 탭**

| 이름 | 값 |
|---|---|
| `FIREBASE_PROJECT_ID` | 1단계에서 만든 새 Firebase 프로젝트 ID |
| `PAGES_ORIGIN` | `https://깃허브아이디.github.io` — 저장소 경로와 마지막 `/` 제외 |

**Secrets 탭**

| 이름 | 값 |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT` | 3단계 JSON 키 파일의 내용 전체 |
| `SEBIT_SETUP_KEY` | 비밀번호 관리 도구 등으로 만든 영문·숫자·`_`·`-` 24~128자리 비밀 코드 |

`SEBIT_SETUP_KEY`는 첫 학급 개설 화면에서 입력할 코드이므로 따로 보관합니다. 학생에게 제공하지 않습니다. 교사 로그인 비밀번호와는 별개입니다.

실제 키와 비밀번호는 소스 파일에 적지 않습니다. `site/config.js`에 자동 기록되는 것은 공개 가능한 Firebase 함수 주소뿐입니다.

## 5. GitHub에서 배포 실행

1. Actions → **SEBIT - Firebase and GitHub Pages** → Run workflow를 누릅니다.
2. 테스트 전용 Firebase 프로젝트가 맞는지 확인하고 체크합니다. 기존 운영 프로젝트에는 실행하지 않습니다.
3. 다음 세 단계가 순서대로 진행됩니다.
   - `verify`: 임시 Firestore 에뮬레이터와 화면 로직 검사.
   - `backend`: Firebase 함수·규칙·인덱스 배포, 서버 연결과 익명 접근 차단 검사.
   - `pages`: `site/` 폴더만 GitHub Pages에 게시.
4. `pages`가 완료되면 표시된 주소를 엽니다. 배포가 처음이면 준비 시간이 걸릴 수 있습니다.

워크플로는 버튼으로 실행합니다. 단순히 코드를 수정할 때마다 운영 서버를 자동으로 바꾸지 않습니다. 재배포에는 같은 절차를 사용합니다.

코드가 검사에 통과해도 프로젝트 IAM·조직 정책·Pages 권한 때문에 배포가 실패할 수 있습니다. 현재 패키지는 실제 계정에서 그 단계까지 검증된 것은 아닙니다.

## 6. 학급 만들고 가상 학생으로 확인

1. 완성된 웹 주소에서 학급 이름·개설 코드·교사 비밀번호를 입력합니다.
2. 가상 학생 2~3명을 등록하고 학생 접속을 엽니다.
3. 별도 브라우저 또는 iPad에서 학생 아이디와 임시 PIN으로 로그인하고 개인 PIN으로 변경합니다.
4. 점수 지급 → 구매 → 주머니 → 지급 요청 → 교사 지급 완료를 확인합니다.
5. 활동 보상·메시지·백업 파일 다운로드와 복원을 확인합니다. 복원은 테스트 자료에서만 진행합니다.
6. 실제 학교 iPad Safari에서 키보드·대화상자·다운로드·3분 로그아웃을 확인한 뒤 학생에게 주소·QR을 배포합니다.

예금 만기와 요청 만료는 예약 함수가 약 1분 간격으로 처리하며, 화면 조회와 거래 때도 다시 검사합니다. 예약 서비스 지연 중에도 중복 지급은 거래 기록으로 방지합니다.

## 자주 막히는 부분

| 표시/현상 | 확인 |
|---|---|
| Actions에 배포 메뉴 없음 | `.github/workflows/deploy.yml`이 기본 브랜치에 있는지 |
| Firebase 연결 주소가 아직 설정되지 않았어요 | `site/index.html` 로컬 파일 대신 Actions가 게시한 Pages 주소를 열었는지 |
| 허용된 SEBIT 주소에서 접속해 주세요 | `PAGES_ORIGIN`의 도메인이 실제 Pages 주소와 같은지 |
| Firebase 응답을 읽지 못했어요 | 서버 `sebit_api` 배포가 성공했는지, 프로젝트 ID가 정확한지 |
| `PERMISSION_DENIED` / API 활성화 실패 | 실패한 서비스의 IAM 역할·조직 정책 확인 |
| `pages` 단계 실패 | Settings → Pages의 Source, 저장소의 Pages 사용 가능 여부 확인 |
| 학급 개설 코드를 확인해 주세요 | GitHub Secret `SEBIT_SETUP_KEY`와 입력한 값이 같은지 |
| 학생 로그인이 막힘 | 교사가 학생 접속을 열었는지·전출 상태인지·PIN 재발급 여부 확인 |

## 교사 비밀번호를 잊은 경우 — 관리자용

Firebase 프로젝트에 관리 권한이 있는 사람만 실행합니다. Google Cloud Shell에서 저장소를 내려받고 개발 의존성을 설치한 뒤 다음 명령을 실행합니다. 선생님의 PC에 Python을 설치하는 절차는 아닙니다.

```
python3 -m venv /tmp/sebit-admin
/tmp/sebit-admin/bin/pip install -r functions/requirements.txt
/tmp/sebit-admin/bin/python scripts/reset_teacher.py 프로젝트ID
```

화면에서 새 비밀번호를 입력합니다. 비밀번호는 화면에 표시하지 않으며 모든 교사 세션을 종료합니다. Cloud Shell 사용자에게 Firestore 접근 권한이 있어야 합니다. 학생 데이터는 초기화하지 않습니다.

## 공식 문서

- https://firebase.google.com/docs/functions/get-started
- https://firebase.google.com/docs/functions/config-env
- https://firebase.google.com/docs/projects/iam/roles-predefined-product
- https://github.com/google-github-actions/auth
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
