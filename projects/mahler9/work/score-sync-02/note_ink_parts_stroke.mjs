import {groupPresence} from './ink_presence.mjs';
// Collect native printed ink, never source-theme membership. Call BEFORE reparent
// or animation. Glyph paths and transforms stay fixed; active straight stems
// receive the explicit, reversible screen-space stroke emphasis below.
const KINDS=['stem','flag','dots'],SELECTOR=KINDS.map(k=>'g.'+k).join(',');
const primitive=e=>['path','use','ellipse','polygon','polyline','circle','rect'].includes(e.localName);
const nativeId=e=>e.getAttribute('data-native-id')??e.getAttribute('id')??'';
const unique=xs=>[...new Set(xs)];
const number=v=>Number.isFinite(v)?Math.round(v*1e9)/1e9:null;
function geometry(leaf,world){
 const c=leaf.getCTM(),w=world.getCTM();if(!c||!w)throw Error('Detached or nonrendered CTM');
 const t=w.inverse().multiply(c),matrix=['a','b','c','d','e','f'].map(k=>number(t[k]));
 if(matrix.some(x=>x===null))throw Error('Nonfinite native CTM');
 const attrs=[...leaf.attributes].filter(a=>!['id','data-native-id','class'].includes(a.name)).map(a=>[a.name,a.value]).sort((a,b)=>a[0].localeCompare(b[0]));
 return JSON.stringify([leaf.localName,attrs,matrix]);
}
export function collector(world,notesByNative,recordNotes,options={}){
 const records=Array.isArray(recordNotes)?recordNotes:[...recordNotes.values()];
 const recordById=new Map(records.map(r=>[r.n?.id??r.id,r]));
 const groups=new Map(),geometricMotions=new Map();
 const audit={counts:{stem:0,flag:0,dots:0},restDots:0,unresolved:[],motionDivergences:[],sharedChordParts:0,primitiveLeaves:0};
 const ownerNotes=owner=>{
  const es=owner.matches('g.note')?[owner]:[...owner.querySelectorAll('g.note')];
  return es.map(e=>notesByNative.get(nativeId(e))).filter(Boolean);
 };
 for(const part of world.querySelectorAll(SELECTOR)){
  const kind=KINDS.find(k=>part.matches('g.'+k));const owner=part.closest('g.note,g.chord');
  if(!owner){
   if(kind==='dots'&&part.closest('g.rest,g.mRest,g.multiRest')){audit.restDots++;continue;}
   audit.unresolved.push({kind,native_id:nativeId(part),reason:'no nearest note/chord semantic owner'});continue;
  }
  const ns=ownerNotes(owner);if(!ns.length){audit.unresolved.push({kind,native_id:nativeId(part),reason:'semantic owner lacks source UUID notes'});continue;}
  const times=unique(ns.map(n=>n.q));const storage=unique(ns.map(n=>String(n.storage_staff))),display=unique(ns.map(n=>String(n.staff)));
  if(times.length!==1){audit.unresolved.push({kind,native_id:nativeId(part),reason:'chord members have different source onsets',source_ids:ns.map(n=>n.id)});continue;}
  const members=ns.map(n=>({id:n.id,enabled:recordById.get(n.id)?.sourceVisible===true}));
  const missing=ns.filter(n=>!recordById.has(n.id));if(missing.length){audit.unresolved.push({kind,native_id:nativeId(part),reason:'missing frozen sourceVisible record',source_ids:missing.map(n=>n.id)});continue;}
  let motion=owner.matches('g.note')?['staff',display[0]]:['staff',storage.length===1?storage[0]:storage];
  const beam=part.closest('g.beam'),beamNotes=beam?ownerNotes(beam):[];
  const dynamic=(kind!=='dots')&&(display.length>1||storage.length>1||unique(beamNotes.map(n=>n.staff)).length>1||options.protectedStems?.has(part)||options.protectedStems?.has(part.closest('g.stem')));
  if(dynamic){motion=['unmerged-dynamic-connector',nativeId(owner),nativeId(part)];audit.motionDivergences.push({kind,native_id:nativeId(part),source_ids:ns.map(n=>n.id),reason:'connector/chord may deform independently; no cross-element merge'});}
  if(options.motionKey)motion=options.motionKey({part,kind,owner,notes:ns,defaultMotion:motion,dynamic});
  audit.counts[kind]++;if(ns.length>1)audit.sharedChordParts++;
  for(const leaf of part.querySelectorAll('path,use,ellipse,polygon,polyline,circle,rect')){
   // A flag nested under a stem owns its leaves once, not again as stem ink.
   if(!primitive(leaf)||leaf.closest(SELECTOR)!==part)continue;
   let shape;try{shape=geometry(leaf,world);}catch(error){audit.unresolved.push({kind,native_id:nativeId(part),reason:String(error)});continue;}
   const spatial=JSON.stringify([kind,times[0],shape]),mk=JSON.stringify(motion),key=JSON.stringify([kind,times[0],shape,motion]);
   if(!geometricMotions.has(spatial))geometricMotions.set(spatial,new Set());geometricMotions.get(spatial).add(mk);
   if(!groups.has(key))groups.set(key,{kind,q:times[0],motion,shape,elements:[],parts:[],members:[],source_owner_ids:[]});
   const g=groups.get(key);g.elements.push(leaf);g.parts.push(leaf);g.members.push(...members);g.source_owner_ids.push(nativeId(owner));audit.primitiveLeaves++;
  }
 }
 const clusters=[...groups.values()];for(const g of clusters){g.elements=unique(g.elements);g.parts=g.elements;g.source_owner_ids=unique(g.source_owner_ids);const by=new Map();for(const n of g.members)by.set(n.id,{id:n.id,enabled:(by.get(n.id)?.enabled??false)||n.enabled});g.members=[...by.values()];}
 for(const [shape,motions]of geometricMotions)if(motions.size>1)audit.motionDivergences.push({reason:'same native primitive geometry has different motion identities; kept separate',shape,motions:[...motions]});
 audit.clusters=clusters.length;audit.sharedPhysicalClusters=clusters.filter(g=>g.members.length>1).length;
 return{clusters,partsclusters:clusters,audit};
}
export function stemWidth(native,scale,presence,minimum=1){
 if(!(native>0&&scale>0&&minimum>0))throw Error('Invalid stem metrics');
 const original=native*scale,target=Math.pow(Math.pow(original,12)+Math.pow(minimum,12),1/12);
 return (original+Math.max(0,Math.min(1,presence))*(target-original))/scale;
}
const sourceStyles=new WeakMap();
export function applyClusters(clusters,highlights,colors,resolveInk,paint={}){
 for(const c of clusters){const color=resolveInk(c.members,highlights,colors);const presence=groupPresence(c.members,highlights,paint.domains);
 for(const e of c.elements){if(e.style.color!==color)e.style.color=color;if(e.style.fill!==color)e.style.fill=color;
  if(c.kind!=='stem'||e.localName!=='path'||!e.parentElement.matches('g.stem')||!e.hasAttribute('stroke-width'))continue;
  const d=e.getAttribute('d')??'',values=d.match(/[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?/gi)?.map(Number);if(!/^\s*M[^MLCQAZVHST]*L[^MLCQAZVHST]*$/i.test(d)||values?.length!==4||Math.abs(values[0]-values[2])>1e-8)continue;
  if(!sourceStyles.has(e))sourceStyles.set(e,{width:e.style.strokeWidth,cap:e.style.strokeLinecap,native:+e.getAttribute('stroke-width')});const original=sourceStyles.get(e);
  const width=presence?String(stemWidth(original.native,paint.scale,presence)):original.width,cap=presence?'butt':original.cap;
  if(e.style.strokeWidth!==width)e.style.strokeWidth=width;if(e.style.strokeLinecap!==cap)e.style.strokeLinecap=cap;
 }
 }
}
