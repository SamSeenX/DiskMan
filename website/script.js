
function toggleMenu() {
    const navLinks = document.getElementById('nav-links');
    navLinks.classList.toggle('active');

    // Animate hamburger to X (optional, can be done with CSS based on active class on button if we add one)
    // For now, just toggling the menu visibility
}

/* Hero Carousel Logic */
document.addEventListener('DOMContentLoaded', () => {
    const carouselDetails = document.getElementById('heroCarousel');
    if (!carouselDetails) return;

    const cards = document.querySelectorAll('.carousel-card');
    let currentIndex = 0; // 0 = CLI, 1 = Web
    let hasScrolled = false;

    // Initial State: CLI (0) is active, Web (1) is next (right)
    updateCarousel(0);

    window.rotateCarousel = function (index) {
        currentIndex = index;
        updateCarousel(index);
    }

    function updateCarousel(activeIndex) {
        cards.forEach(card => {
            const cardIndex = parseInt(card.getAttribute('data-index'));

            // Cleanup classes
            card.classList.remove('active', 'prev', 'next');

            if (cardIndex === activeIndex) {
                card.classList.add('active');
            } else if (cardIndex > activeIndex) {
                card.classList.add('next'); // Push to right
            } else {
                card.classList.add('prev'); // Push to left
            }
        });
    }

    // Scroll Observer to trigger switch once
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !hasScrolled) {
                // If user scrolls to it and it's visible fully 
                // We want to trigger a switch to show interactivity
                // But only if we are at the top view (CLI). 
                // Let's switch to Web to show "Web Dashboard available"

                // Delay slightly for effect
                setTimeout(() => {
                    if (currentIndex === 0) {
                        rotateCarousel(1);
                    }
                    hasScrolled = true;
                }, 800);
            }
        });
    }, { threshold: 0.6 }); // Trigger when 60% visible

    observer.observe(carouselDetails);
});
