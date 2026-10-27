/** Native beamSpan rigid beam translation + exact stem-end correction.
 * All coordinates are frozen canonical-world coordinates; do not mix getBBox local units.
 * Caller owns storage-row translation and per-note display-row override.
 */
export function solveBeamSpan(stems, rowDeltas, {minimumStem=240, preferredDelta}={}) {
 if (!stems.length) throw Error('beamSpan has no resolved stems');
 let lower=-Infinity, upper=Infinity;
 for(const s of stems){
  const d=Math.sign(s.endY-s.headY);
  if(!d || !Number.isFinite(rowDeltas[s.staff]))throw Error('Invalid native stem/staff '+s.id);
  const bound=s.headY+rowDeltas[s.staff]-s.endY+d*minimumStem;
  if(d>0)lower=Math.max(lower,bound);else upper=Math.min(upper,bound);
 }
 if(lower>upper)throw Error('beamSpan requires larger staff/annotation gap: no positive native stem solution '+JSON.stringify({lower,upper,minimumStem}));
 const preferred=preferredDelta??stems.reduce((a,s)=>a+rowDeltas[s.staff],0)/stems.length;
 const beamDelta=Math.max(lower,Math.min(upper,preferred));
 const transforms=stems.map(s=>{
  const noteDelta=rowDeltas[s.staff], k=(s.endY+beamDelta-s.headY-noteDelta)/(s.endY-s.headY);
  if(!(k>0) || !Number.isFinite(k))throw Error('Inverted/invalid stem '+s.id);
  // Stem inherits its note display delta. This LOCAL matrix fixes the head anchor
  // while moving the beam end to the rigidly translated original beam polygon.
  const y=(1-k)*s.headY;
  const actualEnd=k*s.endY+y+noteDelta, expectedEnd=s.endY+beamDelta;
  const actualHead=k*s.headY+y+noteDelta, expectedHead=s.headY+noteDelta;
  return {id:s.id,k,y,matrix:[1,0,0,k,0,y],headResidual:actualHead-expectedHead,endResidual:actualEnd-expectedEnd};
 });
 return {beamDelta,transforms,minimumStem,feasibleInterval:[lower,upper]};
}

/** Apply only to measure-level beamSpan, which has NO inherited staff transform.
 * polygon/path leaf original transforms are retained after canonical-world translation.
 * Deduplicate chord stems before calling. A stem shared by two connectors must be
 * solved as a joined connector component, never last-write-wins.
 */
export function applyBeamSpan(span, rowDeltas, options={}) {
 const solved=solveBeamSpan(span.stems,rowDeltas,options);
 for(const p of span.polygons)p.e.setAttribute('transform',`translate(0 ${solved.beamDelta}) ${p.original??''}`);
 const byId=new Map(solved.transforms.map(s=>[s.id,s]));
 for(const s of span.stems){const t=byId.get(s.id);s.e.setAttribute('transform',`matrix(${t.matrix.join(' ')}) ${s.original??''}`);}
 span.e.style.opacity=1-span.rows.reduce((a,n)=>a*(1-(options.weights?.[n]??1)),1);
 return solved;
}
