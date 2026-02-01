// Sidebar Toggle Functionality

document.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const navItems = document.querySelectorAll('.nav-item');
    
    // Toggle sidebar on button click
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            // Save preference to localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        });
    }

    // Load sidebar preference from localStorage
    const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (sidebarCollapsed) {
        sidebar.classList.add('collapsed');
    }

    // Set active nav item based on current page
    const currentPath = window.location.pathname;
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (currentPath.includes(href.replace(/\//g, ''))) {
            item.classList.add('active');
        }
        
        // Add data-title for tooltip
        const text = item.querySelector('span').textContent;
        item.setAttribute('data-title', text);
    });

    // Add active class to nav items on click
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // Close sidebar on mobile when a link is clicked
    if (window.innerWidth <= 768) {
        navItems.forEach(item => {
            item.addEventListener('click', function() {
                sidebar.classList.add('collapsed');
                localStorage.setItem('sidebarCollapsed', true);
            });
        });
    }
});
