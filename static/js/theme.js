/**
 * Theme Engine: Light, Dark Obsidian & Pure AMOLED Night
 * Krishna Priyatham Portfolio & Blog Design System
 */

(function () {
  'use strict';

  var KEY = 'theme';

  function injectNightStyles() {
    if (document.getElementById('theme-night-styles')) return;
    var style = document.createElement('style');
    style.id = 'theme-night-styles';
    style.textContent = `
      /* Pure AMOLED Pitch Black Night Mode Overrides */
      html.night,
      html.night body {
        background-color: #000000 !important;
        color: #f8fafc !important;
      }

      html.night nav {
        background-color: rgba(0, 0, 0, 0.94) !important;
        border-bottom-color: rgba(255, 255, 255, 0.12) !important;
        box-shadow: 0 4px 25px rgba(0, 0, 0, 0.85) !important;
      }

      html.night #blog-mobile-menu {
        background-color: rgba(5, 5, 8, 0.98) !important;
        border-color: rgba(255, 255, 255, 0.12) !important;
      }

      html.night footer {
        background-color: #000000 !important;
        border-top-color: rgba(255, 255, 255, 0.12) !important;
      }

      /* Card, article, post, and container surfaces */
      html.night .bg-white,
      html.night .bg-slate-50,
      html.night .dark\\:bg-slate-900,
      html.night .dark\\:bg-slate-900\\/50,
      html.night .dark\\:bg-slate-900\\/60,
      html.night .dark\\:bg-slate-900\\/70,
      html.night .dark\\:bg-slate-900\\/80,
      html.night .dark\\:bg-slate-900\\/90,
      html.night .dark\\:bg-slate-900\\/95,
      html.night .dark\\:bg-slate-950,
      html.night .dark\\:bg-slate-950\\/50,
      html.night .dark\\:bg-slate-950\\/60,
      html.night article,
      html.night section.bg-white,
      html.night .post-card,
      html.night .article-card,
      html.night .editor-card,
      html.night .preview-card {
        background-color: #050508 !important;
      }

      html.night .dark\\:bg-slate-800,
      html.night .dark\\:bg-slate-800\\/50,
      html.night .dark\\:bg-slate-800\\/70,
      html.night .dark\\:bg-slate-800\\/80 {
        background-color: #0e0e14 !important;
      }

      html.night .dark\\:border-slate-800,
      html.night .dark\\:border-slate-800\\/50,
      html.night .dark\\:border-slate-800\\/60,
      html.night .dark\\:border-slate-800\\/70,
      html.night .dark\\:border-slate-800\\/80,
      html.night .dark\\:border-slate-700,
      html.night .dark\\:border-slate-700\\/50,
      html.night .dark\\:border-slate-700\\/60 {
        border-color: rgba(255, 255, 255, 0.12) !important;
      }

      html.night input,
      html.night textarea,
      html.night select {
        background-color: #08080c !important;
        border-color: rgba(255, 255, 255, 0.15) !important;
        color: #ffffff !important;
      }

      html.night .dark\\:text-white {
        color: #ffffff !important;
      }
      html.night .dark\\:text-slate-200 {
        color: #f1f5f9 !important;
      }
      html.night .dark\\:text-slate-300 {
        color: #e2e8f0 !important;
      }
      html.night .dark\\:text-slate-400 {
        color: #94a3b8 !important;
      }

      html.night [data-theme-toggle] {
        color: #22d3ee !important;
      }
    `;
    if (document.head) {
      document.head.appendChild(style);
    } else {
      document.addEventListener('DOMContentLoaded', function () {
        document.head.appendChild(style);
      });
    }
  }

  injectNightStyles();

  function stored() {
    try {
      var val = localStorage.getItem(KEY);
      if (val === 'light' || val === 'dark' || val === 'night') return val;
      // Legacy compatibility
      var legacy = localStorage.getItem('darkMode');
      if (legacy === 'enabled') return 'dark';
      if (legacy === 'disabled') return 'light';
    } catch (e) {
      return null;
    }
    return null;
  }

  function preferred() {
    return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  }

  function apply(theme) {
    var root = document.documentElement;
    root.setAttribute('data-theme', theme);
    root.classList.toggle('dark', theme === 'dark' || theme === 'night');
    root.classList.toggle('night', theme === 'night');

    if (document.body) {
      document.body.classList.toggle('dark-mode', theme === 'dark' || theme === 'night');
      document.body.classList.toggle('night-mode', theme === 'night');
      document.body.classList.toggle('light-mode', theme === 'light');
    }
  }

  // Apply immediately to prevent flash of wrong theme
  var currentTheme = stored() || preferred();
  apply(currentTheme);

  window.getTheme = function () {
    var root = document.documentElement;
    if (root.classList.contains('night')) return 'night';
    if (root.classList.contains('dark')) return 'dark';
    return 'light';
  };

  function refreshIcons() {
    var theme = window.getTheme();
    Array.prototype.forEach.call(document.querySelectorAll('[data-theme-toggle]'), function (btn) {
      var sun = btn.querySelector('[data-icon-sun]');
      var moon = btn.querySelector('[data-icon-moon]');
      var night = btn.querySelector('[data-icon-night]');

      // Auto-inject night icon if not present in template markup
      if (!night) {
        var temp = document.createElement('span');
        temp.innerHTML = '<svg data-icon-night class="w-5 h-5 hidden" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M19 3v4m2-2h-4"/></svg>';
        night = temp.firstElementChild;
        btn.appendChild(night);
      }

      if (sun) sun.classList.toggle('hidden', theme !== 'light');
      if (moon) moon.classList.toggle('hidden', theme !== 'dark');
      if (night) night.classList.toggle('hidden', theme !== 'night');

      var label = theme === 'light' ? 'Current: Light Mode (click for Dark Obsidian)' :
                  theme === 'dark' ? 'Current: Dark Obsidian (click for Night AMOLED)' :
                  'Current: Night AMOLED (click for Light Mode)';
      btn.setAttribute('aria-label', label);
      btn.setAttribute('title', label);
    });
  }

  window.setTheme = function (theme) {
    if (theme !== 'light' && theme !== 'dark' && theme !== 'night') {
      theme = 'dark';
    }
    try {
      localStorage.setItem(KEY, theme);
      localStorage.setItem('darkMode', theme === 'light' ? 'disabled' : 'enabled');
    } catch (e) {}

    apply(theme);
    refreshIcons();

    try {
      window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
    } catch (e) {}
  };

  window.toggleTheme = function () {
    var cur = window.getTheme();
    var next = cur === 'light' ? 'dark' : (cur === 'dark' ? 'night' : 'light');
    window.setTheme(next);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      apply(currentTheme);
      refreshIcons();
    });
  } else {
    apply(currentTheme);
    refreshIcons();
  }
})();
