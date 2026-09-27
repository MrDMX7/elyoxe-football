// تيفو 3D lineup pitch (feature 103). ES module, loaded only when the visitor opens «ثلاثي الأبعاد» on a match's lineup
// (three.js from jsDelivr through the page's import map). Players are cards on the grass, in the identity's card atom:
// home in its club colour at the bottom, away at the top. Drag to orbit, pinch/scroll to zoom, tap a card for name + rating.
// Positions come from FotMob position_id (tens = depth row 1..11, units = lateral slot 1..9), as in render.js pitchSide.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const L = 105, Wd = 68;   // pitch length (z) and width (x), metres
const RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

function place(p, away){
  const row = Math.floor(p.position_id / 10), lat = p.position_id % 10;
  const x = row === 1 ? 50 : away ? lat * 10 : 100 - lat * 10;
  const y = away ? 7 + (row - 1) / 10 * 38 : 93 - (row - 1) / 10 * 38;
  return [(x / 100 - 0.5) * Wd, (y / 100 - 0.5) * L];
}
function grassTexture(){
  const c = document.createElement("canvas"); c.width = 512; c.height = 800; const x = c.getContext("2d");
  for (let i = 0; i < 16; i++){ x.fillStyle = i % 2 ? "#1d5b45" : "#1a5240"; x.fillRect(0, i * 50, 512, 50); }
  x.strokeStyle = "rgba(246,247,242,.85)"; x.lineWidth = 4;
  const sx = 512 / Wd, sz = 800 / L, R = (a, b, w, h) => x.strokeRect(a * sx, b * sz, w * sx, h * sz);
  R(1, 1, Wd - 2, L - 2); x.beginPath(); x.moveTo(sx, 400); x.lineTo(512 - sx, 400); x.stroke();
  x.beginPath(); x.arc(256, 400, 9.15 * sx, 0, Math.PI * 2); x.stroke();
  R((Wd - 40.3) / 2, 1, 40.3, 16.5); R((Wd - 18.3) / 2, 1, 18.3, 5.5); R((Wd - 40.3) / 2, L - 17.5, 40.3, 16.5); R((Wd - 18.3) / 2, L - 6.5, 18.3, 5.5);
  x.fillStyle = "rgba(246,247,242,.85)"; [[256, 11 * sz], [256, 800 - 11 * sz], [256, 400]].forEach(([a, b]) => { x.beginPath(); x.arc(a, b, 4, 0, Math.PI * 2); x.fill(); });
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
function cardTexture(num, bg, fg){
  const c = document.createElement("canvas"); c.width = 128; c.height = 160; const x = c.getContext("2d");
  x.fillStyle = bg; x.fillRect(0, 0, 128, 160); x.fillStyle = fg; x.font = '700 92px "Barlow Condensed", sans-serif'; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText(String(num || ""), 64, 84);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function lum(hex){ const n = parseInt(hex.slice(1), 16); return (0.299 * (n >> 16 & 255) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255; }
function goal(z){
  const g = new THREE.Group(), m = new THREE.MeshStandardMaterial({ color:0xf6f7f2 }), post = new THREE.CylinderGeometry(0.12, 0.12, 2.44, 8), bar = new THREE.CylinderGeometry(0.12, 0.12, 7.32, 8);
  const a = new THREE.Mesh(post, m); a.position.set(-3.66, 1.22, 0); const b = a.clone(); b.position.x = 3.66; const c = new THREE.Mesh(bar, m); c.rotation.z = Math.PI / 2; c.position.y = 2.44;
  g.add(a, b, c); g.position.z = z; return g;
}

export function mount(el, md){
  const TC = window.TC || {};
  const col = (id, i) => (TC[id] && (TC[id][i || 0] || TC[id][0])) || (i ? "#F6F7F2" : "#5C6660");
  el.innerHTML = ""; el.classList.add("p3d");
  const tip = document.createElement("div"); tip.className = "p3tip"; tip.hidden = true; el.appendChild(tip);
  const W = el.clientWidth, H = Math.min(560, Math.max(380, W * 1.15));
  const renderer = new THREE.WebGLRenderer({ antialias:true, alpha:false }); renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); renderer.setSize(W, H);
  renderer.setClearColor(0x0a2620); el.appendChild(renderer.domElement);
  const scene = new THREE.Scene(); scene.fog = new THREE.Fog(0x0a2620, 110, 230);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x0a2620, 1.1)); const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(-30, 60, 40); scene.add(sun);
  const pitch = new THREE.Mesh(new THREE.PlaneGeometry(Wd + 6, L + 6), new THREE.MeshStandardMaterial({ color:0x163f33 })); pitch.rotation.x = -Math.PI / 2; pitch.position.y = -0.02; scene.add(pitch);
  const grass = new THREE.Mesh(new THREE.PlaneGeometry(Wd, L), new THREE.MeshStandardMaterial({ map:grassTexture() })); grass.rotation.x = -Math.PI / 2; scene.add(grass);
  scene.add(goal(-L / 2), goal(L / 2));
  // the stands: rows of fan cards in each club's colours behind its goal (the tifo idea, in 3D)
  const standRow = (z, id, flip) => { const g = new THREE.Group(), geo = new THREE.BoxGeometry(1.6, 1.6, 0.2); const mats = [new THREE.MeshStandardMaterial({ color:col(id, 0) }), new THREE.MeshStandardMaterial({ color:col(id, 1) })];
    for (let r = 0; r < 6; r++) for (let c = -22; c <= 22; c++){ const m = new THREE.Mesh(geo, mats[(c + r) % 7 < 2 ? 1 : 0]); m.position.set(c * 1.8, 1 + r * 1.9, z + (flip ? -r * 1.4 : r * 1.4)); m.rotation.x = flip ? 0.35 : -0.35; g.add(m); }
    scene.add(g); };
  standRow(L / 2 + 8, md.home.id, false); standRow(-L / 2 - 8, md.away.id, true);
  const L0 = md.lineups || {}, cards = [];
  [[L0.home, md.home, false], [L0.away, md.away, true]].forEach(([side, team, away]) => {
    if (!side || !side.starters) return;
    const bg = col(team.id, 0), fg = lum(bg) > 0.6 ? "#0E1512" : "#F6F7F2";
    side.starters.forEach(p => {
      if (!p.position_id) return; const [x, z] = place(p, away);
      const mat = new THREE.MeshStandardMaterial({ map:cardTexture(p.number, bg, fg) }), back = new THREE.MeshStandardMaterial({ color:bg });
      const card = new THREE.Mesh(new THREE.BoxGeometry(3.4, 4.3, 0.22), [back, back, back, back, mat, mat]);
      card.position.set(x, 2.4, z); card.userData = { p, team, away }; scene.add(card); cards.push(card);
      const shadow = new THREE.Mesh(new THREE.CircleGeometry(1.2, 20), new THREE.MeshBasicMaterial({ color:0x000000, transparent:true, opacity:0.25 })); shadow.rotation.x = -Math.PI / 2; shadow.position.set(x, 0.02, z); scene.add(shadow);
    });
  });
  const camera = new THREE.PerspectiveCamera(42, W / H, 0.5, 400); camera.position.set(0, 58, 84);
  const ctl = new OrbitControls(camera, renderer.domElement); ctl.target.set(0, 0, 4); ctl.enableDamping = true; ctl.maxPolarAngle = Math.PI / 2.7; ctl.minPolarAngle = 0.15; ctl.minDistance = 25; ctl.maxDistance = 170; ctl.enablePan = false;
  ctl.autoRotate = !RM; ctl.autoRotateSpeed = 0.35;
  ctl.addEventListener("start", () => { ctl.autoRotate = false; });
  // cards turn to face the camera, like fans holding them up
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  renderer.domElement.addEventListener("pointerup", e => {
    const r = renderer.domElement.getBoundingClientRect(); ptr.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
    ray.setFromCamera(ptr, camera); const hit = ray.intersectObjects(cards)[0];
    if (!hit){ tip.hidden = true; return; }
    const { p, team } = hit.object.userData;
    tip.innerHTML = `<b>${p.number || ""}</b> <span class="lat">${String(p.name).replace(/[<>&]/g, "")}</span><br><span>${team.name_ar || team.name}</span>${p.rating != null ? ` <span class="rt ${p.rating >= 7.5 ? "hi" : p.rating >= 6.5 ? "mid" : "lo"}">${Number(p.rating).toFixed(1)}</span>` : ""}`;
    tip.hidden = false;
  });
  let alive = true, raf = 0;
  const loop = () => { if (!alive) return; cards.forEach(c => { c.rotation.y = Math.atan2(camera.position.x - c.position.x, camera.position.z - c.position.z); }); ctl.update(); renderer.render(scene, camera); raf = requestAnimationFrame(loop); };
  // intro: drop from above into the broadcast view (skipped with reduced motion)
  if (!RM){ const from = new THREE.Vector3(0, 140, 10), to = camera.position.clone(), t0 = performance.now(); camera.position.copy(from); const step = now => { const k = Math.min(1, (now - t0) / 1400), e = 1 - Math.pow(1 - k, 3); camera.position.lerpVectors(from, to, e); if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); }
  loop();
  const ro = new ResizeObserver(() => { const w = el.clientWidth, h = Math.min(560, Math.max(380, w * 1.15)); renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); }); ro.observe(el);
  const io = new IntersectionObserver(([en]) => { if (!en.isIntersecting){ alive = false; cancelAnimationFrame(raf); } else if (!alive){ alive = true; loop(); } }); io.observe(el);
  return { dispose(){ alive = false; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); renderer.dispose(); } };
}
