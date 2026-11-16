/* ================= 계정: 구글 로그인(Firebase) + 게스트 =================
   - 구글 로그인: Firebase Auth. 처음 로그인하면 '계정 만들기'에서 닉네임을 정한다.
     닉네임은 Firestore 의 nicknames/{소문자 닉네임} 문서로 선점한다. 보안 규칙(firestore.rules)이 중복을 막는다.
     점수·승패는 users/{uid} 에 저장돼 어느 기기에서든 이어진다.
   - 게스트: 이 브라우저 고유의 4자리 꼬리표로 '게스트-K3F9' 같은 이름이 자동으로 붙는다. 바꿀 수 없다.
     기록은 이 브라우저에만 저장된다.
   - Firebase 설정(window.CHARTGAP_FIREBASE)이 없으면 구글 로그인 버튼은 꺼지고 게스트로만 들어갈 수 있다.
   대전 화면의 이름표는 각자 기기가 보내는 값이라, 기술적으로 흉내 낼 수는 있다(표시용). */
const ACC={type:null,uid:null,email:"",fb:null,auth:null,db:null,ready:false,profile:null};
const NICK_RE=/^[0-9A-Za-z가-힣_]{2,12}$/;
// 운영자(GM) 계정: 공개 코드에 이메일을 두지 않으려고 이메일의 SHA-256 값만 둔다.
// 'admin' 같은 예약 닉네임은 Firestore 규칙에서도 운영자 이메일에게만 허락한다(콘솔에 게시한 규칙).
const OWNER_HASH="3a249d43dfb8548e7768bbafb940773f9423daddcaa15e7ef5e82ebe7af1aab3";
const RESERVED=/^(게스트|손님|guest|admin|gm|운영자|관리자)/i;
async function sha256hex(s){try{const b=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s));return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("")}catch(e){return ""}}
function guestTag(){let g="";try{g=localStorage.getItem("cg_guest")||""}catch(e){}
  if(!/^[A-Z2-9]{4}$/.test(g)){g=Array.from({length:4},()=>"ABCDEFGHJKLMNPQRSTUVWXYZ23456789"[Math.random()*32|0]).join("");try{localStorage.setItem("cg_guest",g)}catch(e){}}return g}
const guestNick=()=>"게스트-"+guestTag();
const isGuestNick=n=>/^게스트-/.test(String(n||""));
function nickKey(n){return String(n).toLowerCase()}
function nickProblem(n){
  if(!NICK_RE.test(n))return "닉네임은 2~12자의 한글·영문·숫자·밑줄(_)만 쓸 수 있어요.";
  if(RESERVED.test(n)&&!(ACC.gm&&!/^(게스트|손님|guest)/i.test(n)))return "이 단어로 시작하는 닉네임은 쓸 수 없어요.";
  return null;
}

/* ---- 기록: 계정은 Firestore + 기기 캐시, 게스트는 이 브라우저 ---- */
const profKey=()=>ACC.type=="google"&&ACC.uid?"cg_profile_"+ACC.uid:"cg_profile";
loadProfile=function(){try{return Object.assign({total:0,wins:0,losses:0,games:0},JSON.parse(localStorage.getItem(profKey())||"{}"))}catch(e){return {total:0,wins:0,losses:0,games:0}}};
saveProfile=function(p){try{localStorage.setItem(profKey(),JSON.stringify(p))}catch(e){}
  if(ACC.type=="google"&&ACC.db&&ACC.uid)ACC.db.doc("users/"+ACC.uid).set({total:p.total|0,wins:p.wins|0,losses:p.losses|0,games:p.games|0,updatedAt:Date.now()},{merge:true}).catch(()=>{})};

/* ---- presence 에 계정 종류를 싣는다 (게스트 표시용) ---- */
const _setLobbyPresence=setLobbyPresence;
let lastAcct="";
setLobbyPresence=function(st){const a=ACC.type=="guest"?"g":ACC.type?(ACC.gm?"gm":"u"):"";if(B.room&&a&&a!==lastAcct){lastAcct=a;B.room.presence({acct:a,gm:ACC.gm?1:null}).catch(()=>{})}_setLobbyPresence(st)};  // 바뀔 때만 보낸다 (보내면 로비가 다시 그려지므로)
const _battleEnter2=battleEnter;
battleEnter=async function(code,host,settings,pw){await _battleEnter2(code,host,settings,pw);if(B.mroom)B.mroom.presence({acct:ACC.type=="guest"?"g":"u",gm:ACC.gm?1:null}).catch(()=>{})};
const guestBadge=`<span class="gtag">게스트</span>`,gmBadge=`<span class="gmtag" title="운영자">GM</span>`;

/* ---- 시작 ---- */
async function authBoot(){
  const cfgFb=window.CHARTGAP_FIREBASE;
  if(cfgFb&&window.firebase){
    try{ACC.fb=firebase.apps&&firebase.apps.length?firebase.app():firebase.initializeApp(cfgFb);ACC.auth=firebase.auth();ACC.db=firebase.firestore()}
    catch(e){ACC.fb=null}
  }
  let mode="";try{mode=localStorage.getItem("cg_mode")||""}catch(e){}
  if(ACC.auth){
    let first=true;
    ACC.auth.onAuthStateChanged(async u=>{
      if(u){await afterGoogle(u);return}
      if(ACC.type=="google"){ACC.type=null;ACC.uid=null}
      if(first&&mode=="guest"){startGuest();}else if(!ACC.type)loginScreen();
      first=false;
    });
    return;
  }
  if(mode=="guest")startGuest();else loginScreen();
}
function startGuest(){ACC.type="guest";ACC.uid=null;nick=guestNick();try{localStorage.setItem("cg_mode","guest");localStorage.setItem("cg_nick",nick)}catch(e){}home()}
async function googleLogin(){
  const m=$("#lmsg");if(!ACC.auth){if(m)m.textContent="구글 로그인이 아직 설정되지 않았어요. 게스트로 시작해 주세요.";return}
  try{if(m)m.textContent="구글 로그인 창을 여는 중…";await ACC.auth.signInWithPopup(new firebase.auth.GoogleAuthProvider())}
  catch(e){if(m)m.textContent=e&&e.code=="auth/popup-closed-by-user"?"로그인 창을 닫았어요. 다시 시도해 주세요.":e&&e.code=="auth/unauthorized-domain"?"이 주소는 아직 로그인 허용 목록에 없어요. Firebase 설정에서 도메인을 추가해야 해요.":"로그인하지 못했어요. 팝업 차단을 풀고 다시 시도해 주세요."}
}
async function afterGoogle(u){
  ACC.type="google";ACC.uid=u.uid;ACC.email=u.email||"";
  ACC.gm=!!(u.emailVerified!==false&&ACC.email&&await sha256hex(ACC.email.trim().toLowerCase())===OWNER_HASH);
  try{localStorage.setItem("cg_mode","google")}catch(e){}
  let doc=null;try{const s=await ACC.db.doc("users/"+u.uid).get();doc=s.exists?s.data():null}catch(e){}
  if(doc){ACC.profile=doc;const p={total:doc.total|0,wins:doc.wins|0,losses:doc.losses|0,games:doc.games|0},local=loadProfile();
    // 기기 캐시가 더 크면(오프라인 중 쌓인 기록) 그쪽을 올린다
    const merged={total:Math.max(p.total,local.total),wins:Math.max(p.wins,local.wins),losses:Math.max(p.losses,local.losses),games:Math.max(p.games,local.games)};
    try{localStorage.setItem(profKey(),JSON.stringify(merged))}catch(e){}if(JSON.stringify(merged)!==JSON.stringify(p))saveProfile(merged)}
  if(doc&&doc.nick&&!nickProblem(doc.nick)){nick=doc.nick;try{localStorage.setItem("cg_nick",nick)}catch(e){}home()}
  else createAccountScreen(u);
}
async function logout(){document.querySelectorAll(".modal").forEach(m=>m.remove());if(B.mroom)battleLeave();
  try{localStorage.removeItem("cg_mode")}catch(e){}ACC.type=null;ACC.uid=null;if(ACC.auth)await ACC.auth.signOut().catch(()=>{});loginScreen()}

/* ---- 로그인 화면 ---- */
const G_LOGO=`<svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-17.1z"/><path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.7c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.2-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"/></svg>`;
function loginScreen(){
  S=null;clearInterval(timer);B.view="login";setBar("");
  const on=!!ACC.auth;
  screen("auth",`<section class="pn2 authp"><div class="ph"><span>빈칸차트 시작하기</span></div><div class="authb">
    <p class="authlead">실제 주식 차트의 가려진 구간을 맞히는 게임이에요.<br>구글 계정으로 들어가면 닉네임과 기록이 어느 기기에서든 이어져요.</p>
    <button class="gbtn" onclick="googleLogin()" ${on?"":"disabled"}>${G_LOGO}<span>Google 계정으로 로그인</span></button>
    ${on?"":`<p class="xs muted" style="margin:-4px 0 0;text-align:center">구글 로그인은 아직 설정 중이에요. 지금은 게스트로 시작할 수 있어요.</p>`}
    <div class="or"><span>또는</span></div>
    <button class="btn2 big" style="width:100%" onclick="startGuest()">게스트로 시작</button>
    <p class="xs muted" style="margin:0;text-align:center;line-height:1.6">게스트는 <b>${esc(guestNick())}</b> 같은 이름이 자동으로 붙고, 기록은 이 브라우저에만 남아요.</p>
    <p id="lmsg" class="xs" style="color:#C0461A;margin:0;min-height:16px;text-align:center"></p></div></section>`);
}

/* ---- 계정 만들기 / 닉네임 바꾸기 ---- */
function createAccountScreen(u,changing){
  S=null;clearInterval(timer);B.view="account";setBar(changing?null:"");
  const sug=changing?nick:String((u&&u.displayName)||"").replace(/[^0-9A-Za-z가-힣_]/g,"").slice(0,12);
  screen("auth",`<section class="pn2 authp"><div class="ph orange"><span>${changing?"닉네임 바꾸기":"계정 만들기"}</span>${changing?`<small><button class="x" onclick="home()" aria-label="닫기">✕</button></small>`:""}</div><div class="authb">
    ${changing?"":`<div class="row" style="gap:10px">${avatar(sug||"?",48)}<div><b>${esc((u&&u.displayName)||"구글 계정")}</b><div class="xs muted">${esc((u&&u.email)||"")}</div></div></div>
    <p class="authlead" style="margin:0">게임에서 쓸 닉네임을 정해 주세요. 다른 사람과 겹칠 수 없어요.</p>`}
    <label class="xs b muted" for="newnick">닉네임</label>
    <input id="newnick" class="inp" maxlength="12" value="${esc(sug)}" placeholder="2~12자 한글·영문·숫자" oninput="checkNickLive()" onkeydown="if(event.key=='Enter')claimNick(${changing?1:0})">
    <p id="nmsg" class="xs" style="margin:0;min-height:16px;color:var(--muted)">2~12자의 한글·영문·숫자·밑줄(_)</p>
    <button class="cta" onclick="claimNick(${changing?1:0})">${changing?"바꾸기":"이 닉네임으로 시작"}</button>
    ${changing?"":`<button class="linkbtn" style="align-self:center" onclick="logout()">다른 계정으로 로그인</button>`}</div></section>`);
  setTimeout(()=>{const i=$("#newnick");if(i){i.focus();i.select()}},30);
}
let nickTimer=null;
function checkNickLive(){
  const n=String($("#newnick").value||"").trim(),m=$("#nmsg");clearTimeout(nickTimer);
  const prob=nickProblem(n);if(prob){m.style.color="#C0461A";m.textContent=prob;return}
  if(n===nick&&ACC.profile){m.style.color="var(--muted)";m.textContent="지금 쓰는 닉네임이에요.";return}
  m.style.color="var(--muted)";m.textContent="확인하는 중…";
  nickTimer=setTimeout(async()=>{try{const s=await ACC.db.doc("nicknames/"+nickKey(n)).get();if(String($("#newnick").value||"").trim()!==n)return;
    const mine=s.exists&&s.data().uid===ACC.uid;m.style.color=s.exists&&!mine?"#C0461A":"var(--good)";m.textContent=s.exists&&!mine?"이미 쓰는 사람이 있어요.":"쓸 수 있는 닉네임이에요."}catch(e){m.textContent=""}},350);
}
async function claimNick(changing){
  const n=String($("#newnick").value||"").trim(),m=$("#nmsg"),prob=nickProblem(n);
  if(prob){m.style.color="#C0461A";m.textContent=prob;return}
  if(!ACC.db||!ACC.uid){m.textContent="로그인이 풀렸어요. 다시 로그인해 주세요.";return}
  m.style.color="var(--muted)";m.textContent="저장하는 중…";
  const old=ACC.profile&&ACC.profile.nick?nickKey(ACC.profile.nick):null,key=nickKey(n),uid=ACC.uid,db=ACC.db;
  try{
    await db.runTransaction(async tx=>{
      const ref=db.doc("nicknames/"+key),s=await tx.get(ref);
      if(s.exists&&s.data().uid!==uid)throw new Error("taken");
      if(!s.exists)tx.set(ref,{uid,nick:n,at:Date.now()});
      if(old&&old!==key){const oref=db.doc("nicknames/"+old),os=await tx.get(oref);if(os.exists&&os.data().uid===uid)tx.delete(oref)}
      const p=loadProfile();
      tx.set(db.doc("users/"+uid),{nick:n,total:p.total|0,wins:p.wins|0,losses:p.losses|0,games:p.games|0,createdAt:(ACC.profile&&ACC.profile.createdAt)||Date.now(),updatedAt:Date.now()},{merge:true});
    });
    ACC.profile=Object.assign({},ACC.profile||{},{nick:n});nick=n;try{localStorage.setItem("cg_nick",nick)}catch(e){}
    lastLobbyP="";home();
  }catch(e){m.style.color="#C0461A";m.textContent=e&&e.message=="taken"?"방금 다른 사람이 가져갔어요. 다른 닉네임을 골라 주세요.":"저장하지 못했어요. 잠시 후 다시 시도해 주세요."}
}

/* ---- 내 계정 메뉴 (상단바의 내 이름을 누르면) ---- */
function accountMenu(){
  document.querySelectorAll(".modal").forEach(m=>m.remove());
  const el=document.createElement("div");el.className="modal";el.onclick=e=>{if(e.target===el)el.remove()};
  const g=ACC.type=="guest";
  el.innerHTML=`<div class="sheet pn2"><div class="ph dark"><span>내 계정</span><small><button class="x" onclick="this.closest('.modal').remove()" aria-label="닫기">✕</button></small></div><div style="padding:12px;display:grid;gap:8px">
    <div class="row" style="gap:10px">${avatar(nick,44)}<div><b>${esc(nick)}</b> ${g?guestBadge:""}${ACC.gm?gmBadge:""}<div class="xs muted">${g?"게스트 · 기록은 이 브라우저에만 남아요":esc(ACC.email)}</div></div></div>
    ${g?`<button class="gbtn" onclick="this.closest('.modal').remove();googleLogin()" ${ACC.auth?"":"disabled"}>${G_LOGO}<span>Google 계정으로 로그인</span></button><p class="xs muted" style="margin:0">로그인하면 닉네임을 직접 정할 수 있어요. 게스트 기록은 옮겨지지 않아요.</p>`
      :`<button class="btn2 big" onclick="this.closest('.modal').remove();createAccountScreen(null,true)">닉네임 바꾸기</button>`}
    <button class="btn2 big danger" onclick="logout()">${g?"게스트 그만하기":"로그아웃"}</button></div></div>`;
  document.body.appendChild(el);
}
/* 상단바의 내 정보에 계정 메뉴와 게스트 표시를 붙인다 */
const _setBar=setBar;
setBar=function(right,active){
  _setBar(right,active);const me=$(".appbar .me");
  if(right==null&&me&&ACC.type){me.setAttribute("role","button");me.tabIndex=0;me.title="내 계정";me.onclick=accountMenu;me.onkeydown=e=>{if(e.key=="Enter")accountMenu()};
    if(ACC.type=="guest"&&!me.querySelector(".gtag"))me.querySelector("b").insertAdjacentHTML("afterend",guestBadge);
    if(ACC.gm&&!me.querySelector(".gmtag"))me.querySelector("b").insertAdjacentHTML("afterend",gmBadge)}
};
/* 로비 내 정보: 닉네임은 계정에서만 바꾼다 */
const _home=home;
home=function(){
  if(!ACC.type){loginScreen();return}
  if(ACC.type=="guest")nick=guestNick();
  _home();
  const inp=$("#nick");if(inp){const b=document.createElement("span");b.className="nickname";b.innerHTML=`<b>${esc(nick)}</b>${ACC.type=="guest"?guestBadge:""}<button class="linkbtn" onclick="accountMenu()">${ACC.type=="guest"?"로그인":"계정"}</button>`;inp.replaceWith(b)}
  // 접속자 목록·방 슬롯에 게스트 표시
  markGuests();
};
function markGuests(){
  const guests=new Set(),gms=new Set();
  for(const src of [B.lobby||[],B.peers||[]])for(const p of src){if(!p.presence||!p.presence.nick)continue;const n=cleanNick(p.presence.nick);if(p.presence.acct=="g")guests.add(n);if(p.presence.gm==1&&!isGuestNick(n))gms.add(n)}
  if(ACC.type=="guest")guests.add(nick);if(ACC.gm)gms.add(nick);
  document.querySelectorAll(".urow .sp, .snick, .pcard .sh b, .ulist .urow b.sp, .chatlog .cl b, .nickname b").forEach(el=>{
    const n=el.textContent.replace(/\s*나$/,"").replace(/GM|게스트/g,"").trim();
    if(gms.has(n)&&!el.parentElement.querySelector(".gmtag"))el.insertAdjacentHTML("afterend",gmBadge);
    else if((guests.has(n)||isGuestNick(n))&&!el.querySelector(".gtag")&&!el.closest(".chatlog"))el.insertAdjacentHTML("beforeend"," "+guestBadge)});
}
for(const fn of ["battleRoom","renderReveal","battleResultView"]){const orig=window[fn];if(typeof orig=="function")window[fn]=function(){const r=orig.apply(this,arguments);markGuests();return r}}
const _render=render;render=function(){_render();markGuests()};

const _refreshChat=refreshChat;refreshChat=function(w){_refreshChat(w);markGuests()};
