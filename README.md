# 토론 동아리 사이트

동아리방 예약 · 토론 타이머 · 토론 기록/전적 · 회원 관리를 한곳에서 하는 웹사이트입니다.

| 폴더 | 내용 | 올리는 곳 |
|------|------|-----------|
| `frontend/` | Vue 3 + Vite + TypeScript | Vercel (무료 Hobby) |
| `supabase/schema.sql` | DB 테이블, 접근 규칙, 함수 | Supabase (무료) |

별도의 백엔드 서버가 없습니다. 브라우저가 Supabase에 직접 연결합니다.

## 구조

```
브라우저(Vue) ──공개 키 + 로그인 토큰──▶ Supabase (로그인 · DB)
```

- 프로젝트 어디에도 Secret 키(`sb_secret_…`)를 넣지 않습니다. 필요한 것은 Project URL과 공개 키뿐입니다.
- 테이블은 로그인한 회원에게 읽기만 열려 있고, 쓰기는 전부 DB 함수로만 합니다. 함수가 매번 로그인 여부와 관리자 여부를 검사합니다.
- 다른 회원에게는 이름·학과·기수만 보입니다. 학번은 본인과 관리자만 볼 수 있습니다.

## 기능

- **회원가입 / 로그인**: 누구나 이름 + 학번 + 비밀번호로 가입하고(관리자 승인 없음), 같은 정보로 로그인합니다.
- **동아리방 예약**: 한국 시간 08:00~24:00, 30분 단위. 같은 시간대에는 양쪽 모두 '동시 사용 허용'일 때 최대 2팀. 토론과 연결해 예약하면 상대 팀이 같은 시간에 예약했는지 알려줍니다.
- **타이머**: 순서별 발언 시간, 양 팀이 시간을 나눠 쓰는 자유토론 시계, 30초 전·종료 시 종소리, 순서 편집(브라우저에 저장). 로그인 없이 쓸 수 있습니다.
- **토론 기록**: 논제·날짜·방식·찬반 참가자·승패. 연도/학기/방식 필터와 검색, 전적 순위.
- **마이페이지**: 내 전적과 참가한 토론, 비밀번호 변경.
- **회원 관리(관리자)**: 회원 목록, 비밀번호 초기화(학번으로 되돌리고 다음 로그인 때 변경 강제), 관리자 지정, 계정 삭제.

## 설치

### 1. Supabase

1. [supabase.com](https://supabase.com)에서 프로젝트를 만듭니다.
2. **SQL Editor**에 `supabase/schema.sql` 전체를 붙여넣고 실행합니다. (이전 버전을 실행한 적이 있어도 그대로 다시 실행하면 됩니다)
3. **Authentication > Sign In / Providers**에서
   - "Allow new users to sign up"을 **켭니다**.
   - Email 항목의 "Confirm email"을 **끕니다**. (학번으로 만든 가상 이메일을 쓰기 때문에 메일 인증을 할 수 없습니다)
4. **Project Settings > API Keys**에서 Project URL과 Publishable key를 확인합니다.

### 2. 내 컴퓨터에서 실행 (선택)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

`http://localhost:5173`에 접속해 회원가입을 합니다.

### 3. 첫 관리자 지정

사이트에서 본인 계정으로 가입한 뒤, Supabase **SQL Editor**에서 한 번 실행합니다.

```sql
update public.users set role = 'admin' where student_id = '본인학번8자리';
```

그 뒤로는 사이트의 회원 관리 화면에서 다른 관리자를 지정할 수 있습니다.

### 4. 배포 (Vercel)

1. [vercel.com](https://vercel.com)에 GitHub 계정으로 가입하고 이 저장소를 Import 합니다.
2. **Root Directory**를 `frontend`로 지정합니다.
3. Environment Variables에 `frontend/.env.example`의 세 값(`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_CLUB_NAME`)을 넣고 Deploy 합니다.

## 알아둘 점

- 가입에 승인 절차가 없어서 사이트 주소를 아는 사람은 누구나 가입해 예약과 기록을 볼 수 있고, 남의 학번으로 가입할 수도 있습니다. 회원 관리 화면에서 모르는 계정은 삭제하세요(삭제하면 그 학번으로 다시 가입할 수 있습니다).
- 로그인용 가상 이메일은 `학번@member.debate-club.local` 형태입니다. 회원이 가입한 뒤에는 이 도메인(`VITE_MEMBER_EMAIL_DOMAIN`)을 바꾸지 마세요.
- 이메일로 비밀번호를 찾는 기능은 없습니다. 비밀번호를 잊으면 관리자가 초기화합니다.
- 타이머의 기본 순서·시간은 예시입니다. '순서 편집'에서 동아리 규칙에 맞게 바꾸세요.
- 한 번에 가져오는 기록은 Supabase 기본 한도(1,000행)까지입니다. 토론 기록이 그보다 많아지면 연도 필터를 쓰세요.
