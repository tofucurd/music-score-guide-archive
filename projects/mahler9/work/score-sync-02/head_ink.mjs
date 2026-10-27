// A shared printed notehead has one visible ink outcome, independent of native
// SVG paint order. This does NOT expand any event's semantic theme membership.
const MAIN='#C94732',priority={'#C94732':0,'#AA7200':1,'#27835D':2,'#8650B6':3};
const cache=new Map();const rgb=h=>{if(!cache.has(h))cache.set(h,[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)));return cache.get(h);};
export function resolveInk(members,highlights,colors){
 let alpha=0;const materials=new Map();
 for(const n of members){if(n.enabled===false)continue;const a=Math.min(1,Math.max(0,highlights[n.id]??0));alpha=Math.max(alpha,a);const c=colors[n.id];if(c&&a)materials.set(c,Math.max(materials.get(c)??0,a));}
 if(!alpha)return 'rgb(0, 0, 0)';
 let result=rgb(MAIN).map(v=>v*alpha);
 // Palette priority is permanent, never UUID/instrument/current paint order.
 for(const [c,a]of [...materials].sort((x,y)=>(priority[x[0]]??0)-(priority[y[0]]??0)||x[0].localeCompare(y[0]))){const k=a/alpha;result=result.map((v,i)=>v*(1-k)+rgb(c)[i]*a);}
 return `rgb(${result.map(Math.round).join(', ')})`;
}
