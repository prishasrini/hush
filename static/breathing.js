/* Deadline-based timing keeps countdowns accurate even when a frame is delayed. */
class BreathSession {
  constructor(steps, rounds, now = () => performance.now()) {
    this.steps = steps;
    this.rounds = rounds;
    this.now = now;
    this.index = 0;
    this.round = 1;
    this.paused = false;
    this.done = false;
    this.deadline = this.now() + steps[0].seconds * 1000;
  }
  snapshot() {
    const time = this.now();
    while (!this.paused && !this.done && time >= this.deadline) {
      this.index++;
      if (this.index === this.steps.length) { this.index = 0; this.round++; }
      if (this.round > this.rounds) { this.done = true; break; }
      this.deadline += this.steps[this.index].seconds * 1000;
    }
    const remaining = this.paused ? this.remaining : Math.max(0, this.deadline - time);
    return {step: this.steps[this.index], index: this.index, round: this.round,
      remaining, seconds: Math.ceil(remaining / 1000), paused: this.paused, done: this.done};
  }
  pause() {
    const state = this.snapshot();
    if (!this.done && !this.paused) { this.remaining = state.remaining; this.paused = true; }
  }
  resume() {
    if (this.paused && !this.done) { this.deadline = this.now() + this.remaining; this.paused = false; }
  }
}
if (typeof module !== 'undefined') module.exports = {BreathSession};
if (typeof document !== 'undefined') {
  const circle = document.getElementById('breathe-circle');
  const instruction = document.getElementById('breathe-instruction');
  const counter = document.getElementById('breathe-counter');
  const progress = document.getElementById('breath-progress');
  const start = document.getElementById('breath-start');
  const pause = document.getElementById('breath-pause');
  const pace = document.getElementById('breath-pace');
  const rounds = document.getElementById('breath-rounds');
  const scene = document.getElementById('breath-scene');
  const ringLabel = document.getElementById('ring-label');
  const stars = [...document.querySelectorAll('.constellation-star')];
  const lines = [...document.querySelectorAll('.constellation-line')];
  const starStatus = document.getElementById('star-status');
  const stillMode = document.getElementById('breath-still');
  const showNumbers = document.getElementById('breath-numbers');
  let starCount = 0, creditedRounds = 0;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  function motionPreference() {
    scene.classList.toggle('still', stillMode.checked || reducedMotion.matches);
  }
  stillMode.addEventListener('change', motionPreference);
  reducedMotion.addEventListener('change', motionPreference);
  motionPreference();
  showNumbers.addEventListener('change', () => { counter.hidden = !showNumbers.checked; });
  function bloom(star) {
    if (scene.classList.contains('still')) return;
    star.classList.remove('bloom');
    void star.offsetWidth;
    star.classList.add('bloom');
  }
  stars.forEach(star => star.addEventListener('click', () => bloom(star)));
  function addStars(completedRounds) {
    while (creditedRounds < completedRounds) {
      creditedRounds++;
      if (starCount === stars.length) continue;
      const star = stars[starCount];
      star.hidden = false;
      if (starCount > 0) lines[starCount - 1].classList.add('visible');
      starCount++;
      bloom(star);
    }
    starStatus.textContent = starCount ? 'your lights stay when you pause. touch one to let it glow.' : 'a little light settles here after each round. no need to touch or keep pace perfectly.';
  }
  const patterns = {
    gentle: [{label:'breathe in', seconds:4, scale:1.35}, {label:'breathe out', seconds:6, scale:1}],
    box: [{label:'breathe in', seconds:4, scale:1.35}, {label:'hold gently', seconds:4, scale:1.35},
      {label:'breathe out', seconds:4, scale:1}, {label:'hold gently', seconds:4, scale:1}],
    '478': [{label:'breathe in', seconds:4, scale:1.35}, {label:'hold gently', seconds:7, scale:1.35},
      {label:'breathe out', seconds:8, scale:1}]
  };
  let session = null, timer = null, previousPhase = '';
  function reset(completed = false) {
    clearInterval(timer); timer = null; session = null; previousPhase = '';
    circle.style.transitionDuration = '0s'; circle.style.transform = 'scale(1)';
    scene.dataset.phase = 'rest';
    ringLabel.textContent = completed ? 'rest here' : 'tap to begin';
    circle.setAttribute('aria-label', completed ? 'Start another breathing session' : 'Start breathing');
    instruction.textContent = completed ? 'finished — return to your own comfortable breathing' : 'begin whenever you feel ready';
    counter.textContent = ''; progress.textContent = completed ? 'you can rest here or start again' : 'no rush, no score';
    pause.disabled = true; pause.textContent = 'pause'; start.disabled = false;
    pace.disabled = false; rounds.disabled = false;
  }
  function render() {
    if (!session) return;
    const state = session.snapshot();
    addStars(Math.min(session.rounds, state.round - 1));
    if (state.done) { reset(true); return; }
    const phase = `${state.round}-${state.index}`;
    if (phase !== previousPhase) {
      circle.style.transitionDuration = `${state.remaining / 1000}s`;
      circle.style.transform = `scale(${state.step.scale})`;
      instruction.textContent = state.step.label;
      ringLabel.textContent = state.step.label;
      scene.dataset.phase = state.step.label === 'breathe in' ? 'in' : state.step.label === 'breathe out' ? 'out' : 'hold';
      previousPhase = phase;
    }
    counter.textContent = state.seconds;
    progress.textContent = `round ${state.round} of ${session.rounds}`;
  }
  function begin() {
    reset(); creditedRounds = 0;
    session = new BreathSession(patterns[pace.value], Number(rounds.value));
    circle.setAttribute('aria-label', 'Pause breathing');
    start.disabled = true; pace.disabled = true; rounds.disabled = true; pause.disabled = false;
    render(); timer = setInterval(render, 100);
  }
  start.addEventListener('click', begin);
  function togglePause() {
    if (!session) return;
    if (session.paused) {
      session.resume(); previousPhase = ''; render(); timer = setInterval(render, 100); pause.textContent = 'pause';
      circle.setAttribute('aria-label', 'Pause breathing');
    } else {
      session.pause();
      addStars(Math.min(session.rounds, session.round - 1));
      if (session.done) { reset(true); return; }
      clearInterval(timer);
      const frozen = getComputedStyle(circle).transform;
      circle.style.transitionDuration = '0s'; circle.style.transform = frozen;
      instruction.textContent = 'paused — breathe at your own pace'; pause.textContent = 'resume';
      scene.dataset.phase = 'rest'; ringLabel.textContent = 'paused';
      circle.setAttribute('aria-label', 'Resume breathing');
    }
  }
  pause.addEventListener('click', togglePause);
  circle.addEventListener('click', () => session ? togglePause() : begin());
  document.getElementById('breath-reset').addEventListener('click', () => reset());
  window.stopBreath = () => reset();
  document.addEventListener('visibilitychange', () => { if (document.hidden && session && !session.paused) togglePause(); });
  window.addEventListener('pagehide', () => reset());
}
