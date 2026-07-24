const COLORS={character:"#a43a32",place:"#416b7d",spell:"#c99b45",creature:"#52715b",object:"#755d83"};
const COMMUNITY_COLORS=["#a43a32","#416b7d","#c99b45","#52715b","#755d83","#c46b3c","#508b8b","#96713e"];
const shortBook=t=>({"Philosopher's Stone":"PS","Chamber of Secrets":"CS","Prisoner of Azkaban":"PA","Goblet of Fire":"GF","Order of the Phoenix":"OP","Half-Blood Prince":"HBP","Deathly Hallows":"DH"}[t]);
let data, visibleNodes=[], visibleEdges=[], selected=[], scale=1, pan={x:0,y:0}, drag=null, hovered=null;
const canvas=document.querySelector("#graph"),ctx=canvas.getContext("2d"), filters={};

fetch("data/graph.json").then(r=>r.json()).then(graph=>{
  data=graph; document.querySelector("#stat-nodes").textContent=data.meta.entityCount;
  document.querySelector("#stat-edges").textContent=data.meta.relationCount.toLocaleString();
  buildFilters(); computeLayout(); update(); buildInsights();
});
function buildFilters(){
  Object.keys(COLORS).forEach(type=>{filters[type]=true; document.querySelector("#filters").insertAdjacentHTML("beforeend",
    `<label class="type-filter" style="--c:${COLORS[type]}"><input type="checkbox" data-type="${type}" checked><i></i>${type[0].toUpperCase()+type.slice(1)}</label>`)});
  document.querySelectorAll("[data-type]").forEach(x=>x.onchange=()=>{filters[x.dataset.type]=x.checked;selected=[];update()});
  const people=data.nodes.filter(n=>n.type==="character").sort((a,b)=>a.id.localeCompare(b.id));
  document.querySelector("#distance-root").insertAdjacentHTML("beforeend",people.map(n=>`<option value="${n.id}">${n.id}</option>`).join(""));
}
function computeLayout(){
  const W=900,H=600, byType={}; Object.keys(COLORS).forEach(t=>byType[t]=[]);
  data.nodes.forEach(n=>byType[n.type].push(n));
  const centers={character:[430,300],place:[680,210],spell:[690,430],creature:[210,440],object:[190,180]};
  Object.entries(byType).forEach(([type,nodes])=>nodes.forEach((n,i)=>{
    const a=i*2.399, r=18*Math.sqrt(i); n.x=centers[type][0]+Math.cos(a)*r; n.y=centers[type][1]+Math.sin(a)*r;
  }));
}
function update(){
  const min=+document.querySelector("#weight").value, minDegree=+document.querySelector("#degree").value;
  const query=document.querySelector("#search").value.toLowerCase();
  const neighbourhood=neighbourhoodIds(min);
  visibleNodes=data.nodes.filter(n=>filters[n.type]&&(n.degree||0)>=minDegree&&
    (!neighbourhood||neighbourhood.has(n.id))&&(!query||n.id.toLowerCase().includes(query)));
  let ids=new Set(visibleNodes.map(n=>n.id));
  visibleEdges=data.edges.filter(e=>e.weight>=min&&ids.has(e.source)&&ids.has(e.target));
  if(!query){ids=new Set(visibleEdges.flatMap(e=>[e.source,e.target]));const root=document.querySelector("#distance-root").value;if(root)ids.add(root);visibleNodes=data.nodes.filter(n=>filters[n.type]&&(n.degree||0)>=minDegree&&(!neighbourhood||neighbourhood.has(n.id))&&ids.has(n.id))}
  document.querySelector("#empty").style.display=visibleNodes.length?"none":"block"; draw();
}
function neighbourhoodIds(minWeight){
  const root=document.querySelector("#distance-root").value;
  if(!root)return null;
  const limit=+document.querySelector("#distance").value,adjacency={};
  data.nodes.forEach(n=>adjacency[n.id]=[]);
  data.edges.filter(e=>e.weight>=minWeight).forEach(e=>{adjacency[e.source].push(e.target);adjacency[e.target].push(e.source)});
  const distance=new Map([[root,0]]),queue=[root];
  while(queue.length){const current=queue.shift(),nextDistance=distance.get(current)+1;if(nextDistance>limit)continue;
    for(const next of adjacency[current])if(!distance.has(next)){distance.set(next,nextDistance);queue.push(next)}}
  return new Set(distance.keys());
}
function resize(){
  const r=canvas.getBoundingClientRect(),d=devicePixelRatio||1;
  const width=Math.round(r.width*d),height=Math.round(r.height*d);
  if(canvas.width!==width||canvas.height!==height){
    canvas.width=width;canvas.height=height;
  }
  ctx.setTransform(d,0,0,d,0,0);
}
function screen(n){const r=canvas.getBoundingClientRect();return{x:(n.x-450)*scale+r.width/2+pan.x,y:(n.y-300)*scale+r.height/2+pan.y}}
function draw(){
  resize(); const selectedIds=new Set(selected.map(n=>n.id)), pathIds=new Set(window.pathIds||[]);
  const communityMode=document.querySelector("#community-mode").checked;
  ctx.clearRect(0,0,canvas.width,canvas.height); ctx.lineCap="round";
  visibleEdges.forEach(e=>{const a=data.nodes.find(n=>n.id===e.source),b=data.nodes.find(n=>n.id===e.target),p=screen(a),q=screen(b);
    const active=(selectedIds.has(a.id)||selectedIds.has(b.id)),onPath=pathIds.has(a.id)&&pathIds.has(b.id);
    ctx.strokeStyle=onPath?"#c99b45":active?"#a43a3277":"#8a887a28";ctx.lineWidth=onPath?3:Math.min(4,.3+Math.sqrt(e.weight)*.25);ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke()});
  visibleNodes.forEach(n=>{const p=screen(n),radius=Math.max(3,Math.min(12,2+Math.sqrt(n.mentions)*.14))*Math.sqrt(scale);
    ctx.beginPath();ctx.arc(p.x,p.y,radius,0,Math.PI*2);ctx.fillStyle=communityMode?COMMUNITY_COLORS[(n.community-1)%COMMUNITY_COLORS.length]:COLORS[n.type];ctx.fill();
    if(selectedIds.has(n.id)||pathIds.has(n.id)){ctx.strokeStyle="#fff";ctx.lineWidth=2;ctx.stroke()}
    if(radius>6||n===hovered||selectedIds.has(n.id)){ctx.font=`${n===hovered?600:500} 10px Manrope`;ctx.fillStyle="#25251f";ctx.fillText(n.id,p.x+radius+4,p.y+3)}
  });
  renderCommunityLegend(communityMode);
}
function renderCommunityLegend(show){
  const legend=document.querySelector("#community-legend");
  legend.classList.toggle("visible",show);
  if(!show)return;
  const groups={};
  data.nodes.forEach(n=>(groups[n.community]??=[]).push(n));
  legend.innerHTML=`<b>LOUVAIN COMMUNITIES</b>${Object.entries(groups).sort((a,b)=>a[0]-b[0]).map(([id,nodes])=>{
    const leaders=[...nodes].sort((a,b)=>b.weightedDegree-a.weightedDegree).slice(0,2).map(n=>n.id.split(" ").at(-1)).join(" / ");
    return `<div title="${nodes.map(n=>n.id).join(", ")}"><i style="background:${COMMUNITY_COLORS[(id-1)%COMMUNITY_COLORS.length]}"></i>C${id} · ${leaders} (${nodes.length})</div>`}).join("")}`;
}
function nodeAt(x,y){return [...visibleNodes].reverse().find(n=>{const p=screen(n);return Math.hypot(x-p.x,y-p.y)<14})}
canvas.onmousemove=e=>{const r=canvas.getBoundingClientRect();if(drag){pan.x+=e.clientX-drag.x;pan.y+=e.clientY-drag.y;drag={x:e.clientX,y:e.clientY};draw();return}hovered=nodeAt(e.clientX-r.left,e.clientY-r.top);canvas.style.cursor=hovered?"pointer":"grab";draw()};
canvas.onmousedown=e=>drag={x:e.clientX,y:e.clientY}; canvas.onmouseup=e=>{const moved=Math.hypot(e.clientX-drag.x,e.clientY-drag.y);drag=null;if(moved<4&&hovered)selectNode(hovered)};
canvas.onmouseleave=()=>drag=null;
canvas.onwheel=e=>{e.preventDefault();scale=Math.max(.45,Math.min(2.5,scale*(e.deltaY>0?.9:1.1)));draw()};
function selectNode(n){if(selected[0]?.id===n.id)selected=[];else if(selected.length<2)selected.push(n);else selected=[n];renderDetail(n);if(selected.length===2)findPath();else{window.pathIds=[];document.querySelector("#path-result").textContent=""}draw()}
function renderDetail(n){
 const edges=data.edges.filter(e=>e.source===n.id||e.target===n.id).sort((a,b)=>b.weight-a.weight).slice(0,5),max=Math.max(...Object.values(n.books));
 document.querySelector("#detail").innerHTML=`<p class="eyebrow">Entity profile</p><span class="detail-type" style="color:${COLORS[n.type]}">${n.type} · community ${n.community}</span><h3>${n.id}</h3>${n.effect?`<p>${n.effect}</p>`:""}<div class="big-number">${n.mentions.toLocaleString()}</div><div class="big-label">mentions · degree ${n.degree}</div><h4>Across the series</h4>${data.meta.books.map(b=>`<div class="book-row"><div><span>${shortBook(b)}</span><b>${n.books[b]||0}</b></div><i style="width:${(n.books[b]||0)/max*100}%"></i></div>`).join("")}<h4>Strongest links</h4><div class="connections">${edges.map(e=>{const sentiment=e.sentiment?.label||"not calculated";return `<div class="connection"><span>${e.source===n.id?e.target:e.source}</span><span class="sentiment ${sentiment.replace(" ","-")}">${sentiment}</span><b>${e.weight}</b></div>`}).join("")}</div>`;
}
function findPath(){
 const [start,end]=selected.map(n=>n.id), adjacency={};visibleNodes.forEach(n=>adjacency[n.id]=[]);
 visibleEdges.forEach(e=>{adjacency[e.source]?.push(e.target);adjacency[e.target]?.push(e.source)});
 const q=[[start]],seen=new Set([start]);let found=null;
 while(q.length){const p=q.shift(),last=p.at(-1);if(last===end){found=p;break}for(const x of adjacency[last]||[])if(!seen.has(x)){seen.add(x);q.push([...p,x])}}
 window.pathIds=found||[];document.querySelector("#path-result").textContent=found?`Shortest path (${found.length-1} hops): ${found.join("  →  ")}`:"No path under the current filters.";draw();
}
function buildInsights(){
 const bridge=[...data.nodes].filter(n=>n.type!=="character").sort((a,b)=>b.weightedDegree-a.weightedDegree)[0];
 document.querySelector("#bridge-title").textContent=`${bridge.id} is the strongest non-human bridge.`;
 document.querySelector("#bridge-copy").textContent=`With ${bridge.weightedDegree.toLocaleString()} weighted connections, it binds otherwise separate character circles together.`;
 const top=[...data.nodes].sort((a,b)=>b.weightedDegree-a.weightedDegree).slice(0,5),mx=top[0].weightedDegree;
 document.querySelector("#bridge-bars").innerHTML=top.map(n=>`<div class="bar"><div><span>${n.id}</span><b>${n.weightedDegree}</b></div><i style="width:${n.weightedDegree/mx*100}%"></i></div>`).join("");
 const communities={};data.nodes.forEach(n=>(communities[n.community]??=[]).push(n));
 const rankedCommunities=Object.entries(communities).sort((a,b)=>b[1].length-a[1].length),largest=rankedCommunities[0];
 const leaders=[...largest[1]].sort((a,b)=>b.weightedDegree-a.weightedDegree).slice(0,3).map(n=>n.id);
 document.querySelector("#community-title").textContent=`Community ${largest[0]} contains ${largest[1].length} of ${data.nodes.length} entities.`;
 document.querySelector("#community-copy").textContent=`Its strongest representatives are ${leaders.join(", ")}. Louvain groups entities whose weighted connections are denser with each other than with the rest of the graph.`;
 document.querySelector("#community-bars").innerHTML=rankedCommunities.slice(0,5).map(([id,nodes])=>`<div class="bar"><div><span>Community ${id}</span><b>${nodes.length}</b></div><i style="width:${nodes.length/largest[1].length*100}%;background:${COMMUNITY_COLORS[(id-1)%COMMUNITY_COLORS.length]}"></i></div>`).join("");
 const sentimentCounts={positive:0,neutral:0,negative:0};let sentimentTotal=0;
 data.edges.forEach(e=>{sentimentCounts[e.sentiment.label]++;sentimentTotal+=e.sentiment.score});
 const mean=sentimentTotal/data.edges.length,dominant=Object.entries(sentimentCounts).sort((a,b)=>b[1]-a[1])[0];
 document.querySelector("#sentiment-title").textContent=`The network’s emotional balance is ${mean>=0?"slightly positive":"slightly negative"}.`;
 document.querySelector("#sentiment-copy").textContent=`The mean VADER context score is ${mean.toFixed(3)}. ${dominant[1]} of ${data.edges.length} relations are ${dominant[0]}; this describes shared paragraph context, not how entities feel about each other.`;
 const sentimentMax=Math.max(...Object.values(sentimentCounts));
 document.querySelector("#sentiment-bars").innerHTML=Object.entries(sentimentCounts).map(([label,count])=>`<div class="bar ${label}"><div><span>${label}</span><b>${count}</b></div><i style="width:${count/sentimentMax*100}%"></i></div>`).join("");
 const pair=["Dobby","Lord Voldemort"];document.querySelector("#pair-title").textContent=`${pair[0]} and ${pair[1]} are only a few steps apart.`;
 document.querySelector("#pair-copy").textContent="Use the graph’s path finder to see which shared narrative bridges connect two very different figures.";
 document.querySelector("#show-pair").onclick=()=>{selected=pair.map(id=>data.nodes.find(n=>n.id===id));filters.character=true;document.querySelectorAll("[data-type]").forEach(x=>{x.checked=true;filters[x.dataset.type]=true});document.querySelector("#search").value="";update();findPath();renderDetail(selected[1]);location.hash="explore"};
}
document.querySelector("#search").oninput=update;document.querySelector("#weight").oninput=e=>{document.querySelector("#weight-output").textContent=e.target.value;selected=[];update()};
document.querySelector("#degree").oninput=e=>{document.querySelector("#degree-output").textContent=e.target.value;selected=[];update()};
document.querySelector("#community-mode").onchange=draw;
document.querySelector("#distance-root").onchange=e=>{selected=[];window.pathIds=[];if(e.target.value){const node=data.nodes.find(n=>n.id===e.target.value);selected=[node];renderDetail(node)}update()};
document.querySelector("#distance").onchange=update;
document.querySelector("#clear-distance").onclick=()=>{document.querySelector("#distance-root").value="";selected=[];window.pathIds=[];document.querySelector("#path-result").textContent="";update()};
document.querySelector("#all-types").onclick=()=>{document.querySelectorAll("[data-type]").forEach(x=>x.checked=filters[x.dataset.type]=true);update()};
document.querySelector("#reset").onclick=()=>{scale=1;pan={x:0,y:0};selected=[];window.pathIds=[];document.querySelector("#distance-root").value="";document.querySelector("#search").value="";update()};
document.querySelector("#zoom-in").onclick=()=>{scale=Math.min(2.5,scale*1.2);draw()};document.querySelector("#zoom-out").onclick=()=>{scale=Math.max(.45,scale*.8);draw()};
window.onresize=draw;
