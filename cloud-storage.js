/* Project saving: immediate browser copy, with private cloud sync after sign-in. */
(() => {
  const config = window.SANSHUI_CLOUD || {};
  const ready = Boolean(config.url && config.publishableKey && window.supabase?.createClient);
  const db = ready ? window.supabase.createClient(config.url, config.publishableKey) : null;
  let signedInUser = null;
  let cloudProjects = [];
  let saving = false;
  const $save = $('#quickSaveBtn');
  const $status = $('#saveState');

  function setStatus(message) { $status.textContent = message; }
  function savedTime(value) {
    return value ? new Date(value).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' }) : '当前浏览器';
  }
  function projectCard(project, source, date) {
    const name = esc(project?.title || '未命名项目');
    const scenic = esc(project?.scenic || '未填写景区');
    return `<button class="saved-project-card" data-source="${source}" data-id="${esc(project?.storageId || '')}"><b>《${name}》</b><span>${scenic} · ${source === 'cloud' ? '云端' : '此浏览器'}</span><small>${esc(savedTime(date))} · 点击打开</small></button>`;
  }
  function renderSavedProjects() {
    const local = (() => { try { return JSON.parse(localStorage.getItem('yongjia_demo_project')); } catch { return null; } })();
    const cloudCards = cloudProjects.map(row => projectCard({ ...row.payload, storageId: row.id }, 'cloud', row.updated_at));
    const localCard = local && !cloudProjects.some(row => row.id === local.storageId) ? projectCard(local, 'local') : '';
    $('#savedProjectList').innerHTML = [...cloudCards, localCard].join('') || '<p>还没有保存的项目。打开项目后点“保存项目”即可保存。</p>';
    $$('#savedProjectList .saved-project-card').forEach(button => button.addEventListener('click', () => {
      const row = button.dataset.source === 'cloud' ? cloudProjects.find(item => item.id === button.dataset.id) : null;
      let value = row?.payload;
      if (!value) { try { value = JSON.parse(localStorage.getItem('yongjia_demo_project')); } catch { return; } }
      state.project = { ...structuredClone(demoProject), ...value, storageId: row?.id || value.storageId || null, storageOwnerId: row ? signedInUser.id : value.storageOwnerId || null };
      state.hasProject = true;
      state.scenic = state.project.scenic || state.scenic;
      state.audience = state.project.audience || state.audience;
      state.duration = state.project.duration || state.duration;
      localStorage.setItem('yongjia_demo_project', JSON.stringify(state.project));
      setStatus(row ? '已打开云端项目' : '已打开此浏览器的项目');
      nav('project');
    }));
  }
  async function refreshCloudProjects() {
    if (!db || !signedInUser) { cloudProjects = []; renderSavedProjects(); return; }
    const { data, error } = await db.from('projects').select('id,title,scenic_name,payload,updated_at').order('updated_at', { ascending: false }).limit(30);
    if (error) { toast(`读取云端项目失败：${error.message}`); return; }
    cloudProjects = data || [];
    renderSavedProjects();
  }
  function updateAccount() {
    $('#cloudLoginArea').hidden = !ready || Boolean(signedInUser);
    $('#cloudAccountArea').hidden = !signedInUser;
    $('#cloudAccountName').textContent = signedInUser?.email || '';
    $('#cloudStatusText').textContent = !ready
      ? '云端储存尚未启用。现在可以先保存到此浏览器；连接数据库后即可同步。'
      : signedInUser ? '已登录。保存项目时会同时写入你的私有云端项目库。'
        : '云端已连接。输入邮箱获取登录邮件，登录后即可跨设备保存和打开项目。';
    $('#cloudBtn').textContent = signedInUser ? '云端已连接' : '云端账号';
  }
  async function uploadSelectedFiles(projectId) {
    const files = [...($('#mapUpload')?.files || []), ...($('#materialUpload')?.files || [])];
    if (!files.length) return [];
    const entries = [];
    for (const file of files) {
      const path = `${signedInUser.id}/${projectId}/${crypto.randomUUID()}-${file.name.replace(/[^a-zA-Z0-9._-]/g, '_')}`;
      const { error } = await db.storage.from('project-assets').upload(path, file, { contentType: file.type || 'application/octet-stream' });
      if (error) throw new Error(`“${file.name}”上传失败：${error.message}`);
      entries.push({ name: file.name, path, size: file.size, type: file.type });
    }
    return entries;
  }
  async function quickSave() {
    if (saving) return;
    saving = true;
    $save.disabled = true;
    try {
      saveProject();
      setStatus('已保存到此浏览器');
      if (!db || !signedInUser) {
        const pendingFiles = ($('#mapUpload')?.files.length || 0) + ($('#materialUpload')?.files.length || 0);
        toast(pendingFiles ? '项目文字已保存；文件需连接云端后上传' : '已保存到此浏览器；云端连接后可同步');
        return;
      }
      setStatus('正在同步云端…');
      const fields = { owner_id: signedInUser.id, title: state.project.title || '未命名项目', scenic_name: state.project.scenic || state.scenic, payload: state.project };
      const currentId = state.project.storageOwnerId === signedInUser.id ? state.project.storageId : null;
      const query = currentId
        ? db.from('projects').update(fields).eq('id', currentId).eq('owner_id', signedInUser.id).select('id').single()
        : db.from('projects').insert(fields).select('id').single();
      const { data, error } = await query;
      if (error) throw error;
      state.project.storageId = data.id;
      state.project.storageOwnerId = signedInUser.id;
      const added = await uploadSelectedFiles(data.id);
      if (added.length) {
        state.project.files = [...(state.project.files || []), ...added];
        const result = await db.from('projects').update({ payload: state.project }).eq('id', data.id).eq('owner_id', signedInUser.id);
        if (result.error) throw result.error;
        if ($('#mapUpload')) $('#mapUpload').value = '';
        if ($('#materialUpload')) $('#materialUpload').value = '';
      }
      saveProject();
      setStatus(`已同步云端 · ${savedTime(new Date())}`);
      toast('项目已保存到云端');
      await refreshCloudProjects();
    } catch (error) {
      setStatus('云端保存失败，已留存此浏览器');
      toast(`云端保存失败：${error.message || error}`);
    } finally { saving = false; $save.disabled = false; }
  }

  $save.addEventListener('click', quickSave);
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && ['project','studio'].includes(state.view)) {
      event.preventDefault(); quickSave();
    }
  });
  $('#cloudBtn').addEventListener('click', () => { updateAccount(); openModal('#cloudModal'); });
  $('#cloudLoginBtn').addEventListener('click', async () => {
    const email = $('#cloudEmail').value.trim();
    if (!email || !$('#cloudEmail').checkValidity()) { toast('请输入有效的邮箱地址'); return; }
    const button = $('#cloudLoginBtn'); button.disabled = true;
    const { error } = await db.auth.signInWithOtp({ email, options: { emailRedirectTo: `${location.origin}${location.pathname}` } });
    button.disabled = false;
    toast(error ? `邮件发送失败：${error.message}` : '登录邮件已发送，请在邮箱中打开链接');
  });
  $('#cloudLogoutBtn').addEventListener('click', async () => { await db?.auth.signOut(); signedInUser = null; cloudProjects = []; updateAccount(); renderSavedProjects(); });
  window.addEventListener('projectlibraryopen', refreshCloudProjects);
  window.addEventListener('projectlocalsaved', renderSavedProjects);
  renderSavedProjects(); updateAccount();
  if (localStorage.getItem('yongjia_demo_project')) setStatus('此浏览器有已保存项目');
  if (db) {
    db.auth.getUser().then(({ data }) => { signedInUser = data?.user || null; updateAccount(); refreshCloudProjects(); });
    db.auth.onAuthStateChange((_event, session) => { signedInUser = session?.user || null; updateAccount(); setTimeout(refreshCloudProjects, 0); });
  }
})();

