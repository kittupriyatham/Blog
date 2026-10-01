/* analytics.js - first-party, no-third-party web analytics beacon.
 *
 * Posts same-origin events to /api/analytics using navigator.sendBeacon so
 * they survive navigation/unload. Per-page config must be set BEFORE this
 * script loads:
 *
 *   window.ANALYTICS = { page: 'feed'|'post'|'article',
 *                         post_id: 'abc'|null,
 *                         type: 'post'|'article'|null };
 *
 * Captured CLIENT-side: shares, click_out, time_spent (per post/article) and
 * time_on_blog (whole-blog running total). The rest (view, reach_in, post_opened,
 * likes, comments) is recorded server-side in app.py so the displayed counters
 * and the analytics log can never drift apart.
 */
(function () {
  'use strict';
  var CFG = window.ANALYTICS || {};
  var PAGE = CFG.page || 'unknown';
  var POST_ID = CFG.post_id || null;
  var POST_TYPE = CFG.type || null;

  // --- session id (first-party cookie, so the server route can read it too) ---
  function getSid() {
    var m = document.cookie.match(/(?:^|;\s*)__ab_sess=([^;]+)/);
    return m ? m[1] : '';
  }
  var SESSION_ID = getSid();

  // --- utm params currently on the URL ---
  function utm() {
    var out = {};
    var p = new URLSearchParams(location.search);
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'].forEach(function (k) {
      if (p.has(k)) { out[k] = p.get(k); }
    });
    return out;
  }

  function isExternal(href) {
    if (!href) return false;
    try { return new URL(href, location.href).host !== location.host; } catch (e) { return false; }
  }

  function send(ev) {
    var payload = Object.assign({ session_id: SESSION_ID }, utm(), ev);
    var body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/analytics', new Blob([body], { type: 'application/json' }));
    } else {
      var x = new XMLHttpRequest();
      x.open('POST', '/api/analytics', true);
      x.setRequestHeader('Content-Type', 'application/json');
      try { x.send(body); } catch (e) { /* fire-and-forget */ }
    }
  }

  // --- timing: time_spent (per post/article) + time_on_blog (running total) ---
  var ACTIVE = Date.now();
  var TOTAL = 0;
  try { TOTAL = Number(sessionStorage.getItem('__blog_time_total_ms') || '0'); } catch (e) {}
  var FLUSHED = false;

  function flush() {
    if (FLUSHED) return;
    var ms = Date.now() - ACTIVE;
    if (ms < 1000) return; // ignore sub-second reads
    FLUSHED = true;
    TOTAL += Math.round(ms);
    try { sessionStorage.setItem('__blog_time_total_ms', String(TOTAL)); } catch (e) {}
    send({ event: 'time_on_blog', milliseconds: TOTAL, page: PAGE, path: location.pathname });
    if ((PAGE === 'post' || PAGE === 'article') && POST_ID) {
      send({ event: 'time_spent', post_id: POST_ID, type: POST_TYPE, milliseconds: Math.round(ms) });
    }
  }

  function onHide() { flush(); }
  function onShow() { ACTIVE = Date.now(); FLUSHED = false; }

  // --- click hooks (capture phase so beacons fire before navigation) ---
  document.addEventListener('click', function (e) {
    var et = e.target;
    while (et && et.nodeType === 3) { et = et.parentNode; } // text node -> element
    if (!et) return;

    // shares (tagged share buttons carry data-share)
    var sb = et.closest('[data-share]');
    if (sb && sb.dataset.share) {
      send({ event: 'shares', post_id: POST_ID, method: sb.dataset.share });
    }

    // outbound link => click_out
    var a = et.closest('a');
    if (a && isExternal(a.href) && a.href.indexOf('javascript:') !== 0) {
      var host = 'external';
      try { host = new URL(a.href, location.href).hostname.replace(/^www\./, ''); } catch (e2) {}
      send({ event: 'click_out', post_id: POST_ID,
             platform: a.dataset.platform || host, url: a.href });
    }
  }, true);

  function init() {
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { onHide(); } else { onShow(); }
    });
    window.addEventListener('pagehide', onHide);
    window.addEventListener('beforeunload', onHide);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();