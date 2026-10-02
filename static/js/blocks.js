/* Insertable rich-text blocks.
 *
 * The editor menus (the post/feed editor's Attach menu and the article editor's
 * block menu) are rendered server-side by templates/_rich_blocks_menu.html with
 * `data-kind` values. This file supplies the snippet each entry inserts and the
 * click handling; the `rich_text` Jinja filter (src/content/rich_text.py)
 * renders the syntax on the page. Keep all three in step — the syntax
 * documented in rich_text.py is the contract here.
 */
(function () {
  "use strict";

  var RICHTEXT_SNIPPETS = {
    heading:  '# Section heading',
    quote:    ':::quote\nQuoted text\n:::',
    callout:  ':::callout{type=info}\nSomething worth noting.\n:::',
    link:     ':::link https://example.com\nShort description (optional)\n:::',
    table:    ':::table\n| Header A | Header B |\n| --- | --- |\n| Cell 1 | Cell 2 |\n:::',
    poll:     ':::poll\nYour question?\n- Option one\n- Option two\n:::',
    gallery:  ':::gallery\nhttps://example.com/image-1.jpg\nhttps://example.com/image-2.jpg\n:::',
    toggle:   ':::toggle Click to expand\nHidden content goes here.\n:::',
    cta:      ':::cta https://example.com\nButton label\n:::',
    embed:    ':::embed https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    math:     ':::math\nE = mc^2\n:::',
    footnote: '[^1]\n\n[^1]: Footnote text',
    divider:  ':::divider',
    toc:      ':::toc'
  };

  function insertAtCursor(ta, text) {
    if (!ta) { return; }
    var start = ta.selectionStart == null ? ta.value.length : ta.selectionStart;
    var end = ta.selectionEnd == null ? start : ta.selectionEnd;
    var before = ta.value.slice(0, start);
    // Keep the block on its own lines so the line-oriented parser sees it.
    var prefix = (before.length && !/\n\s*\n$/.test(before)) ? '\n\n' : '';
    var suffix = '\n\n';
    ta.value = before + prefix + text + suffix + ta.value.slice(end);
    var nl = text.indexOf('\n');
    var caret = start + prefix.length + (nl >= 0 ? nl + 1 : text.length);
    ta.selectionStart = ta.selectionEnd = caret;
    ta.focus();
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // Insert a block at the cursor of a plain textarea (post / feed editor).
  function insertRichTextSnippet(ta, kind) {
    var text = RICHTEXT_SNIPPETS[kind];
    if (!ta || !text) { return; }
    insertAtCursor(ta, text);
  }

  // One document-level delegate so it works for every menu and every editor.
  // Capture phase: attach.js stops propagation of clicks inside #attach-menu
  // (so the menu does not close on its own buttons), which would otherwise hide
  // these entries from a bubble-phase listener.
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.rich-text-insert');
    if (!btn) { return; }
    e.preventDefault();
    var kind = btn.getAttribute('data-kind');

    // The article editor registers window.insertRichTextBlock: it adds a whole
    // new text block instead of typing into a single textarea.
    if (btn.closest('#blocks-container') && typeof window.insertRichTextBlock === 'function') {
      window.insertRichTextBlock(btn.closest('.group'), kind);
      return;
    }

    var target = btn.getAttribute('data-target');
    var ta = target ? document.querySelector(target) : null;
    if (!ta && btn.closest('.group')) { ta = btn.closest('.group').querySelector('textarea'); }
    if (!ta) { ta = document.getElementById('post-content'); }
    insertRichTextSnippet(ta, kind);

    var menu = document.getElementById('attach-menu');
    if (menu) { menu.classList.add('hidden'); }
  }, true);

  window.RICHTEXT_SNIPPETS = RICHTEXT_SNIPPETS;
  window.insertRichTextSnippet = insertRichTextSnippet;
})();
