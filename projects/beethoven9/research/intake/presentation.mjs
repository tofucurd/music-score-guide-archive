// Presentation-only first movement entrance. Audio, q, x and highlights stay exact.
import fs from 'node:fs';

export function attachPresentationSpec(spec, mode) {
  if (mode === 'cover') return;
  const policy=JSON.parse(fs.readFileSync(new URL('../../content/presentation.json',import.meta.url),'utf8'));
  for(const scene of spec.scenes||[spec]) {
    if(scene.movement_label===policy.opening.movement_label)scene.presentation=policy.opening;
  }
}

// Serialized into Chromium along with the native actor; no DOM or clock changes.
export function openingState(state, policy) {
  if(!policy || state.seconds>=policy.duration_seconds || state.seconds<0)return state;
  const t=Math.max(0,Math.min(1,state.seconds/policy.duration_seconds));
  const phase=policy.initial_phase+(1-policy.initial_phase)*t;
  const cap=phase*phase*phase*(10+phase*(-15+6*phase));
  return {...state,weights:Object.fromEntries(Object.entries(state.weights).map(([id,w])=>[id,Math.min(w,cap)]))};
}
