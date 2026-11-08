(() => {
  const toast = document.querySelector('#cart-toast');
  let toastTimer;
  function showToast(message, count) {
    if (!toast) return;
    toast.textContent = message;
    if (Number.isFinite(count)) {
      const detail = document.createElement('span');
      detail.className = 'toast-count';
      detail.textContent = `${count} item${count === 1 ? '' : 's'} in cart`;
      toast.append(detail);
    }
    toast.classList.add('visible');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove('visible'), 2600);
  }

  document.querySelectorAll('.add-to-cart-form').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const original = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.dataset.original = original;
      button.textContent = 'Adding…';
    }
    try {
      const response = await fetch(form.action, {
        method: 'POST', body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || 'Could not add this item. Please try again.');
      const count = Number(data.cart_count || 0);
      let countBadge = document.querySelector('.cart-count');
      if (countBadge) countBadge.textContent = count;
      else if (count) {
        countBadge = document.createElement('i');
        countBadge.className = 'cart-count';
        countBadge.textContent = count;
        document.querySelector('.header-cart')?.append(countBadge);
      }
      const cartCopy = document.querySelector('.cart-head-copy small');
      if (cartCopy) cartCopy.textContent = `${count} items · ${(Number(data.cart_total_lamports) / 1e9).toFixed(9)} SOL`;
      document.querySelector('.header-cart')?.setAttribute('aria-label', `Cart, ${count} items`);
      showToast('Added to cart', count);
    } catch (error) {
      showToast(error.message || 'Could not add item');
    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = button.dataset.original || original;
      }
    }
  }));

  document.querySelector('.catalog-toolbar select[name="sort"]')?.addEventListener('change', () => {
    document.querySelector('#sort-form')?.requestSubmit();
  });

  document.querySelectorAll('.stepper-change').forEach((button) => button.addEventListener('click', () => {
    const input = button.closest('.stepper')?.querySelector('input[name="quantity"]');
    if (!input) return;
    input.value = String(Math.max(1, Math.min(99, Number(input.value || 1) + Number(button.dataset.step))));
    const buyNowQuantity = document.querySelector('.buy-now-form input[name="quantity"]');
    if (buyNowQuantity) buyNowQuantity.value = input.value;
  }));

  const tabs = [...document.querySelectorAll('[data-product-tab]')];
  const selectTab = (tab) => {
    tabs.forEach((other) => {
      const active = other === tab;
      other.classList.toggle('active', active);
      other.setAttribute('aria-selected', active ? 'true' : 'false');
      const panel = document.getElementById(other.dataset.productTab);
      if (panel) panel.hidden = !active;
    });
  };
  tabs.forEach((tab) => tab.addEventListener('click', () => selectTab(tab)));
  if (window.location.hash === '#reviews') {
    const reviewTab = tabs.find((tab) => tab.id === 'reviews');
    if (reviewTab) selectTab(reviewTab);
  }

  const paymentPage = document.querySelector('.checkout-page[data-order-id]');
  if (paymentPage && paymentPage.dataset.initialStatus !== 'paid') {
    const orderId = paymentPage.dataset.orderId;
    const pending = document.querySelector('#pending-state');
    const success = document.querySelector('#success-state');
    const badge = document.querySelector('#payment-status');
    let checking = false;
    const poll = async () => {
      if (checking || document.hidden) return;
      checking = true;
      try {
        const response = await fetch(paymentPage.dataset.statusUrl, { headers: { Accept: 'application/json' } });
        if (response.ok) {
          const data = await response.json();
          if (data.status === 'paid') {
            pending.hidden = true;
            success.hidden = false;
            badge.classList.remove('pending');
            badge.classList.add('paid');
            badge.textContent = 'Paid';
            document.querySelector('#receipt-signature').textContent = data.signature;
            document.querySelector('#explorer-link').href = `https://explorer.solana.com/tx/${encodeURIComponent(data.signature)}?cluster=devnet`;
            return;
          }
        }
      } catch (_) {
        // Keep checkout usable during transient RPC/network errors; the next poll retries.
      } finally {
        checking = false;
      }
      window.setTimeout(poll, 2000);
    };
    window.setTimeout(poll, 1000);
  }
})();
