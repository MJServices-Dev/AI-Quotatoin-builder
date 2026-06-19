/* ══════════════════════════════════════════════════════════════
   Theme Toggle — Persistent dark/light mode with Lucide icons
   ══════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    const STORAGE_KEY = 'qb-theme';

    // Apply saved theme instantly (before paint)
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }

    document.addEventListener('DOMContentLoaded', () => {
        // Inject toggle button
        if (!document.getElementById('themeToggle')) {
            const btn = document.createElement('button');
            btn.id = 'themeToggle';
            btn.className = 'theme-toggle';
            btn.title = 'Toggle dark/light mode';
            btn.setAttribute('aria-label', 'Toggle dark mode');
            
            // Set initial icon
            btn.innerHTML = `<i data-lucide="${isDark() ? 'sun' : 'moon'}" class="icon-md"></i>`;
            document.body.appendChild(btn);
            
            if (window.lucide) {
                window.lucide.createIcons({ root: btn });
            }

            btn.addEventListener('click', () => {
                const next = isDark() ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                localStorage.setItem(STORAGE_KEY, next);
                
                // Update icon
                btn.innerHTML = `<i data-lucide="${next === 'dark' ? 'sun' : 'moon'}" class="icon-md"></i>`;
                if (window.lucide) {
                    window.lucide.createIcons({ root: btn });
                }
            });
        }
    });

    function isDark() {
        return document.documentElement.getAttribute('data-theme') === 'dark';
    }
})();
