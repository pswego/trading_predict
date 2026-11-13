// 서버 없이 브라우저끼리 직접 연결(WebRTC)해서 claude.ai room 과 같은 모양의 API 를 만든다.
// 방 이름마다 '방장 브라우저'가 중계한다: 처음 들어온 사람이 방장이 되고, 나머지는 방장에게 연결한다.
// 연결 중개(서로 찾기)에만 PeerJS 무료 공개 서버를 쓰고, 게임 데이터는 브라우저끼리 직접 오간다.
(function(){
  var PREFIX="chartgap-v1-";
  function rid(){return Math.random().toString(36).slice(2,10)}
  function makeRoom(name){
    return new Promise(function(resolve,reject){
      var me=rid(),mine={},others={},hs=[],peer=null,conns={},hostConn=null,isHub=false,done=false,closed=false;
      function snap(){var out=[{peer:me,by:null,isMe:true,sameTab:true,kind:"viewer",guest:false,presence:Object.freeze(Object.assign({},mine)),updatedAt:Date.now()}];
        for(var k in others)out.push({peer:k,by:null,isMe:false,sameTab:false,kind:"viewer",guest:false,presence:Object.freeze(Object.assign({},others[k])),updatedAt:Date.now()});return out}
      function fire(){var s=snap();hs.forEach(function(h){try{h({peers:s,joined:[],left:[],updated:[]})}catch(e){}})}
      function hubBroadcast(){var all={};all[me]=mine;for(var k in others)all[k]=others[k];
        for(var c in conns){try{conns[c].send({t:"all",all:all})}catch(e){}}}
      function ok(){if(!done){done=true;resolve(api)}}
      function becomeHub(){
        isHub=true;peer=new Peer(PREFIX+name);
        peer.on("open",function(){ok();fire()});
        peer.on("connection",function(c){
          c.on("data",function(m){if(!m||m.t!=="p"||typeof m.p!=="object")return;if(JSON.stringify(m.p).length>4096)return;others[c.peer]=m.p;fire();hubBroadcast()});
          c.on("open",function(){conns[c.peer]=c;hubBroadcast()});
          c.on("close",function(){delete conns[c.peer];delete others[c.peer];fire();hubBroadcast()});
        });
        peer.on("error",function(e){if(e&&e.type==="unavailable-id"){peer.destroy();becomeGuest()}else if(!done){done=true;reject({code:"upstream_error"})}});
      }
      function becomeGuest(){
        isHub=false;peer=new Peer();
        peer.on("open",function(id){me=id;hostConn=peer.connect(PREFIX+name,{reliable:true});
          hostConn.on("open",function(){ok();hostConn.send({t:"p",p:mine})});
          hostConn.on("data",function(m){if(!m||m.t!=="all")return;others={};for(var k in m.all){if(k!==me)others[k]=m.all[k]}fire()});
          hostConn.on("close",function(){others={};fire();if(!closed){setTimeout(function(){if(!closed){try{peer.destroy()}catch(e){}becomeHub()}},800)}});
        });
        peer.on("error",function(e){if(!done){done=true;reject({code:"upstream_error"})}});
      }
      var api={name:name,
        presence:function(patch){for(var k in patch){if(patch[k]===null)delete mine[k];else mine[k]=patch[k]}
          if(isHub){fire();hubBroadcast()}else if(hostConn&&hostConn.open){hostConn.send({t:"p",p:mine})}return Promise.resolve()},
        peers:snap,onPeers:function(h){hs.push(h);setTimeout(fire,0);return function(){hs=hs.filter(function(x){return x!==h})}},
        emit:function(){return Promise.resolve()},on:function(){return function(){}},
        connected:function(){return !!peer&&!peer.disconnected},onConnection:function(h){setTimeout(function(){h(true)},0);return function(){}},
        leave:function(){closed=true;try{peer&&peer.destroy()}catch(e){}return Promise.resolve()}};
      becomeHub();
      setTimeout(function(){if(!done){done=true;reject({code:"upstream_error"})}},12000);
    });
  }
  // 로비: 서버가 없어서 '열린 방' 목록은 없다. 방 코드로만 참가한다.
  var lobby={presence:function(){return Promise.resolve()},peers:function(){return []},onPeers:function(){return function(){}},
    emit:function(){return Promise.resolve()},on:function(){return function(){}},connected:function(){return true},onConnection:function(){return function(){}},
    join:function(n){return makeRoom(n)},p2p:true};
  window.claude={use:function(n){return Promise.resolve(n==="room"&&window.Peer?lobby:null)}};
})();
