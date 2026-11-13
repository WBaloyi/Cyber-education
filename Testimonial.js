document.addEventListener('DOMContentLoaded', () => {
    // Live character count for the testimonial message.
    const message = document.getElementById('testimonial-message');
    const counter = document.getElementById('testimonial-message-count');
    if (message && counter) {
        const updateCount = () => { counter.textContent = `${message.value.length} / ${counter.dataset.max}`; };
        message.addEventListener('input', updateCount);
        updateCount();
    }

    const carousel = document.querySelector('[data-carousel]');
    if (!carousel) return;

    const viewport = carousel.querySelector('.testimonial-viewport');
    const wrapper = carousel.querySelector('.testimonial-wrapper');
    const indicatorGroup = carousel.querySelector('.indicators');
    const previousButton = carousel.querySelector('[data-carousel-prev]');
    const nextButton = carousel.querySelector('[data-carousel-next]');
    const status = carousel.querySelector('[data-carousel-status]');
    if (!viewport || !wrapper || !indicatorGroup) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let slides = [];
    let indicators = [];
    let currentIndex = 0;
    let intervalId = null;
    let hovering = false;
    let focused = false;

    // Rebuild the slide list and one indicator dot per slide.
    const refreshSlides = () => {
        slides = [...wrapper.querySelectorAll('.testimonial-card')];
        indicatorGroup.replaceChildren();
        indicators = slides.map((slide, index) => {
            slide.setAttribute('role', 'group');
            slide.setAttribute('aria-roledescription', 'slide');
            slide.setAttribute('aria-label', `${index + 1} of ${slides.length}`);
            const dot = document.createElement('button');
            dot.type = 'button';
            dot.setAttribute('aria-label', `Show testimonial ${index + 1}`);
            dot.addEventListener('click', () => {
                showSlide(index);
                restartRotation();
            });
            indicatorGroup.appendChild(dot);
            return dot;
        });
    };

    const showSlide = (index, announce = false) => {
        if (slides.length === 0) return;
        currentIndex = (index + slides.length) % slides.length;
        wrapper.style.transform = `translateX(-${currentIndex * 100}%)`;
        slides.forEach((slide, slideIndex) => {
            const hidden = slideIndex !== currentIndex;
            slide.setAttribute('aria-hidden', String(hidden));
            slide.inert = hidden;
        });
        indicators.forEach((indicator, indicatorIndex) => {
            const isActive = indicatorIndex === currentIndex;
            indicator.classList.toggle('active', isActive);
            if (isActive) indicator.setAttribute('aria-current', 'true');
            else indicator.removeAttribute('aria-current');
        });
        if (status) {
            const text = `Testimonial ${currentIndex + 1} of ${slides.length}`;
            // Only announce changes the user asked for, not automatic rotation.
            status.setAttribute('aria-live', announce ? 'polite' : 'off');
            status.textContent = text;
        }
    };

    const stopRotation = () => {
        window.clearInterval(intervalId);
        intervalId = null;
    };

    const startRotation = () => {
        stopRotation();
        if (reducedMotion.matches || hovering || focused || document.hidden || slides.length < 2) return;
        intervalId = window.setInterval(() => showSlide(currentIndex + 1), 5000);
    };

    const restartRotation = () => startRotation();

    previousButton?.addEventListener('click', () => {
        showSlide(currentIndex - 1, true);
        restartRotation();
    });
    nextButton?.addEventListener('click', () => {
        showSlide(currentIndex + 1, true);
        restartRotation();
    });

    carousel.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft') showSlide(currentIndex - 1, true);
        else if (event.key === 'ArrowRight') showSlide(currentIndex + 1, true);
    });

    // Swipe support for touch screens.
    let touchStartX = null;
    viewport.addEventListener('touchstart', event => {
        touchStartX = event.touches[0].clientX;
        stopRotation();
    }, { passive: true });
    viewport.addEventListener('touchend', event => {
        if (touchStartX === null) return;
        const distance = event.changedTouches[0].clientX - touchStartX;
        if (Math.abs(distance) > 40) showSlide(currentIndex + (distance < 0 ? 1 : -1), true);
        touchStartX = null;
        startRotation();
    });

    carousel.addEventListener('mouseenter', () => { hovering = true; stopRotation(); });
    carousel.addEventListener('mouseleave', () => { hovering = false; startRotation(); });
    carousel.addEventListener('focusin', () => { focused = true; stopRotation(); });
    carousel.addEventListener('focusout', event => {
        if (carousel.contains(event.relatedTarget)) return;
        focused = false;
        startRotation();
    });
    document.addEventListener('visibilitychange', startRotation);
    reducedMotion.addEventListener?.('change', startRotation);

    refreshSlides();
    showSlide(0);
    startRotation();
});
