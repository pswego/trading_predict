/* ================= 운영(GM) 기능 =================
   Firestore 에 저장하고 모두가 실시간으로 받는다. 쓰기는 firestore.rules 가 운영자 이메일에게만 허락한다.
   - notices/current : 공지 {text, at, by}. 모든 화면 위 띠 + 로비 채팅 맨 위에 보인다.
   - warnings/{id}   : 경고 {to: 소문자 닉네임, nick, msg, at, by}. 받은 사람에게 확인 창이 뜬다.
   - mutes/{소문자 닉네임} : 채팅 금지 {nick, until, reason, at}. 금지 중엔 채팅을 보낼 수 없고, 다른 사람 화면에서도 숨긴다.
   운영 페이지는 상단바의 '운영' 탭(GM 에게만 보임)에서 연다. */
const ADM={notice:null,mutes:{},warnings:[],users:[],unsubW:null,subKey:"",subbed:false,lastNoticeAt:0};
const ackKey="cg_warn_ack";
function acked(){try{return new Set(JSON.parse(localStorage.getItem(ackKey)||"[]"))}catch(e){return new Set()}}
function ack(id){const s=acked();s.add(id);try{localStorage.setItem(ackKey,JSON.stringify([...s].slice(-200)))}catch(e){}}
const isMuted=n=>{const m=ADM.mutes[nickKey(n)];return !!(m&&Number(m.until)>Date.now())};
const fmtTime=t=>{const d=new Date(Number(t)||0);return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`};

function adminSubscribe(){
  if(!ACC.db)return;
  if(!ADM.subbed){ADM.subbed=true;
    ACC.db.doc("notices/current").onSnapshot(s=>{const d=s.exists?s.data():null;ADM.notice=d&&d.text?d:null;showNoticeBar();
      if(ADM.notice&&Number(ADM.notice.at)>ADM.lastNoticeAt&&ADM.lastNoticeAt)toast("새 공지: "+ADM.notice.text);ADM.lastNoticeAt=Math.max(ADM.lastNoticeAt,Number(ADM.notice&&ADM.notice.at)||1);
      if(B.view=="lobby")refreshChat("lobby");if(B.view=="admin")adminPage()},()=>{});
    ACC.db.collection("mutes").onSnapshot(q=>{const m={};q.forEach(d=>m[d.id]=d.data());ADM.mutes=m;if(B.view=="admin")adminPage();refreshChat("lobby");refreshChat("room")},()=>{});
  }
  // 나에게 온 경고: 닉네임이 바뀌면 다시 구독
  const k=nick?nickKey(nick):"";
  if(k&&k!==ADM.subKey){ADM.subKey=k;if(ADM.unsubW)ADM.unsubW();
    ADM.unsubW=ACC.db.collection("warnings").where("to","==",k).onSnapshot(q=>{const a=acked(),list=[];q.forEach(d=>{const w=d.data();if(!a.has(d.id))list.push({id:d.id,...w})});
      list.sort((x,y)=>x.at-y.at);if(list.length)showWarning(list[0])},()=>{})}
}
function showWarning(w){
  if(document.querySelector(".modal.warnm"))return;
  const el=document.createElement("div");el.className="modal warnm";
  el.innerHTML=`<div class="sheet pn2" role="alertdialog" aria-labelledby="wt"><div class="ph" style="background:#C92A2A"><span id="wt">운영자 경고</span></div><div style="padding:14px;display:grid;gap:10px">
    <p style="margin:0;font-size:15px;line-height:1.6;white-space:pre-wrap">${esc(String(w.msg||"").slice(0,300))}</p>
    <p class="xs muted" style="margin:0">${fmtTime(w.at)} · 이 경고는 운영자가 보냈어요. 같은 행동이 반복되면 채팅이 제한될 수 있어요.</p>
    <button class="cta" onclick="ack('${esc(w.id)}');this.closest('.modal').remove();adminSubscribe()">확인했어요</button></div></div>`;
  document.body.appendChild(el);
}
function toast(msg){const t=document.createElement("div");t.className="toast";t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),5000)}
function showNoticeBar(){
  let bar=$("#noticebar");
  if(!ADM.notice){if(bar)bar.remove();return}
  if(!bar){bar=document.createElement("div");bar.id="noticebar";$(".appbar").insertAdjacentElement("afterend",bar)}
  bar.innerHTML=`<b>공지</b><span>${esc(String(ADM.notice.text).slice(0,200))}</span>`;
}

/* ---- 채팅: 금지된 사람은 보내지 못하고, 다른 사람 화면에서도 숨긴다. 로비 채팅 맨 위에 공지 ---- */
const _chatLines=chatLines;
chatLines=function(where){
  const lines=_chatLines(where).filter(l=>l.sys||!isMuted(l.n));
  if(where=="lobby"&&ADM.notice)lines.unshift({t:0,sys:"[공지] "+String(ADM.notice.text).slice(0,200),notice:true});
  return lines;
};
const _sendChat=sendChat;
sendChat=function(where){if(isMuted(nick)){const m=ADM.mutes[nickKey(nick)];toast(`채팅이 제한된 상태예요 (${fmtTime(m.until)}까지)${m.reason?": "+m.reason:""}`);return}_sendChat(where)};
const _chatHtml=chatHtml;
chatHtml=function(where){return _chatHtml(where).replace(/<div class="cl sys">(\[공지\][^<]*)<\/div>/,'<div class="cl notice">$1</div>')};

/* ---- 상단바에 '운영' 탭 (GM 만) ---- */
const _setBar2=setBar;
setBar=function(right,active){
  _setBar2(right,active);adminSubscribe();showNoticeBar();
  const nav=$(".appbar .tabs2");
  if(ACC.gm&&nav&&!nav.querySelector('[href="#admin"]'))nav.insertAdjacentHTML("beforeend",`<a href="#admin" class="${active=="admin"?"on":""}" onclick="event.preventDefault();adminPage()">운영</a>`);
};

/* ---- 운영 페이지 ---- */
async function adminPage(){
  if(!ACC.gm){home();return}
  S=null;clearInterval(timer);B.view="admin";setBar(null,"admin");
  const online=chatPeers("lobby").map(p=>({n:cleanNick(p.presence.nick),st:String(p.presence.st||"").slice(0,4),g:p.presence.acct=="g",gm:p.presence.gm==1}));
  const mutes=Object.entries(ADM.mutes).filter(([,m])=>Number(m.until)>Date.now());
  const presets=["채팅 예절을 지켜 주세요.","욕설·비방은 금지예요.","같은 말을 반복하지 마세요(도배).","다른 사람의 게임을 방해하지 마세요."];
  const userRow=u=>`<div class="urow"><span class="sp b">${esc(u.n)}${u.gm?gmBadge:""}${u.g?guestBadge:""}</span><span class="ust">${esc(u.st)}</span>${u.gm?"":`<button class="btn2 sm" onclick="adminWarnPick('${esc(u.n)}')">경고</button><button class="btn2 sm" onclick="adminMute('${esc(u.n)}',10)">10분 금지</button>`}${isMuted(u.n)?`<span class="stag play">금지 중</span>`:""}</div>`;
  screen("admin",`<div class="col">
    ${panel("공지 보내기",`<div class="solo"><label class="xs b muted" for="ntext">모든 사람의 화면 위와 로비 채팅에 보여요</label>
      <textarea id="ntext" class="inp" style="height:84px;padding:10px;resize:vertical" maxlength="200" placeholder="예: 오늘 밤 10시에 서버 점검이 있어요.">${esc(ADM.notice?ADM.notice.text:"")}</textarea>
      <div class="row" style="gap:6px"><button class="cta sm" onclick="adminNotice()">공지 게시</button>${ADM.notice?`<button class="btn2 big danger" onclick="adminNotice(true)">공지 내리기</button><span class="xs muted">게시 ${fmtTime(ADM.notice.at)}</span>`:""}</div><p id="admsg" class="xs" style="margin:0;min-height:16px;color:#C0461A"></p></div>`,{color:"orange"})}
    ${panel("경고 보내기",`<div class="solo"><label class="xs b muted" for="wnick">받을 사람 닉네임</label><input id="wnick" class="inp" maxlength="12" placeholder="정확한 닉네임">
      <label class="xs b muted" for="wmsg">경고 내용</label><textarea id="wmsg" class="inp" style="height:70px;padding:10px;resize:vertical" maxlength="300"></textarea>
      <div class="row" style="gap:4px;flex-wrap:wrap">${presets.map(p=>`<button class="btn2 sm" onclick="$('#wmsg').value='${p}'">${p.slice(0,10)}…</button>`).join("")}</div>
      <div class="row" style="gap:6px"><button class="cta sm" onclick="adminWarn()">경고 보내기</button><span class="xs muted">상대가 접속해 있으면 바로, 아니면 다음 접속 때 떠요</span></div><p id="wmsg2" class="xs" style="margin:0;min-height:16px"></p></div>`,{color:"dark"})}
  </div><div class="col">
    ${panel(`지금 접속자 <span class="num">${online.length}</span>`,`<div class="ulist" style="max-height:340px">${online.map(userRow).join("")||`<div class="cl sys" style="padding:10px">접속자가 없어요.</div>`}</div>`,{cls:"grow"})}
    ${panel(`채팅 금지 <span class="num">${mutes.length}</span>`,`<div class="ulist">${mutes.map(([k,m])=>`<div class="urow"><span class="sp b">${esc(m.nick||k)}</span><span class="xs muted">${fmtTime(m.until)}까지${m.reason?" · "+esc(m.reason):""}</span><button class="btn2 sm" onclick="adminMute('${esc(m.nick||k)}',0)">해제</button></div>`).join("")||`<div class="cl sys" style="padding:10px">없어요.</div>`}
      <div class="row" style="gap:4px;padding:8px;flex-wrap:wrap"><label for="mnick" class="sr">닉네임</label><input id="mnick" class="inp" style="flex:1;min-width:120px" maxlength="12" placeholder="닉네임"><button class="btn2 sm" onclick="adminMute($('#mnick').value,10)">10분</button><button class="btn2 sm" onclick="adminMute($('#mnick').value,60)">1시간</button><button class="btn2 sm" onclick="adminMute($('#mnick').value,1440)">1일</button></div></div>`,{color:"green"})}
  </div><div class="col">
    ${panel("최근 경고",`<div class="ulist" id="wlist"><div class="cl sys" style="padding:10px">불러오는 중…</div></div>`,{cls:"grow",color:"dark"})}
    ${panel("가입한 계정",`<div class="ulist" id="ulist2" style="max-height:300px"><div class="cl sys" style="padding:10px">불러오는 중…</div></div>`,{cls:"grow"})}
  </div>`);
  loadAdminLists();
}
async function loadAdminLists(){
  try{const q=await ACC.db.collection("warnings").orderBy("at","desc").limit(30).get();const rows=[];q.forEach(d=>{const w=d.data();rows.push(`<div class="urow"><span class="sp"><b>${esc(w.nick||w.to)}</b> · ${esc(String(w.msg||"").slice(0,40))}</span><span class="xs muted">${fmtTime(w.at)}</span><button class="btn2 sm" onclick="adminDelWarn('${d.id}')">삭제</button></div>`)});
    const el=$("#wlist");if(el)el.innerHTML=rows.join("")||`<div class="cl sys" style="padding:10px">보낸 경고가 없어요.</div>`}catch(e){const el=$("#wlist");if(el)el.innerHTML=`<div class="cl sys" style="padding:10px">불러오지 못했어요. 규칙을 확인해 주세요.</div>`}
  try{const q=await ACC.db.collection("users").orderBy("total","desc").limit(100).get();const rows=[];q.forEach(d=>{const u=d.data();if(!u.nick)return;rows.push(`<div class="urow">${lvBadge(levelOf(u.total|0).lv)}<span class="sp b">${esc(u.nick)}</span><span class="num xs">${(u.total|0).toLocaleString()}P · ${u.games|0}판 · ${u.wins|0}승</span></div>`)});
    const el=$("#ulist2");if(el)el.innerHTML=rows.join("")||`<div class="cl sys" style="padding:10px">아직 없어요.</div>`}catch(e){const el=$("#ulist2");if(el)el.innerHTML=`<div class="cl sys" style="padding:10px">불러오지 못했어요.</div>`}
}
async function adminNotice(remove){
  const m=$("#admsg"),text=String($("#ntext").value||"").trim().slice(0,200);
  if(!remove&&!text){m.textContent="공지 내용을 입력해 주세요.";return}
  try{await ACC.db.doc("notices/current").set(remove?{text:"",at:Date.now(),by:ACC.uid}:{text,at:Date.now(),by:ACC.uid});m.style.color="var(--good)";m.textContent=remove?"공지를 내렸어요.":"공지를 게시했어요."}
  catch(e){m.style.color="#C0461A";m.textContent="저장하지 못했어요. 운영자 규칙이 게시됐는지 확인해 주세요."}
}
function adminWarnPick(n){$("#wnick").value=n;$("#wmsg").focus()}
async function adminWarn(){
  const n=cleanNick($("#wnick").value),msg=String($("#wmsg").value||"").trim().slice(0,300),m=$("#wmsg2");
  if(!n||!msg){m.style.color="#C0461A";m.textContent="닉네임과 내용을 모두 입력해 주세요.";return}
  try{await ACC.db.collection("warnings").add({to:nickKey(n),nick:n,msg,at:Date.now(),by:ACC.uid});m.style.color="var(--good)";m.textContent=`${n}님에게 경고를 보냈어요.`;$("#wmsg").value="";loadAdminLists()}
  catch(e){m.style.color="#C0461A";m.textContent="보내지 못했어요. 운영자 규칙이 게시됐는지 확인해 주세요."}
}
async function adminDelWarn(id){try{await ACC.db.doc("warnings/"+id).delete();loadAdminLists()}catch(e){toast("삭제하지 못했어요.")}}
async function adminMute(n,minutes){
  n=cleanNick(n);if(!n){toast("닉네임을 입력해 주세요.");return}
  try{const ref=ACC.db.doc("mutes/"+nickKey(n));if(minutes>0)await ref.set({nick:n,until:Date.now()+minutes*60000,reason:"",at:Date.now()});else await ref.delete();
    toast(minutes>0?`${n}님의 채팅을 ${minutes>=1440?minutes/1440+"일":minutes>=60?minutes/60+"시간":minutes+"분"} 동안 막았어요.`:`${n}님의 채팅 금지를 풀었어요.`)}
  catch(e){toast("저장하지 못했어요. 운영자 규칙이 게시됐는지 확인해 주세요.")}
}
/* 시작할 때와 로그인 상태가 바뀔 때 구독 */
const _home3=home;home=function(){_home3();adminSubscribe();showNoticeBar()};
