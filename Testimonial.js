document.addEventListener('DOMContentLoaded', () => {
    // Live character count for the testimonial message.
    const message = document.getElementById('testimonial-message');
    const counter = document.getElementById('testimonial-message-count');
    if (message && counter) {
        const updateCount = () => { counter.textContent = `${message.value.length} / ${counter.dataset.max}`; };
        message.addEventListener('input', updateCount);
        updateCount();
    }

    // Sliding testimonial cards: two at a time on wide screens, one on phones.
    const slider = document.querySelector('[data-slider]');
    if (!slider) return;
    const track = slider.querySelector('.testi-track');
    const cards = [...track.children];
    const dots = slider.querySelector('.testi-dots');
    const status = slider.querySelector('[data-carousel-status]');
    const prev = document.querySelector('[data-carousel-prev]');
    const next = document.querySelector('[data-carousel-next]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const DELAY = 5000;
    let index = 0;
    let timer = null;
    let paused = false;

    const perView = () => {
        const width = slider.clientWidth;
        const count = width < 560 ? 1 : width < 900 ? 2 : 3;
        track.style.setProperty('--per-view', count);
        return count;
    };
    const steps = () => Math.max(1, cards.length - perView() + 1);

    const buildDots = () => {
        dots.replaceChildren();
        for (let n = 0; n < steps(); n += 1) {
            const dot = document.createElement('button');
            dot.type = 'button';
            dot.setAttribute('aria-label', `Show testimonials ${n + 1} of ${steps()}`);
            dot.addEventListener('click', () => { go(n, true); restart(); });
            dots.appendChild(dot);
        }
        dots.hidden = steps() < 2;
    };

    const go = (n, announce = false) => {
        index = (n + steps()) % steps();
        const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
        track.style.transform = `translateX(-${index * (cards[0].offsetWidth + gap)}px)`;
        const first = index;
        const last = index + perView() - 1;
        cards.forEach((card, c) => {
            const hidden = c < first || c > last;
            card.setAttribute('aria-hidden', String(hidden));
            card.inert = hidden;
        });
        [...dots.children].forEach((dot, d) => {
            dot.classList.toggle('active', d === index);
            if (d === index) dot.setAttribute('aria-current', 'true');
            else dot.removeAttribute('aria-current');
        });
        if (status) {
            status.setAttribute('aria-live', announce ? 'polite' : 'off');
            status.textContent = `Showing testimonials ${first + 1} to ${Math.min(last + 1, cards.length)} of ${cards.length}`;
        }
    };

    const stop = () => { window.clearInterval(timer); timer = null; };
    const restart = () => {
        stop();
        if (reducedMotion.matches || paused || document.hidden || steps() < 2) return;
        timer = window.setInterval(() => go(index + 1), DELAY);
    };

    prev?.addEventListener('click', () => { go(index - 1, true); restart(); });
    next?.addEventListener('click', () => { go(index + 1, true); restart(); });
    slider.addEventListener('mouseenter', () => { paused = true; stop(); });
    slider.addEventListener('mouseleave', () => { paused = false; restart(); });
    slider.addEventListener('focusin', () => { paused = true; stop(); });
    slider.addEventListener('focusout', event => {
        if (slider.contains(event.relatedTarget)) return;
        paused = false;
        restart();
    });
    slider.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft') { go(index - 1, true); restart(); }
        if (event.key === 'ArrowRight') { go(index + 1, true); restart(); }
    });

    // Swipe on touch screens.
    let touchX = null;
    slider.addEventListener('touchstart', event => { touchX = event.touches[0].clientX; stop(); }, { passive: true });
    slider.addEventListener('touchend', event => {
        if (touchX === null) return;
        const distance = event.changedTouches[0].clientX - touchX;
        if (Math.abs(distance) > 40) go(index + (distance < 0 ? 1 : -1), true);
        touchX = null;
        restart();
    });

    document.addEventListener('visibilitychange', restart);
    reducedMotion.addEventListener?.('change', restart);
    window.addEventListener('resize', () => { buildDots(); go(Math.min(index, steps() - 1)); });

    buildDots();
    go(0);
    restart();
});
