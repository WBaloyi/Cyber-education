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

// Light / dark mode toggle. The starting theme is set in base.html before the page draws.
document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;
    const root = document.documentElement;
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)');

    const savedTheme = () => {
        try { return localStorage.getItem('theme'); } catch (error) { return null; }
    };

    const apply = theme => {
        root.setAttribute('data-theme', theme);
        root.setAttribute('data-bs-theme', theme);
        const label = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        toggle.setAttribute('aria-label', label);
        toggle.title = label;
    };

    apply(root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light');

    toggle.addEventListener('click', () => {
        const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        apply(next);
        try { localStorage.setItem('theme', next); } catch (error) { /* private mode: still switches for this page */ }
    });

    // Follow the device setting until the visitor picks a theme themselves.
    systemDark.addEventListener?.('change', event => {
        if (!savedTheme()) apply(event.matches ? 'dark' : 'light');
    });
});
