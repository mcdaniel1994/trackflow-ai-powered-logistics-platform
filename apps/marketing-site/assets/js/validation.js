(function () {
  'use strict';

  const form = document.getElementById('application-form');
  if (!form) return;

  const clearBtn = document.getElementById('clear-form');
  const successMessage = document.getElementById('success-message');
  const commentsTextarea = document.getElementById('comments');
  const commentsCounter = document.getElementById('comments-counter');
  const monthlyVolumeSelect = document.getElementById('monthly-volume');
  const volumeWarning = document.getElementById('monthly-volume-warning');

  // ── Error messages — reads from window.TRANSLATIONS if available (language-aware)
  var ERRORS_EN = {
    'company-name':      'Company name must have at least 2 characters',
    'contact-person':    'Enter first and last name of contact',
    'corporate-email':   'Enter a valid corporate email (example: name@company.com)',
    'phone':             'Phone must include country code (example: +1 213 555 0147)',
    'company-website':   'If you include website, it must be a valid URL',
    'operating-country': 'Select main operating country',
    'product-type':      'Select the type of product you handle',
    'monthly-volume':    'Select estimated monthly volume',
    'services':          'Select at least one service of interest',
    'current-3pl':       'Indicate if you currently work with another logistics provider',
    'privacy-policy':    'You must accept the privacy policy to continue',
    'comments':          'Comment exceeds the 500-character limit',
  };

  function getError(key) {
    var lang = window.currentLang || 'en';
    if (window.TRANSLATIONS && window.TRANSLATIONS[lang]) {
      return window.TRANSLATIONS[lang]['errors.' + key] || ERRORS_EN[key];
    }
    return ERRORS_EN[key];
  }

  function getTranslation(key, fallback) {
    var lang = window.currentLang || 'en';
    if (window.TRANSLATIONS && window.TRANSLATIONS[lang]) {
      return window.TRANSLATIONS[lang][key] || fallback;
    }
    return fallback;
  }

  function formatRemainingCount(count) {
    return count + ' ' + getTranslation('counter.remaining', 'remaining');
  }

  function formatOverLimitCount(count) {
    return count + ' ' + getTranslation('counter.over', 'over limit');
  }

  // Alias kept for backward compat with switch cases below
  var ERRORS = ERRORS_EN;

  // ── Validators ────────────────────────────────────────────────────────────
  function validators(fieldId) {
    switch (fieldId) {
      case 'company-name': {
        var val = document.getElementById('company-name').value.trim();
        if (!val || val.length < 2) return getError('company-name');
        if (/\d/.test(val)) return getError('company-name');
        return null;
      }
      case 'contact-person': {
        var val = document.getElementById('contact-person').value.trim();
        if (!val) return getError('contact-person');
        var parts = val.split(/\s+/).filter(Boolean);
        if (parts.length < 2) return getError('contact-person');
        return null;
      }
      case 'corporate-email': {
        var val = document.getElementById('corporate-email').value.trim();
        if (!val) return getError('corporate-email');
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) return getError('corporate-email');
        return null;
      }
      case 'phone': {
        var val = document.getElementById('phone').value.trim();
        if (!val) return getError('phone');
        if (!/^\+\d[\d\s\-().]{5,}$/.test(val)) return getError('phone');
        return null;
      }
      case 'company-website': {
        var val = document.getElementById('company-website').value.trim();
        if (!val) return null; // optional
        try {
          var url = new URL(val);
          if (url.protocol !== 'http:' && url.protocol !== 'https:') return getError('company-website');
          return null;
        } catch (_) {
          return getError('company-website');
        }
      }
      case 'operating-country':
      case 'product-type':
      case 'monthly-volume': {
        var el = document.getElementById(fieldId);
        if (!el || !el.value) return getError(fieldId);
        return null;
      }
      case 'services': {
        var checked = document.querySelectorAll('input[name="services"]:checked');
        if (checked.length === 0) return getError('services');
        return null;
      }
      case 'current-3pl': {
        var selected = document.querySelector('input[name="current-3pl"]:checked');
        if (!selected) return getError('current-3pl');
        return null;
      }
      case 'comments': {
        var val = document.getElementById('comments').value;
        if (val.length > 500) {
          var over = val.length - 500;
          return getError('comments') + ' (' + over + ' over limit)';
        }
        return null;
      }
      case 'privacy-policy': {
        var el = document.getElementById('privacy-policy');
        if (!el || !el.checked) return getError('privacy-policy');
        return null;
      }
      default:
        return null;
    }
  }

  // ── UI state helpers ──────────────────────────────────────────────────────
  function showError(fieldId, message) {
    const errorEl = document.getElementById(fieldId + '-error');
    const inputEl = getInputEl(fieldId);

    if (errorEl) {
      errorEl.querySelector('.error-text').textContent = message;
      errorEl.classList.remove('hidden');
      errorEl.classList.add('flex');
    }
    if (inputEl) {
      inputEl.classList.remove('border-gray-300', 'border-green-500');
      inputEl.classList.add('border-red-500');
      inputEl.setAttribute('aria-invalid', 'true');
    }
  }

  function showSuccess(fieldId) {
    const errorEl = document.getElementById(fieldId + '-error');
    const inputEl = getInputEl(fieldId);

    if (errorEl) {
      errorEl.classList.add('hidden');
      errorEl.classList.remove('flex');
    }
    if (inputEl) {
      inputEl.classList.remove('border-gray-300', 'border-red-500');
      inputEl.classList.add('border-green-500');
      inputEl.setAttribute('aria-invalid', 'false');
    }
  }

  function clearState(fieldId) {
    const errorEl = document.getElementById(fieldId + '-error');
    const inputEl = getInputEl(fieldId);

    if (errorEl) {
      errorEl.classList.add('hidden');
      errorEl.classList.remove('flex');
    }
    if (inputEl) {
      inputEl.classList.remove('border-red-500', 'border-green-500');
      inputEl.classList.add('border-gray-300');
      inputEl.removeAttribute('aria-invalid');
    }
  }

  function getInputEl(fieldId) {
    // Text/email/tel/url/select/textarea inputs have matching IDs
    const el = document.getElementById(fieldId);
    if (el) return el;
    // For groups (services, current-3pl) return null — no single border to highlight
    return null;
  }

  // ── Run a single field validation ─────────────────────────────────────────
  function validateField(fieldId) {
    const error = validators(fieldId);
    if (error) {
      showError(fieldId, error);
      return false;
    }
    showSuccess(fieldId);
    return true;
  }

  // ── Attach blur / change listeners ────────────────────────────────────────
  ['company-name', 'contact-person', 'corporate-email', 'phone', 'company-website'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('blur', function () { validateField(id); });
  });

  ['operating-country', 'product-type', 'monthly-volume'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('change', function () { validateField(id); });
  });

  document.querySelectorAll('input[name="services"]').forEach(function (cb) {
    cb.addEventListener('change', function () { validateField('services'); });
  });

  document.querySelectorAll('input[name="current-3pl"]').forEach(function (rb) {
    rb.addEventListener('change', function () { validateField('current-3pl'); });
  });

  var privacyEl = document.getElementById('privacy-policy');
  if (privacyEl) privacyEl.addEventListener('change', function () { validateField('privacy-policy'); });

  // ── Comments: live character counter ─────────────────────────────────────
  if (commentsTextarea && commentsCounter) {
    commentsTextarea.addEventListener('input', function () {
      var remaining = 500 - commentsTextarea.value.length;
      if (remaining >= 0) {
        commentsCounter.textContent = formatRemainingCount(remaining);
        commentsCounter.classList.remove('text-red-600');
        commentsCounter.classList.add('text-gray-500');
      } else {
        commentsCounter.textContent = formatOverLimitCount(Math.abs(remaining));
        commentsCounter.classList.add('text-red-600');
        commentsCounter.classList.remove('text-gray-500');
      }
      if (commentsTextarea.value.length > 0) validateField('comments');
    });
  }

  // ── Low-volume warning ────────────────────────────────────────────────────
  if (monthlyVolumeSelect && volumeWarning) {
    monthlyVolumeSelect.addEventListener('change', function () {
      if (monthlyVolumeSelect.value === '0-100') {
        volumeWarning.classList.remove('hidden');
      } else {
        volumeWarning.classList.add('hidden');
      }
    });
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var allFields = [
      'company-name',
      'contact-person',
      'corporate-email',
      'phone',
      'company-website',
      'operating-country',
      'product-type',
      'monthly-volume',
      'services',
      'current-3pl',
      'comments',
      'privacy-policy',
    ];

    var allValid = true;
    allFields.forEach(function (id) {
      if (!validateField(id)) allValid = false;
    });

    if (allValid) {
      form.classList.add('hidden');
      successMessage.classList.remove('hidden');
      successMessage.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      var firstInvalid = form.querySelector('[aria-invalid="true"]');
      if (firstInvalid) firstInvalid.focus();
    }
  });

  // ── Clear form ────────────────────────────────────────────────────────────
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      form.reset();

      if (volumeWarning) volumeWarning.classList.add('hidden');

      if (commentsCounter) {
        commentsCounter.textContent = formatRemainingCount(500);
        commentsCounter.classList.remove('text-red-600');
        commentsCounter.classList.add('text-gray-500');
      }

      var allFields = [
        'company-name', 'contact-person', 'corporate-email', 'phone',
        'company-website', 'operating-country', 'product-type',
        'monthly-volume', 'comments', 'privacy-policy', 'services', 'current-3pl',
      ];
      allFields.forEach(clearState);
    });
  }

}());
