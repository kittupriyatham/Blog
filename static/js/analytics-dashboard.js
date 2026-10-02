/* analytics-dashboard.js - vanilla chart renderer for /admin/analytics.
 *
 * Reads window.ANALYTICS_DATA (server-rendered JSON, no framework). Draws an
 * SVG line chart for the daily time series and horizontal CSS bars for the
 * categorical breakdowns. Tables/cards are server-rendered and work without JS.
 */
(function () {
  'use strict';
  var D = window.ANALYTICS_DATA || {};

  function fmtMs(ms) {
    ms = ms || 0;
    var m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000);
    if (m >= 60) { return Math.floor(m / 60) + 'h ' + (m % 60) + 'm'; }
    return m + 'm ' + s + 's';
  }

  function maxVal(items, key) {
    var m = 0;
    for (var i = 0; i < items.length; i++) { var v = items[i][key] || 0; if (v > m) m = v; }
    return m || 1;
  }

  function lineChart(id, items, key, asMs) {
    var el = document.getElementById(id);
    if (!el) return;
    if (!items.length) { el.innerHTML = '<p class="text-xs text-slate-400">No data yet.</p>'; return; }
    var w = 640, h = 128, pad = 26, plotW = w - pad * 2, plotH = h - pad * 2;
    var max = maxVal(items, key);
    var pts = '', circles = '', grid = '';
    for (var g = 0; g <= 4; g++) {
      var gy = pad + (plotH / 4) * g;
      grid += '<line x1="' + pad + '" y1="' + gy.toFixed(1) + '" x2="' + (w - pad) + '" y2="' + gy.toFixed(1) + '" stroke="currentColor" stroke-width="1" opacity="0.08"/>';
    }
    for (var i = 0; i < items.length; i++) {
      var x = pad + plotW * (items.length > 1 ? i / (items.length - 1) : 0.5);
      var y = pad + plotH - ((items[i][key] || 0) / max) * plotH;
      pts += (i ? ' ' : '') + x.toFixed(1) + ',' + y.toFixed(1);
      var lab = asMs ? fmtMs(items[i][key]) : String(items[i][key]);
      var tag = items[i].date || items[i].method || items[i].platform || '';
      circles += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="3" fill="currentColor" opacity="0.55"><title>' + tag + ' - ' + lab + '</title></circle>';
    }
    el.innerHTML = '<svg class="w-full" viewBox="0 0 ' + w + ' ' + h + '" fill="none" xmlns="http://www.w3.org/2000/svg">'
      + grid + '<polyline points="' + pts + '" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>' + circles + '</svg>';
  }

  function barChart(id, items, labelKey, asMs) {
    var el = document.getElementById(id);
    if (!el) return;
    if (!items.length) { el.innerHTML = '<p class="text-xs text-slate-400">No data yet.</p>'; return; }
    var max = maxVal(items, 'count');
    var html = '';
    for (var i = 0; i < items.length; i++) {
      var it = items[i], v = it.count || 0, pct = Math.round((v / max) * 100);
      var lab = it[labelKey] || '';
      var vlabel = asMs ? fmtMs(v) : String(v);
      html += '<div class="mb-2.5"><div class="flex items-center gap-2 text-xs">'
        + '<span class="w-28 max-w-[112px] text-slate-500 dark:text-slate-400 truncate" title="' + lab + '">' + lab + '</span>'
        + '<div class="flex-1 h-3 bg-slate-100 dark:bg-slate-800 rounded overflow-hidden"><div class="h-3 rounded bg-brand-500" style="width:' + pct + '%"></div></div>'
        + '<span class="text-slate-600 dark:text-slate-300 w-16 text-right font-medium">' + vlabel + '</span>'
        + '</div></div>';
    }
    el.innerHTML = html;
  }

  var daily = D.daily || [];
  lineChart('chart-views', daily, 'view', false);
  lineChart('chart-time', daily, 'time_on_blog_ms', true);
  barChart('bar-method', D.by_method || [], 'method', false);
  barChart('bar-platform', D.by_platform || [], 'platform', false);
  barChart('bar-country', D.by_country || [], 'country', false);
  barChart('bar-region', D.by_region || [], 'label', false);

  // Social performance: total engagement (likes + comments + views) per social
  // platform, summed from the cached metrics. Empty until a refresh has cached
  // something - the section's table is server-rendered and stands on its own.
  var social = D.social || {};
  barChart('bar-social', social.by_platform || [], 'platform', false);
})();
