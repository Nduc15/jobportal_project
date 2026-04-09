// Chỉ giữ lại các hiệu ứng UI, không còn jobsData giả
document.addEventListener('DOMContentLoaded', function() {
    // Filter chips (nếu vẫn muốn dùng client-side filter tạm, nhưng sau này sẽ thay bằng Django)
    const chips = document.querySelectorAll('.filter-chip');
    if (chips.length) {
        chips.forEach(chip => {
            chip.addEventListener('click', function() {
                const location = this.getAttribute('data-location');
                // Thay vì filter js, sau này sẽ gửi request lên server
                console.log('Lọc theo:', location);
                // Tạm thời reload hoặc gọi Ajax
                window.location.href = '?location=' + location;
            });
        });
    }

    // Hiệu ứng hover tooltip cho job title
    const style = document.createElement('style');
    style.textContent = `.job-card .job-title:hover { color: #1a7f6b; cursor: help; text-decoration: underline dotted; }`;
    document.head.appendChild(style);
});