# 배포하기 (온라인 대전용 서버)

온라인 대전은 서버의 WebSocket 방(`/ws/room/<이름>`)으로 동작합니다. 서버 하나만 인터넷에 띄우면
링크를 받은 누구나(로그인 없이) 같은 방에서 대전할 수 있어요.

- 게임 페이지: `/` (또는 `/game`) — 공부하기·자동 해설·그리기·온라인 대전 포함, 실제 문제 300개 수록
- 상태 확인: `/api/health`
- 서버는 방 정보를 저장하지 않습니다. 재시작하면 진행 중인 방은 사라져요.

## Render (무료, 가장 간단)

1. https://render.com 에 GitHub 계정으로 가입합니다.
2. **New → Blueprint** 를 누르고 이 저장소(`pswego/trading_predict`)를 고릅니다.
   - 브랜치는 이 작업이 들어 있는 브랜치를 고르세요 (main 에 합친 뒤라면 main).
3. 저장소의 `render.yaml` 을 읽어서 서버 하나(`chartgap`)를 만들어 줍니다. **Apply** 를 누르세요.
4. 빌드가 끝나면(5~10분) `https://chartgap-xxxx.onrender.com` 같은 주소가 생깁니다. 이 주소를 친구에게 보내면 끝이에요.

무료 플랜은 15분 동안 접속이 없으면 잠들고, 다음 접속 때 깨어나는 데 30초~1분 걸려요.
대전 중에는 계속 연결돼 있어서 잠들지 않습니다.

## Fly.io

```bash
fly launch --no-deploy        # 저장소 루트에서. Dockerfile 을 자동으로 찾는다
fly secrets set CHARTGAME_SECRET=$(openssl rand -hex 16)
fly deploy
```

## 내 컴퓨터에서 친구와 해 보기

```bash
cd backend && .venv/bin/uvicorn chartgame.api.main:app --host 0.0.0.0 --port 8000
```
같은 와이파이에 있는 친구는 `http://<내 컴퓨터 IP>:8000/game` 으로 들어오면 됩니다.

## 게임 문제를 새로 만들었을 때

```bash
cd backend && .venv/bin/chartgame standalone   # chartgame/static/game.html 을 다시 만든다
```
만든 파일을 커밋해서 푸시하면 Render 가 자동으로 다시 배포합니다.
