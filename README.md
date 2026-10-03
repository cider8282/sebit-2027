# SEBIT · GitHub Pages + Firebase 전환본

선생님 PC와 학생 iPad에 Python을 설치할 필요가 없습니다. 배포 후 인터넷 주소 또는 QR로 접속합니다. PC 실행 창을 켜 둘 필요도 없습니다.

이 파일은 **배포를 준비한 코드**입니다. 아직 선생님의 GitHub·Firebase 계정에 연결하거나 실제 주소로 배포하지 않았습니다. 첫 연결은 `DEPLOY.md` 순서대로 설정해야 합니다.

## 실행 방식

| 역할 | 담당 |
|---|---|
| 화면·그림·글꼴 제공 | GitHub Pages |
| 로그인·PIN·교사 권한·구매·보상 검사 | Firebase Cloud Functions |
| 학급 기록 보관·동시 거래 처리 | Firebase Firestore |
| 예금 만기·지급 요청 만료 처리 | Firebase 예약 함수, 약 1분 간격 + 접속/거래 시 재확인 |
| 개발 도구 설치와 배포 | GitHub Actions의 임시 컴퓨터 |

서버 내부에는 검증된 기존 Python 업무 로직을 유지했습니다. 그 코드는 Firebase에서 실행됩니다. 사용자의 컴퓨터에 Python을 설치하거나 `.cmd`를 실행하지 않습니다. Firebase Authentication 서비스 대신 기존 학생 아이디·PIN과 교사 비밀번호 로그인을 서버에서 검증합니다.

## 비용과 첫 연결

Firebase Cloud Functions를 배포하려면 **Blaze 요금제와 결제 수단 연결**이 필요합니다. 무료 Spark 요금제만 사용하는 구성은 아닙니다. Functions·Firestore·Scheduler·Secret Manager·배포 이미지 저장소 등의 사용량에 따라 비용이 생길 수 있으며 무료 운영을 보장하지 않습니다. 예산 알림은 자동 과금 중지 장치가 아닙니다.

기존 운영 앱과 분리된 **새 GitHub 저장소와 새 Firebase 프로젝트**로 테스트하세요. 포함된 Firestore 규칙은 모든 브라우저 직접 접근을 차단합니다. 기존 앱과 같은 Firebase 프로젝트에 적용하면 기존 앱의 접근도 막힐 수 있습니다.

Firebase 웹 앱의 `apiKey` 등을 HTML에 붙이는 작업만으로는 완료되지 않습니다. 포함된 서버 함수와 보안 규칙도 함께 배포해야 합니다. `DEPLOY.md`에 초기 설정과 자동 배포 방법을 적었습니다.

## 그대로 유지한 내용

- 환상 동물 등급·학생/교사 화면·직업·퀘스트·활동·은행·법·모범시민·온도계·메시지.
- 새 간식 이미지 5종과 문구 대표 그림 1종. 기존 종류를 유지하고 새 그림을 사용합니다.
- 새 학급 시작. 기존 학생·점수·가격·재고를 불러오지 않습니다.
- 간식 5종은 판매 준비·가격 0·재고 0 상태입니다. 교사가 실제 값을 설정하고 판매를 시작합니다.
- 수동 JSON 백업·복원. 복원은 현재 교사 비밀번호를 유지하고 학생 접속을 닫으며 기존 세션을 종료합니다.

## 바뀐 부분

- 로컬 SQLite 대신 Firestore 트랜잭션으로 기록을 저장합니다. 구매에 따른 잔액·재고·주머니·거래 내역을 한 번에 반영합니다.
- 동일한 요청을 재전송하면 한 번만 처리합니다. 요청 기록은 해당 학급 회차 동안 보존합니다.
- 학생은 자신의 기록만 내려받으며, 상인·생활지킴이에게 필요한 자료만 추가로 제공합니다.
- 첫 학급 설정에는 배포 관리자가 정한 비밀 개설 코드가 필요합니다.
- GitHub Pages의 `/저장소이름/` 경로에서도 글꼴·그림·스크립트가 열리도록 상대 경로로 바꿨습니다.
- 화면 상태는 약 15초 간격으로 갱신합니다. 숨겨진 탭·입력 중인 화면에서는 갱신을 미룹니다. 자신의 저장 결과는 즉시 다시 읽습니다.
- 학생 3분 미사용 로그아웃을 유지합니다. 교사는 이 3분 제한이 없으며 세션에는 별도의 최대 수명이 있습니다.

## 파일 구성

| 경로 | 내용 |
|---|---|
| `site/` | GitHub Pages에 공개되는 웹 파일만 포함 |
| `functions/` | Firebase에서 실행할 서버 코드 |
| `firestore.rules` | 브라우저 직접 데이터 접근 차단 |
| `firestore.indexes.json` | 데이터 청크 인덱스 제외·만료 세션 정리 설정 |
| `.github/workflows/deploy.yml` | 검사 → Firebase 배포 → API 확인 → Pages 배포 |
| `scripts/` | 연결 설정·배포 확인·관리자 비밀번호 복구 |
| `tests/` | Firestore 에뮬레이터·HTTP·화면 로직 검사 |
| `DEPLOY.md` | 처음 연결하고 배포하는 순서 |
| `VALIDATION.md` | 실제 통과한 검사와 남은 확인 |
| `SPEC.md` | 학급 운영 규칙과 전환 기준 |
| `ASSET-NOTES.md` | 새 상품 그림 생성 기록 |

`site/index.html`을 파일로 직접 열면 설정 전에는 연결 안내가 나옵니다. 실제 기록 사용은 Firebase 연결과 HTTPS 배포 후 가능합니다.

## 검증 상태

Firestore 에뮬레이터에서 34개, 화면 로직 8개, 웹 배포 경로·연결 검사 7개를 통과했습니다. SDK의 함수 배포 명세 생성도 확인했습니다. 실제 Firebase 계정의 배포 권한·과금 설정, GitHub Actions 실행, iPad Safari, 한 학급의 실제 동시 접속은 아직 검증하지 않았습니다.

처음 배포한 주소에서 가상 학생 2~3명으로 로그인 → 점수 지급 → 구매 → 주머니 → 지급 완료 → 백업/복원을 확인한 뒤 학생에게 안내하세요.

## 공식 안내

- Firebase 시작·Blaze 요구 사항: https://firebase.google.com/docs/functions/get-started
- Firestore 트랜잭션: https://firebase.google.com/docs/firestore/manage-data/transactions
- 예약 함수: https://firebase.google.com/docs/functions/schedule-functions
- GitHub Pages 자동 배포: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
