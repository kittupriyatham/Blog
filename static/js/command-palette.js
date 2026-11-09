/**
 * Interactive Command Palette (Ctrl+K)
 * Krishna Priyatham Portfolio & Blog Design System
 */

(function () {
  'use strict';

  var COMMANDS = [
    { title: 'Home', desc: 'Return to portfolio main landing page', url: '/home', icon: 'fas fa-home' },
    { title: 'About Me', desc: 'Read background, research domains & 3D avatar', url: '/about', icon: 'fas fa-user-astronaut' },
    { title: 'Featured Projects', desc: 'Explore AI, Quantum, Web & Engineering works', url: '/projects', icon: 'fas fa-laptop-code' },
    { title: 'Achievements', desc: 'View awards, certifications & academic bento', url: '/achievements', icon: 'fas fa-trophy' },
    { title: 'Resume', desc: 'View and download professional CV & credentials', url: '/resume', icon: 'fas fa-file-alt' },
    { title: 'Contact', desc: 'Get in touch via email, social links & networks', url: '/contact', icon: 'fas fa-paper-plane' },
    { title: 'Engineering Blog', desc: 'Read technical articles, research & guides', url: 'https://blog.potluri-krishna-priyatham.tech', external: true, icon: 'fas fa-book-open' },
    { title: 'Toggle Theme', desc: 'Switch between Dark Obsidian and Light theme', action: 'toggleTheme', icon: 'fas fa-moon' }
  ];

  function injectPaletteUI() {
    if (document.getElementById('cmd-palette-modal')) return;

    // Inject styles
    var style = document.createElement('style');
    style.id = 'cmd-palette-styles';
    style.textContent = `
      #cmd-palette-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(3, 7, 18, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        z-index: 99999;
        display: none;
        align-items: flex-start;
        justify-content: center;
        padding-top: 14vh;
        animation: cmdFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      }
      #cmd-palette-backdrop.active {
        display: flex;
      }
      #cmd-palette-modal {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(6, 182, 212, 0.35);
        border-radius: 20px;
        width: 90%;
        max-width: 580px;
        box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 35px rgba(6, 182, 212, 0.2);
        overflow: hidden;
        animation: cmdScaleUp 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        font-family: 'Poppins', 'Inter', -apple-system, sans-serif;
      }
      body:not(.dark-mode) #cmd-palette-modal {
        background: rgba(255, 255, 255, 0.98);
        border-color: rgba(99, 102, 241, 0.3);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
      }
      .cmd-input-wrapper {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 20px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      }
      body:not(.dark-mode) .cmd-input-wrapper {
        border-bottom-color: rgba(0, 0, 0, 0.08);
      }
      .cmd-input-wrapper i {
        color: #22d3ee;
        font-size: 16px;
      }
      body:not(.dark-mode) .cmd-input-wrapper i {
        color: #4f46e5;
      }
      #cmd-palette-input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: #f8fafc;
        font-size: 15px;
        font-family: inherit;
      }
      body:not(.dark-mode) #cmd-palette-input {
        color: #0f172a;
      }
      #cmd-palette-input::placeholder {
        color: #64748b;
      }
      .cmd-kbd-esc {
        font-size: 11px;
        padding: 3px 7px;
        background: rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        color: #94a3b8;
        font-family: monospace;
      }
      body:not(.dark-mode) .cmd-kbd-esc {
        background: rgba(0, 0, 0, 0.06);
        color: #64748b;
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
        color: #f8fafc;
      }
      body:not(.dark-mode) .cmd-item {
        color: #0f172a;
      }
      .cmd-item:hover, .cmd-item.selected {
        background: rgba(6, 182, 212, 0.12);
        color: #22d3ee;
      }
      body:not(.dark-mode) .cmd-item:hover,
      body:not(.dark-mode) .cmd-item.selected {
        background: rgba(99, 102, 241, 0.08);
        color: #4f46e5;
      }
      .cmd-item-icon {
        width: 34px;
        height: 34px;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.05);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        flex-shrink: 0;
      }
      body:not(.dark-mode) .cmd-item-icon {
        background: rgba(0, 0, 0, 0.04);
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
        color: #94a3b8;
        margin-top: 2px;
      }
      body:not(.dark-mode) .cmd-item-desc {
        color: #64748b;
      }
      .cmd-item-arrow {
        font-size: 11px;
        color: #64748b;
      }
      .cmd-footer {
        padding: 10px 18px;
        background: rgba(0, 0, 0, 0.2);
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 11.5px;
        color: #64748b;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
      }
      body:not(.dark-mode) .cmd-footer {
        background: rgba(0, 0, 0, 0.02);
        border-top-color: rgba(0, 0, 0, 0.06);
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
    var selectedIndex = 0;
    var filtered = COMMANDS;

    function renderList() {
      list.innerHTML = '';
      if (filtered.length === 0) {
        var empty = document.createElement('li');
        empty.style.padding = '24px';
        empty.style.textAlign = 'center';
        empty.style.color = '#94a3b8';
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
        var toggleBtn = document.getElementById('dark-mode-toggle');
        if (toggleBtn) {
          toggleBtn.click();
        } else if (typeof window.toggleTheme === 'function') {
          window.toggleTheme();
        }
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
