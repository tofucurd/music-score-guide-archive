// Freeze domains by actual onset / tie-extended end / envelope version, never by
// coincident instantaneous alpha. Source UUID/theme membership is unchanged.
export function groupPresence(members,highlights,domains){
 const values=new Map();
 for(const n of members){if(n.enabled===false)continue;const a=Math.max(0,Math.min(1,highlights[n.id]??0));if(!a)continue;
  const domain=domains?.[n.id];if(typeof domain!=='string'||!domain)throw Error('Missing highlight domain '+n.id);
  if(values.has(domain)&&Math.abs(values.get(domain)-a)>1e-10)throw Error('Inconsistent alpha in frozen highlight domain '+domain);
  values.set(domain,a);
 }
 let inactive=1;for(const a of values.values())inactive*=1-a;return 1-inactive;
}
