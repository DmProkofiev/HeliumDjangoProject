/* HELIUM — ЛИЧНЫЙ КАБИНЕТ */

(function () {
    'use strict';

    // ПЕРЕКЛЮЧЕНИЕ ПАНЕЛЕЙ
    const menuItems = document.querySelectorAll('.menu-item');
    const panels = document.querySelectorAll('.content-panel');

    function activateTab(tabName) {
        menuItems.forEach(b => b.classList.remove('menu-active'));
        panels.forEach(p => p.classList.remove('content-active'));

        const btn = document.querySelector('.menu-item[data-tab="' + tabName + '"]');
        const panel = document.getElementById('panel-' + tabName);

        if (btn) btn.classList.add('menu-active');
        if (panel) panel.classList.add('content-active');
    }

    menuItems.forEach(btn => {
        btn.addEventListener('click', () => activateTab(btn.dataset.tab));
    });

    const params = new URLSearchParams(window.location.search);
    const initialTab = params.get('tab');
    if (initialTab) activateTab(initialTab);

    // 2. КОРЗИНА
    const cartForm = document.getElementById('cart-form');
    if (!cartForm) return;

    const checkboxes = Array.from(cartForm.querySelectorAll('.cart-checkbox'));
    const selectAll = document.getElementById('select-all');
    const totalEl = document.getElementById('cart-total-amount');
    const submitBtn = document.getElementById('cart-checkout-btn');

    function recalcTotal() {
        let total = 0;
        let selectedCount = 0;

        checkboxes.forEach(cb => {
            if (cb.checked) {
                total += parseFloat(cb.dataset.price) || 0;
                selectedCount++;
            }
        });

        if (totalEl) {
            totalEl.textContent = Math.round(total).toLocaleString('ru-RU') + ' ₽';
        }

        if (submitBtn) {
            submitBtn.disabled = selectedCount === 0;
            submitBtn.classList.toggle('is-disabled', selectedCount === 0);
        }
    }

    checkboxes.forEach(cb => {
        cb.addEventListener('change', () => {
            if (selectAll) {
                selectAll.checked = checkboxes.every(c => c.checked);
            }
            recalcTotal();
        });
    });

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            checkboxes.forEach(cb => cb.checked = selectAll.checked);
            recalcTotal();
        });
    }

    // УДАЛЕНИЕ ТОВАРА ИЗ КОРЗИНЫ
    const removeForm = document.getElementById('cart-remove-form');

    document.querySelectorAll('.cart-remove-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const url = btn.dataset.removeUrl;
            if (!url || !removeForm) return;
            if (!confirm('Убрать товар из корзины?')) return;

            removeForm.action = url;
            removeForm.submit();
        });
    });

    recalcTotal();
})();