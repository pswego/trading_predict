// 테스트용 가짜 room: 같은 브라우저의 탭끼리 BroadcastChannel 로 presence 를 주고받는다
(()=>{const me=Math.random().toString(36).slice(2,10);
function makeRoom(name){const bc=new BroadcastChannel("mock-"+name);let mine={},others={},hs=[];
  const snap=()=>[{peer:me,by:null,isMe:true,sameTab:true,kind:"viewer",guest:false,presence:Object.freeze({...mine}),updatedAt:Date.now()},...Object.entries(others).map(([k,v])=>({peer:k,by:null,isMe:false,sameTab:false,kind:"viewer",guest:false,presence:Object.freeze({...v}),updatedAt:Date.now()}))];
  const fire=()=>{const ps=snap();hs.forEach(h=>h({peers:ps,joined:[],left:[],updated:[]}))};
  bc.onmessage=e=>{const m=e.data;if(m.t=="p"){others[m.peer]=m.p;fire()}if(m.t=="hello"){bc.postMessage({t:"p",peer:me,p:mine})}if(m.t=="bye"){delete others[m.peer];fire()}};
  bc.postMessage({t:"hello"});
  return {name,presence:async patch=>{for(const[k,v]of Object.entries(patch)){if(v===null)delete mine[k];else mine[k]=v}bc.postMessage({t:"p",peer:me,p:mine});setTimeout(fire,0)},
    peers:snap,onPeers:h=>{hs.push(h);setTimeout(fire,0);return()=>{}},emit:async()=>{},on:()=>()=>{},connected:()=>true,onConnection:()=>()=>{},
    leave:async()=>{bc.postMessage({t:"bye",peer:me});bc.close()}}}
const lobby=makeRoom("lobby");lobby.join=async n=>makeRoom(n);
window.claude={use:async n=>n=="room"?lobby:null};})();
