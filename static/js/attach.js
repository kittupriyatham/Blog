(function () {
  function insertAtCursor(textarea, text) {
    if (!textarea) return 0;
    var start = textarea.selectionStart == null ? textarea.value.length : textarea.selectionStart;
    var end = textarea.selectionEnd == null ? textarea.value.length : textarea.selectionEnd;
    textarea.value = textarea.value.slice(0, start) + text + textarea.value.slice(end);
    textarea.selectionStart = textarea.selectionEnd = start + text.length;
    textarea.focus();
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    return start;
  }

  window.initAttachMenu = function () {
    var btn = document.getElementById('attach-btn');
    var menu = document.getElementById('attach-menu');
    var articlePicker = document.getElementById('article-picker');
    var postPicker = document.getElementById('post-picker');
    var fileBtn = document.getElementById('attach-file');
    var articleBtn = document.getElementById('attach-article');
    var postBtn = document.getElementById('attach-post');
    var codeBtn = document.getElementById('attach-code');
    var fileInput = document.getElementById('attach-file-input');
    var textarea = document.getElementById('post-content');
    if (!btn || !menu) return;

    var pickers = [articlePicker, postPicker].filter(Boolean);

    function hide(el) { if (el) el.classList.add('hidden'); }
    function closeAll() {
      hide(menu);
      pickers.forEach(hide);
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (menu.classList.contains('hidden')) { closeAll(); menu.classList.remove('hidden'); }
      else { closeAll(); }
    });
    [menu].concat(pickers).forEach(function (el) {
      el.addEventListener('click', function (e) { e.stopPropagation(); });
    });

    if (fileBtn && fileInput) {
      fileBtn.addEventListener('click', function () { closeAll(); fileInput.click(); });
    }
    function togglePicker(picker) {
      var wasHidden = picker.classList.contains('hidden');
      closeAll();
      if (wasHidden) picker.classList.remove('hidden');
    }
    if (articleBtn && articlePicker) articleBtn.addEventListener('click', function () { menu.classList.add('hidden'); togglePicker(articlePicker); });
    if (postBtn && postPicker) postBtn.addEventListener('click', function () { menu.classList.add('hidden'); togglePicker(postPicker); });

    if (codeBtn && textarea) {
      codeBtn.addEventListener('click', function () {
        var pos = insertAtCursor(textarea, '```\n\n```');
        textarea.selectionStart = textarea.selectionEnd = pos + 4;
        closeAll();
      });
    }

    Array.prototype.forEach.call(document.querySelectorAll('.mention-article, .mention-post'), function (el) {
      el.addEventListener('click', function () {
        insertAtCursor(textarea, el.getAttribute('data-link'));
        closeAll();
      });
    });

    document.addEventListener('click', closeAll);
  };
})();
