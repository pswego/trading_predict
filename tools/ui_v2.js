/* ================= 화면 v2: 끄투풍 레퍼런스 배치 =================
   여기서 정의하는 함수(home, render, result, battleLobby, battleRoom, battleResultView, study, battleForm)는
   위쪽의 같은 이름 함수를 덮어쓴다. 게임 규칙·채점·대전 진행 로직은 위쪽 코드를 그대로 쓴다.
   데스크톱(900px 이상)은 레퍼런스처럼 여러 패널을 나란히, 그보다 좁으면 한 줄로 쌓는다. */

/* ---- 공통 조각 ---- */
const MODE_LABEL={choice4:["4지선다","#3E78C2"],ox:["O/X","#D9534F"],draw:["그리기","#3E9B6E"]};
const AV_COLORS=["#3E8DCB","#C2563A","#3E9B6E","#B07A3A","#7A4FB8","#3EA86B","#D9534F","#2F8F9D"];
const hashStr=s=>{let h=0;for(const c of String(s))h=(h*31+c.charCodeAt(0))|0;return Math.abs(h)};
const avColor=n=>AV_COLORS[hashStr(n)%AV_COLORS.length];
const avText=n=>{n=String(n||"?");return /^[0-9]/.test(n)?n.slice(0,2):n.slice(0,1).toUpperCase()};
function lvColor(lv){return lv>=15?"#7A4FB8":lv>=10?"#C2563A":lv>=6?"#3E8DCB":lv>=3?"#3EA86B":"#8A97A3"}
const lvBadge=lv=>`<span class="lv" style="background:${lvColor(lv)}">${clampInt(lv,1,99,1)}</span>`;
const avatar=(n,size=46)=>`<span class="avx" aria-hidden="true" style="width:${size}px;height:${size}px;font-size:${Math.round(size*.46)}px;border-radius:${Math.round(size*.28)}px;background:${avColor(n)}">${esc(avText(n))}</span>`;
const modeTag=t=>{const m=MODE_LABEL[t]||["?","#8A97A3"];return `<span class="mtag" style="background:${m[1]}">${m[0]}</span>`};
const panel=(title,body,{color="",right="",cls="",style=""}={})=>`<section class="pn2 ${cls}" style="${style}"><div class="ph ${color}"><span>${title}</span>${right?`<small>${right}</small>`:""}</div>${body}</section>`;

/* ---- 내 정보 (이 브라우저에만 저장) ---- */
function loadProfile(){try{return Object.assign({total:0,wins:0,losses:0,games:0},JSON.parse(localStorage.getItem("cg_profile")||"{}"))}catch(e){return {total:0,wins:0,losses:0,games:0}}}
function saveProfile(p){try{localStorage.setItem("cg_profile",JSON.stringify(p))}catch(e){}}
function levelOf(total){const lv=Math.floor(Math.sqrt(Math.max(0,total)/300))+1,cur=300*(lv-1)**2,nxt=300*lv**2;return {lv,pct:Math.round((total-cur)/(nxt-cur)*100)}}
const myLevel=()=>levelOf(loadProfile().total).lv;
if(!cleanNick(nick)){nick="손님"+String(1000+Math.floor(Math.random()*9000));try{localStorage.setItem("cg_nick",nick)}catch(e){}}

/* ---- 채팅: 각자 presence 의 chat 에 최근 메시지를 두고, 모두의 것을 시간순으로 합쳐 보여 준다 ---- */
const CH={mine:{lobby:[],room:[]},sys:{lobby:[],room:[]},known:{lobby:new Map(),room:new Map()},last:0,t0:Date.now()};
function chatPeers(where){const src=where=="room"?B.peers:B.lobby;return (src||[]).filter(p=>p.kind=="viewer"&&p.presence&&p.presence.nick)}
function trackJoins(where){
  const now=Date.now(),seen=new Map();for(const p of chatPeers(where))seen.set(p.peer,cleanNick(p.presence.nick));
  const k=CH.known[where];if((k.size||where=="room")&&now-CH.t0>4000){for(const [peer,n] of seen)if(!k.has(peer)&&!(chatPeers(where).find(x=>x.peer==peer)||{}).sameTab)CH.sys[where].push({t:now,s:`${n}님이 입장했습니다.`});
    for(const [peer,n] of k)if(!seen.has(peer))CH.sys[where].push({t:now,s:`${n}님이 나갔습니다.`})}
  CH.known[where]=seen;CH.sys[where]=CH.sys[where].slice(-20);
}
function chatLines(where){
  const out=[...CH.sys[where].map(x=>({t:x.t,sys:x.s}))];
  for(const p of chatPeers(where)){const arr=Array.isArray(p.presence.chat)?p.presence.chat:[];for(const m of arr.slice(-10)){if(!m||typeof m.m!="string")continue;out.push({t:Number(m.t)||0,n:cleanNick(p.presence.nick),me:p.sameTab,m:String(m.m).slice(0,120),id:m.i})}}
  const ids=new Set();return out.filter(x=>!x.id||(!ids.has(x.id)&&ids.add(x.id))).sort((a,b)=>a.t-b.t).slice(-40);
}
function chatHtml(where){const lines=chatLines(where);
  return lines.length?lines.map(l=>l.sys?`<div class="cl sys">${esc(l.sys)}</div>`:`<div class="cl"><b style="color:${avColor(l.n)}">${esc(l.n)}</b> : ${esc(l.m)}</div>`).join(""):`<div class="cl sys">아직 대화가 없어요. 먼저 인사해 보세요.</div>`}
function chatPanel(where,title){
  const can=where=="room"?!!B.mroom:!!B.room;
  return panel(title,`<div class="chatlog" id="chatlog-${where}">${can?chatHtml(where):`<div class="cl sys">채팅은 온라인에 연결돼 있을 때만 쓸 수 있어요.</div>`}</div>
    <form class="chatin" onsubmit="event.preventDefault();sendChat('${where}')"><label for="chat-${where}" class="sr">채팅 입력</label><input id="chat-${where}" maxlength="80" autocomplete="off" placeholder="메시지를 입력하세요" ${can?"":"disabled"}><button class="btn2" ${can?"":"disabled"}>전송</button></form>`,{color:"green",cls:"grow"});
}
function sendChat(where){
  const el=$("#chat-"+where),m=String(el&&el.value||"").replace(/[\u0000-\u001f]/g,"").trim().slice(0,80);if(!m)return;
  if(Date.now()-CH.last<700)return;CH.last=Date.now();
  const arr=CH.mine[where];arr.push({i:Math.random().toString(36).slice(2,9),t:Date.now(),m});CH.mine[where]=arr.slice(-8);
  const r=where=="room"?B.mroom:B.room;if(r)r.presence({chat:CH.mine[where]}).catch(()=>{});
  el.value="";refreshChat(where);el.focus();
}
function refreshChat(where){const box=$("#chatlog-"+where);if(!box)return;const atEnd=box.scrollHeight-box.scrollTop-box.clientHeight<40;box.innerHTML=chatHtml(where);if(atEnd)box.scrollTop=box.scrollHeight}
function scrollChats(){document.querySelectorAll(".chatlog").forEach(b=>b.scrollTop=b.scrollHeight)}

/* ---- 상단바 ---- */
function setBar(right,active){
  const bar=$(".appbar");if(!bar)return;
  const tabs=[["lobby","로비","home()"],["study","차트 공부","study()"]];
  const P=loadProfile(),L2=levelOf(P.total);
  bar.innerHTML=`<span class="logo" role="link" tabindex="0" onclick="home()" onkeydown="if(event.key=='Enter')home()">빈칸<span>차트</span></span>
  ${active?`<nav class="tabs2">${tabs.map(([k,l,f])=>`<a href="#${k}" class="${k==active?"on":""}" onclick="event.preventDefault();${f}">${l}</a>`).join("")}</nav>`:""}
  <span class="sp"></span>${right!=null?right:`<span class="me">${lvBadge(L2.lv)}<b>${esc(nick)}</b><em>${P.total.toLocaleString()} P</em></span>`}`;
}
let lastLobbyP="";function setLobbyPresence(st){const v={nick:cleanNick(nick),st,lv:myLevel()},k=JSON.stringify(v);if(!B.room||k===lastLobbyP)return;lastLobbyP=k;B.room.presence(v).catch(()=>{})}
function screen(cls,html){app.className="scr "+cls;app.innerHTML=html;scrollChats()}

/* ---- 로비 (첫 화면) ---- */
function home(){
  if(B.mroom&&!B.keep)battleLeave();
  S=null;clearInterval(timer);B.view="lobby";setBar(null,"lobby");setLobbyPresence("로비");trackJoins("lobby");
  const P=loadProfile(),L2=levelOf(P.total);
  const pool=Q.filter(q=>q.iv==cfg.iv&&q.d==cfg.diff),left=pool.filter(q=>!seen.has(key(q))).length;
  const seg=(k,opts)=>`<div class="seg2">${opts.map(([v,t])=>`<button class="${cfg[k]==v?"on":""}" onclick="cfg.${k}='${v}';save();home()">${t}</button>`).join("")}</div>`;
  const users=chatPeers("lobby").map(p=>({n:cleanNick(p.presence.nick),st:String(p.presence.st||"로비").slice(0,4),lv:clampInt(p.presence.lv,1,99,1),me:p.sameTab}));
  if(!users.some(u=>u.me))users.unshift({n:nick,st:"로비",lv:L2.lv,me:true});
  const rooms=(B.lobby||[]).filter(p=>!p.isMe&&p.presence&&p.presence.hosting&&p.presence.hosting.pub!==false&&Math.abs(Date.now()-(Number(p.presence.hosting.ts)||0))<90000).map(p=>p.presence.hosting).slice(0,40);
  const online=!!B.room;
  screen("lobby",`
  ${panel(`접속자 <span class="num">${online?users.length:"-"}</span>`,`<div class="ulist">${online?users.map(u=>`<div class="urow${u.me?" me":""}">${lvBadge(u.lv)}<span class="sp">${esc(u.n)}</span><span class="ust">${esc(u.st)}</span></div>`).join(""):`<div class="cl sys" style="padding:10px">온라인에 연결하지 못했어요.</div>`}</div>`,{cls:"users"})}
  <div class="col mid">
    ${panel("방 목록",`<div class="tblwrap"><table class="rooms"><thead><tr><th style="width:34px">#</th><th style="width:76px">모드</th><th>방 제목</th><th>규칙</th><th style="width:60px">코드</th><th style="width:56px">인원</th><th style="width:64px">상태</th></tr></thead><tbody>
      ${rooms.length?rooms.map((h,i)=>{const code=String(h.code||"").replace(/[^A-Z0-9]/g,"").slice(0,4),n=clampInt(h.n,0,50,1),max=clampInt(h.max,2,50,8),playing=h.status=="playing";
        return `<tr tabindex="0" onclick="battlePick('${code}',${h.lock?1:0})" onkeydown="if(event.key=='Enter')battlePick('${code}',${h.lock?1:0})"><td class="num muted">${i+1}</td><td>${modeTag(h.cfg&&h.cfg.type)}</td><td class="b">${esc(cleanTitle(h.title)||(cleanNick(h.nick)||"익명")+"의 방")}${h.lock?` <span class="lock">[비번]</span>`:""}</td><td>${esc(L[h.cfg&&h.cfg.diff]||"")} · ${esc(L[h.cfg&&h.cfg.iv]||"")}</td><td class="num">${esc(code)}</td><td class="num">${n}/${max}</td><td><span class="stag ${playing?"play":n>=max?"full":""}">${playing?"게임중":n>=max?"가득":"대기"}</span></td></tr>`}).join("")
       :`<tr><td colspan="7" class="empty">${online?"지금 열린 방이 없어요. 방을 만들고 친구에게 코드를 알려 주세요.":"온라인에 연결하지 못했어요. 새로고침해 주세요."}</td></tr>`}
      </tbody></table></div>`,{right:`<span class="phbtns"><button class="btn2 sm" onclick="openJoin()" ${online?"":"disabled"}>코드로 입장</button><button class="btn2 sm blue" onclick="battleForm()" ${online?"":"disabled"}>방 만들기</button></span>`,cls:"grow rooms-p"})}
    ${chatPanel("lobby","로비 채팅")}
  </div>
  <div class="col side">
    ${panel("내 정보",`<div class="mine">${avatar(nick,56)}<div class="sp"><div class="row" style="gap:6px">${lvBadge(L2.lv)}<label for="nick" class="sr">닉네임</label><input id="nick" class="nickin" maxlength="12" value="${esc(nick)}" onchange="nick=cleanNick(this.value)||nick;this.value=nick;try{localStorage.setItem('cg_nick',nick)}catch(e){};setLobbyPresence('로비');home()"></div>
      <div class="expbar"><i style="width:${L2.pct}%"></i></div><div class="row xs muted" style="justify-content:space-between"><span>경험치 ${L2.pct}%</span><span class="num">${P.wins}승 ${P.losses}패</span></div></div></div>`)}
    ${panel("혼자 하기",`<div class="solo"><div class="fl"><span>문제 방식</span>${seg("type",[["choice4","4지선다"],["ox","O / X"],["draw","그리기"]])}</div>
      <div class="fl"><span>난이도</span>${seg("diff",[["easy","쉬움"],["normal","보통"],["hard","어려움"]])}</div>
      <div class="fl"><span>차트 단위</span>${seg("iv",[["day","일봉"],["week","주봉"]])}</div>
      <div class="remain"><span>이 조건 남은 문제</span><span class="num"><b>${left}</b> / ${pool.length}</span></div>
      <div class="sp"></div><button class="cta" onclick="start()">10문제 시작</button>
      <p class="xs muted" style="margin:8px 0 0;text-align:center">과거 데이터 기반 오락용 · 투자 권유 아님 · 가격 출처 네이버 금융 · <button class="linkbtn" onclick="seen.clear();save();home()">푼 문제 기록 지우기</button></p></div>`,{cls:"grow"})}
  </div>`);
  if(B.lobbyMsg||(B.pending&&B.pending.lock&&!$(".modal")))openJoin(B.lobbyMsg);
}
function battleLobby(msg){
  if(msg===undefined){const a=document.activeElement;if(B.view=="lobby"&&a&&(a.id=="chat-lobby"||a.id=="nick"||a.closest&&a.closest(".modal"))){refreshChat("lobby");return}}
  else B.lobbyMsg=msg;
  home();if(msg&&!$(".modal"))openJoin(msg);
}
function openJoin(msg){
  document.querySelectorAll(".modal").forEach(m=>m.remove());
  const pend=B.pending;const el=document.createElement("div");el.className="modal";el.onclick=e=>{if(e.target===el){el.remove();B.lobbyMsg="";B.pending=null}};
  el.innerHTML=`<div class="sheet pn2"><div class="ph"><span>코드로 입장</span><small><button class="x" onclick="this.closest('.modal').remove();B.lobbyMsg='';B.pending=null" aria-label="닫기">✕</button></small></div><div style="padding:12px;display:grid;gap:8px">
    <label class="xs b muted" for="code">방 코드</label><input id="code" class="inp" maxlength="4" placeholder="4자리 코드" style="text-transform:uppercase" value="${esc(pend?pend.code:"")}" onkeydown="if(event.key=='Enter')battleJoin()">
    <label class="xs b muted" for="pw">비밀번호 <span style="font-weight:400">(걸린 방만)</span></label><input id="pw" class="inp" type="password" maxlength="12" placeholder="없으면 비워 두세요" onkeydown="if(event.key=='Enter')battleJoin()">
    <p id="bmsg" class="xs" style="color:#C0461A;margin:0;min-height:16px">${esc(msg||"")}</p><button class="cta" onclick="battleJoin()">입장</button></div></div>`;
  document.body.appendChild(el);setTimeout(()=>{const f=pend&&pend.lock?$("#pw"):$("#code");f&&f.focus()},30);
}
function battlePick(code,lock){B.lobbyMsg="";B.pending={code,lock:!!lock};if(!lock){openJoin();$("#code").value=code;battleJoin()}else{openJoin();$("#code").value=code;$("#pw").focus()}}
// 입장 성공·실패 뒤 열린 입력 창 정리
const _battleEnter=battleEnter;
battleEnter=async function(code,host,settings,pw){await _battleEnter(code,host,settings,pw);if(B.mroom){document.querySelectorAll(".modal").forEach(m=>m.remove());B.mroom.presence({lv:myLevel()}).catch(()=>{})}};
// 로비가 바뀌면(접속자·방 목록·채팅) 다시 그린다. 입력 중이면 채팅만 갱신
if(typeof roomP!=="undefined")roomP.then(r=>{if(!r)return;r.onPeers(()=>trackJoins("lobby"));if(B.view=="lobby")home()});

/* ---- 방 만들기 / 설정 ---- */
const _battleForm=battleForm;
battleForm=function(editing,keep){
  _battleForm(editing,keep);
  setBar(B.mroom?roomBarRight():null,B.mroom?null:"lobby");
  const backBtn=app.querySelector(".row");const formCard=$("#bform");if(!formCard)return;
  const foot=formCard.parentElement.querySelectorAll(":scope > div, :scope > p");
  const html=`<section class="pn2 formp"><div class="ph orange"><span>${editing?"방 설정 바꾸기":"방 만들기"}</span><small><button class="x" onclick="${editing?"battleRoom()":"home()"}" aria-label="닫기">✕</button></small></div>${formCard.outerHTML.replace('class="card"','class="formbody"')}${[...foot].filter(x=>x!==formCard&&x!==backBtn).map(x=>x.outerHTML).join("")}</section>`;
  screen("form",html);
};

/* ---- 대전방 ---- */
function roomBarRight(){const g=B.host?B.game:(hostGame()||B.game);return `<span class="me"><span class="chip num">#${esc(B.code||"")}</span><b>${esc(g&&g.title||"대전방")}</b>${window.__relay?`<em class="ok">● 중계 서버 ${window.__relay()}</em>`:""}</span>`}
function battleRoom(){
  B.view="room";S=null;clearInterval(timer);trackJoins("room");setBar(roomBarRight());setLobbyPresence("대전");
  const ps=players().sort((a,b)=>a.joined-b.joined),g=B.host?B.game:(hostGame()||B.game),n=ps.length,max=g?clampInt(g.max,2,50,8):8,allReady=ps.filter(p=>!p.host).every(p=>p.ready);
  const slots=Math.max(8,Math.min(max,Math.ceil(n/4)*4||8));
  const lvOf=p=>{const raw=B.peers.find(x=>x.peer===p.peer);return raw&&raw.presence?clampInt(raw.presence.lv,1,99,1):1};
  const slot=i=>{const p=ps[i];if(!p)return i<max?`<div class="slot empty">빈 자리</div>`:`<div class="slot closed">닫힘</div>`;
    return `<div class="slot${p.host?" host":""}${p.me?" me":""}"><div class="sh"><span>${p.host?"방장":"참가자"}</span><span class="${p.host||p.ready?"ok":"wait"}">${p.host?"준비":p.ready?"준비":"대기"}</span></div>
      <div class="sbody">${avatar(p.nick,64)}<div class="row" style="gap:5px;justify-content:center">${lvBadge(lvOf(p))}<b class="snick">${esc(p.nick)}</b></div>${B.host&&!p.me?`<button class="kick" onclick="battleKickAsk('${esc(p.peer).replace(/[^A-Za-z0-9_-]/g,"")}')" aria-label="${esc(p.nick)} 내보내기">내보내기</button>`:""}</div></div>`};
  const info=[["방 코드",`<b class="num" style="font-size:15px;letter-spacing:3px">${esc(B.code)}</b>`],["모드",modeTag(g&&g.cfg&&g.cfg.type)],["난이도",esc(L[g&&g.cfg&&g.cfg.diff]||"")],["차트",esc(L[g&&g.cfg&&g.cfg.iv]||"")],["문제 수",g?`${g.n}문제`:""],["제한 시간",g?`문제당 ${g.sec}초 · 공개 ${g.reveal}초`:""],["입장",g&&g.pwh?"비밀번호":"누구나"],["방 목록",g&&g.pub===false?"숨김 (코드로만)":"보이기"]];
  screen("room",`<div class="col mid">
    ${panel(`대기실 <span class="num">${n} / ${max}</span>`,`<div class="slots">${Array.from({length:slots},(_,i)=>slot(i)).join("")}</div>${B.hostGone?`<p class="warn">방장이 나갔어요. 다른 방에 참가해 주세요.</p>`:""}`,{right:"서로 안 보이면 두 기기 모두 새로고침",cls:"grow"})}
    <section class="pn2 actions">${B.host?`<button class="cta" ${n<2||!allReady?"disabled":""} onclick="battleStart()">${n<2?"상대를 기다리는 중":!allReady?`모두 준비하면 시작 (${ps.filter(p=>!p.host&&p.ready).length}/${n-1})`:"대전 시작"}</button>`:`<button class="cta" onclick="toggleReady()">${B.ready?"준비 취소":"준비"}</button>`}
      ${B.host?`<button class="btn2 big" onclick="battleForm(true)">방 설정</button>`:""}<button class="btn2 big" onclick="copyCode()">코드 복사</button><button class="btn2 big danger" onclick="battleLeave();home()">나가기</button></section><p id="cmsg" class="xs" style="color:#fff;margin:0 4px;min-height:14px"></p>
  </div><div class="col side">
    ${panel("방 정보",`<div class="itbl">${info.map(([k,v])=>`<div><span>${k}</span><span>${v}</span></div>`).join("")}</div>`,{color:"dark"})}
    ${chatPanel("room","방 채팅")}
  </div>`);
}
// 대전방 사람 목록이 바뀌면 채팅 입장 알림도 갱신
const _onBattlePeers=onBattlePeers;
onBattlePeers=function(){trackJoins("room");const a=document.activeElement;if(a&&a.id=="chat-room"&&B.view=="room"){refreshChat("room");return}_onBattlePeers();if(B.view==null&&S&&S.battle)refreshChat("room")};

/* ---- 게임 화면 ---- */
function playerCards(){
  const ps=roundPlayers().sort((a,b)=>b.score-a.score),qi=S.i;
  const lvOf=p=>{const raw=B.peers.find(x=>x.peer===p.peer);return raw&&raw.presence?clampInt(raw.presence.lv,1,99,1):1};
  return `<div class="pcards" id="bstrip">${ps.map((p,i)=>{const done=p.res.length>qi&&p.res[qi]!="-";return `<div class="pcard${p.me?" me":""}"><div class="sh"><span class="row" style="gap:4px">${lvBadge(lvOf(p))}<b>${esc(p.nick)}</b></span><span class="${done?"ok":"wait"}">${done?"제출":"푸는 중"}</span></div><div class="pc-b">${avatar(p.nick,40)}<span class="num xs muted">${i+1}위</span><span class="pscore">${p.score.toLocaleString()}</span></div></div>`}).join("")}</div>`;
}
function rankList(){return `<div class="ulist" id="bstrip">${roundPlayers().sort((a,b)=>b.score-a.score).map((x,i)=>{const c=x.res[S.i];return `<div class="urow${x.me?" me":""}"><span class="num muted" style="width:16px">${i+1}</span>${avatar(x.nick,22)}<span class="sp">${esc(x.nick)}</span><span class="num" style="width:44px;text-align:right;color:${c=="1"?"var(--good)":c=="0"?"var(--bad)":"#8A97A3"}">${c=="1"?"정답":c=="0"?"오답":"…"}</span><b class="num" style="width:48px;text-align:right">${x.score.toLocaleString()}</b></div>`}).join("")}</div>`}
battleStrip=function(){return S&&S.done?rankList():playerCards()};
function render(){
  const q=S.q,p=q.p,o=p.options,ox=cfg.type=="ox",draw=cfg.type=="draw",ov=p.option_volume,n=S.list.length;
  if(S.done)return renderReveal();
  let fill=null,fillVol=null;
  if(ox){fill=o[S.ox];fillVol=ov&&ov[S.ox]}else if(!draw&&S.sel!=null){fill=o[S.order[S.sel]];fillVol=ov&&ov[S.order[S.sel]]}
  // 데스크톱: 차트·보기·도구·막대·플레이어 카드가 한 화면에 들어가도록 차트 높이를 맞춘다
  const wide=innerWidth>=900,cw=Math.min(innerWidth,1440)-300-16-8-26-2;
  const thumbPx=draw||ox?0:Math.round(Math.min(110,innerHeight*.13)),fixed=46+16+38+20+54+66+(S.battle?118:0)+(thumbPx?thumbPx+40:0)+24;
  const chartPx=Math.max(220,Math.min(520,innerHeight-fixed));
  const mh=wide?Math.round(chartPx*720/cw):undefined,th=wide?Math.round(thumbPx*220/((cw-24)/4)):96;
  S.mh=mh;
  setBar(`<span class="me"><span class="xs" style="color:#D3E2F0">내 점수</span><b class="bigscore">${S.score.toLocaleString()}</b>${S.battle?`<span class="xs" style="color:#D3E2F0">· ${roundPlayers().sort((a,b)=>b.score-a.score).findIndex(x=>x.me)+1}위</span>`:""}${S.streak>=2?`<em>연속 ${S.streak}</em>`:""}</span>`);
  const head=`문제 <span class="num">${S.i+1} / ${n}</span> · 종목명 비공개`;
  const sub=`${(MODE_LABEL[cfg.type]||[""])[0]} · ${L[q.d]} · ${L[q.iv]} · ${L[q.m]} ${L[q.t]}`;
  let tools="";
  if(draw)tools=`<div class="toolbar"><button class="btn2" onclick="S.drawn=[];render()" ${S.drawn.length?"":"disabled"}>다시 그리기</button><span class="sp hint">빗금 구간에 이어질 흐름을 그리세요 · 일치도 ${DRAW_PASS[q.d]}% 미만은 0점</span><button class="cta sm" onclick="answer('draw')" ${drawCoverage(S.drawn,p.layout.G)<.6?"disabled":""}>제출</button></div>`;
  else if(ox)tools=`<div class="toolbar"><span class="sp hint">빈칸에 들어간 이 모양, 실제 차트일까요?</span><button class="oxb o" onclick="answer('O')" aria-label="O, 실제다">O</button><button class="oxb x" onclick="answer('X')" aria-label="X, 가짜다">X</button></div>`;
  else tools=`<div class="opts4">${S.order.map((k,i)=>`<button class="opt2${S.sel===i?" sel":""}" onclick="pick(${i})" aria-label="보기 ${i+1}"><span class="on2">${i+1}</span>${chart(p,o[k],{thumb:true,range:o,id:i,th})}</button>`).join("")}</div>
    <div class="toolbar"><span class="sp hint">${S.sel==null?"빈칸에 실제로 들어간 모양을 고르세요 (키보드 1~4)":`${S.sel+1}번을 골랐어요. 한 번 더 누르거나 확정하세요`}</span><button class="cta sm" onclick="answer(S.sel)" ${S.sel==null?"disabled":""}>${S.sel==null?"보기 선택":"확정"}</button></div>`;
  const timerP=`<section class="pn2 bars">${S.lim?`<div class="barrow"><span>제한 시간</span><div class="tbar"><i id="tb" style="width:100%"></i></div><span class="num" id="tsec">${Math.round(S.lim/1000)}초</span></div>`:""}<div class="barrow"><span>전체 진행</span><div class="tbar"><i style="width:${Math.round(S.i/n*100)}%;background:#4A86C2"></i></div><span class="num">${S.i+1} / ${n}</span></div></section>`;
  const sideSolo=panel("문제 정보",`<div class="itbl">${[["시장",L[q.m]],["규모",`당시 ${L[q.t]}`],["차트",L[q.iv]],["난이도",L[q.d]],["방식",(MODE_LABEL[cfg.type]||[""])[0]]].map(([k,v])=>`<div><span>${k}</span><span>${esc(v)}</span></div>`).join("")}</div>`,{color:"dark"})+
    panel("이번 판",`<div class="dots2">${Array.from({length:n},(_,i)=>`<i class="${i<S.res.length?(S.res[i].ok?"ok":"no"):i==S.i?"cur":""}"></i>`).join("")}</div><div class="itbl"><div><span>점수</span><span class="num b">${S.score.toLocaleString()}</span></div><div><span>정답</span><span class="num">${S.res.filter(r=>r.ok).length} / ${S.res.length}</span></div><div><span>연속 정답</span><span class="num">${S.streak}</span></div></div>`,{color:"orange"})+
    `<button class="btn2 big danger" style="width:100%" onclick="home()">그만하기</button>`;
  screen("game",`<div class="col mid">
    <section class="pn2 chartp"><div class="ph"><span>${head}</span><small>${esc(sub)}</small></div><div class="main">${chart(p,fill,{range:ox?[o[0],o[S.ox]]:o,id:9,mh,draw,drawn:S.drawn,geo:draw,fillVol,volume:p.volume})}</div>${tools}</section>
    ${timerP}${S.battle?playerCards():""}
  </div><div class="col side">${S.battle?chatPanel("room","게임 채팅")+`<button class="btn2 big danger" style="width:100%" onclick="battleLeave();home()">나가기</button>`:sideSolo}</div>`);
  if(draw)bindDraw();
}
// 타이머 표시에 초 숫자도
const _next=next;next=function(){_next();const tick=setInterval(()=>{if(!S||S.done||!$("#tsec")){clearInterval(tick);return}$("#tsec").textContent=Math.max(0,(S.lim-(performance.now()-S.t0))/1000).toFixed(1)+"초"},100)};

/* ---- 정답 공개 화면 ---- */
function renderReveal(){
  const q=S.q,p=q.p,o=p.options,r=q.r,ox=cfg.type=="ox",draw=cfg.type=="draw",ov=p.option_volume,n=S.list.length;
  let ghost=null;if(ox&&S.ox!==0)ghost=o[S.ox];if(!ox&&!draw&&S.ans!=null&&S.order[S.ans]!==0)ghost=o[S.order[S.ans]];
  const wide=innerWidth>=900,cw=Math.min(innerWidth,1440)-380-16-8-26-2,chartPx=Math.max(220,Math.min(480,innerHeight-46-16-38-36-56-(!ox&&!draw?150:0)-30));
  const mh=wide?Math.round(chartPx*720/cw):undefined;
  setBar(`<span class="me"><span class="xs" style="color:#D3E2F0">문제 ${S.i+1} / ${n} · 정답 공개</span><b class="bigscore">${S.score.toLocaleString()}</b></span>`);
  const pc=v=>`<span class="num ${v>0?"up":v<0?"dn":""}">${v>0?"+":""}${v.toFixed(1)}%</span>`;
  const verdict=draw?(S.acc>=85?"거의 똑같아요":S.ok?"잘 그렸어요":"아쉬워요"):S.ok?"정답!":S.ans==null?"시간 초과":"아쉬워요";
  const grade=`<div class="grade"><div class="row" style="justify-content:space-between;align-items:baseline"><span class="vd ${S.ok?"good":"bad"}">${verdict}</span><span class="pts ${S.pts?"":"zero"}">+${S.pts}점</span></div>
    ${draw?`<div class="row xs muted" style="justify-content:space-between"><span>일치도 <b class="num" style="color:var(--ink)">${S.acc}%</b></span><span>통과 기준 ${DRAW_PASS[q.d]}%</span></div><div class="accbar"><i style="width:${S.acc}%;background:${S.ok?"var(--good)":"var(--bad)"}"></i><span style="left:${DRAW_PASS[q.d]}%"></span></div>`
     :ox?`<p class="xs muted" style="margin:0">${S.ox===0?"보여 드린 모양이 실제였어요.":"보여 드린 모양은 가짜였어요. 흐린 것이 가짜, 선명한 것이 실제예요."}</p>`
     :`<p class="xs muted" style="margin:0">${S.ans==null?"시간 안에 고르지 못했어요.":`내 선택 ${S.ans+1}번 · 정답 ${S.order.indexOf(0)+1}번${S.ok?"":" · 흐리게 겹친 것이 내가 고른 모양"}`}</p>`}</div>`;
  const legend=`<div class="legend">${draw?`<span><i class="lg-draw"></i>내가 그린 흐름</span>`:""}${ghost?`<span><i class="lg-ghost"></i>${ox?"보여 준 가짜":"내가 고른 모양"}</span>`:""}<span><i class="lg-gap"></i>빈칸 구간 (실제)</span></div>`;
  const optsRow=!ox&&!draw?`<div class="opts4 small">${S.order.map((k,i)=>{const isReal=k===0,isMine=S.ans===i;return `<div class="opt2 ${isReal?"real":isMine?"wrong":"dim"}"><span class="on2">${i+1}</span>${isReal?`<span class="otag good">실제</span>`:isMine?`<span class="otag bad">내 선택</span>`:""}${chart(p,o[k],{thumb:true,range:o,id:i,th:84})}${!isReal?`<div class="src">${esc(SRC[q.r.decoy_sources[k-1]]||"")}</div>`:""}</div>`}).join("")}</div>`:"";
  const items=analyze(q);
  const ex=items.map(it=>`<div class="exi"><div class="row" style="gap:6px"><span class="tg" style="background:${TAG[it.tag][1]}22;color:${TAG[it.tag][1]}">${TAG[it.tag][0]}</span>${it.n?PN(it.n):""}</div><div class="exr"><span>보이는 단서</span><span>${it.seen}</span></div><div class="exr"><span>그래서 빈칸은</span><span>${it.so}</span></div><div class="exr"><span>실제로는</span><span>${it.real}</span></div></div>`).join("");
  const rank=S.battle?panel("이번 문제 순위",rankList()):"";
  screen("reveal",`<div class="col mid">
    <section class="pn2 chartp"><div class="ph"><span>${esc(r.name)} <span class="num" style="font-size:13px;opacity:.85">${esc(r.code)}</span></span><small>당시 ${L[r.cap_tier_then]} · ${r.gap_start} ~ ${r.gap_end}</small></div>
      <div class="main">${chart(p,o[0],{ghost,range:ox?[o[0],o[S.ox]]:o,style:"real",fillVol:ov&&ov[0],id:9,mh,draw,drawn:S.drawn,geo:false})}</div>${legend}
      <div class="stat3"><div><span>빈칸 수익률</span>${pc(r.gap_return_pct)}</div><div><span>구간 최고</span>${pc(r.gap_max_pct)}</div><div><span>구간 최저</span>${pc(r.gap_min_pct)}</div></div>
      ${r.delisted?`<p class="xs muted" style="margin:0 12px 10px">이 종목은 ${r.delisted.date}에 상장폐지됐어요 (${esc(r.delisted.reason)}).</p>`:""}${optsRow}</section>
  </div><div class="col side wide">
    ${panel("채점",grade,{color:"orange"})}
    ${panel("해설",`<div class="exlist">${ex}<p class="xs muted" style="margin:6px 2px 0">패턴 이름을 누르면 설명이 떠요. 규칙으로 찾은 단서라 틀릴 수 있어요.</p></div>`,{right:"자동 분석",cls:"grow"})}
    ${rank}
    ${S.battle?`<div id="bwait">${battleWaitHtml()}</div>`:`<button class="cta" onclick="advance()">${S.i==n-1?"결과 보기":"다음 문제"}</button>`}
  </div>`);
}

/* ---- 최종 결과 (혼자) ---- */
function result(){
  const P=loadProfile();if(!S.counted&&!S.battle){S.counted=true;P.total+=S.score;P.games+=1;saveProfile(P)}
  const n=S.res.filter(r=>r.ok).length,msg=n>=9?"차트 고수!":n>=7?"감이 좋아요":n>=5?"나쁘지 않아요":"다음엔 더 잘할 거예요";
  setBar(null,"lobby");
  screen("fin",`<div class="col mid">${panel("문제별 결과",`<div class="tblwrap"><table class="rooms"><thead><tr><th style="width:40px">#</th><th style="width:56px">결과</th><th>종목</th><th>빈칸 기간</th><th style="width:76px">수익률</th><th style="width:60px">점수</th></tr></thead><tbody>
    ${S.res.map((r,i)=>`<tr><td class="num muted">${i+1}</td><td><span class="stag ${r.ok?"":"play"}">${r.ok?"정답":"오답"}</span></td><td class="b">${esc(r.q.r.name)}${r.acc!=null?` <span class="xs muted">일치도 ${r.acc}%</span>`:""}</td><td class="num xs">${r.q.r.gap_start} ~ ${r.q.r.gap_end}</td><td class="num ${r.q.r.gap_return_pct>0?"up":"dn"}">${r.q.r.gap_return_pct>0?"+":""}${r.q.r.gap_return_pct.toFixed(1)}%</td><td class="num b">${r.pts}</td></tr>`).join("")}</tbody></table></div>`,{cls:"grow"})}</div>
  <div class="col side">${panel("결과",`<div class="final"><div class="xs muted">${L[cfg.diff]} · ${(MODE_LABEL[cfg.type]||[""])[0]} · ${L[cfg.iv]}</div><div class="fscore">${S.score.toLocaleString()}</div><div class="b">${msg} · ${n} / ${S.res.length} 정답</div>
    <div class="marks2">${S.res.map(r=>`<i class="${r.ok?"ok":""}"></i>`).join("")}</div></div>`,{color:"orange"})}
    ${B.mroom?`<button class="cta" onclick="battleResultView()">대전 결과로</button>`:`<button class="cta" onclick="start()">한 판 더</button>`}
    <button class="btn2 big" onclick="copyRes('${S.res.map(r=>r.ok?"🟩":"🟥").join("")}',${n})">결과 복사</button>${B.mroom?"":`<button class="btn2 big" onclick="home()">로비로</button>`}<p id="note" class="xs" style="color:#fff;text-align:center;margin:0"></p></div>`);
}

/* ---- 대전 최종 결과 ---- */
const _battleFinish=battleFinish;
battleFinish=function(){
  if(S&&S.battle&&!S.counted){S.counted=true;const P=loadProfile();P.total+=S.score;P.games+=1;
    setTimeout(()=>{const ps=roundPlayers().sort((a,b)=>b.score-a.score);if(ps.length>1){if(ps[0]&&ps[0].me)P.wins+=1;else P.losses+=1}saveProfile(P)},2500)}
  _battleFinish();
};
function battleResultView(){
  B.view="result";clearInterval(timer);setBar(roomBarRight());
  const ps=roundPlayers().sort((a,b)=>b.score-a.score),me=ps.findIndex(p=>p.me),n=B.mine?B.mine.list.length:(B.game&&B.game.n)||10;
  const lvOf=p=>{const raw=B.peers.find(x=>x.peer===p.peer);return raw&&raw.presence?clampInt(raw.presence.lv,1,99,1):1};
  screen("fin",`<div class="col mid">${panel("최종 순위",`<div class="ulist">${ps.map((p,i)=>`<div class="urow big${p.me?" me":""}"><span class="rank${i<3?" r"+(i+1):""}">${i+1}</span>${avatar(p.nick,34)}${lvBadge(lvOf(p))}<b class="sp">${esc(p.nick)}${p.me?` <span class="xs" style="color:#C0461A">나</span>`:""}</b><span class="mini2">${Array.from({length:n},(_,k)=>`<i class="${p.res[k]=="1"?"ok":p.res[k]=="0"?"no":""}"></i>`).join("")}</span><b class="num" style="width:60px;text-align:right;font-size:16px">${p.score.toLocaleString()}</b>${B.host&&!p.me?`<button class="kick" onclick="battleKickAsk('${esc(p.peer).replace(/[^A-Za-z0-9_-]/g,"")}')">내보내기</button>`:""}</div>`).join("")}</div>`,{right:esc(gameInfo(B.game)),cls:"grow"})}</div>
  <div class="col side">${panel("내 결과",`<div class="final"><div class="fscore">${me==0?"우승!":me>0?`${me+1}위`:"-"}</div><div class="b">${ps.length}명 중 ${me+1}위 · ${(B.mine?B.mine.score:0).toLocaleString()}점</div></div>`,{color:"orange"})}
    ${B.host?`<button class="cta" onclick="battleRematch()">한 판 더 (같은 설정)</button><button class="btn2 big" onclick="battleBackToRoom()">대기실로 · 설정 바꾸기</button>`:`<section class="pn2" style="padding:12px;text-align:center" class="xs">방장이 '한 판 더'를 누르면 바로 시작해요.</section>`}
    ${B.mine?`<button class="btn2 big" onclick="result()">내 문제별 결과 보기</button>`:""}<button class="btn2 big danger" onclick="battleLeave();home()">방 나가기</button>
    ${chatPanel("room","방 채팅")}</div>`);
}

/* ---- 차트 공부 ---- */
function study(tab){
  if(tab)studyTab=tab;S=null;clearInterval(timer);B.view="study";setBar(null,"study");setLobbyPresence("공부");
  const L2=LESSONS[studyTab];
  screen("study",`${panel("목차",`<div class="toc">${Object.entries(LESSONS).map(([k,v])=>`<button class="${k==studyTab?"on":""}" onclick="study('${k}')">${v.t}<span class="num">${v.items.length}</span></button>`).join("")}</div>`,{color:"dark",cls:"tocp"})}
  <div class="col mid lessons">${L2.items.map(it=>`<section class="pn2 lesson2"><div class="ph"><span>${it.h}</span></div><div class="lb"><p>${it.p}</p>${it.fig?it.fig():""}${it.tip?`<div class="tip"><b>요령</b> ${it.tip}</div>`:""}</div></section>`).join("")}
  <button class="cta" onclick="home()">문제 풀러 가기</button></div>`);
  window.scrollTo(0,0);
}
addEventListener("resize",()=>{if(B.view=="lobby"||B.view=="room")return;});
