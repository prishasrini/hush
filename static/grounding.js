/* Local-only grounding: no sensor access, typed answers, or saved observations. */
class GroundingMoment {
  constructor() { this.observations = 0; this.promptIndex = 0; this.resting = false; }
  notice() {
    if (this.resting || this.observations >= 5) return false;
    this.observations++;
    this.promptIndex = this.observations * 3;
    return true;
  }
  alternate() { if (!this.resting && this.observations < 5) this.promptIndex = (this.promptIndex + 1) % 15; }
  get complete() { return this.observations >= 5; }
}
if (typeof module !== 'undefined') module.exports = {GroundingMoment};
if (typeof document !== 'undefined') {
  const prompts = [
    {sense:'look around', text:'Notice something with a colour you like.', detail:'Let your eyes rest on it for a moment. You do not have to name it here.'},
    {sense:'feel a surface', text:'Notice the texture of something within easy reach.', detail:'Perhaps your sleeve or the chair. Only touch something comfortable and safe.'},
    {sense:'notice where you are', text:'Notice something familiar about this place.', detail:'It could be an object nearby, or something you know about where you are.'},
    {sense:'feel supported', text:'Notice where the chair or floor supports you.', detail:'If that does not feel comfortable, choose another prompt.'},
    {sense:'look around', text:'Find a shape nearby and notice its edges.', detail:'A window, a book, a leaf — anything you can comfortably see.'},
    {sense:'notice a detail', text:'Notice the texture of your clothing.', detail:'You can feel it gently or look at it. There is no right answer.'},
    {sense:'listen gently', text:'Notice one sound around you.', detail:'You can keep your eyes open. If hearing is not useful, choose another prompt.'},
    {sense:'look around', text:'Notice where light meets shadow.', detail:'Let your attention settle on a small detail, without searching for the perfect one.'},
    {sense:'feel a surface', text:'Notice whether a comfortable object feels smooth or textured.', detail:'A familiar object is enough. You can skip touching anything.'},
    {sense:'notice a scent', text:'Notice a scent already around you, if there is one.', detail:'No need to find anything or take a deep breath. Another prompt is always available.'},
    {sense:'notice where you are', text:'Notice one thing that helps you recognise this place.', detail:'A familiar object or a detail you know about the room can be enough.'},
    {sense:'look around', text:'Notice something still nearby.', detail:'You can look at it for as long or as briefly as you like.'},
    {sense:'notice a taste', text:'Notice a taste already in your mouth, if comfortable.', detail:'You do not need to eat or drink anything. Choose another prompt if you prefer.'},
    {sense:'feel supported', text:'Notice the contact between your hand and a comfortable surface.', detail:'It can be your own sleeve, a desk or your lap. Skip this if it does not feel right.'},
    {sense:'look around', text:'Notice a small detail you had not paid attention to.', detail:'There is no need to find anything new. A familiar detail is just as welcome.'}
  ];
  const notice = document.getElementById('ground-notice');
  const alternate = document.getElementById('ground-alternate');
  const rest = document.getElementById('ground-rest');
  const restart = document.getElementById('ground-restart');
  const sense = document.getElementById('ground-sense');
  const prompt = document.getElementById('ground-prompt');
  const detail = document.getElementById('ground-detail');
  const scene = document.getElementById('ground-scene');
  const stones = [...document.querySelectorAll('.ground-stone')];
  const still = document.getElementById('ground-still');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let moment = new GroundingMoment(), stoneCount = 0;
  function motionPreference() { scene.classList.toggle('still', still.checked || reduced.matches); }
  still.addEventListener('change', motionPreference);
  reduced.addEventListener('change', motionPreference);
  motionPreference();
  function glow(stone) {
    if (scene.classList.contains('still')) return;
    stone.classList.remove('glow'); void stone.offsetWidth; stone.classList.add('glow');
  }
  stones.forEach(stone => stone.addEventListener('click', () => glow(stone)));
  function render() {
    notice.hidden = moment.resting || moment.complete;
    alternate.hidden = moment.resting || moment.complete;
    rest.hidden = moment.complete;
    restart.hidden = !moment.complete;
    rest.textContent = moment.resting ? 'continue when ready' : 'rest here';
    if (moment.complete) {
      sense.textContent = 'a moment for yourself';
      prompt.textContent = 'You can rest here, or return to your day.';
      detail.textContent = 'There is no particular feeling you need to have. Human support is available through the link above.';
    } else if (moment.resting) {
      sense.textContent = 'take your time';
      prompt.textContent = 'Nothing else to do right now.';
      detail.textContent = 'Your stones stay here. Continue if and when you want to.';
    } else {
      const current = prompts[moment.promptIndex];
      sense.textContent = current.sense; prompt.textContent = current.text; detail.textContent = current.detail;
    }
  }
  notice.addEventListener('click', () => {
    if (!moment.notice()) return;
    const stone = stones[Math.min(stoneCount, stones.length - 1)];
    stone.hidden = false; stoneCount = Math.min(stoneCount + 1, stones.length); glow(stone);
    render();
    // The last action becomes hidden at completion: keep keyboard focus usable.
    if (moment.complete) restart.focus({preventScroll:true});
  });
  alternate.addEventListener('click', () => { moment.alternate(); render(); });
  rest.addEventListener('click', () => { moment.resting = !moment.resting; render(); });
  restart.addEventListener('click', () => { moment = new GroundingMoment(); render(); notice.focus({preventScroll:true}); });
  render();
}
