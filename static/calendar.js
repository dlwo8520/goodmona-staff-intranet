(() => {
  'use strict';
  const app = document.getElementById('calendar-app');
  if (!app) return;
  let selected = app.dataset.date;
  let payload = JSON.parse(document.getElementById('calendar-data').textContent);
  let renderedDate = '';
  let generation = 0;
  const mode = app.dataset.mode;
  const token = document.querySelector('#calendar-token [name=csrfmiddlewaretoken]').value;
  const statuses = {pending:'승인 대기', approved:'승인 완료', rejected:'반려', cancelled:'취소'};
  function el(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className=cls; if (text !== undefined) node.textContent=text; return node; }
  function hidden(form, name, value) { const input=el('input'); input.type='hidden'; input.name=name; input.value=value; form.append(input); }
  function actionForm(url, fields, label, secondary=false) {
    const form=el('form','calendar-action'); form.method='post'; form.action=url;
    hidden(form,'csrfmiddlewaretoken',token); hidden(form,'calendar','1'); hidden(form,'return_date',selected);
    const filters=new URLSearchParams(location.search);
    if(filters.get('department')) hidden(form,'return_department',filters.get('department'));
    if(filters.get('pending')==='1') hidden(form,'return_pending','1');
    for (const [key,value] of Object.entries(fields)) hidden(form,key,value);
    const button=el('button',secondary?'button secondary small':'button small',label); button.type='submit'; form.append(button); return form;
  }
  function mark() {
    if(mode==='manage') {
      document.getElementById('calendar-pending-total').textContent=`전체 대기 ${payload.pending_total}건`;
      const outside=document.getElementById('outside-pending');outside.hidden=!payload.outside_pending;
      if(payload.outside_pending) { const query=new URLSearchParams(location.search);query.delete('month');query.set('date',payload.outside_date);outside.href=`?${query}`;outside.textContent=`다른 달 대기 ${payload.outside_pending}건 →`; }
    }
    for(const day of app.querySelectorAll('[data-calendar-date]')) {
      day.classList.toggle('selected',day.dataset.calendarDate===selected);
      day.setAttribute('aria-current',day.dataset.calendarDate===selected?'date':'false');
      const events=day.querySelector('.calendar-events'); events.replaceChildren();
      const counts=payload.events[day.dataset.calendarDate];
      if(mode==='vehicles') { if(counts) events.append(el('span','state pending',`예약 ${counts}건`)); continue; }
      if(!counts) continue;
      for(const [status,count] of Object.entries(counts)) {
        const label=mode==='manage'?({pending:'대기',approved:'승인',rejected:'반려',cancelled:'취소'})[status]:statuses[status];
        events.append(el('span',`state ${status}`,`${label} ${count}`));
      }
    }
    for(const input of document.querySelectorAll('[data-selected-date]')) input.value=selected;
    document.getElementById('selected-date-title').textContent=`${selected.slice(0,4)}년 ${Number(selected.slice(5,7))}월 ${Number(selected.slice(8))}일`;
    if(document.getElementById('calendar-balance')) document.getElementById('calendar-balance').textContent=payload.balance;
  }
  function staffing() {
    if(mode!=='leave') return;
    const period=document.querySelector('[name=period]:checked')?.value || 'full';
    const check=payload.availability[period];
    const box=document.getElementById('staffing-summary'); box.replaceChildren();
    if(check.department) box.append(el('strong','',check.department));
    for(const slot of check.slots) box.append(el('p','',`${slot.label} · 근무 예정 ${slot.scheduled}명 · 승인된 연차 ${slot.approved}명 · 내 연차 승인 시 ${slot.remaining}명 근무 · 최소 필요 ${slot.minimum}명`));
    const reason=document.getElementById('availability-reason'); reason.hidden=!check.reason; reason.textContent=check.reason;
    document.getElementById('leave-submit').disabled=!check.allowed;
  }
  function requests(force=false) {
    const list=document.getElementById('day-requests'); if(!list) return;
    if(!force && renderedDate===selected && list.contains(document.activeElement)) return;
    list.replaceChildren();
    for(const item of payload.items) {
      const article=el('article','calendar-request');
      if(mode==='manage') { article.append(el('strong','',item.employee),el('p','muted small',item.department)); }
      const row=el('div','row'); row.append(el('span','',item.period_label),el('span',`state ${item.status}`,item.status_label)); article.append(row);
      if(item.reason) article.append(el('p','request-note',item.reason));
      if(item.note) article.append(el('p','muted small',item.note));
      const actions=el('div','actions');
      if(mode==='manage') {
        if(item.period==='unknown') {
          article.append(el('p','availability-reason','이전 반차 · 오전/오후 확인 필요'));
          const form=actionForm(`/manage/leave/${item.id}/period/`,{},'시간 확인 저장',true);
          const select=el('select'); select.name='period'; for(const [value,label] of [['am','오전 반차'],['pm','오후 반차']]) { const option=el('option','',label); option.value=value; select.append(option); } form.prepend(select); actions.append(form);
        }
        if(item.status==='pending') {
          const approve=actionForm(`/manage/leave/${item.id}/process/`,{action:'approve'},'승인');
          approve.querySelector('button').disabled=!item.can_approve; actions.append(approve);
          const reject=actionForm(`/manage/leave/${item.id}/process/`,{action:'reject'},'반려',true);
          const note=el('input'); note.name='note'; note.placeholder='반려 사유 (선택)'; note.maxLength=200; reject.prepend(note); actions.append(reject);
          if(item.approval_reason) article.append(el('p','availability-reason',item.approval_reason));
        } else if(item.status==='approved') actions.append(actionForm(`/manage/leave/${item.id}/process/`,{action:'cancel'},'승인 취소 · 잔여일 복원',true));
      } else if(item.status==='pending') actions.append(actionForm(`/leave/${item.id}/cancel/`,{},'신청 취소',true));
      article.append(actions); list.append(article);
    }
    if(!payload.items.length) list.append(el('p','empty-state','선택한 날짜에 신청이 없습니다.'));
    renderedDate=selected;
  }
  function clock(minutes) { if(minutes===1440)return '24:00'; return `${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`; }
  function vehicles() {
    if(mode!=='vehicles') return;
    const box=document.getElementById('vehicle-schedule'); box.replaceChildren();
    const rows=[...payload.items.map(item=>({...item,busy:true})),...payload.gaps.map(item=>({...item,busy:false}))].sort((a,b)=>a.start-b.start);
    for(const item of rows) {
      const row=el('div',`time-slot ${item.busy?'occupied':'free-slot'}`);
      row.append(el('strong','',`${clock(item.start)}–${clock(item.end)}`),el('span','small',item.busy?(item.mine?'내 예약':'예약됨'):'예약 가능'));
      if(item.mine) { if(item.purpose)row.append(el('p','small',item.purpose)); row.append(actionForm(`/vehicles/${item.id}/cancel/`,{vehicle:payload.vehicle},'예약 취소',true)); }
      box.append(row);
    }
    document.querySelector('#booking-form [name=vehicle]').value=payload.vehicle || '';
  }
  function render(force=false) { mark(); staffing(); requests(force); vehicles(); }
  async function refresh(force=false) {
    const version=++generation;
    const query=new URLSearchParams(location.search); query.set('date',selected);
    try {
      const response=await fetch(`${app.dataset.api}?${query}`,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
      if(!response.ok || response.redirected) throw new Error('session');
      const data=await response.json(); if(version!==generation)return;
      payload=data;render(force); document.getElementById('calendar-sync').textContent='자동 갱신 중 · 5초 간격';
    } catch (_) { document.getElementById('calendar-sync').textContent='일정을 다시 확인하는 중입니다. 접속 상태를 확인해 주세요.'; }
  }
  app.addEventListener('click',event=>{const day=event.target.closest('[data-calendar-date]');if(!day)return;event.preventDefault();selected=day.dataset.calendarDate;const url=new URL(location.href);url.searchParams.set('date',selected);history.replaceState({},'',url);refresh(true);});
  document.getElementById('leave-form')?.addEventListener('change',staffing);
  render(true);refresh();
  window.setInterval(()=>{if(!document.hidden)refresh();},5000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
