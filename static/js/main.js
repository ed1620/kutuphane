// =============================================
// EGE KÜTÜPHANESİ — Ana JavaScript
// =============================================

// Flash mesajlarını 5 saniye sonra otomatik kapat
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
});
