(function () {
    'use strict';
    const SCROLL_STEP = 480;
    document.querySelectorAll('.carousel').forEach(function (carousel) {
        const track = carousel.querySelector('.carousel-track');
        if (!track) return;
        const prevBtn = document.querySelector(
            '.carousel-prev[data-target="' + carousel.id + '"]'
        );
        const nextBtn = document.querySelector(
            '.carousel-next[data-target="' + carousel.id + '"]'
        );
        function updateControls() {
            const scrollLeft = track.scrollLeft;
            const maxScroll = track.scrollWidth - track.clientWidth;

            if (prevBtn) {
                prevBtn.disabled = scrollLeft <= 1;
            }
            if (nextBtn) {
                nextBtn.disabled = scrollLeft >= maxScroll - 1;
            }
            carousel.classList.toggle('has-left', scrollLeft > 1);
            carousel.classList.toggle('has-right', scrollLeft < maxScroll - 1);
        }
        if (prevBtn) {
            prevBtn.addEventListener('click', function () {
                track.scrollBy({ left: -SCROLL_STEP, behavior: 'smooth' });
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', function () {
                track.scrollBy({ left: SCROLL_STEP, behavior: 'smooth' });
            });
        }
        track.addEventListener('scroll', updateControls);
        window.addEventListener('resize', updateControls);
        updateControls();
    });
})();

/* AJAX лайки и корзина без перезагрузки страницы */
(function () {
    'use strict';

    function getCookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? m.pop() : '';
    }

    const CSRF = getCookie('csrftoken');

    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form.classList.contains('ajax-action')) return;

        e.preventDefault();

        const button = form.querySelector('button');
        if (!button || button.disabled) return;
        button.disabled = true;

        fetch(form.action, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': CSRF,
            },
            credentials: 'same-origin',
        })
        .then(function (r) {
            if (r.redirected && r.url.indexOf('/login') !== -1) {
                window.location.href = r.url;
                throw new Error('redirected to login');
            }
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        })
        .then(function (data) {
            //ЛАЙК
            if (typeof data.liked !== 'undefined') {
                button.classList.toggle('is-liked', data.liked);

                if (typeof data.likes_count !== 'undefined') {
                    const m = form.action.match(/\/like\/(\d+)\//);
                    if (m) {
                        document
                            .querySelectorAll('form[action*="/like/' + m[1] + '/"] .like-count')
                            .forEach(function (el) {
                                el.textContent = data.likes_count;
                            });
                    }
                }
            }
            //КОРЗИНА
            if (typeof data.in_cart !== 'undefined') {
                button.classList.toggle('is-active', data.in_cart);
                const label = button.querySelector('.cart-label');
                if (label) {
                    label.textContent = data.in_cart ? 'В корзине' : 'В корзину';
                }
            }
        })
        .catch(function (err) {
            if (err && err.message !== 'redirected to login') {
                console.error('Action failed:', err);
            }
        })
        .finally(function () {
            button.disabled = false;
        });
    });
})();