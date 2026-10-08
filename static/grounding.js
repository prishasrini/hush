/* Observations stay in memory. No sensors, storage or answer submissions. */
class GroundingMoment {
  constructor() { this.observations=0; this.promptIndex=0; this.resting=false; this.easy=false; }
  notice() { if(this.resting || this.complete)return false; this.observations++; this.promptIndex=(this.promptIndex+1)%3; return true; }
  alternate() { if(!this.resting && !this.complete)this.promptIndex=(this.promptIndex+1)%3; }
  get complete() { return this.observations>=3; }
}
if(typeof module!=='undefined')module.exports={GroundingMoment};
if(typeof document!=='undefined') {
  const prompts=[
    ['look around','Notice one colour near you.','Anything nearby is enough. You do not need to name it.'],
    ['notice a texture','Touch something nearby, if comfortable.','Notice how it feels. Your sleeve or a familiar object is enough.'],
    ['listen for a moment','Notice one sound around you.','Nearby or far away. If listening does not suit you, skip this prompt.']
  ];
  const easyPrompts=[
    ['one nearby thing','Look at one familiar object.','Notice just its colour. Nothing to type or remember.'],
    ['stay with that object','Notice one edge or curve on it.','There is no need to find anything else.'],
    ['one small detail','Notice where light falls on that object.','Take your time. You can finish here whenever you like.']
  ];
  const notice=document.getElementById('ground-notice'),alternate=document.getElementById('ground-alternate');
  const rest=document.getElementById('ground-rest'),restart=document.getElementById('ground-restart'),easy=document.getElementById('ground-easy');
  const sense=document.getElementById('ground-sense'),prompt=document.getElementById('ground-prompt'),detail=document.getElementById('ground-detail');
  const canvas=document.getElementById('ground-canvas'),layer=document.getElementById('paint-strokes');
  const undo=document.getElementById('paint-undo'),hint=document.getElementById('paint-hint'),status=document.getElementById('paint-status');
  let colour='#bca8f5', stroke=null, activePointer=null, points=[], ribbonIndex=0;
  const ns='http://www.w3.org/2000/svg';
  document.querySelectorAll('.paint-colour').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('.paint-colour').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    colour=button.dataset.colour;
    document.getElementById('paint-colour-name').textContent=`${button.dataset.name} selected`;
  }));
  function newStroke(width=15) {
    if(layer.children.length>=80) { status.textContent='Your canvas has lots of marks. Undo a mark to make room, or rest here.'; return null; }
    const path=document.createElementNS(ns,'path');path.setAttribute('stroke',colour);
    path.setAttribute('stroke-width',width);path.setAttribute('opacity','.82');
    layer.appendChild(path);hint.hidden=true;undo.disabled=false;return path;
  }
  function point(event) {
    const p=canvas.createSVGPoint();p.x=event.clientX;p.y=event.clientY;
    const mapped=p.matrixTransform(canvas.getScreenCTM().inverse());
    return [Math.max(0,Math.min(600,mapped.x)),Math.max(0,Math.min(400,mapped.y))];
  }
  function draw() { stroke.setAttribute('d',points.map((p,i)=>`${i?'L':'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ')); }
  function finish() { stroke=null;activePointer=null;points=[]; }
  canvas.addEventListener('pointerdown',event=>{
    if(activePointer!==null || event.button!==0)return;
    stroke=newStroke();if(!stroke)return;
    activePointer=event.pointerId;canvas.setPointerCapture(activePointer);
    const p=point(event);points=[p,[p[0]+.1,p[1]]];draw();
    status.textContent='Your mark is yours. There is no right way to draw.';
  });
  canvas.addEventListener('pointermove',event=>{
    if(event.pointerId!==activePointer || !stroke || points.length>=1500)return;
    const p=point(event),last=points[points.length-1];if(Math.hypot(p[0]-last[0],p[1]-last[1])<2)return;
    points.push(p);draw();
  });
  canvas.addEventListener('pointerup',finish);canvas.addEventListener('pointercancel',finish);canvas.addEventListener('lostpointercapture',finish);
  document.getElementById('paint-ribbon').addEventListener('click',()=>{
    finish();const path=newStroke(18);if(!path)return;const y=80+(ribbonIndex++%5)*55;
    path.setAttribute('d',`M70 ${y} C180 ${y-50},240 ${y+50},320 ${y} S450 ${y-40},530 ${y}`);
    status.textContent='A ribbon in your chosen colour. You can add another or undo it.';
  });
  undo.addEventListener('click',()=>{
    finish();layer.lastElementChild?.remove();undo.disabled=!layer.children.length;
    hint.hidden=Boolean(layer.children.length);status.textContent='Last mark undone. You can keep exploring at your own pace.';
  });

  let moment=new GroundingMoment();
  const scene=document.getElementById('notice-surface'),feedback=document.getElementById('notice-feedback');
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)'),still=document.getElementById('ground-still');
  still.checked=motion.matches;
  function setMotion() { scene.classList.toggle('still',still.checked||motion.matches); }
  still.addEventListener('change',setMotion);motion.addEventListener('change',setMotion);setMotion();
  document.querySelectorAll('.paint-colour').forEach(original=>{
    const button=original.cloneNode(true);button.removeAttribute('aria-pressed');
    button.setAttribute('aria-label',`${original.dataset.name} sky`);
    button.addEventListener('click',()=>{
      document.getElementById('notice-colour').setAttribute('stop-color',original.dataset.colour);
      document.querySelectorAll('#notice-palette button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      feedback.textContent=`${original.dataset.name} in the sky. You can keep noticing at your own pace.`;
    });
    document.getElementById('notice-palette').appendChild(button);
  });
  const listen=document.getElementById('ground-listen');
  let voice=null;
  function loadVoice() {
    // Only expose spoken guidance when a local English voice is available.
    voice=window.speechSynthesis?.getVoices().find(v=>v.localService&&v.lang.toLowerCase().startsWith('en'));
    listen.hidden=!voice;
  }
  function stopReading() { window.speechSynthesis?.cancel(); }
  loadVoice();window.speechSynthesis?.addEventListener('voiceschanged',loadVoice);
  listen.addEventListener('click',()=>{
    if(!voice)return;stopReading();const speech=new SpeechSynthesisUtterance(`${prompt.textContent} ${detail.textContent}`);
    speech.voice=voice;speech.rate=.85;window.speechSynthesis.speak(speech);
  });
  function render() {
    notice.hidden=alternate.hidden=moment.resting||moment.complete;restart.hidden=!moment.complete;
    rest.hidden=moment.complete;easy.hidden=moment.complete;
    rest.textContent=moment.resting?'continue when ready':'pause here';
    easy.setAttribute('aria-pressed',String(moment.easy));easy.textContent=moment.easy?'use different senses':'make this easier';
    if(moment.complete) {sense.textContent='a moment for yourself';prompt.textContent='You can finish here.';detail.textContent='Stay with your surroundings, rest, or notice something else. You do not need to feel a particular way.';}
    else if(moment.resting) {sense.textContent='take your time';prompt.textContent='Nothing else to do right now.';detail.textContent='Your scene stays here. Continue only when you want to.';}
    else {const current=(moment.easy?easyPrompts:prompts)[moment.promptIndex];sense.textContent=current[0];prompt.textContent=current[1];detail.textContent=current[2];}
  }
  notice.addEventListener('click',()=>{
    stopReading();const step=moment.promptIndex;if(!moment.notice())return;
    document.getElementById(['notice-glow','notice-shore','notice-ripples'][step]).setAttribute('opacity',step===0?'.8':'.65');
    feedback.textContent=['A little colour in the sky.','A soft line along the shore.','A few ripples on the pond.'][step];
    render();if(moment.complete)restart.focus({preventScroll:true});
  });
  alternate.addEventListener('click',()=>{stopReading();moment.alternate();render();});
  easy.addEventListener('click',()=>{stopReading();moment.easy=!moment.easy;render();});
  rest.addEventListener('click',()=>{stopReading();moment.resting=!moment.resting;render();});
  restart.addEventListener('click',()=>{stopReading();const simplified=moment.easy;moment=new GroundingMoment();moment.easy=simplified;render();notice.focus({preventScroll:true});});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){finish();stopReading();}});
  window.addEventListener('pagehide',stopReading);
  document.querySelectorAll('.tab').forEach(tab=>tab.addEventListener('click',stopReading));
  document.getElementById('ground-painting').addEventListener('toggle',event=>{if(!event.target.open)finish();});
  render();
}
