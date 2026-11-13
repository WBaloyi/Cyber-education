// Fade sections in as they scroll into view. Skipped when the visitor prefers reduced motion,
// and without JavaScript everything is simply visible.
document.addEventListener('DOMContentLoaded', () => {
    const sections = document.querySelectorAll('.reveal');
    if (!sections.length || !('IntersectionObserver' in window)
        || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    document.documentElement.classList.add('reveal-ready');
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
        });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    sections.forEach(section => observer.observe(section));
});

// The mobile navigation menu is handled by Bootstrap's navbar collapse (see templates/base.html).
