/**
 * Interactive Command Palette (Ctrl+K)
 * Krishna Priyatham Portfolio & Blog Design System
 */

(function () {
  'use strict';

  var COMMANDS = [
    { title: 'Feed', desc: 'Latest articles, notes & research updates', url: '/', icon: 'fas fa-stream' },
    { title: 'Articles', desc: 'In-depth long-form technical research and guides', url: '/articles', icon: 'fas fa-newspaper' },
    { title: 'Posts', desc: 'Short-form engineering thoughts & snippets', url: '/posts', icon: 'fas fa-comment-alt' },
    { title: 'About the Author', desc: 'Read background, research domains & 3D avatar', url: '/about', icon: 'fas fa-user-astronaut' },
    { title: 'AI Studio', desc: 'Interactive LLM chat, ideation and assistant', url: '/ai_studio', icon: 'fas fa-wand-magic-sparkles' },
    { title: 'Analytics', desc: 'Platform traffic, engagement & syndication metrics', url: '/admin/analytics', icon: 'fas fa-chart-line' },
    { title: 'Portfolio Website', desc: 'Return to main engineering portfolio', url: 'https://potluri-krishna-priyatham.tech', external: true, icon: 'fas fa-external-link-alt' },
    { title: 'RSS Feed', desc: 'Subscribe to RSS feed in reader', url: '/rss.xml', external: true, icon: 'fas fa-rss' },
    { title: 'Cycle Theme', desc: 'Switch between Light, Dark Obsidian, and Night AMOLED', action: 'toggleTheme', icon: 'fas fa-circle-half-stroke' },
    { title: 'Light Mode', desc: 'Switch to crisp editorial Alabaster & Indigo theme', action: 'setThemeLight', icon: 'fas fa-sun' },
    { title: 'Dark Mode', desc: 'Switch to Quantum Obsidian Slate & Neon theme', action: 'setThemeDark', icon: 'fas fa-moon' },
    { title: 'Night Mode', desc: 'Switch to Pure AMOLED Pitch Black theme', action: 'setThemeNight', icon: 'fas fa-star' }
  ];

  function getActiveTheme() {
    if (typeof window.getTheme === 'function') {
      return window.getTheme();
    }
    var root = document.documentElement;
    var body = document.body;
    if (root.classList.contains('night') || (body && body.classList.contains('night-mode')) || root.getAttribute('data-theme') === 'night') {
      return 'night';
    }
    if (root.classList.contains('dark') || (body && body.classList.contains('dark-mode')) || root.getAttribute('data-theme') === 'dark') {
      return 'dark';
    }
    return 'light';
  }

  function injectPaletteUI() {
    if (document.getElementById('cmd-palette-modal')) return;

    // Inject styles
    var style = document.createElement('style');
    style.id = 'cmd-palette-styles';
    style.textContent = `
      #cmd-palette-backdrop {
        position: fixed;
        inset: 0;
        z-index: 99999;
        display: none;
        align-items: flex-start;
        justify-content: center;
        padding-top: 14vh;
        animation: cmdFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
      }
      #cmd-palette-backdrop.active {
        display: flex;
      }

      /* Light Theme Variables */
      #cmd-palette-backdrop[data-palette-theme="light"],
      :root[data-theme="light"] #cmd-palette-backdrop,
      body.light-mode #cmd-palette-backdrop {
        background: rgba(15, 23, 42, 0.35);
        --cmd-bg: rgba(255, 255, 255, 0.98);
        --cmd-border: rgba(99, 102, 241, 0.28);
        --cmd-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 25px rgba(99, 102, 241, 0.12);
        --cmd-divider: rgba(0, 0, 0, 0.08);
        --cmd-text: #0f172a;
        --cmd-text-muted: #64748b;
        --cmd-accent: #4f46e5;
        --cmd-kbd-bg: rgba(0, 0, 0, 0.06);
        --cmd-kbd-text: #64748b;
        --cmd-item-hover-bg: rgba(99, 102, 241, 0.09);
        --cmd-item-hover-color: #4f46e5;
        --cmd-item-icon-bg: rgba(0, 0, 0, 0.04);
        --cmd-footer-bg: rgba(0, 0, 0, 0.02);
        --cmd-footer-border: rgba(0, 0, 0, 0.06);
      }

      /* Dark Obsidian Theme Variables (Default) */
      #cmd-palette-backdrop,
      #cmd-palette-backdrop[data-palette-theme="dark"],
      :root[data-theme="dark"] #cmd-palette-backdrop,
      body.dark-mode #cmd-palette-backdrop {
        background: rgba(3, 7, 18, 0.75);
        --cmd-bg: rgba(15, 23, 42, 0.96);
        --cmd-border: rgba(6, 182, 212, 0.35);
        --cmd-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 35px rgba(6, 182, 212, 0.2);
        --cmd-divider: rgba(255, 255, 255, 0.08);
        --cmd-text: #f8fafc;
        --cmd-text-muted: #94a3b8;
        --cmd-accent: #22d3ee;
        --cmd-kbd-bg: rgba(255, 255, 255, 0.08);
        --cmd-kbd-text: #94a3b8;
        --cmd-item-hover-bg: rgba(6, 182, 212, 0.12);
        --cmd-item-hover-color: #22d3ee;
        --cmd-item-icon-bg: rgba(255, 255, 255, 0.05);
        --cmd-footer-bg: rgba(0, 0, 0, 0.25);
        --cmd-footer-border: rgba(255, 255, 255, 0.06);
      }

      /* Night Pure AMOLED Theme Variables */
      #cmd-palette-backdrop[data-palette-theme="night"],
      :root[data-theme="night"] #cmd-palette-backdrop,
      body.night-mode #cmd-palette-backdrop,
      html.night #cmd-palette-backdrop {
        background: rgba(0, 0, 0, 0.88);
        --cmd-bg: rgba(0, 0, 0, 0.98);
        --cmd-border: rgba(255, 255, 255, 0.16);
        --cmd-shadow: 0 25px 70px -10px rgba(0, 0, 0, 0.98), 0 0 40px rgba(6, 182, 212, 0.15);
        --cmd-divider: rgba(255, 255, 255, 0.12);
        --cmd-text: #ffffff;
        --cmd-text-muted: #cbd5e1;
        --cmd-accent: #22d3ee;
        --cmd-kbd-bg: rgba(255, 255, 255, 0.12);
        --cmd-kbd-text: #cbd5e1;
        --cmd-item-hover-bg: rgba(6, 182, 212, 0.18);
        --cmd-item-hover-color: #22d3ee;
        --cmd-item-icon-bg: rgba(255, 255, 255, 0.08);
        --cmd-footer-bg: rgba(5, 5, 8, 0.95);
        --cmd-footer-border: rgba(255, 255, 255, 0.10);
      }

      #cmd-palette-modal {
        background: var(--cmd-bg);
        border: 1px solid var(--cmd-border);
        border-radius: 20px;
        width: 90%;
        max-width: 580px;
        box-shadow: var(--cmd-shadow);
        overflow: hidden;
        animation: cmdScaleUp 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        font-family: 'Poppins', 'Inter', -apple-system, sans-serif;
        color: var(--cmd-text);
        transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, color 0.2s ease;
      }
      .cmd-input-wrapper {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 20px;
        border-bottom: 1px solid var(--cmd-divider);
      }
      .cmd-input-wrapper i {
        color: var(--cmd-accent);
        font-size: 16px;
      }
      #cmd-palette-input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: var(--cmd-text);
        font-size: 15px;
        font-family: inherit;
      }
      #cmd-palette-input::placeholder {
        color: var(--cmd-text-muted);
      }
      .cmd-kbd-esc {
        font-size: 11px;
        padding: 3px 7px;
        background: var(--cmd-kbd-bg);
        border-radius: 6px;
        color: var(--cmd-kbd-text);
        font-family: monospace;
      }
      .cmd-list {
        max-height: 340px;
        overflow-y: auto;
        padding: 8px;
        list-style: none;
        margin: 0;
      }
      .cmd-item {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 14px;
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.15s ease;
        color: var(--cmd-text);
      }
      .cmd-item:hover, .cmd-item.selected {
        background: var(--cmd-item-hover-bg);
        color: var(--cmd-item-hover-color);
      }
      .cmd-item-icon {
        width: 34px;
        height: 34px;
        border-radius: 8px;
        background: var(--cmd-item-icon-bg);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        flex-shrink: 0;
        color: var(--cmd-accent);
      }
      .cmd-item-text {
        flex: 1;
      }
      .cmd-item-title {
        font-size: 13.5px;
        font-weight: 600;
      }
      .cmd-item-desc {
        font-size: 11.5px;
        color: var(--cmd-text-muted);
        margin-top: 2px;
      }
      .cmd-item-arrow {
        font-size: 11px;
        color: var(--cmd-text-muted);
      }
      .cmd-footer {
        padding: 10px 18px;
        background: var(--cmd-footer-bg);
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 11.5px;
        color: var(--cmd-text-muted);
        border-top: 1px solid var(--cmd-footer-border);
      }
      @keyframes cmdFadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }
      @keyframes cmdScaleUp {
        from { opacity: 0; transform: scale(0.96) translateY(-10px); }
        to { opacity: 1; transform: scale(1) translateY(0); }
      }
    `;
    document.head.appendChild(style);

    // Create backdrop and modal HTML
    var backdrop = document.createElement('div');
    backdrop.id = 'cmd-palette-backdrop';
    backdrop.innerHTML = `
      <div id="cmd-palette-modal" role="dialog" aria-modal="true" aria-label="Command Palette">
        <div class="cmd-input-wrapper">
          <i class="fas fa-terminal"></i>
          <input type="text" id="cmd-palette-input" placeholder="Type a command or jump to page..." autocomplete="off" spellcheck="false" />
          <span class="cmd-kbd-esc">ESC</span>
        </div>
        <ul class="cmd-list" id="cmd-palette-list" role="listbox"></ul>
        <div class="cmd-footer">
          <span>Navigate with <kbd>↑</kbd> <kbd>↓</kbd></span>
          <span>Press <kbd>↵ Enter</kbd> to select</span>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);

    var input = document.getElementById('cmd-palette-input');
    var list = document.getElementById('cmd-palette-list');
    var modal = document.getElementById('cmd-palette-modal');
    var selectedIndex = 0;
    var filtered = COMMANDS;

    function syncPaletteTheme() {
      var activeTheme = getActiveTheme();
      backdrop.setAttribute('data-palette-theme', activeTheme);
      if (modal) modal.setAttribute('data-palette-theme', activeTheme);
    }

    function renderList() {
      list.innerHTML = '';
      if (filtered.length === 0) {
        var empty = document.createElement('li');
        empty.style.padding = '24px';
        empty.style.textAlign = 'center';
        empty.style.color = 'var(--cmd-text-muted, #94a3b8)';
        empty.style.fontSize = '13px';
        empty.textContent = 'No matching commands found.';
        list.appendChild(empty);
        return;
      }

      filtered.forEach(function (cmd, idx) {
        var li = document.createElement('li');
        li.className = 'cmd-item' + (idx === selectedIndex ? ' selected' : '');
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', idx === selectedIndex ? 'true' : 'false');
        li.innerHTML = `
          <div class="cmd-item-icon"><i class="${cmd.icon}"></i></div>
          <div class="cmd-item-text">
            <div class="cmd-item-title">${cmd.title}</div>
            <div class="cmd-item-desc">${cmd.desc}</div>
          </div>
          <i class="fas fa-arrow-right cmd-item-arrow"></i>
        `;
        li.addEventListener('click', function () {
          executeCommand(cmd);
        });
        li.addEventListener('mouseenter', function () {
          selectedIndex = idx;
          updateSelection();
        });
        list.appendChild(li);
      });
    }

    function updateSelection() {
      var items = list.querySelectorAll('.cmd-item');
      items.forEach(function (el, idx) {
        el.classList.toggle('selected', idx === selectedIndex);
        el.setAttribute('aria-selected', idx === selectedIndex ? 'true' : 'false');
      });
      if (items[selectedIndex]) {
        items[selectedIndex].scrollIntoView({ block: 'nearest' });
      }
    }

    function executeCommand(cmd) {
      closePalette();
      if (cmd.action === 'toggleTheme') {
        if (typeof window.toggleTheme === 'function') {
          window.toggleTheme();
        } else {
          var toggleBtn = document.querySelector('[data-theme-toggle]');
          if (toggleBtn) toggleBtn.click();
        }
      } else if (cmd.action === 'setThemeLight') {
        if (typeof window.setTheme === 'function') window.setTheme('light');
      } else if (cmd.action === 'setThemeDark') {
        if (typeof window.setTheme === 'function') window.setTheme('dark');
      } else if (cmd.action === 'setThemeNight') {
        if (typeof window.setTheme === 'function') window.setTheme('night');
      } else if (cmd.url) {
        if (cmd.external) {
          window.open(cmd.url, '_blank', 'noopener,noreferrer');
        } else {
          window.location.href = cmd.url;
        }
      }
    }

    function filterCommands() {
      var q = input.value.trim().toLowerCase();
      if (!q) {
        filtered = COMMANDS;
      } else {
        filtered = COMMANDS.filter(function (cmd) {
          return cmd.title.toLowerCase().indexOf(q) !== -1 || cmd.desc.toLowerCase().indexOf(q) !== -1;
        });
      }
      selectedIndex = 0;
      renderList();
    }

    input.addEventListener('input', filterCommands);

    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % Math.max(1, filtered.length);
        updateSelection();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + filtered.length) % Math.max(1, filtered.length);
        updateSelection();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          executeCommand(filtered[selectedIndex]);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        closePalette();
      }
    });

    backdrop.addEventListener('click', function (e) {
      if (e.target === backdrop) closePalette();
    });

    function openPalette() {
      syncPaletteTheme();
      backdrop.classList.add('active');
      input.value = '';
      filtered = COMMANDS;
      selectedIndex = 0;
      renderList();
      setTimeout(function () { input.focus(); }, 50);
    }

    function closePalette() {
      backdrop.classList.remove('active');
    }

    window.openCommandPalette = openPalette;
    window.closeCommandPalette = closePalette;
    window.addEventListener('themechange', syncPaletteTheme);

    // Observer to catch class changes on documentElement or body
    var themeObserver = new MutationObserver(syncPaletteTheme);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    if (document.body) {
      themeObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    }

    // Listen for Ctrl+K or Cmd+K
    window.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (backdrop.classList.contains('active')) {
          closePalette();
        } else {
          openPalette();
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectPaletteUI);
  } else {
    injectPaletteUI();
  }
})();
