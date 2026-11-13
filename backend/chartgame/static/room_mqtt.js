// 무료 공개 MQTT 중계 서버(WebSocket)를 거쳐 claude.ai room 과 같은 모양의 API 를 만든다.
// 브라우저 → 중계 서버로만 연결하므로 와이파이·휴대폰 데이터 등 네트워크가 달라도 연결된다.
// 각자 자기 presence 를 'chartgap/v1/<방>/<내 id>' 에 보관(retain)해 두고, 같은 방 주제를 구독해 모두의 상태를 받는다.
// 공개 서버라 누구나 읽고 쓸 수 있다: 받은 내용은 표시용으로만 쓴다.
(function(){
  var qs=new URLSearchParams(location.search);
  var BROKERS=qs.get("broker")?[qs.get("broker")]:["wss://broker.hivemq.com:8884/mqtt","wss://broker.emqx.io:8084/mqtt","wss://test.mosquitto.org:8081/mqtt"];
  var ROOT="chartgap/v1/", me=Math.random().toString(36).slice(2,12), client=null, rooms={}, connP=null;
  var STALE=45000, BEAT=15000;
  function connect(){
    if(connP)return connP;
    connP=new Promise(function(resolve,reject){
      var i=0;
      (function tryNext(){
        if(i>=BROKERS.length){reject(new Error("no broker"));return}
        var url=BROKERS[i++],settled=false;
        var c=mqtt.connect(url,{clientId:"cg_"+me+"_"+Math.random().toString(36).slice(2,6),clean:true,keepalive:30,reconnectPeriod:2000,connectTimeout:6000,
          will:{topic:ROOT+"_bye/"+me,payload:"1",qos:0,retain:false}});
        var t=setTimeout(function(){if(!settled){settled=true;try{c.end(true)}catch(e){}tryNext()}},7000);
        c.on("connect",function(){if(settled){return}settled=true;clearTimeout(t);client=c;
          c.subscribe(ROOT+"_bye/+");
          c.on("message",onMessage);
          c.on("connect",function(){for(var n in rooms)rooms[n]._resub()}); // 재연결
          resolve(c)});
        c.on("error",function(){if(!settled){settled=true;clearTimeout(t);try{c.end(true)}catch(e){}tryNext()}});
      })();
    });
    return connP;
  }
  function onMessage(topic,buf){
    var parts=topic.slice(ROOT.length).split("/");
    if(parts[0]==="_bye"){for(var n in rooms)rooms[n]._gone(parts[1]);return}
    var r=rooms[parts[0]];if(r)r._msg(parts[1],buf);
  }
  function makeRoom(name){
    return connect().then(function(c){
      var base=ROOT+name+"/",mine={},others={},seen={},hs=[],timer=null,left=false;
      function snap(){var now=Date.now(),out=[{peer:me,by:null,isMe:true,sameTab:true,kind:"viewer",guest:false,presence:Object.freeze(Object.assign({},mine)),updatedAt:now}];
        for(var k in others){if(now-(seen[k]||0)<STALE)out.push({peer:k,by:null,isMe:false,sameTab:false,kind:"viewer",guest:false,presence:Object.freeze(Object.assign({},others[k])),updatedAt:seen[k]})}return out}
      function fire(){var s=snap();hs.forEach(function(h){try{h({peers:s,joined:[],left:[],updated:[]})}catch(e){}})}
      function pub(){if(left)return;var body=JSON.stringify(mine);if(body.length>4096)return;c.publish(base+me,body,{qos:1,retain:true})}
      var r={name:name,
        _msg:function(peer,buf){if(peer===me)return;var s=buf.toString();if(!s){delete others[peer];delete seen[peer];fire();return}
          try{var p=JSON.parse(s);if(p&&typeof p==="object"){others[peer]=p;seen[peer]=Date.now();fire()}}catch(e){}},
        _gone:function(peer){if(others[peer]){delete others[peer];delete seen[peer];fire()}},
        _resub:function(){c.subscribe(base+"+");pub()},
        presence:function(patch){for(var k in patch){if(patch[k]===null)delete mine[k];else mine[k]=patch[k]}pub();fire();return Promise.resolve()},
        peers:snap,onPeers:function(h){hs.push(h);setTimeout(fire,0);return function(){hs=hs.filter(function(x){return x!==h})}},
        emit:function(){return Promise.resolve()},on:function(){return function(){}},
        connected:function(){return c.connected},onConnection:function(h){setTimeout(function(){h(c.connected)},0);return function(){}},
        leave:function(){left=true;clearInterval(timer);c.publish(base+me,"",{qos:1,retain:true});c.unsubscribe(base+"+");delete rooms[name];return Promise.resolve()}};
      rooms[name]=r;c.subscribe(base+"+");
      timer=setInterval(function(){if(Object.keys(mine).length)pub();fire()},BEAT); // 살아 있다는 신호 + 오래된 사람 정리
      addEventListener("pagehide",function(){if(!left)c.publish(base+me,"",{qos:0,retain:true})});
      return r;
    });
  }
  var lobbyP=null;
  window.claude={use:function(n){
    if(n!=="room"||!window.mqtt)return Promise.resolve(null);
    if(!lobbyP)lobbyP=makeRoom("lobby").then(function(r){r.join=function(name){return makeRoom(name)};return r}).catch(function(){return null});
    return lobbyP}};
})();
