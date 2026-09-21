// ---
// Uptime Timeline Graph
let currentUptimeMac = '';
let currentUptimeName = '';

function loadUptimeGraph(mac, name) {
  currentUptimeMac = mac;
  currentUptimeName = name;
  document.getElementById('uptimeDeviceName').textContent = name;
  document.getElementById('uptimeTimeRange').value = '24';
  refreshUptimeGraph();
}

function refreshUptimeGraph() {
  const hours = document.getElementById('uptimeTimeRange').value;
  fetch(`${uptime_history_url}?mac_address=${encodeURIComponent(currentUptimeMac)}&hours=${hours}`)
    .then(response => response.json())
    .then(data => {
      drawUptimeGraph(data, parseFloat(hours));
    })
    .catch(err => {
      console.error('Failed to load uptime history:', err);
      const canvas = document.getElementById('uptimeCanvas');
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      document.getElementById('uptimeStats').textContent = 'Failed to load uptime data.';
    });
}

function drawUptimeGraph(data, hours) {
  const canvas = document.getElementById('uptimeCanvas');
  const container = document.getElementById('uptimeGraphContainer');

  // Set canvas resolution to match display size
  const dpr = window.devicePixelRatio || 1;
  const rect = container.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = rect.height + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);

  const w = rect.width;
  const h = rect.height;
  const barTop = 20;
  const barHeight = 40;
  const tickAreaTop = barTop + barHeight + 5;

  const since = data.since;
  const now = data.now;
  const totalDuration = now - since;

  if (totalDuration <= 0) {
    ctx.fillStyle = '#6c757d';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No data available', w / 2, h / 2);
    document.getElementById('uptimeStats').textContent = '';
    return;
  }

  const COLORS = {
    online: '#4CAF50',
    offline: '#ff0000',
    unknown: '#6c757d'
  };

  // Build segments from events
  const segments = [];
  let currentState = data.initial_state; // 'online', 'offline', or 'unknown'
  let currentStart = since;

  for (const event of data.events) {
    if (event.timestamp > currentStart) {
      segments.push({
        start: currentStart,
        end: event.timestamp,
        state: currentState
      });
    }
    currentState = event.state;
    currentStart = event.timestamp;
  }

  // Final segment to now
  if (currentStart < now) {
    segments.push({
      start: currentStart,
      end: now,
      state: currentState
    });
  }

  // If no segments at all, fill with unknown
  if (segments.length === 0) {
    segments.push({
      start: since,
      end: now,
      state: 'unknown'
    });
  }

  // Draw rounded background
  const radius = 6;
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(0, barTop, w, barHeight, radius);
  ctx.clip();

  // Draw each segment
  for (const seg of segments) {
    const x1 = ((seg.start - since) / totalDuration) * w;
    const x2 = ((seg.end - since) / totalDuration) * w;
    ctx.fillStyle = COLORS[seg.state] || COLORS.unknown;
    ctx.fillRect(x1, barTop, Math.max(x2 - x1, 1), barHeight);
  }
  ctx.restore();

  // Draw border around the bar
  ctx.strokeStyle = 'rgba(128, 128, 128, 0.4)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(0, barTop, w, barHeight, radius);
  ctx.stroke();

  // Draw time ticks
  const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
  ctx.fillStyle = isDark ? '#adb5bd' : '#6c757d';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'center';

  const tickCount = Math.min(Math.max(Math.floor(w / 100), 3), 10);
  for (let i = 0; i <= tickCount; i++) {
    const ratio = i / tickCount;
    const x = ratio * w;
    const t = since + ratio * totalDuration;
    const date = new Date(t * 1000);

    // Draw tick mark
    ctx.strokeStyle = isDark ? '#adb5bd' : '#6c757d';
    ctx.beginPath();
    ctx.moveTo(x, barTop + barHeight);
    ctx.lineTo(x, barTop + barHeight + 4);
    ctx.stroke();

    // Format label based on hours range
    let label;
    if (hours <= 24) {
      label = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (hours <= 168) {
      label = date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
              date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else {
      label = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    ctx.fillText(label, x, tickAreaTop + 14);
  }

  // Update start/end labels
  const startDate = new Date(since * 1000);
  const endDate = new Date(now * 1000);
  document.getElementById('uptimeStartLabel').textContent = '';
  document.getElementById('uptimeEndLabel').textContent = '';

  // Calculate uptime percentage
  let onlineTime = 0;
  let offlineTime = 0;
  for (const seg of segments) {
    const duration = seg.end - seg.start;
    if (seg.state === 'online') onlineTime += duration;
    else if (seg.state === 'offline') offlineTime += duration;
  }
  const knownTime = onlineTime + offlineTime;
  const uptimePct = knownTime > 0 ? ((onlineTime / knownTime) * 100).toFixed(1) : '—';
  const totalEvents = data.events.length;

  function formatDuration(secs) {
    if (secs < 60) return Math.round(secs) + 's';
    if (secs < 3600) return Math.round(secs / 60) + 'm';
    if (secs < 86400) return (secs / 3600).toFixed(1) + 'h';
    return (secs / 86400).toFixed(1) + 'd';
  }

  document.getElementById('uptimeStats').textContent =
    `Uptime: ${uptimePct}% · Online: ${formatDuration(onlineTime)} · Offline: ${formatDuration(offlineTime)} · ${totalEvents} state change(s)`;

  // Tooltip on hover
  canvas.onmousemove = function(e) {
    const canvasRect = canvas.getBoundingClientRect();
    const mx = e.clientX - canvasRect.left;
    const my = e.clientY - canvasRect.top;

    if (my >= barTop && my <= barTop + barHeight && mx >= 0 && mx <= w) {
      const ratio = mx / w;
      const t = since + ratio * totalDuration;
      const date = new Date(t * 1000);

      // Find which segment this falls in
      let hoveredState = 'unknown';
      for (const seg of segments) {
        if (t >= seg.start && t <= seg.end) {
          hoveredState = seg.state;
          break;
        }
      }

      const stateLabel = hoveredState === 'online' ? 'RUNNING' : (hoveredState === 'offline' ? 'OFF' : 'Unknown');
      canvas.title = `${date.toLocaleString()} — ${stateLabel}`;
      canvas.style.cursor = 'crosshair';
    } else {
      canvas.title = '';
      canvas.style.cursor = 'default';
    }
  };

  canvas.onmouseleave = function() {
    canvas.title = '';
    canvas.style.cursor = 'default';
  };
}

// Re-draw on window resize while modal is open
window.addEventListener('resize', function() {
  const modal = document.getElementById('uptimeModal');
  if (modal && modal.classList.contains('show') && currentUptimeMac) {
    refreshUptimeGraph();
  }
});
