import {collector,applyClusters} from './note_ink_parts_stroke.mjs';
// Native notation remains vector geometry. Each measure/event has one identity.
import {solveBeamSpan,applyBeamSpan} from './beamspan_connector.mjs';
import {inkBox} from './ink_bounds.mjs';
import {resolveInk} from './head_ink.mjs';
const SVG='http://www.w3.org/2000/svg';
const rootURL='/';
const load=async path=>{const r=await fetch(rootURL+path);if(!r.ok)throw Error('Missing '+path);return r.json();};
const text=async path=>{const r=await fetch(rootURL+path);if(!r.ok)throw Error('Missing '+path);return r.text();};
const need=(x,m)=>{if(!x)throw Error(m);};
const create=(tag,attrs={})=>{const e=document.createElementNS(SVG,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;};
const box=inkBox;
const html=s=>new DOMParser().parseFromString(s,'image/svg+xml').documentElement;
const moves=new Map();
const set=(e,k,v)=>{v=String(v);if(e.getAttribute(k)!==v)e.setAttribute(k,v);};
const palette={main:'#C94732',purple:'#8650B6',green:'#27835D',ochre:'#AA7200'};
const rgb=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
const blend=(hex,a)=>{const c=rgb(hex);return `rgb(${c.map(v=>Math.round(v*a)).join(',')})`;};

async function prepare(m){
 if(moves.has(m))return moves.get(m);
 const meta=await load(`work/score-sync-02/canonical/M${m}/source.json`),data=await load(meta.data);
 const [defs,css,system,...bodies]=await Promise.all([text(meta.defs),text(meta.style),text(meta.system),...meta.measures.map(a=>text(a.svg))]);
 const scene=create('svg',{id:meta.root_id,x:0,y:0,width:3840,height:1834,viewBox:'0 0 3840 1834',overflow:'hidden','font-family':'ScoreTimes',color:'black'});
 scene.append(html(defs));const style=create('style');style.textContent=css;scene.append(style);
 const world=create('g');world.append(html(system));for(const body of bodies)world.append(html(body));const clip=create('g',{'clip-path':'url(#score-clip)'});clip.append(world);scene.append(clip);document.querySelector('#scenes').append(scene);
 for(const e of scene.querySelectorAll('[font-family="Times, serif"]'))e.setAttribute('font-family','ScoreTimes');
 for(const e of scene.querySelectorAll('tspan'))if(!e.children.length&&/[\ue000-\uf8ff]/.test(e.textContent))e.setAttribute('font-family','Leland');
 await document.fonts.ready;
 const nodes=new Map([...scene.querySelectorAll('[data-native-id]')].map(e=>[e.getAttribute('data-native-id'),e]));
 const notesByNative=new Map(data.notes.map(n=>[n.engraver_id,n])),noteBoxes={},staffs=[],controls=[],beams=[],measures=[];
 const refs=meta.controls;
 // Source-native geometry is measured before any animation transform exists.
 for(const n of data.notes){const e=nodes.get(n.engraver_id),h=e?.querySelector('.notehead');if(!h)continue;const b=box(h,world);noteBoxes[n.engraver_id]={...b,staff:n.staff,storage:n.storage_staff,id:n.id};}
 const staffOf=e=>e.closest('g.staff')?.getAttribute('data-row')??null;
 for(const descriptor of meta.measures){const e=nodes.get(descriptor.id);need(e,'Native measure absent '+descriptor.id);const b=box(e,world),record={e,b,raw:descriptor.raw,staffs:[],notes:[],controls:[],beams:[],bars:[]};
  for(const row of descriptor.staves){const g=nodes.get(row.id);need(g,'Native staff absent '+row.id);g.setAttribute('data-row',row.n);const item={e:g,n:row.n,sourceY:row.center,b:box(g,world)};record.staffs.push(item);staffs.push(item);}
  for(const n of [...e.querySelectorAll('g.note')]){const key=n.getAttribute('data-native-id'),source=notesByNative.get(key);if(!source)continue;const h=n.querySelector('.notehead');record.notes.push({e:n,h,n:source,stem:n.querySelector('g.stem'),head:noteBoxes[key],originalTransform:n.getAttribute('transform')??'',sourceVisible:!!h&&source.visible!==false&&getComputedStyle(h).visibility!=='hidden'&&getComputedStyle(h).display!=='none'});}
  measures.push(record);
 }
 function anchor(id){
  if(noteBoxes[id]){const b=noteBoxes[id];return {x:b.x+b.width/2,y:b.y+b.height/2,staff:b.staff};}
  const ref=refs[id];if(ref?.notes?.length)return anchor(ref.notes[0]);
  const e=nodes.get(id);if(!e)return null;const b=box(e,world),n=ref?.staffs?.[0]??staffOf(e);return n?{x:b.x+b.width/2,y:b.y+b.height/2,staff:n}:null;
 }
 const unknown=[],spans=[];
 for(const record of measures){
  for(const e of [...record.e.children]){
   const cls=e.getAttribute('class')??'';if(cls==='staff')continue;
   if(cls==='barLine'){
    for(const leaf of e.querySelectorAll('path,polygon,polyline')){const b=box(leaf,world);const rows=Object.keys(meta.centers).filter(n=>meta.centers[n]>=b.y-400&&meta.centers[n]<=b.y+b.height+400).sort((a,b)=>+a-+b);if(!rows.length){unknown.push({cls:'generated-bar',raw:record.raw,b});continue;}record.bars.push({e:leaf,b,rows,original:leaf.getAttribute('transform')??''});}
    continue;
   }
   if(cls==='mNum'){e.style.display='none';continue;}
   const id=e.getAttribute('data-native-id'),ref=refs[id];
   if(!ref){unknown.push({id,cls,raw:record.raw});continue;}
   if(cls==='beamSpan')continue;
   const start=ref.start?anchor(ref.start):null,end=ref.end?anchor(ref.end):null;
   let rows=ref.staffs.filter(n=>meta.centers[n]!==undefined);
   const global=cls==='tempo'||cls==='reh';
   if(!rows.length&&!global){unknown.push({id,cls,raw:record.raw,reason:'no source staff'});continue;}
   const b=box(e,world),item={e,id,cls,rows,start,end,b,global,original:e.getAttribute('transform')??''};record.controls.push(item);controls.push(item);
  }
  for(const e of record.e.querySelectorAll('g.beam')){
   const id=e.getAttribute('data-native-id'),ref=refs[id];if(!ref)continue;
   const row=staffOf(e),members=[...e.querySelectorAll('g.note')].filter(n=>n.closest('g.beam')===e).map(n=>{const key=n.getAttribute('data-native-id'),head=noteBoxes[key];return {e:n,key,head,stem:n.querySelector('g.stem')};}).filter(n=>n.head);
   if(new Set(members.map(n=>n.head.staff)).size<2)continue;
   const polygons=[...e.children].filter(n=>['polygon','path','polyline'].includes(n.tagName));
   const b=box(e,world),rows=[...new Set(members.map(n=>n.head.staff))];const nativeBeam=polygons[0]?box(polygons[0],world):b;const at=rows.reduce((a,n)=>Math.abs(meta.centers[n]-nativeBeam.y)<Math.abs(meta.centers[a]-nativeBeam.y)?n:a,rows[0]);
   const beam={e,id,row,members,polygons,at,b,rows};record.beams.push(beam);beams.push(beam);
   for(const member of members)if(member.stem){const s=box(member.stem,world),h=member.head.y+member.head.height/2;member.stemAnchor=Math.abs(s.y-h)<Math.abs(s.y+s.height-h)?s.y:s.y+s.height;member.stemEnd=member.stemAnchor===s.y?s.y+s.height:s.y;need(Math.abs(member.stemEnd-member.stemAnchor)>1,'Invalid native stem '+member.key);}
  }
 }
 // Measure-level beamSpan has no inherited staff translation. Resolve every
 // member in its source voice, including intermediate notes and next measures.
 const connectorStems=new Map();
 for(const [id,ref]of Object.entries(refs)){
  if(ref.tag!=='beamSpan')continue;
  const e=nodes.get(id);need(e,'Missing beamSpan '+id);
  const stems=[],seen=new Set();
  for(const key of ref.notes){
   const note=nodes.get(key),head=noteBoxes[key];need(note&&head,'Missing beamSpan member '+key);
   const stem=note.querySelector('g.stem')??note.closest('g.chord')?.querySelector('g.stem');need(stem,'Missing beamSpan stem '+key);
   if(seen.has(stem))continue;seen.add(stem);
   need(!connectorStems.has(stem),'Overlapping independent beamSpan stems '+key);connectorStems.set(stem,id);
   const b=box(stem,world),h=head.y+head.height/2,headY=Math.abs(b.y-h)<Math.abs(b.y+b.height-h)?b.y:b.y+b.height,endY=headY===b.y?b.y+b.height:b.y;
   stems.push({id:key,e:stem,headY,endY,staff:head.staff,original:stem.getAttribute('transform')??''});
  }
  const polygons=[...e.querySelectorAll('polygon,path,polyline')].map(p=>({e:p,original:p.getAttribute('transform')??''}));need(polygons.length,'beamSpan has no native beam '+id);
  spans.push({id,e,b:box(e,world),stems,polygons,rows:ref.staffs});
 }
 // Native system labels are replaced with explicit fixed Han labels; braces and
 // system rule remain source-owned generated geometry and get endpoint transforms.
 const systemLayer=world.firstElementChild,generated=[];
 for(const e of systemLayer.children){const cls=e.getAttribute('class')??'';
  if(cls==='label'||cls==='labelAbbr'){e.style.display='none';continue;}
  const b=box(e,world),rows=Object.keys(meta.centers).filter(n=>meta.centers[n]>=b.y-500&&meta.centers[n]<=b.y+b.height+500).sort((a,b)=>+a-+b);
  if(rows.length)generated.push({e,b,rows,original:e.getAttribute('transform')??''});
  else if(b.width||b.height)unknown.push({cls,reason:'unowned generated system geometry',b});
 }
 const cols=new Map();
 for(const p of data.grid){if(p.grace)continue;const e=nodes.get(p.id);if(!e||e.classList.contains('mRest'))continue;const h=e.querySelector('.notehead')??(e.classList.contains('rest')?e:null);if(!h)continue;const b=box(h,world);if(!b.width)continue;const prior=cols.get(p.q);if(prior===undefined||b.x<prior)cols.set(p.q,b.x);}
 for(const descriptor of meta.measures){if(!cols.has(descriptor.q[0])){const e=nodes.get(descriptor.id).querySelector('g.staff>path');cols.set(descriptor.q[0],box(e,world).x+200);}}
 const last=meta.measures.at(-1),lastBar=nodes.get(last.id).querySelector('g.barLine');if(lastBar)cols.set(last.q[1],box(lastBar,world).x);
 const geometry={movement:m,axis:[...cols].sort((a,b)=>a[0]-b[0]),note_boxes:noteBoxes,measure_boxes:measures.map(a=>({raw:a.raw,...a.b})),staff_boxes:measures.flatMap(a=>a.staffs.map(s=>({raw:a.raw,n:s.n,center:s.sourceY,...s.b,cross_staff_members:a.notes.filter(i=>i.n.storage_staff===s.n&&i.n.staff!==s.n).map(i=>i.n.engraver_id)}))),control_boxes:measures.flatMap(a=>a.controls.map(c=>({raw:a.raw,id:c.id,rows:c.rows,global:c.global,...c.b}))),unknown,counts:{measures:measures.length,notes:Object.keys(noteBoxes).length,cross_staff_beams:beams.length,beam_spans:spans.length,controls:controls.length}};
 const noteInk=collector(world,notesByNative,measures.flatMap(r=>r.notes),{protectedStems:new Set(connectorStems.keys())});geometry.note_ink_audit=noteInk.audit;
 need(!noteInk.audit.unresolved.length,'Unresolved printed note parts '+JSON.stringify(noteInk.audit.unresolved.slice(0,10)));
 need(!unknown.length,'Native ownership unknown '+JSON.stringify(unknown.slice(0,10)));
 // One compositing layer per musical staff, not per staff per measure.
 // Every source glyph stays the same node with its frozen canonical coordinates.
 const rowLayer=create('g'),controlLayer=create('g'),rowHolders=new Map();
 for(const n of Object.keys(meta.centers).sort((a,b)=>+a-+b)){const holder=create('g',{'data-owner-row':n});rowLayer.append(holder);rowHolders.set(n,holder);}
 for(const record of measures){
  record.chunks=new Map();
  for(const row of record.staffs){const chunk=create('g',{'data-owner-measure':record.raw,'data-owner-row':row.n});chunk.append(row.e);record.chunks.set(row.n,chunk);}
  for(const item of record.controls)if(!item.global&&item.rows.length===1&&record.chunks.has(item.rows[0])){item.rowOwned=item.rows[0];record.chunks.get(item.rowOwned).append(item.e);}
  controlLayer.append(record.e);
 }
 world.append(rowLayer,controlLayer);
 const headClusters=new Map();
 for(const record of measures)for(const item of record.notes){if(!item.h||!item.head)continue;
  const h=item.head,glyphs=[...item.h.querySelectorAll('use')].map(e=>e.getAttribute('href')??e.getAttributeNS('http://www.w3.org/1999/xlink','href')).join('|');
  const key=[item.n.staff,item.n.q,glyphs,...[h.x,h.y,h.width,h.height].map(x=>x.toFixed(5))].join('/');
  if(!headClusters.has(key))headClusters.set(key,[]);const cluster=headClusters.get(key);cluster.push({id:item.n.id,h:item.h,enabled:item.sourceVisible});item.inkCluster=cluster;
 }
 const labelLayer=create('g',{'font-family':'Han','font-size':22,fill:'#263c41'});scene.append(labelLayer);
 const labelNodes=new Map();for(const label of meta.labels){const t=create('text',{x:348,'text-anchor':'end','dominant-baseline':'middle'});labelLayer.append(t);labelNodes.set(label.id,t);}
 const actor={m,meta,data,scene,world,nodes,noteBoxes,measures,generated,spans,rowLayer,controlLayer,rowHolders,labelLayer,labelNodes,headClusters,noteInk,geometry};moves.set(m,actor);return actor;
}

function apply(actor,p){
 const {meta,world,noteBoxes}=actor,{scale,rows,weights}=p.layout,dy={},visibleInk=new Set();
 for(const [n,y]of Object.entries(meta.centers))dy[n]=(rows[n]??0)/scale-y;
 const offset=p.offset??0;set(world,'transform',`matrix(${scale} 0 0 ${scale} ${1344-scale*p.x+offset} 0)`);
 actor.scene.style.opacity=p.opacity??1;
 const visibleLeft=(380-1344-offset)/scale+p.x,visibleRight=(3730-1344-offset)/scale+p.x;
 let previousMeasure=null;const previousRows=new Map();
 const place=(parent,e,previous)=>{const next=previous?previous.nextSibling:parent.firstChild;if(next!==e)parent.insertBefore(e,next);};
 for(const[n,holder]of actor.rowHolders){set(holder,'transform',`translate(0 ${dy[n]??0})`);set(holder,'opacity',weights[n]??0);}
 const weight=ns=>1-ns.reduce((v,n)=>v*(1-(weights[n]??0)),1);
 const shift=ns=>{const total=ns.reduce((a,n)=>a+(weights[n]??0),0);return total?ns.reduce((a,n)=>a+(dy[n]??0)*(weights[n]??0),0)/total:(dy[ns[0]]??0);};
 for(const record of actor.measures){
  const visible=record.b.x+record.b.width>=visibleLeft&&record.b.x<=visibleRight;
  if(!visible){record.e.remove();for(const chunk of record.chunks.values())chunk.remove();continue;}
  place(actor.controlLayer,record.e,previousMeasure);previousMeasure=record.e;
  for(const[n,chunk]of record.chunks){if(!(weights[n]>0)){chunk.remove();continue;}const holder=actor.rowHolders.get(n);place(holder,chunk,previousRows.get(n));previousRows.set(n,chunk);}
  for(const item of record.notes){const {n,e,h,head}=item;if(n.staff!==n.storage_staff)set(e,'transform',`translate(0 ${(dy[n.staff]??0)-(dy[n.storage_staff]??0)}) ${item.originalTransform}`);
   if(h)visibleInk.add(item.inkCluster);
  }
  for(const item of record.controls){
   if(item.rowOwned)continue;
   const w=item.global?1:weight(item.rows);item.e.style.opacity=w;
   if(item.global){const desired=42;set(item.e,'transform',`translate(0 ${desired/scale-item.b.y}) ${item.original}`);}
   else if(item.start&&item.end&&Math.abs(item.end.x-item.start.x)>1&&item.start.staff!==item.end.staff){const a=dy[item.start.staff]??0,b=dy[item.end.staff]??0,k=(b-a)/(item.end.x-item.start.x);set(item.e,'transform',`matrix(1 ${k} 0 1 0 ${a-k*item.start.x}) ${item.original}`);}
   else set(item.e,'transform',`translate(0 ${shift(item.rows)}) ${item.original}`);
  }
  for(const beam of record.beams){
   if(beam.b.x+beam.b.width<visibleLeft||beam.b.x>visibleRight||weight(beam.rows)<=1e-9)continue;
   const stems=beam.members.filter(n=>n.stem).map(n=>({id:n.key,headY:n.stemAnchor,endY:n.stemEnd,staff:n.head.staff}));
   const solved=solveBeamSpan(stems,dy,{preferredDelta:dy[beam.at]??0});
   for(const poly of beam.polygons)set(poly,'transform',`translate(0 ${solved.beamDelta-(dy[beam.row]??0)})`);
   const transforms=new Map(solved.transforms.map(t=>[t.id,t]));
   for(const n of beam.members)if(n.stem){const t=transforms.get(n.key);set(n.stem,'transform',`matrix(${t.matrix.join(' ')})`);}
  }
  for(const item of record.bars)applyGenerated(item,dy,weights,meta.centers);
 }
 for(const cluster of visibleInk){const color=resolveInk(cluster,p.highlights??{},p.colors??{});for(const member of cluster){if(member.h.style.color!==color)member.h.style.color=color;if(member.h.style.fill!==color)member.h.style.fill=color;}}
 applyClusters(actor.noteInk.clusters.filter(c=>c.elements.some(e=>e.isConnected)),p.highlights??{},p.colors??{},resolveInk,{scale,domains:p.domains});
 for(const span of actor.spans){const visible=span.b.x+span.b.width>=visibleLeft&&span.b.x<=visibleRight,w=weight(span.rows);if(visible&&w>1e-9)applyBeamSpan(span,dy,{weights});else span.e.style.opacity=0;}
 for(const item of actor.generated)applyGenerated(item,dy,weights,meta.centers);
 for(const label of meta.labels){const t=actor.labelNodes.get(label.id),ns=label.rows.filter(n=>(weights[n]??0)>0);t.style.display=ns.length?'':'none';if(!ns.length)continue;const y=ns.reduce((a,n)=>a+rows[n]*(weights[n]??0),0)/ns.reduce((a,n)=>a+(weights[n]??0),0),w=weight(ns);set(t,'y',y);set(t,'opacity',w);const caption=p.translations?.[`M${actor.m}:${label.id}`]??p.translations?.[label.abbr]??p.translations?.[label.text]??label.text;if(t.textContent!==caption)t.textContent=caption;}
 return {visible_measures:actor.measures.filter(a=>a.e.parentNode===actor.controlLayer).length};
}
function applyGenerated(item,dy,weights,centers){
 const presence=1-item.rows.reduce((v,n)=>v*(1-(weights[n]??0)),1);item.e.style.opacity=presence;if(presence<1e-9)return;
 function edge(order){let remaining=1,total=0;for(const n of order){const probability=remaining*(weights[n]??0);total+=probability*(centers[n]+(dy[n]??0));remaining*=1-(weights[n]??0);}return total/presence;}
 const ya=item.b.y,yb=ya+item.b.height;
 const targetA=edge(item.rows)+ya-centers[item.rows[0]],targetB=edge([...item.rows].reverse())+yb-centers[item.rows.at(-1)];
 const k=Math.abs(yb-ya)>1?(targetB-targetA)/(yb-ya):1;
 set(item.e,'transform',`matrix(1 0 0 ${k} 0 ${targetA-k*ya}) ${item.original}`);
}

window.nativePrepare=prepare;
window.nativeGeometry=async m=>(await prepare(m)).geometry;
window.nativeFrame=async spec=>{
 const started=performance.now();
 for(const actor of moves.values())actor.scene.style.display='none';
 for(const p of spec.scenes){const actor=await prepare(p.movement);actor.scene.style.display='';apply(actor,p);}
 document.querySelector('#navigation').innerHTML=spec.navigation??'';
 const line=document.querySelector('#reading-line');set(line,'y1',spec.cursor?.[0]??50);set(line,'y2',spec.cursor?.[1]??1810);line.style.opacity=spec.cursor_opacity??1;
 const applied=performance.now();await document.fonts.ready;if(spec.sync_capture)document.querySelector('#frame').getBBox();else await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
 return {ready:true,apply_ms:applied-started,paint_wait_ms:performance.now()-applied,hidden:document.hidden,visibility:document.visibilityState};
};

window.nativePositions=()=>[...moves.values()].filter(a=>a.scene.style.display!=='none').map(a=>({movement:a.m,notes:a.measures.flatMap(r=>r.notes.filter(n=>n.h?.isConnected).map(n=>{const b=n.h.getBoundingClientRect();return {id:n.n.id,enabled:n.sourceVisible,x:b.x,y:b.y,width:b.width,height:b.height,color:n.h.style.color}})),controls:a.measures.flatMap(r=>r.controls.filter(c=>c.e.isConnected).map(c=>{const b=c.e.getBoundingClientRect();return{id:c.id,x:b.x,y:b.y,width:b.width,height:b.height}}))}));
