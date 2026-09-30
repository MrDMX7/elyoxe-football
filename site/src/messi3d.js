// تيفو: every Messi goal on one pitch (/messi/). ES module, three.js from jsDelivr through the page's import map, loaded
// when the section scrolls into view. The owner's rule for effects (2026-09-30): each one must explain, reveal or compare,
// and one moment must be impossible without 3D. Here it is the arcs: each goal flies from where he struck it to the exact
// point it crossed the goal line (StatsBomb end_location, with height), season after season on the same half-pitch.
// Seen from above, a map of where he shoots from; turned to face the goal, where the ball goes. A flat chart can show one
// or the other, never both at once. Colour = the foot (left, his, in saffron; right in chalk; head in teal).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
const L = 105, W = 68, YD = 0.9144;                       // metres; StatsBomb is 120x80 yards
const COL = { L:0xF0BC5A, R:0xE9ECE4, H:0x5CC9A4, O:0xA7ADA4 };
// StatsBomb (x toward the goal he attacks, y across) -> world: goal at z = 0 of a half pitch drawn from z = 0 to z = L/2
const P = (x, y) => [(y - 40) * W / 80, (120 - x) * L / 120];

function halfPitch(){
  const c = document.createElement("canvas"); c.width = 680; c.height = 525; const g = c.getContext("2d");
  for (let i = 0; i < 7; i++){ g.fillStyle = i % 2 ? "#17493a" : "#154235"; g.fillRect(0, i * 75, 680, 75); }
  g.strokeStyle = "rgba(246,247,242,.7)"; g.lineWidth = 3;
  const sx = 680 / W, sz = 525 / (L / 2), R = (x, z, w, h) => g.strokeRect(x * sx, z * sz, w * sx, h * sz);
  R(1, 1, W - 2, L / 2); R((W - 40.3) / 2, 1, 40.3, 16.5); R((W - 18.3) / 2, 1, 18.3, 5.5);
  g.beginPath(); g.arc(340, 11 * sz, 9.15 * sx, 0.2 * Math.PI, 0.8 * Math.PI); g.stroke();
  g.beginPath(); g.arc(340, (L / 2) * sz, 9.15 * sx, Math.PI, 2 * Math.PI); g.stroke();
  g.fillStyle = "rgba(246,247,242,.8)"; g.beginPath(); g.arc(340, 11 * sz, 4, 0, 7); g.fill();
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
function goalFrame(){
  const g = new THREE.Group(), m = new THREE.MeshStandardMaterial({ color:0xf6f7f2 });
  const post = new THREE.CylinderGeometry(0.1, 0.1, 2.44, 8), bar = new THREE.CylinderGeometry(0.1, 0.1, 7.32, 8);
  const a = new THREE.Mesh(post, m); a.position.set(-3.66, 1.22, 0); const b = a.clone(); b.position.x = 3.66;
  const c = new THREE.Mesh(bar, m); c.rotation.z = Math.PI / 2; c.position.y = 2.44;
  const net = new THREE.Mesh(new THREE.PlaneGeometry(7.32, 2.44), new THREE.MeshBasicMaterial({ color:0xffffff, transparent:true, opacity:0.06, side:THREE.DoubleSide }));
  net.position.set(0, 1.22, -0.9); g.add(a, b, c, net); return g;
}
// one arc: a quadratic curve from the strike (on the grass) to the crossing point (x across, height), raised by distance
function arc(s){
  // a goal crosses the line between the posts: StatsBomb sometimes records where the ball ended in the net instead, so the
  // crossing point is pulled back onto the goal mouth (x = 120, y within the posts)
  const [x0, z0] = P(s.x, s.y), [x1, z1] = s.ex != null ? P(120, Math.min(43.8, Math.max(36.2, s.ey))) : [0, 0];
  const h1 = s.ez != null ? Math.min(s.ez * YD, 2.4) : 0.4, d = Math.hypot(x1 - x0, z1 - z0);
  const lift = s.body === "H" ? 0.6 : Math.min(4.5, 0.6 + d * 0.11);
  const pts = []; const N = 18;
  for (let i = 0; i <= N; i++){
    const t = i / N, u = 1 - t, cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, cy = Math.max(h1, s.body === "H" ? 1.9 : 0) + lift;
    pts.push(u * u * x0 + 2 * u * t * cx + t * t * x1, u * u * (s.body === "H" ? 1.9 : 0.05) + 2 * u * t * cy + t * t * h1, u * u * z0 + 2 * u * t * cz + t * t * z1);
  }
  return pts;
}

export function mount(el, data, ui){
  const goals = [], misses = [];
  data.matches.forEach(m => m.shots.forEach(s => (s.goal ? goals : misses).push(Object.assign({ date:m.date, season:m.season, opp:m.opp, team:m.team, comp:m.comp }, s))));
  const W0 = el.clientWidth || 360, H0 = Math.max(320, Math.min(560, Math.round(W0 * 0.8)));
  const renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true }); renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1)); renderer.setSize(W0, H0);
  el.appendChild(renderer.domElement); renderer.domElement.setAttribute("aria-hidden", "true");
  const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(42, W0 / H0, 0.1, 400);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x0a2620, 1.1)); const sun = new THREE.DirectionalLight(0xffffff, 0.8); sun.position.set(-20, 40, 30); scene.add(sun);
  const grass = new THREE.Mesh(new THREE.PlaneGeometry(W, L / 2), new THREE.MeshStandardMaterial({ map:halfPitch(), roughness:1 }));
  grass.rotation.x = -Math.PI / 2; grass.position.set(0, 0, L / 4); scene.add(grass); scene.add(goalFrame());

  // every shot that did not go in: a faint dot where he struck it (the volume behind the goals)
  const mp = new Float32Array(misses.length * 3); misses.forEach((s, i) => { const [x, z] = P(s.x, s.y); mp.set([x, 0.06, z], i * 3); });
  const mg = new THREE.BufferGeometry(); mg.setAttribute("position", new THREE.BufferAttribute(mp, 3));
  const dots = new THREE.Points(mg, new THREE.PointsMaterial({ color:0xE9ECE4, size:0.28, transparent:true, opacity:0.22, depthWrite:false }));
  scene.add(dots);

  // the goals: one LineSegments per foot, drawn up to a moving count (the career plays out in order)
  const byFoot = {}, order = goals.map((s, i) => i);
  goals.forEach((s, gi) => { (byFoot[s.body] = byFoot[s.body] || []).push(gi); });
  const lines = {};
  Object.keys(byFoot).forEach(f => {
    const idx = byFoot[f], seg = new Float32Array(idx.length * 18 * 6);
    idx.forEach((gi, k) => { const p = arc(goals[gi]); for (let j = 0; j < 18; j++) seg.set(p.slice(j * 3, j * 3 + 6), (k * 18 + j) * 6); });
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(seg, 3)); geo.setDrawRange(0, 0);
    const ln = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color:COL[f] || COL.O, transparent:true, opacity:f === "L" ? 0.32 : 0.28, depthWrite:false }));   // normal blending: additive burned the goal mouth white and hid where the ball went
    scene.add(ln); lines[f] = { ln, idx };
  });
  // how many goals of each foot fall within the first n goals of his career
  function show(n){
    Object.values(lines).forEach(o => { let k = 0; while (k < o.idx.length && o.idx[k] < n) k++; o.ln.geometry.setDrawRange(0, k * 18 * 2); });
    const g = goals[Math.max(0, n - 1)];
    if (ui && ui.onStep) ui.onStep(n, g);
  }

  const ctl = new OrbitControls(cam, renderer.domElement); ctl.enableDamping = true; ctl.target.set(0, 1, 10); ctl.maxPolarAngle = Math.PI * 0.49; ctl.minDistance = 8; ctl.maxDistance = 90;
  const VIEWS = { behind:[[0, 16, 48], [0, 1, 12]], above:[[0, 62, 22], [0, 0, 20]], goal:[[0, 2.2, -9], [0, 1.1, 0]] };
  function view(k, t){ const v = VIEWS[k]; cam.position.set(...v[0]); ctl.target.set(...v[1]); ctl.update(); }
  view("behind");

  let n = RM ? goals.length : 0, playing = !RM, last = 0;
  function frame(t){
    requestAnimationFrame(frame);
    if (playing && t - last > 28){ last = t; n = Math.min(goals.length, n + Math.max(1, Math.round(goals.length / 420))); show(n); if (n >= goals.length) playing = false; }
    ctl.update(); renderer.render(scene, cam);
  }
  show(n); requestAnimationFrame(frame);
  new ResizeObserver(() => { const w = el.clientWidth; if (!w) return; const h = Math.max(320, Math.min(560, Math.round(w * 0.8))); renderer.setSize(w, h); cam.aspect = w / h; cam.updateProjectionMatrix(); }).observe(el);
  return {
    total:goals.length, view, play(){ if (n >= goals.length) n = 0; playing = true; },
    seek(k){ playing = false; n = Math.max(0, Math.min(goals.length, k)); show(n); },
    misses(on){ dots.visible = on; },
  };
}
