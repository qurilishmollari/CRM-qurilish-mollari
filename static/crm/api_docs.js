(() => {
  const endpoints = JSON.parse(document.getElementById('api-endpoint-data').textContent);
  const container = document.getElementById('api-endpoints');
  const token = document.getElementById('api-token');
  document.getElementById('clear-api-token').addEventListener('click', () => { token.value = ''; });
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function field(parent, label, input, id) {
    const wrapper = node('div', undefined, 'field');
    const caption = node('label', label);
    caption.htmlFor = id; input.id = id;
    wrapper.append(caption, input); parent.append(wrapper); return input;
  }
  let group;
  endpoints.forEach((endpoint, index) => {
    if (group !== endpoint.group) { group = endpoint.group; container.append(node('h2', group)); }
    const details = node('details');
    const summary = node('summary');
    summary.append(node('span', endpoint.method, 'method'), node('code', '/api/v1/' + endpoint.path), node('span', endpoint.title));
    details.append(summary);
    const content = node('form', undefined, 'endpoint-content');
    let idInput, queryInput, bodyInput;
    if (endpoint.path.includes('{id}')) {
      idInput = node('input'); idInput.type = 'number'; idInput.min = '1'; idInput.required = true;
      field(content, 'Obyekt ID', idInput, 'object-' + index);
    }
    if (endpoint.query !== undefined) {
      queryInput = node('input'); queryInput.value = endpoint.query;
      field(content, 'Query parametrlari (masalan q=sement&page=1)', queryInput, 'query-' + index);
    }
    if (endpoint.body !== undefined) {
      bodyInput = node('textarea'); bodyInput.spellcheck = false;
      const body = structuredClone(endpoint.body);
      if (body.client_request_id === 'NEW_UUID') body.client_request_id = crypto.randomUUID();
      if (body.date === 'YYYY-MM-DD') {
        const parts = new Intl.DateTimeFormat('en', {timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(new Date());
        body.date = ['year', 'month', 'day'].map(type => parts.find(part => part.type === type).value).join('-');
      }
      bodyInput.value = JSON.stringify(body, null, 2);
      field(content, 'JSON so‘rov', bodyInput, 'body-' + index);
      if (body.client_request_id) {
        const fresh = node('button', 'Yangi operatsiya uchun yangi UUID', 'secondary'); fresh.type = 'button';
        fresh.addEventListener('click', () => {
          try { const data = JSON.parse(bodyInput.value); data.client_request_id = crypto.randomUUID(); bodyInput.value = JSON.stringify(data, null, 2); }
          catch (_) { status.textContent = 'Avval JSON xatosini tuzating.'; }
        });
        content.append(fresh);
      }
    }
    const execute = node('button', 'So‘rov yuborish'); execute.type = 'submit';
    const status = node('span', '', 'request-status'); status.setAttribute('aria-live', 'polite');
    const output = node('pre', 'Javob shu yerda ko‘rinadi.');
    content.append(execute, status, output); details.append(content); container.append(details);
    content.addEventListener('submit', async event => {
      event.preventDefault();
      let body;
      try { if (bodyInput) body = JSON.stringify(JSON.parse(bodyInput.value)); }
      catch (_) { status.textContent = 'JSON noto‘g‘ri yozilgan.'; return; }
      if (!endpoint.public && !token.value.trim()) { status.textContent = 'Avval login orqali token oling.'; return; }
      if (['POST', 'PATCH', 'DELETE'].includes(endpoint.method) && !endpoint.path.startsWith('auth/') && !window.confirm('Bu so‘rov haqiqiy bazadagi ma’lumotlarni o‘zgartiradi. Davom etasizmi?')) return;
      const path = endpoint.path.replace('{id}', idInput ? encodeURIComponent(idInput.value) : '');
      const url = new URL('/api/v1/' + path, location.origin);
      if (queryInput) url.search = new URLSearchParams(queryInput.value).toString();
      const headers = {'Content-Type': 'application/json'};
      if (!endpoint.public) headers.Authorization = 'Token ' + token.value.trim().replace(/^Token\s+/i, '');
      execute.disabled = true; status.textContent = 'Yuborilmoqda…';
      try {
        const response = await fetch(url, {method: endpoint.method, headers, body, credentials: 'omit', cache: 'no-store'});
        status.textContent = 'HTTP ' + response.status;
        if (response.headers.get('Content-Type')?.includes('spreadsheetml')) {
          const blobUrl = URL.createObjectURL(await response.blob());
          const download = node('a'); download.href = blobUrl;
          download.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || 'hisobot.xlsx';
          download.click(); setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
          output.textContent = 'Excel fayli yuklandi.';
        } else {
          const text = await response.text();
          try {
            const result = JSON.parse(text);
            output.textContent = JSON.stringify(result, null, 2);
            if (response.ok && endpoint.path === 'auth/login/' && result.token) token.value = result.token;
          } catch (_) { output.textContent = text || 'Javob tanasi bo‘sh.'; }
          if (response.ok && endpoint.path === 'auth/logout/') token.value = '';
        }
      } catch (_) { status.textContent = 'Ulanish xatosi. Internet va serverni tekshiring.'; }
      finally { execute.disabled = false; }
    });
  });
})();
