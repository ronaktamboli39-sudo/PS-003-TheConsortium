// FarmWise AI — Main JavaScript

// ======================================================
// Auto-dismiss flash messages after 5 seconds
// ======================================================
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity 0.4s ease';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
});

// ======================================================
// Crop card: ensure only one selected at a time (already
// handled by radio, but add visual feedback)
// ======================================================
document.querySelectorAll('.crop-card input[type="radio"]').forEach(radio => {
  radio.addEventListener('change', () => {
    // Scroll the selected card into view (mobile)
    radio.closest('.crop-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
});

// ======================================================
// Smooth scroll for any anchor starting with #
// ======================================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  });
});

// ======================================================
// Form validation helpers
// ======================================================
function validateRequired(formId, fields) {
  const form = document.getElementById(formId);
  if (!form) return true;
  for (const field of fields) {
    const el = form.querySelector(`[name="${field}"]`);
    if (el && !el.value.trim()) {
      el.style.borderColor = '#bc4a1d';
      el.focus();
      return false;
    }
  }
  return true;
}
