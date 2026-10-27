// Painted text extents, not SVG's font line box. Source positions/font stay intact.
const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
function mapped(e,world,b){
 const m=world.getScreenCTM().inverse().multiply(e.getScreenCTM());
 return [[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]].map(([x,y])=>new DOMPoint(x,y).matrixTransform(m));
}
function union(points){
 if(!points.length)return {x:0,y:0,width:0,height:0};
 const x=Math.min(...points.map(p=>p.x)),y=Math.min(...points.map(p=>p.y));
 return {x,y,width:Math.max(...points.map(p=>p.x))-x,height:Math.max(...points.map(p=>p.y))-y};
}
function textInk(text,world){
 const leaves=[text,...text.querySelectorAll('tspan')].filter(e=>!e.querySelector('tspan')&&e.textContent.trim());
 const points=[];
 for(const leaf of leaves){
  const chars=[...leaf.textContent],n=leaf.getNumberOfChars();
  // Preserve a conservative native bound for unsupported text layout. Never clip.
  if(n!==chars.length||/f[fil]/i.test(leaf.textContent)){points.push(...mapped(leaf,world,leaf.getBBox()));continue;}
  const style=getComputedStyle(leaf);ctx.font=`${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  for(let i=0;i<n;i++){
   const p=leaf.getStartPositionOfChar(i),m=ctx.measureText(chars[i]);
   const ctm=world.getScreenCTM().inverse().multiply(leaf.getScreenCTM());
   const rotation=leaf.getRotationOfChar(i)*Math.PI/180;
   for(const [x,y]of [[-m.actualBoundingBoxLeft,-m.actualBoundingBoxAscent],[m.actualBoundingBoxRight,-m.actualBoundingBoxAscent],[-m.actualBoundingBoxLeft,m.actualBoundingBoxDescent],[m.actualBoundingBoxRight,m.actualBoundingBoxDescent]]){
    points.push(new DOMPoint(p.x+x*Math.cos(rotation)-y*Math.sin(rotation),p.y+x*Math.sin(rotation)+y*Math.cos(rotation)).matrixTransform(ctm));
   }
  }
 }
 // A mixed text parent can hold direct text outside tspan children.
 for(const ancestor of [text,...text.querySelectorAll('tspan')])if(ancestor.querySelector('tspan')&&[...ancestor.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))points.push(...mapped(ancestor,world,ancestor.getBBox()));
 return union(points);
}
export function inkBox(e,world){
 if(e.tagName==='text')return textInk(e,world);
 if(!e.querySelector('text'))return union(mapped(e,world,e.getBBox()));
 const points=[];
 for(const c of e.children){if(['defs','style','title','desc'].includes(c.tagName))continue;const b=inkBox(c,world);if(b.width||b.height)points.push({x:b.x,y:b.y},{x:b.x+b.width,y:b.y+b.height});}
 return union(points);
}
