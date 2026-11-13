# 토론 동아리 사이트

동아리방 예약 · 토론 타이머 · 토론 기록/전적 · 회원 관리를 한곳에서 하는 웹사이트입니다.

| 폴더 | 내용 | 배포 |
|------|------|------|
| `frontend/` | Vue 3 + Vite + TypeScript | Vercel |
| `backend/`  | FastAPI (Python 3.11) | Google Cloud Run (Docker) |
| `backend/sql/schema.sql` | DB 테이블 + 보안 설정 | Supabase |

## 구조 한눈에 보기

```
브라우저(Vue) ──로그인 토큰──▶ 백엔드(FastAPI) ──service_role 키──▶ Supabase(DB·로그인)
```

- 브라우저는 Supabase를 **로그인 상태 보관**에만 씁니다. 데이터는 전부 백엔드 API로 읽고 씁니다.
- DB는 모든 테이블에 RLS를 켜고 정책을 두지 않아서, 브라우저에서 직접 읽거나 쓸 수 없습니다.
- 권한 검사(로그인 여부, 관리자 여부, 비밀번호 초기화 후 변경 여부)는 백엔드가 요청마다 합니다.

## 기능

- **회원가입 / 로그인**: 누구나 이름 + 학번 + 비밀번호로 가입하고(관리자 승인 없음), 같은 정보로 로그인합니다. 비밀번호를 잊으면 관리자가 학번으로 초기화하고, 다음 로그인 때 새 비밀번호를 정해야 합니다.
- **동아리방 예약**: 한국 시간 08:00~24:00, 30분 단위. 같은 시간대에는 양쪽 모두 '동시 사용 허용'일 때 최대 2팀. 토론과 연결해 예약하면 상대 팀이 같은 시간에 예약했는지 알려줍니다.
- **타이머**: 순서별 발언 시간, 양 팀이 시간을 나눠 쓰는 자유토론 시계, 30초 전·종료 시 종소리, 순서 편집(브라우저에 저장).
- **토론 기록**: 논제·날짜·방식·찬반 참가자·승패. 연도/학기/방식 필터와 검색, 전적 순위.
- **마이페이지**: 내 전적과 참가한 토론.
- **회원 관리(관리자)**: 회원 목록, 비밀번호 초기화, 관리자 지정, 계정 삭제.

## 처음 설치하기

### 1. Supabase

1. [supabase.com](https://supabase.com)에서 프로젝트를 만듭니다.
2. **SQL Editor**에 `backend/sql/schema.sql` 전체를 붙여넣고 실행합니다.
3. **Authentication > Sign In / Providers**에서 "Allow new users to sign up"을 **끕니다**. (가입은 이 사이트의 백엔드를 통해서만 받습니다)
4. **Project Settings > API**에서 Project URL, `anon` 키, `service_role` 키를 복사해 둡니다.
   `service_role` 키는 모든 권한을 가진 키입니다. 백엔드 `.env`에만 넣고, 프론트엔드나 GitHub에는 절대 올리지 않습니다.

### 2. 백엔드

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # 값 채우기
python -m scripts.create_admin --name 홍길동 --student-id 20201234 --password '8자-이상-비밀번호'
uvicorn app.main:app --reload --port 8000
```

`http://localhost:8000/docs`에서 API 목록을 볼 수 있습니다.

### 3. 프론트엔드

```bash
cd frontend
npm install
cp .env.example .env                                   # 값 채우기
npm run dev
```

`http://localhost:5173`에 접속하면 회원가입과 로그인 중에 고를 수 있습니다. 방금 만든 관리자 계정은 로그인으로 들어갑니다.

## 배포

### 백엔드 → Cloud Run

```bash
cd backend
gcloud run deploy debate-club-api --source . --region asia-northeast3 --allow-unauthenticated \
  --set-env-vars "SUPABASE_URL=...,SUPABASE_ANON_KEY=...,ALLOWED_ORIGINS=https://내-도메인,MEMBER_EMAIL_DOMAIN=member.debate-club.local"
```

`SUPABASE_SERVICE_ROLE_KEY`는 명령어에 직접 쓰지 말고 Cloud Run 콘솔의 **보안 비밀(Secret)** 로 등록하는 것을 권합니다.

### 프론트엔드 → Vercel

1. GitHub 저장소를 Vercel에 연결하고 Root Directory를 `frontend`로 지정합니다.
2. Environment Variables에 `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE`(Cloud Run 주소), `VITE_CLUB_NAME`을 넣습니다.
3. 배포된 주소를 백엔드의 `ALLOWED_ORIGINS`에 추가하고 백엔드를 다시 배포합니다.

## 알아둘 점

- `MEMBER_EMAIL_DOMAIN`은 계정을 만든 뒤에는 바꾸지 마세요. (로그인용 가상 이메일이 `학번@도메인`으로 저장됩니다)
- 가입에 승인 절차가 없어서, 사이트 주소를 아는 사람은 누구나 가입해 예약·기록을 볼 수 있고 남의 학번으로 가입할 수도 있습니다. 회원 관리 화면에서 모르는 계정은 삭제하세요(삭제하면 그 학번으로 다시 가입할 수 있습니다).
- 타이머의 기본 순서·시간은 예시입니다. '순서 편집'에서 동아리 규칙에 맞게 바꾸세요.
- 로그인 시도 제한은 서버 인스턴스별로 따로 셉니다. 더 엄격하게 하려면 Supabase의 Auth rate limit 설정도 함께 조정하세요.
