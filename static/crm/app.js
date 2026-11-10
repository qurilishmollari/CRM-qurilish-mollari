document.querySelectorAll('nav a').forEach(link => { if (link.pathname === location.pathname) link.classList.add('active'); });
const lines = document.getElementById('lines');
if (lines) {
  const prices = JSON.parse(document.getElementById('product-prices').textContent);
  const money = new Intl.NumberFormat('uz-UZ', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  // Quantity has three decimal places, price two: calculate using integer units.
  const scaled = (value, places) => {
    const match = String(value || '').match(/^(\d+)(?:\.(\d*))?$/);
    if (!match) return 0n;
    return BigInt(match[1]) * (10n ** BigInt(places)) + BigInt((match[2] || '').padEnd(places, '0').slice(0, places) || '0');
  };
  function recalculate() {
    let total = 0n;
    lines.querySelectorAll('tbody tr').forEach(row => {
      const product = row.querySelector('[name$="-product"]');
      const quantity = row.querySelector('[name$="-quantity"]');
      const price = row.querySelector('[name$="-price"]');
      if (price.dataset.autoPrice === 'true') price.value = prices[product.value] ?? '';
      const deleted = row.querySelector('[name$="-DELETE"]').checked;
      const value = !product.value || deleted ? 0n : scaled(quantity.value, 3) * scaled(price.value, 2);
      row.querySelector('.line-total').textContent = money.format(Number(value) / 100000);
      total += value;
    });
    document.getElementById('document-total').textContent = money.format(Number(total) / 100000);
  }
  lines.addEventListener('input', recalculate);
  lines.addEventListener('change', event => {
    if (event.target.matches('[name$="-product"]')) {
      const price = event.target.closest('tr').querySelector('[name$="-price"]');
      const kind = document.getElementById('id_kind').value;
      if (kind === 'sale' || kind === 'return') price.value = prices[event.target.value] ?? '';
    }
    recalculate();
  });
  document.getElementById('id_kind').addEventListener('change', recalculate);
  document.getElementById('add-line').addEventListener('click', () => {
    const count = document.getElementById('id_lines-TOTAL_FORMS');
    const template = document.getElementById('empty-line');
    lines.querySelector('tbody').insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__prefix__', count.value));
    count.value = Number(count.value) + 1;
    recalculate();
  });
  recalculate();
}
