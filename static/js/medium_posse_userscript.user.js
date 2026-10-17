// ==UserScript==
// @name         Medium POSSE Auto-Paster & Bridge Helper
// @namespace    https://potluri-krishna-priyatham.tech/
// @version      1.0.0
// @description  Bypasses Medium's API & Cloudflare bot protection by reading window.name and auto-pasting blog articles into Medium story editor.
// @author       Kittu Priyatham
// @match        https://medium.com/new-story*
// @match        https://*.medium.com/new-story*
// @icon         https://medium.com/favicon.ico
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  console.log('[Medium POSSE Bridge] Initializing...');

  // 1. Check window.name payload
  var rawData = window.name;
  if (!rawData) {
    console.log('[Medium POSSE Bridge] No window.name payload found. Normal editor session.');
    return;
  }

  var payload = null;
  try {
    payload = JSON.parse(rawData);
  } catch (e) {
    console.log('[Medium POSSE Bridge] window.name is not JSON. Skipping.');
    return;
  }

  if (!payload || !payload.posseMedium) {
    console.log('[Medium POSSE Bridge] Payload not intended for POSSE Medium bridge.');
    return;
  }

  // 2. Immediately clear window.name to prevent duplicate triggering on refresh
  window.name = '';
  console.log('[Medium POSSE Bridge] Captured syndication payload:', payload.title);

  // 3. Helper to wait for DOM element to mount
  function waitForElement(selector, timeoutMs) {
    return new Promise(function (resolve, reject) {
      var startTime = Date.now();
      var check = function () {
        var el = document.querySelector(selector);
        if (el) {
          resolve(el);
          return;
        }
        if (Date.now() - startTime > timeoutMs) {
          reject(new Error('Timeout waiting for: ' + selector));
          return;
        }
        requestAnimationFrame(check);
      };
      check();
    });
  }

  // 4. Inject payload into Medium Editor
  async function injectContent() {
    try {
      // Medium's story editor uses contenteditable with data-block-id or data-selectable-paragraph / role="textbox"
      // Primary container selectors for Medium's editor:
      var titleSelector = 'h3[data-default-value="Title"], [data-selectable-paragraph][data-testid="editorTitleBlock"], h3.graf--title, h1[contenteditable="true"]';
      var bodySelector = 'div[contenteditable="true"][role="textbox"], article div[contenteditable="true"], .postArticle-content [contenteditable="true"]';

      console.log('[Medium POSSE Bridge] Waiting for editor DOM elements...');
      
      // Wait for any contenteditable editor container
      var editor = await waitForElement('div[contenteditable="true"], [contenteditable="true"]', 15000);
      console.log('[Medium POSSE Bridge] Contenteditable editor mounted:', editor);

      // Give ProseMirror / Draft.js 800ms to finalize its internal hooks
      await new Promise(function (res) { setTimeout(res, 800); });

      // Build HTML snippet for paste event
      var htmlToPaste = '';
      if (payload.title) {
        htmlToPaste += '<h1>' + payload.title + '</h1>\n';
      }
      if (payload.html) {
        htmlToPaste += payload.html;
      } else if (payload.canonicalUrl) {
        htmlToPaste += '<p><a href="' + payload.canonicalUrl + '">' + payload.canonicalUrl + '</a></p>';
      }

      var textFallback = (payload.title ? payload.title + '\n\n' : '') +
                         (payload.canonicalUrl ? 'Originally published at ' + payload.canonicalUrl : '');

      // Focus editor
      editor.focus();

      // Programmatically dispatch synthetic ClipboardEvent ('paste')
      var dt = new DataTransfer();
      dt.setData('text/html', htmlToPaste);
      dt.setData('text/plain', textFallback);

      var pasteEvent = new ClipboardEvent('paste', {
        bubbles: true,
        cancelable: true,
        composed: true,
        clipboardData: dt
      });

      console.log('[Medium POSSE Bridge] Dispatching synthetic paste event...');
      var notCancelled = editor.dispatchEvent(pasteEvent);

      if (!notCancelled) {
        console.log('[Medium POSSE Bridge] Paste event handled by Medium successfully.');
      } else {
        console.log('[Medium POSSE Bridge] Native dispatch completed (default action allowed).');
      }

      // Visual indicator / toast confirmation
      var banner = document.createElement('div');
      banner.style.position = 'fixed';
      banner.style.bottom = '24px';
      banner.style.right = '24px';
      banner.style.zIndex = '999999';
      banner.style.padding = '14px 20px';
      banner.style.borderRadius = '12px';
      banner.style.background = '#1a8917';
      banner.style.color = '#ffffff';
      banner.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      banner.style.fontSize = '14px';
      banner.style.boxShadow = '0 6px 20px rgba(0,0,0,0.2)';
      banner.style.display = 'flex';
      banner.style.alignItems = 'center';
      banner.style.gap = '8px';
      banner.innerHTML = '<strong>POSSE Bridge:</strong> Article & Assets imported into Medium!';
      document.body.appendChild(banner);

      setTimeout(function () {
        banner.style.transition = 'opacity 0.6s ease';
        banner.style.opacity = '0';
        setTimeout(function () { banner.remove(); }, 600);
      }, 5000);

    } catch (err) {
      console.error('[Medium POSSE Bridge] Error inserting story content:', err);
    }
  }

  // Trigger when ready
  if (document.readyState === 'complete') {
    injectContent();
  } else {
    window.addEventListener('load', injectContent);
  }
})();
