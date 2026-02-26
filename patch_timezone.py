import re
import os

html_path = 'src/templates/index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add _timezone and formatDateZ
format_date_code = """
    let _translations = {};
    let _timezone = 'local';
    
    function formatDateZ(utcString) {
      if (!utcString) return "";
      let d = new Date(utcString);
      if (isNaN(d.getTime())) {
        if (!utcString.endsWith('Z')) {
          d = new Date(utcString + 'Z');
        }
      }
      if (isNaN(d.getTime())) return utcString;
      
      let targetDate = d;
      if (_timezone !== 'local' && _timezone.startsWith('UTC')) {
        let offsetStr = _timezone.replace('UTC', '');
        let offsetHours = parseFloat(offsetStr) || 0;
        let ms = d.getTime() + (offsetHours * 3600000);
        targetDate = new Date(ms);
        const pad = n => n.toString().padStart(2, '0');
        return `${targetDate.getUTCFullYear()}-${pad(targetDate.getUTCMonth()+1)}-${pad(targetDate.getUTCDate())} ${pad(targetDate.getUTCHours())}:${pad(targetDate.getUTCMinutes())}:${pad(targetDate.getUTCSeconds())}`;
      } else {
        const pad = n => n.toString().padStart(2, '0');
        return `${targetDate.getFullYear()}-${pad(targetDate.getMonth()+1)}-${pad(targetDate.getDate())} ${pad(targetDate.getHours())}:${pad(targetDate.getMinutes())}:${pad(targetDate.getSeconds())}`;
      }
    }
"""
html = html.replace('let _translations = {};', format_date_code)

# 2. Update loadDashboard
load_dash_code = """$('d-lang').textContent = (d.language || 'en').toUpperCase();
      if (d.timezone) _timezone = d.timezone;"""
html = html.replace("$('d-lang').textContent = (d.language || 'en').toUpperCase();", load_dash_code)

# 3. Update loadSettings
load_set_code = """<fieldset><legend data-i18n="gui_lang_settings">Display & General</legend>
    <div class="chk" style="margin-bottom:12px"><label><input type="checkbox" id="s-hc" ${st.enable_health_check !== false ? 'checked' : ''}> <span data-i18n="gui_enable_hc">Enable PCE Health Check</span></label></div>
    <div class="form-row">
      <div class="form-group">
        <label data-i18n="gui_timezone">Timezone</label>
        <select id="s-timezone" style="width:100%; padding:8px; border-radius:var(--radius); background:var(--bg3); border:1px solid var(--border); color:var(--fg);">
          <option value="local" ${st.timezone === 'local' || !st.timezone ? 'selected' : ''}>Local Browser Time</option>
          <option value="UTC" ${st.timezone === 'UTC' ? 'selected' : ''}>UTC</option>
          <option value="UTC-12" ${st.timezone === 'UTC-12' ? 'selected' : ''}>UTC-12</option>
          <option value="UTC-11" ${st.timezone === 'UTC-11' ? 'selected' : ''}>UTC-11</option>
          <option value="UTC-10" ${st.timezone === 'UTC-10' ? 'selected' : ''}>UTC-10</option>
          <option value="UTC-9" ${st.timezone === 'UTC-9' ? 'selected' : ''}>UTC-9</option>
          <option value="UTC-8" ${st.timezone === 'UTC-8' ? 'selected' : ''}>UTC-8</option>
          <option value="UTC-7" ${st.timezone === 'UTC-7' ? 'selected' : ''}>UTC-7</option>
          <option value="UTC-6" ${st.timezone === 'UTC-6' ? 'selected' : ''}>UTC-6</option>
          <option value="UTC-5" ${st.timezone === 'UTC-5' ? 'selected' : ''}>UTC-5</option>
          <option value="UTC-4" ${st.timezone === 'UTC-4' ? 'selected' : ''}>UTC-4</option>
          <option value="UTC-3" ${st.timezone === 'UTC-3' ? 'selected' : ''}>UTC-3</option>
          <option value="UTC-2" ${st.timezone === 'UTC-2' ? 'selected' : ''}>UTC-2</option>
          <option value="UTC-1" ${st.timezone === 'UTC-1' ? 'selected' : ''}>UTC-1</option>
          <option value="UTC+1" ${st.timezone === 'UTC+1' ? 'selected' : ''}>UTC+1</option>
          <option value="UTC+2" ${st.timezone === 'UTC+2' ? 'selected' : ''}>UTC+2</option>
          <option value="UTC+3" ${st.timezone === 'UTC+3' ? 'selected' : ''}>UTC+3</option>
          <option value="UTC+4" ${st.timezone === 'UTC+4' ? 'selected' : ''}>UTC+4</option>
          <option value="UTC+5" ${st.timezone === 'UTC+5' ? 'selected' : ''}>UTC+5</option>
          <option value="UTC+5.5" ${st.timezone === 'UTC+5.5' ? 'selected' : ''}>UTC+5.5</option>
          <option value="UTC+6" ${st.timezone === 'UTC+6' ? 'selected' : ''}>UTC+6</option>
          <option value="UTC+7" ${st.timezone === 'UTC+7' ? 'selected' : ''}>UTC+7</option>
          <option value="UTC+8" ${st.timezone === 'UTC+8' ? 'selected' : ''}>UTC+8</option>
          <option value="UTC+9" ${st.timezone === 'UTC+9' ? 'selected' : ''}>UTC+9</option>
          <option value="UTC+9.5" ${st.timezone === 'UTC+9.5' ? 'selected' : ''}>UTC+9.5</option>
          <option value="UTC+10" ${st.timezone === 'UTC+10' ? 'selected' : ''}>UTC+10</option>
          <option value="UTC+11" ${st.timezone === 'UTC+11' ? 'selected' : ''}>UTC+11</option>
          <option value="UTC+12" ${st.timezone === 'UTC+12' ? 'selected' : ''}>UTC+12</option>
          <option value="UTC+13" ${st.timezone === 'UTC+13' ? 'selected' : ''}>UTC+13</option>
          <option value="UTC+14" ${st.timezone === 'UTC+14' ? 'selected' : ''}>UTC+14</option>
        </select>
      </div>
"""
html = html.replace('<fieldset><legend data-i18n="gui_lang_settings">Display & General</legend>\n    <div class="chk" style="margin-bottom:12px"><label><input type="checkbox" id="s-hc" ${st.enable_health_check !== false ? \'checked\' : \'\'}> <span data-i18n="gui_enable_hc">Enable PCE Health Check</span></label></div>\n    <div class="form-row">', load_set_code)

# 4. Update saveSettings
save_set_code = "settings: { language: rv('s-lang'), theme: theme, timezone: $('s-timezone').value, enable_health_check: $('s-hc').checked }"
html = html.replace("settings: { language: rv('s-lang'), theme: theme, enable_health_check: $('s-hc').checked }", save_set_code)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
