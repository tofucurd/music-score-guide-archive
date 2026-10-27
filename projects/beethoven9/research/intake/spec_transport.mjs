// Transport only. Join + JSON.parse restores the complete native scene verbatim.
export function specChunks(spec, maxCharacters=2*1024*1024) {
  if (!Number.isInteger(maxCharacters)||maxCharacters<1) throw Error('Invalid chunk size');
  const serialized=JSON.stringify(spec), chunks=[];
  for(let offset=0;offset<serialized.length;offset+=maxCharacters) chunks.push(serialized.slice(offset,offset+maxCharacters));
  return chunks;
}
