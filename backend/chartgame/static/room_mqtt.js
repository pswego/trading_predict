// 무료 공개 MQTT 중계 서버(WebSocket)를 거쳐 claude.ai room 과 같은 모양의 API 를 만든다.
// 브라우저 → 중계 서버로만 연결하므로 와이파이·휴대폰 데이터 등 네트워크가 달라도 연결된다.
// 각자 자기 presence 를 'chartgap/v1/<방>/<내 id>' 에 보관(retain)해 두고, 같은 방 주제를 구독해 모두의 상태를 받는다.
// 공개 서버라 누구나 읽고 쓸 수 있다: 받은 내용은 표시용으로만 쓴다.
(function(){
  var qs=new URLSearchParams(location.search);
  var BROKERS=qs.get("broker")?qs.get("broker").split(","):["wss://broker.hivemq.com:8884/mqtt","wss://broker.emqx.io:8084/mqtt","wss://test.mosquitto.org:8081/mqtt"];
  var ROOT="chartgap/v2/", me=Math.random().toString(36).slice(2,12), rooms={}, connP=null;
  var STALE=45000, BEAT=15000;
  // 접속 가능한 중계 서버 '전부'에 동시에 붙는다. 기기마다 서로 다른 서버에 붙어 서로 못 보는 일을 막기 위해서다.
  // 보낼 때는 붙은 서버 모두에 보내고, 받을 때는 어느 서버에서 오든 같은 상태로 합친다.
  var clients=[];
  function eachClient(fn){clients.forEach(function(c){if(c.connected){try{fn(c)}catch(e){}}})}
  function connect(){
    if(connP)return connP;
    connP=new Promise(function(resolve,reject){
      var pending=BROKERS.length,first=false;
      BROKERS.forEach(function(url){
        var c=mqtt.connect(url,{clientId:"cg_"+me+"_"+Math.random().toString(36).slice(2,6),clean:true,keepalive:30,reconnectPeriod:3000,connectTimeout:8000,
          will:{topic:ROOT+"_bye/"+me,payload:"1",qos:0,retain:false}});
        var counted=false;
        c.on("connect",function(){
          if(clients.indexOf(c)<0){clients.push(c);c.on("message",onMessage)}
          c.subscribe(ROOT+"_bye/+");for(var n in rooms)rooms[n]._resub(c);
          if(!first){first=true;resolve()}
        });
        var fail=function(){if(!counted){counted=true;pending--;if(pending===0&&!first)reject(new Error("no broker"))}};
        c.on("error",fail);setTimeout(function(){if(!c.connected)fail()},9000);
      });
    });
    return connP;
  }
  function onMessage(topic,buf){
    var parts=topic.slice(ROOT.length).split("/");
    if(parts[0]==="_bye"){for(var n in rooms)rooms[n]._gone(parts[1]);return}
    var r=rooms[parts[0]];if(r)r._msg(parts[1],buf);
  }
  function makeRoom(name){
    return connect().then(function(){
      var base=ROOT+name+"/",mine={},others={},seen={},hs=[],timer=null,left=false;
      function snap(){var now=Date.now(),out=[{peer:me,by:null,isMe:true,sameTab:true,kind:"viewer",guest:false,presence:Object.freeze(Object.assign({},mine)),updatedAt:now}];
        for(var k in others){if(now-(seen[k]||0)<STALE)out.push({peer:k,by:null,isMe:false,sameTab:false,kind:"viewer",guest:false,presence:Object.freeze(Object.assign({},others[k])),updatedAt:seen[k]})}return out}
      function fire(){var s=snap();hs.forEach(function(h){try{h({peers:s,joined:[],left:[],updated:[]})}catch(e){}})}
      function pub(only){if(left)return;var body=JSON.stringify(mine);if(body.length>4096)return;var send=function(c){c.publish(base+me,body,{qos:1,retain:true})};if(only)send(only);else eachClient(send)}
      var r={name:name,
        _msg:function(peer,buf){if(peer===me)return;var s=buf.toString();if(!s){delete others[peer];delete seen[peer];fire();return}
          try{var p=JSON.parse(s);if(p&&typeof p==="object"){others[peer]=p;seen[peer]=Date.now();fire()}}catch(e){}},
        _gone:function(peer){if(others[peer]){delete others[peer];delete seen[peer];fire()}},
        _resub:function(c){c.subscribe(base+"+");if(Object.keys(mine).length)pub(c)},
        presence:function(patch){for(var k in patch){if(patch[k]===null)delete mine[k];else mine[k]=patch[k]}pub();fire();return Promise.resolve()},
        peers:snap,onPeers:function(h){hs.push(h);setTimeout(fire,0);return function(){hs=hs.filter(function(x){return x!==h})}},
        emit:function(){return Promise.resolve()},on:function(){return function(){}},
        connected:function(){return clients.some(function(c){return c.connected})},onConnection:function(h){setTimeout(function(){h(r.connected())},0);return function(){}},
        leave:function(){left=true;clearInterval(timer);eachClient(function(c){c.publish(base+me,"",{qos:1,retain:true});c.unsubscribe(base+"+")});delete rooms[name];return Promise.resolve()}};
      rooms[name]=r;eachClient(function(c){c.subscribe(base+"+")});
      timer=setInterval(function(){if(Object.keys(mine).length)pub();fire()},BEAT); // 살아 있다는 신호 + 오래된 사람 정리
      addEventListener("pagehide",function(){if(!left)eachClient(function(c){c.publish(base+me,"",{qos:0,retain:true})})});
      return r;
    });
  }
  window.__relay=function(){return clients.filter(function(c){return c.connected}).length+"/"+BROKERS.length};
  var lobbyP=null;
  window.claude={use:function(n){
    if(n!=="room"||!window.mqtt)return Promise.resolve(null);
    if(!lobbyP)lobbyP=makeRoom("lobby").then(function(r){r.join=function(name){return makeRoom(name)};return r}).catch(function(){return null});
    return lobbyP}};
})();
