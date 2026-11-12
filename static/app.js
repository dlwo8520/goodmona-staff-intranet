document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-target]');
  if (!button) return;
  const target = document.getElementById(button.dataset.copyTarget);
  if (!target) return;
  try {
    await navigator.clipboard.writeText(target.innerText || target.value);
    button.textContent = '복사 완료';
  } catch (_) {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(target);
    selection.removeAllRanges(); selection.addRange(range);
    button.textContent = '선택된 내용을 복사해 주세요';
  }
});
if (document.getElementById('pending-leave-count')) {
  async function refreshPendingLeaveCount() {
    if (document.hidden) return;
    try { const response=await fetch('/api/manage/leave/calendar/',{credentials:'same-origin',cache:'no-store'}); if(response.ok && !response.redirected) { const data=await response.json(); document.getElementById('pending-leave-count').textContent=data.pending_total; } } catch (_) {}
  }
  refreshPendingLeaveCount(); setInterval(refreshPendingLeaveCount,5000);
}
