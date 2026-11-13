// 서버 WebSocket 방을 claude.ai room 과 같은 모양으로 감싼다. 게임 코드는 claude.use("room") 만 부른다.
(function(){
  function wsUrl(name){return (location.protocol==="https:"?"wss://":"ws://")+location.host+"/ws/room/"+encodeURIComponent(name)}
  function makeRoom(name){
    return new Promise(function(resolve,reject){
      var ws,mine={},peers=[],hs=[],you=null,open=false,closed=false,timer=null;
      function snap(){return peers.map(function(p){return {peer:p.peer,by:null,isMe:p.peer===you,sameTab:p.peer===you,kind:"viewer",guest:false,presence:Object.freeze(p.presence||{}),updatedAt:Date.now()}})}
      function fire(){var s=snap();hs.forEach(function(h){try{h({peers:s,joined:[],left:[],updated:[]})}catch(e){}})}
      function send(){if(open)ws.send(JSON.stringify({t:"presence",p:mine}))}
      function connect(first){
        ws=new WebSocket(wsUrl(name));
        ws.onopen=function(){open=true;send();if(first)resolve(api)};
        ws.onmessage=function(e){var m;try{m=JSON.parse(e.data)}catch(x){return}if(m.t==="peers"){peers=m.peers||[];you=m.you;fire()}};
        ws.onclose=function(){open=false;if(first&&!you){reject({code:"upstream_error"});return}if(!closed){clearTimeout(timer);timer=setTimeout(function(){connect(false)},1500)}};
      }
      var api={name:name,
        presence:function(patch){for(var k in patch){if(patch[k]===null)delete mine[k];else mine[k]=patch[k]}send();return Promise.resolve()},
        peers:snap,onPeers:function(h){hs.push(h);setTimeout(fire,0);return function(){hs=hs.filter(function(x){return x!==h})}},
        emit:function(){return Promise.resolve()},on:function(){return function(){}},
        connected:function(){return open},onConnection:function(h){setTimeout(function(){h(open)},0);return function(){}},
        leave:function(){closed=true;try{ws.close()}catch(e){}return Promise.resolve()}};
      connect(true);
    });
  }
  var lobby=null;
  window.claude={use:function(n){
    if(n!=="room")return Promise.resolve(null);
    if(!lobby)lobby=makeRoom("lobby").then(function(r){r.join=function(name){return makeRoom(name)};return r}).catch(function(){return null});
    return lobby}};
})();
