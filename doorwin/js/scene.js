/* ============================================================
 * 3D 场景管理：室内房间 / 室外立面、墙体开洞、灯光阴影、
 * 轨道相机（OrbitControls，支持触摸旋转缩放）
 * ============================================================ */

const SceneManager = (function () {
  let container = null;
  let renderer, scene, camera, controls;
  let sun, hemi;
  let wallGroup = null, productGroup = null;
  let state = null;
  let dirty = true;
  let active = true;
  let firstFit = true;

  const WALL_T = 0.24; // 墙体厚度 m

  function init(el) {
    container = el;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    } catch (e) {
      // 设备/系统 WebView 不支持 WebGL：显示友好提示
      const msg = document.createElement('div');
      msg.style.cssText = 'position:absolute;left:0;top:0;right:0;bottom:0;display:flex;' +
        'align-items:center;justify-content:center;color:#fff;font-size:14px;' +
        'text-align:center;padding:30px;z-index:10;line-height:1.8';
      msg.textContent = '⚠️ 此设备不支持 3D 渲染（WebGL 不可用）。\n' +
        '请尝试：系统设置中更新「Android System WebView」，或更换较新的手机。\n\n2D 图纸与报价功能仍可使用。';
      container.appendChild(msg);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(42, 1, 0.05, 60);

    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 0.6;
    controls.maxDistance = 7;
    controls.minPolarAngle = 0.25;
    controls.maxPolarAngle = 1.45;
    controls.target.set(0, 1.1, 0);

    // WebGL 上下文丢失时自动恢复（防止黑屏）
    let ctxRestored = false;
    renderer.domElement.addEventListener('webglcontextrestored', function () { ctxRestored = true; });
    renderer.domElement.addEventListener('webglcontextlost', function (e) {
      e.preventDefault();
      setTimeout(function () {
        if (!ctxRestored) location.reload();
      }, 1000);
    });

    // 灯光
    hemi = new THREE.HemisphereLight(0xffffff, 0x8a7f6f, 0.75);
    scene.add(hemi);
    sun = new THREE.DirectionalLight(0xfff2dd, 0.95);
    sun.position.set(-2.2, 4.2, 5.5);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.left = -4; sun.shadow.camera.right = 4;
    sun.shadow.camera.top = 5; sun.shadow.camera.bottom = -1;
    sun.shadow.camera.near = 0.5; sun.shadow.camera.far = 20;
    sun.shadow.bias = -0.0004;
    sun.shadow.radius = 4;
    scene.add(sun);

    resize();
    window.addEventListener('resize', resize);

    function loop() {
      requestAnimationFrame(loop);
      if (!active || document.hidden) return;
      if (dirty) { rebuild(); dirty = false; }
      controls.update();
      clampCamera(); // 相机锁在场景可视范围内，防止转进墙体/地面
      renderer.render(scene, camera);
    }
    loop();
  }

  /* 相机范围限制：室内锁在房间内，室外锁在地面以上、立面之前 */
  function clampCamera() {
    if (!state || !camera) return;
    const p = camera.position;
    if (state.scene !== 'outdoor') {
      // 房间：x ±2.05 / y 0.35-2.5 / z 0.15-3.25（墙在 z=0，房间深 3.4）
      p.x = Math.max(-2.05, Math.min(2.05, p.x));
      p.y = Math.max(0.35, Math.min(2.5, p.y));
      p.z = Math.max(0.15, Math.min(3.25, p.z));
    } else {
      p.x = Math.max(-6, Math.min(6, p.x));
      p.y = Math.max(0.25, Math.min(8, p.y));
      p.z = Math.max(0.4, Math.min(8, p.z));
    }
  }

  function resize() {
    if (!container) return;
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function setState(s) {
    state = s;
    if (renderer && scene) {
      // 同步重建并立即渲染：参数拖动时即时反馈
      rebuild();
      renderer.render(scene, camera);
    } else {
      dirty = true; // 初始化前只打标记
    }
  }
  function setActive(a) { active = a; if (a) { dirty = true; resize(); } }

  /* 清空场景中的墙体与门窗（材质有缓存，几何体需释放） */
  function clearSceneObjects() {
    [wallGroup, productGroup].forEach(g => {
      if (!g) return;
      scene.remove(g);
      g.traverse(o => {
        if (o.geometry) o.geometry.dispose();
      });
    });
    wallGroup = null; productGroup = null;
  }

  /* 墙面开洞：用四块墙板拼出洞口 */
  function buildWallWithHole(cx, wallW, wallH, holeX, holeY, holeW, holeH, mat) {
    const g = new THREE.Group();
    g.position.set(cx, 0, 0);
    const hw = wallW / 2;
    const left = { x0: -hw, x1: holeX - holeW / 2 };
    const right = { x0: holeX + holeW / 2, x1: hw };
    const bottom = { y0: 0, y1: holeY - holeH / 2 };
    const top = { y0: holeY + holeH / 2, y1: wallH };
    function piece(x0, x1, y0, y1) {
      const m = new THREE.Mesh(
        new THREE.BoxGeometry(x1 - x0, y1 - y0, WALL_T), mat);
      m.position.set((x0 + x1) / 2, (y0 + y1) / 2, 0);
      m.castShadow = true; m.receiveShadow = true;
      g.add(m);
    }
    if (left.x1 - left.x0 > 0.01) piece(left.x0, left.x1, 0, wallH);
    if (right.x1 - right.x0 > 0.01) piece(right.x0, right.x1, 0, wallH);
    if (bottom.y1 > 0.01) piece(holeX - holeW / 2, holeX + holeW / 2, 0, bottom.y1);
    if (top.y1 - top.y0 > 0.01) piece(holeX - holeW / 2, holeX + holeW / 2, top.y0, wallH);
    return g;
  }

  function wallMat(hex) {
    return new THREE.MeshStandardMaterial({ color: hex, roughness: 0.92, metalness: 0, side: THREE.FrontSide });
  }

  /* ---- 室内场景：房间 + 背墙开洞 + 窗台板 ---- */
  function buildIndoor(st) {
    const style = Models.getStyleById(st.styleId);
    const W = st.w * M, H = st.h * M, sill = style.sill * M;
    const roomW = 4.4, roomH = 2.8, roomD = 3.4;
    wallGroup = new THREE.Group();

    // 背墙（开洞）
    const holeW = W + 0.03, holeH = H + 0.03;
    wallGroup.add(buildWallWithHole(0, roomW, roomH, 0, sill + H / 2, holeW, holeH, wallMat('#e8e2d5')));

    // 地板、天花板、两侧墙
    wallGroup.add(pieceBox(0, -0.05, roomD / 2, roomW, 0.1, roomD, '#c9a06a'));          // 木地板
    wallGroup.add(pieceBox(0, roomH + 0.05, roomD / 2, roomW, 0.1, roomD, '#f4f1ea'));   // 天花板
    wallGroup.add(pieceBox(-roomW / 2, roomH / 2, roomD / 2, 0.12, roomH, roomD, '#efe9de')); // 左墙
    wallGroup.add(pieceBox(roomW / 2, roomH / 2, roomD / 2, 0.12, roomH, roomD, '#efe9de'));  // 右墙

    // 窗台板（窗款式才有）
    if (style.cat === '窗') {
      wallGroup.add(pieceBox(0, sill - 0.02, 0.14, W + 0.25, 0.04, 0.28, '#f7f4ec'));
    }

    // 点缀：绿植（简单几何）
    addPlant(wallGroup, -1.9, 1.0, roomD - 0.7);
    addPlant(wallGroup, 1.7, 1.15, roomD - 0.5);

    scene.background = new THREE.Color('#10161e');
    scene.fog = null;
    hemi.intensity = 0.7;
    sun.intensity = 0.9;
    sun.color.set('#ffedd0');
  }

  /* ---- 室外场景：立面墙 + 地面 + 天空 + 灌木 ---- */
  function buildOutdoor(st) {
    const style = Models.getStyleById(st.styleId);
    const W = st.w * M, H = st.h * M, sill = style.sill * M;
    const wallW = 5.6, wallH = 3.6;
    wallGroup = new THREE.Group();

    // 立面墙（开洞）
    const holeW = W + 0.03, holeH = H + 0.03;
    wallGroup.add(buildWallWithHole(0, wallW, wallH, 0, sill + H / 2, holeW, holeH, wallMat('#d8c9a8')));

    // 地面
    const ground = new THREE.Mesh(
      new THREE.BoxGeometry(14, 0.2, 14), wallMat('#9db078'));
    ground.position.set(0, -0.1, 0);
    ground.receiveShadow = true;
    wallGroup.add(ground);

    // 台阶（门款式：门外台阶）
    if (style.cat === '门') {
      wallGroup.add(pieceBox(0, 0.07, 0.7, W + 1.2, 0.14, 1.0, '#c2b49a'));
    }

    // 灌木点缀
    addBush(wallGroup, -2.6, 1.6);
    addBush(wallGroup, 2.6, 1.9);
    addBush(wallGroup, -2.8, 2.6);
    addBush(wallGroup, 2.8, 2.2);

    scene.background = new THREE.Color('#b7d9ec');
    scene.fog = new THREE.Fog('#c7dce8', 14, 42);
    hemi.intensity = 1.05;
    sun.intensity = 1.2;
    sun.color.set('#ffffff');
  }

  function pieceBox(cx, cy, cz, sx, sy, sz, hex) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), wallMat(hex));
    m.position.set(cx, cy, cz);
    m.castShadow = true; m.receiveShadow = true;
    return m;
  }

  /* 室内绿植：花盆 + 树冠 */
  function addPlant(g, x, y, z) {
    g.add(pieceBox(x, y + 0.12, z, 0.22, 0.24, 0.22, '#a5673f'));
    const crown = new THREE.Mesh(new THREE.SphereGeometry(0.2, 12, 10), wallMat('#5f8a4e'));
    crown.position.set(x, y + 0.42, z);
    crown.castShadow = true;
    g.add(crown);
  }

  /* 室外灌木 */
  function addBush(g, x, z) {
    const b = new THREE.Mesh(new THREE.SphereGeometry(0.38, 12, 10), wallMat('#6d9450'));
    b.position.set(x, 0.3, z);
    b.scale.y = 0.75;
    b.castShadow = true; b.receiveShadow = true;
    g.add(b);
  }

  /* ---- 重建场景（参数变化时调用） ---- */
  function rebuild() {
    if (!state) return;
    try {
      _rebuildInner();
    } catch (e) {
      console.error('场景重建失败:', e);
    }
  }

  function _rebuildInner() {
    clearSceneObjects();

    const style = Models.getStyleById(state.styleId);
    if (state.scene === 'outdoor') buildOutdoor(state);
    else buildIndoor(state);

    // 墙体与场景物件
    if (wallGroup) scene.add(wallGroup);

    // 门窗模型（group 中心即洞口中心）
    productGroup = Models.buildProduct(state);
    productGroup.position.set(0, (style.sill + state.h / 2) * M, 0);
    scene.add(productGroup);

    // 相机目标对准门窗中心
    const cy = (style.sill + state.h / 2) * M;
    controls.target.set(0, cy, 0);
    if (firstFit || fitPending) { fitCamera(); firstFit = false; fitPending = false; }
  }

  let fitPending = false;
  function requestFit() { fitPending = true; dirty = true; }

  /* 相机自动取景：按门窗尺寸计算合适距离 */
  function fitCamera() {
    const style = Models.getStyleById(state.styleId);
    const W = state.w * M, H = state.h * M;
    const cy = (style.sill + state.h / 2) * M;
    const dist = Math.max(W, H) * 1.5 + 0.9;
    const a = 0.55; // 相机相对位置角度
    let cx = dist * Math.cos(a), cz = dist * Math.sin(a), camY = cy + dist * 0.42;
    if (state.scene !== 'outdoor') {
      // 室内：把相机收进房间内，避免被侧墙/天花板挡住视线
      cx = Math.min(cx, 1.8);
      cz = Math.min(cz, 3.0);
      camY = Math.min(camY, 2.5);
    }
    camera.position.set(cx, camY, cz);
    controls.target.set(0, cy, 0);
    controls.minDistance = Math.max(0.4, Math.min(W, H) * 0.35);
    camera.lookAt(controls.target); // 立即朝向目标（同步渲染时方向正确）
    clampCamera();
  }

  /* 高分辨率导出 */
  function renderToDataURL(pixelRatio) {
    const old = renderer.getPixelRatio();
    renderer.setPixelRatio(pixelRatio || 2);
    renderer.render(scene, camera);
    const url = renderer.domElement.toDataURL('image/png');
    renderer.setPixelRatio(old);
    return url;
  }

  return { init, setState, setActive, requestFit, renderToDataURL, resize };
})();
