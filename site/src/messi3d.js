// تيفو: the Messi museum's two 3D rooms (/messi/). ES module, three.js from jsDelivr through the page's import map,
// loaded when a room scrolls into view. The owner's rule for effects (2026-09-30): each one must explain, reveal or
// compare, and one moment must be impossible without 3D.
//   mount()   every goal as an arc from where he struck it to the exact point it crossed the goal line (StatsBomb
//             end_location, with height), season after season on one half-pitch. From above: where he shoots from;
//             from the goal: where the ball goes. A flat chart shows one or the other, never both at once.
//   layers()  every season's touches as a layer, time as height: the drift from the right wing to false nine to
//             playmaker is a shape you turn in your hand, not a table of numbers.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
const L = 105, W = 68, YD = 0.9144;                       // metres; StatsBomb is 120x80 yards
const COL = { L:0xF0BC5A, R:0xE9ECE4, H:0x5CC9A4, O:0xA7ADA4 };
const P = (x, y) => [(y - 40) * W / 80, (120 - x) * L / 120];   // StatsBomb -> world, the goal at z = 0

function stage(el, h){
  const W0 = el.clientWidth || 360, H0 = h(W0);
  const renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true, preserveDrawingBuffer:true }); renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1)); renderer.setSize(W0, H0);
  el.innerHTML = ""; el.appendChild(renderer.domElement); renderer.domElement.setAttribute("aria-hidden", "true");
  const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(42, W0 / H0, 0.1, 500);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x0a2620, 1.1)); const sun = new THREE.DirectionalLight(0xffffff, 0.8); sun.position.set(-20, 40, 30); scene.add(sun);
  const ctl = new OrbitControls(cam, renderer.domElement); ctl.enableDamping = true;
  new ResizeObserver(() => { const w = el.clientWidth; if (!w) return; const hh = h(w); renderer.setSize(w, hh); cam.aspect = w / hh; cam.updateProjectionMatrix(); }).observe(el);
  return { renderer, scene, cam, ctl };
}
function pitchTexture(halfOnly){
  const c = document.createElement("canvas"); c.width = 680; c.height = halfOnly ? 525 : 1050; const g = c.getContext("2d"), LL = halfOnly ? L / 2 : L;
  const bands = halfOnly ? 7 : 14; for (let i = 0; i < bands; i++){ g.fillStyle = i % 2 ? "#17493a" : "#154235"; g.fillRect(0, i * 75, 680, 75); }
  g.strokeStyle = "rgba(246,247,242,.7)"; g.lineWidth = 3;
  const sx = 680 / W, sz = c.height / LL, R = (x, z, w, h) => g.strokeRect(x * sx, z * sz, w * sx, h * sz);
  R(1, 1, W - 2, LL - 2); R((W - 40.3) / 2, 1, 40.3, 16.5); R((W - 18.3) / 2, 1, 18.3, 5.5);
  g.beginPath(); g.arc(340, 11 * sz, 9.15 * sx, 0.2 * Math.PI, 0.8 * Math.PI); g.stroke();
  g.beginPath(); g.arc(340, (L / 2) * sz, 9.15 * sx, Math.PI, 2 * Math.PI); g.stroke();
  if (!halfOnly){ R((W - 40.3) / 2, LL - 17.5, 40.3, 16.5); R((W - 18.3) / 2, LL - 6.5, 18.3, 5.5); g.beginPath(); g.arc(340, (L / 2) * sz, 9.15 * sx, 0, Math.PI); g.stroke(); }
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
// one arc: a quadratic curve from the strike to the crossing point (pulled onto the goal mouth: StatsBomb sometimes records
// where the ball ended in the net), raised by distance; a header starts at head height
function arc(s, N){
  N = N || 18;
  const [x0, z0] = P(s.x, s.y), [x1, z1] = P(120, Math.min(43.8, Math.max(36.2, s.ey == null ? 40 : s.ey)));
  const h1 = s.ez != null ? Math.min(s.ez * YD, 2.4) : 0.4, d = Math.hypot(x1 - x0, z1 - z0), y0 = s.body === "H" ? 1.9 : 0.05;
  const cy = Math.max(h1, y0) + (s.body === "H" ? 0.6 : Math.min(4.5, 0.6 + d * 0.11)), cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, pts = [];
  for (let i = 0; i <= N; i++){ const t = i / N, u = 1 - t; pts.push(u * u * x0 + 2 * u * t * cx + t * t * x1, u * u * y0 + 2 * u * t * cy + t * t * h1, u * u * z0 + 2 * u * t * cz + t * t * z1); }
  return pts;
}

export function mount(el, data, ui){
  const goals = [], misses = [];
  data.matches.forEach(m => m.shots.forEach(s => (s.goal ? goals : misses).push(Object.assign({ date:m.date, season:m.season, opp:m.opp, team:m.team, comp:m.comp }, s))));
  const { renderer, scene, cam, ctl } = stage(el, w => Math.max(320, Math.min(560, Math.round(w * 0.8))));
  const grass = new THREE.Mesh(new THREE.PlaneGeometry(W, L / 2), new THREE.MeshStandardMaterial({ map:pitchTexture(true), roughness:1 }));
  grass.rotation.x = -Math.PI / 2; grass.position.set(0, 0, L / 4); scene.add(grass); scene.add(goalFrame());
  const mp = new Float32Array(misses.length * 3); misses.forEach((s, i) => { const [x, z] = P(s.x, s.y); mp.set([x, 0.06, z], i * 3); });
  const mg = new THREE.BufferGeometry(); mg.setAttribute("position", new THREE.BufferAttribute(mp, 3));
  const dots = new THREE.Points(mg, new THREE.PointsMaterial({ color:0xE9ECE4, size:0.28, transparent:true, opacity:0.22, depthWrite:false })); scene.add(dots);

  // the goals shown: one LineSegments per foot over the current list, drawn up to a moving count (the career in order)
  let list = goals, groups = [];
  function build(){
    groups.forEach(o => { scene.remove(o.ln); o.ln.geometry.dispose(); }); groups = [];
    const byFoot = {}; list.forEach((s, i) => { (byFoot[s.body] = byFoot[s.body] || []).push(i); });
    Object.keys(byFoot).forEach(f => {
      const idx = byFoot[f], seg = new Float32Array(idx.length * 18 * 6);
      idx.forEach((gi, k) => { const p = arc(list[gi]); for (let j = 0; j < 18; j++) seg.set(p.slice(j * 3, j * 3 + 6), (k * 18 + j) * 6); });
      const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(seg, 3)); geo.setDrawRange(0, 0);
      const ln = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color:COL[f] || COL.O, transparent:true, opacity:list.length < 80 ? 0.8 : f === "L" ? 0.32 : 0.28, depthWrite:false }));
      scene.add(ln); groups.push({ ln, idx });
    });
  }
  let n = 0, playing = false, last = 0, focusLine = null;
  function show(k){
    n = k; groups.forEach(o => { let c = 0; while (c < o.idx.length && o.idx[c] < k) c++; o.ln.geometry.setDrawRange(0, c * 18 * 2); });
    if (ui && ui.onStep) ui.onStep(k, list[Math.max(0, k - 1)], list.length);
  }
  const VIEWS = { behind:[[0, 16, 48], [0, 1, 12]], above:[[0, 62, 22], [0, 0, 20]], goal:[[0, 2.2, -9], [0, 1.1, 0]] };
  function view(k){ const v = VIEWS[k]; cam.position.set(...v[0]); ctl.target.set(...v[1]); ctl.update(); }
  ctl.maxPolarAngle = Math.PI * 0.49; ctl.minDistance = 4; ctl.maxDistance = 90; view("behind");
  build(); show(RM ? list.length : 0); playing = !RM;
  (function frame(t){
    requestAnimationFrame(frame);
    if (playing && t - last > 28){ last = t; const k = Math.min(list.length, n + Math.max(1, Math.round(list.length / 420))); show(k); if (k >= list.length) playing = false; }
    ctl.update(); renderer.render(scene, cam);
  })(0);
  return {
    get total(){ return list.length; }, view,
    play(){ if (focusLine){ scene.remove(focusLine); focusLine = null; } if (n >= list.length) n = 0; playing = true; },
    seek(k){ playing = false; show(Math.max(0, Math.min(list.length, k))); },
    misses(on){ dots.visible = on; },
    // f: "all" | "L" | "R" | "H" | "Free Kick" | "Penalty"
    filter(f){ list = f === "all" ? goals : goals.filter(s => s.body === f || s.kind === f); build(); playing = false; show(list.length); return list.length; },
    // one goal from the full list: a bright arc, the camera behind the strike
    focus(i){
      const s = goals[i]; if (!s) return; if (list !== goals){ list = goals; build(); }
      playing = false; show(i + 1); if (focusLine) scene.remove(focusLine);
      const p = arc(s, 40), pts = []; for (let j = 0; j < p.length; j += 3) pts.push(new THREE.Vector3(p[j], p[j + 1], p[j + 2]));
      focusLine = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 60, 0.09, 6), new THREE.MeshBasicMaterial({ color:0xFFE3A3 })); scene.add(focusLine);
      const [x0, z0] = P(s.x, s.y); cam.position.set(x0 * 1.1, 5, z0 + 12); ctl.target.set(x0 * 0.3, 1, z0 * 0.4); ctl.update();
    },
    goal(i){ return goals[i]; }, canvas:renderer.domElement,
  };
}

// every season a layer of his touches (StatsBomb 10x10-yard cells), stacked in time; colour by era
export function layers(el, play){
  const { renderer, scene, cam, ctl } = stage(el, w => Math.max(360, Math.min(620, Math.round(w * 0.9))));
  const keys = Object.keys(play.touches || {}).sort(), GAP = 2.2;
  const era = k => k.includes("Barcelona") ? (k < "2009" ? 0x9FB8AE : k < "2015" ? 0xF0BC5A : 0xE58A3A) : k.includes("Paris") ? 0x6FA3E0 : k.includes("Argentina") ? 0x8EC9EE : 0xF5A3C7;
  const box = new THREE.BoxGeometry(1, 1, 1), n = keys.reduce((a, k) => a + play.touches[k].length, 0);
  const mesh = new THREE.InstancedMesh(box, new THREE.MeshStandardMaterial({ transparent:true, opacity:0.85, roughness:0.6 }), n);
  const m4 = new THREE.Matrix4(), col = new THREE.Color(); let i = 0;
  keys.forEach((k, li) => {
    const cells = play.touches[k], mx = Math.max(...cells.map(c => c[2]));
    cells.forEach(([a, b, c]) => {
      const s = c / mx; if (s < 0.08){ m4.makeScale(0.0001, 0.0001, 0.0001); mesh.setMatrixAt(i++, m4); return; }
      const [x, z] = [((b + 0.5) * 10 - 40) * W / 80, (60 - (a + 0.5) * 10) * L / 120];
      m4.compose(new THREE.Vector3(x, li * GAP + 0.3 + s * 0.7, z), new THREE.Quaternion(), new THREE.Vector3(8.2 * s + 0.4, 0.4 + s * 1.3, 8.2 * s + 0.4));
      mesh.setMatrixAt(i, m4); col.setHex(era(k)).multiplyScalar(0.45 + s * 0.75); mesh.setColorAt(i, col); i++;
    });
  });
  scene.add(mesh);
  const base = new THREE.Mesh(new THREE.PlaneGeometry(W, L), new THREE.MeshStandardMaterial({ map:pitchTexture(false), roughness:1 })); base.rotation.x = -Math.PI / 2; scene.add(base);
  const top = keys.length * GAP;
  cam.position.set(70, top * 0.9 + 20, 60); ctl.target.set(0, top / 2, 0); ctl.autoRotate = !RM; ctl.autoRotateSpeed = 0.6; ctl.update();
  renderer.domElement.addEventListener("pointerdown", () => { ctl.autoRotate = false; }, { once:true });
  (function frame(){ requestAnimationFrame(frame); ctl.update(); renderer.render(scene, cam); })();
  return { seasons:keys };
}
