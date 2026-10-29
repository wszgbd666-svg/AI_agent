/* ============================================================
 * 导出：3D 渲染图 / 2D 图纸 / 报价单 → PNG 下载
 * 统一走预览弹窗（手机浏览器下载限制时可用长按保存）
 * ============================================================ */

const Export = (function () {
  let currentDataURL = null;
  let currentName = '';

  function showModal(dataURL, title, name) {
    currentDataURL = dataURL;
    currentName = name;
    const modal = document.getElementById('export-modal');
    document.getElementById('export-title').textContent = title;
    document.getElementById('export-img').src = dataURL;
    modal.hidden = false;
  }

  function closeModal() {
    document.getElementById('export-modal').hidden = true;
    currentDataURL = null;
  }

  function toastMsg(msg) {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3000);
  }

  function download() {
    if (!currentDataURL) return;
    // 安卓 App 内：通过原生接口保存到相册
    if (window.Android && window.Android.saveImage) {
      const r = window.Android.saveImage(currentDataURL);
      if (r && r.indexOf('OK|') === 0) {
        toastMsg('✅ 已保存到 ' + r.slice(3));
      } else {
        toastMsg('保存失败：' + (r ? r.slice(4) : '未知错误'));
      }
      closeModal();
      return;
    }
    const a = document.createElement('a');
    a.href = currentDataURL;
    a.download = currentName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  /* 当前视图导出（由 main.js 调用） */
  function exportCurrentView(state) {
    if (state.view === '2d') {
      showModal(Drawing.exportPNG(), '2D 立面图纸', '门窗图纸_' + state.styleId + '.png');
    } else {
      try {
        showModal(SceneManager.renderToDataURL(2), '3D 效果图', '小贤门窗_' + state.styleId + '.png');
      } catch (e) {
        toastMsg('3D 渲染不可用（当前为 2D 模式）');
      }
    }
  }

  function exportQuote(state) {
    const customer = document.getElementById('q-customer').value.trim();
    const address = document.getElementById('q-address').value.trim();
    showModal(Quote.toCanvas(state, customer, address).toDataURL('image/png'),
      '报价单', '门窗报价单.png');
  }

  function bind() {
    document.getElementById('btn-close-modal').addEventListener('click', closeModal);
    document.getElementById('btn-download').addEventListener('click', () => {
      download();
      closeModal();
    });
    document.getElementById('export-modal').addEventListener('click', e => {
      if (e.target.id === 'export-modal') closeModal();
    });
  }

  return { showModal, closeModal, exportCurrentView, exportQuote, bind };
})();
