
/* ─── Helpers ─────────────────────────────────────────────────────── */
const $=s=>document.getElementById(s);
const api=async(url,opt)=>{const r=await fetch(url,opt);return r.json()};
const post=(url,body)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const put=(url,body)=>api(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const del=url=>api(url,{method:'DELETE'});
const rv=name=>document.querySelector(`input[name="${name}"]:checked`)?.value;
const setRv=(name,val)=>{const r=document.querySelector(`input[name="${name}"][value="${val}"]`);if(r)r.checked=true};
let _editIdx=null; // null = add mode, number = edit mode
let _translations={};

async function loadTranslations(){
  _translations=await api('/api/ui_translations');
  document.querySelectorAll('[data-i18n]').forEach(el=>{
    const k=el.getAttribute('data-i18n');
    if(_translations[k]){
      if(el.tagName==='INPUT'&&el.type==='button') el.value=_translations[k];
      else el.textContent=_translations[k];
    }
  });
}

function initTableResizers() {
  document.querySelectorAll('.rule-table').forEach(table => {
    const ths = table.querySelectorAll('th');
    ths.forEach(th => {
      if (th.querySelector('.resizer')) return;
      const resizer = document.createElement('div');
      resizer.classList.add('resizer');
      th.appendChild(resizer);
      let startX, startWidth;
      resizer.addEventListener('mousedown', function(e) {
        startX = e.pageX;
        startWidth = th.offsetWidth;
        document.body.style.cursor = 'col-resize';
        const onMouseMove = (e) => {
          const newWidth = startWidth + (e.pageX - startX);
          th.style.width = Math.max(newWidth, 30) + 'px';
        };
        const onMouseUp = () => {
          document.body.style.cursor = 'default';
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
        };
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    });
  });
}

function toast(msg,err){const t=$('toast');t.textContent=msg;t.className='toast'+(err?' err':'')+' show';setTimeout(()=>t.className='toast',3000)}
function dlog(msg){const l=$('d-log');l.textContent+='\n['+new Date().toLocaleTimeString()+'] '+msg;l.scrollTop=l.scrollHeight}
function slog(msg){const l=$('s-log');if(l){l.textContent+='\n['+new Date().toLocaleTimeString()+'] '+msg;l.scrollTop=l.scrollHeight}}
function alog(msg){const l=$('a-log');l.textContent+='\n'+msg;l.scrollTop=l.scrollHeight}

/* ─── Tabs ────────────────────────────────────────────────────────── */
function switchTab(id){
  document.querySelectorAll('.tab').forEach((t,i)=>{t.classList.toggle('active',t.textContent.trim().toLowerCase().startsWith(id.slice(0,4)))});
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  $('p-'+id).classList.add('active');
  if(id==='rules') loadRules();
  if(id==='settings') loadSettings();
  if(id==='dashboard') loadDashboard();
}
