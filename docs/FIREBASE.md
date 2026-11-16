# 구글 로그인 켜기 (Firebase, 무료)

구글 로그인과 계정(닉네임 중복 방지, 기기 간 기록 저장)은 Firebase 로 동작합니다.
설정 전에는 게스트로만 들어갈 수 있어요. 아래를 한 번만 하면 됩니다 (10분).

## 1. 프로젝트 만들기
1. https://console.firebase.google.com 에 구글 계정으로 들어갑니다.
2. **프로젝트 추가** → 이름(예: `chartgap`) → Google 애널리틱스는 꺼도 됩니다 → **프로젝트 만들기**.

## 2. 구글 로그인 켜기
1. 왼쪽 메뉴 **빌드 → Authentication** → **시작하기**.
2. **로그인 방법** 탭 → **Google** → **사용 설정** 켜기 → 지원 이메일 고르기 → **저장**.
3. **설정** 탭 → **승인된 도메인** → **도메인 추가** → `pswego.github.io` 입력 → 추가.

## 3. 계정 저장소 만들기
1. 왼쪽 메뉴 **빌드 → Firestore Database** → **데이터베이스 만들기**.
2. 위치는 `asia-northeast3 (서울)` → **프로덕션 모드로 시작** → 만들기.
3. **규칙** 탭을 열고, 저장소의 `firestore.rules` 내용을 그대로 붙여 넣은 뒤 **게시**.
   (닉네임 중복을 막고, 각자 자기 기록만 고칠 수 있게 하는 규칙이에요.)

## 4. 웹 앱 설정값 복사
1. 왼쪽 위 톱니바퀴 → **프로젝트 설정** → 아래쪽 **내 앱** → 웹 아이콘(`</>`) → 앱 이름 입력 → **앱 등록**.
2. 화면에 나오는 `const firebaseConfig = { apiKey: ..., authDomain: ..., projectId: ..., ... }` 부분을 복사합니다.
   이 값들은 공개돼도 되는 값이에요 (접근은 3번의 규칙과 2번의 도메인 목록이 막습니다).

## 5. 게임에 넣기
`tools/firebase_config.js` 의 `null` 을 복사한 값으로 바꿉니다:

```js
window.CHARTGAP_FIREBASE = {
  apiKey: "...",
  authDomain: "chartgap-xxxx.firebaseapp.com",
  projectId: "chartgap-xxxx",
  storageBucket: "...",
  messagingSenderId: "...",
  appId: "..."
};
```

그리고 다시 만들어서 올립니다:

```bash
cd backend && .venv/bin/chartgame standalone --site && cp ../site/index.html ../index.html
git add -A && git commit -m "Firebase 설정" && git push
```

## 동작 방식
- 처음 구글로 로그인하면 **계정 만들기** 화면에서 닉네임을 정합니다. 겹치는 닉네임은 쓸 수 없어요.
- 점수·승패는 계정에 저장돼 어느 기기에서든 이어집니다. 상단바의 내 이름을 누르면 닉네임 바꾸기·로그아웃.
- 게스트는 `게스트-K3F9` 처럼 브라우저마다 다른 이름이 자동으로 붙고 바꿀 수 없어요. 목록에 `게스트` 표시가 붙습니다.
- 한계: 대전 화면의 이름표는 각자 기기가 보내는 값이라, 기술적으로 다른 사람 이름을 흉내 낼 수는 있어요(표시용).
  계정 기록(Firestore)은 규칙 때문에 본인만 고칠 수 있습니다.
