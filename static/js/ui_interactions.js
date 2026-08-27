(function () {
  function showToast(message) {
    let toast = document.querySelector('.ui-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'ui-toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.classList.add('is-visible');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(function () {
      toast.classList.remove('is-visible');
    }, 2200);
  }

  function bindDataTooltips() {
    const targets = document.querySelectorAll('[data-tooltip]');
    if (!targets.length) return;

    const tooltip = document.createElement('div');
    tooltip.className = 'ui-data-tooltip';
    tooltip.id = 'ui-data-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.setAttribute('aria-hidden', 'true');
    document.body.appendChild(tooltip);

    let activeTarget = null;

    function placeTooltip(target, event) {
      const rect = target.getBoundingClientRect();
      const pointerX = event && Number.isFinite(event.clientX)
        ? event.clientX
        : rect.left + rect.width / 2;
      const pointerY = event && Number.isFinite(event.clientY)
        ? event.clientY
        : rect.top;
      const gap = 12;
      const width = tooltip.offsetWidth;
      const height = tooltip.offsetHeight;
      const maxLeft = window.innerWidth - width - gap;
      const maxTop = window.innerHeight - height - gap;
      let left = pointerX + gap;
      let top = pointerY - height - gap;

      if (left > maxLeft) left = pointerX - width - gap;
      if (top < gap) top = rect.bottom + gap;

      tooltip.style.left = Math.max(gap, Math.min(left, maxLeft)) + 'px';
      tooltip.style.top = Math.max(gap, Math.min(top, maxTop)) + 'px';
    }

    function showTooltip(target, event) {
      const message = target.dataset.tooltip;
      if (!message) return;

      activeTarget = target;
      tooltip.textContent = message;
      tooltip.classList.add('is-visible');
      tooltip.setAttribute('aria-hidden', 'false');
      target.setAttribute('aria-describedby', tooltip.id);
      placeTooltip(target, event);
    }

    function hideTooltip(target) {
      if (activeTarget !== target) return;
      activeTarget = null;
      tooltip.classList.remove('is-visible');
      tooltip.setAttribute('aria-hidden', 'true');
    }

    targets.forEach(function (target) {
      target.addEventListener('mouseenter', function (event) {
        showTooltip(target, event);
      });
      target.addEventListener('mousemove', function (event) {
        if (activeTarget === target) placeTooltip(target, event);
      });
      target.addEventListener('mouseleave', function () {
        hideTooltip(target);
      });
      target.addEventListener('focus', function () {
        showTooltip(target);
      });
      target.addEventListener('blur', function () {
        hideTooltip(target);
      });
      target.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          hideTooltip(target);
          target.blur();
        }
      });
    });

    window.addEventListener('resize', function () {
      if (activeTarget) placeTooltip(activeTarget);
    });
  }

  function bindProgressValues() {
    function clampPercent(value) {
      return Math.max(0, Math.min(value, 100));
    }

    document.querySelectorAll('[data-progress-width]').forEach(function (element) {
      const value = Number(element.dataset.progressWidth);
      if (Number.isFinite(value)) {
        element.style.width = clampPercent(value) + '%';
      }
    });

    document.querySelectorAll('[data-progress-height]').forEach(function (element) {
      const value = Number(element.dataset.progressHeight);
      if (Number.isFinite(value)) {
        element.style.height = clampPercent(value) + '%';
      }
    });
  }

  function normalize(value) {
    return value.trim().toLowerCase();
  }

  function setActive(button, selector) {
    const group = button.closest(selector);
    if (!group) return;
    group.querySelectorAll('button, label').forEach(function (item) {
      item.classList.remove('is-active');
    });
    button.classList.add('is-active');
  }

  function rowStatus(row) {
    const status =
      row.querySelector('.review-status, .user-presence, .repo-status, .notification-dot');
    if (!status) return '';
    if (status.classList.contains('notification-dot')) return 'unread';
    return normalize(status.textContent);
  }

  function applyTextFilter(input, selector) {
    const scope = input.closest('main') || document;
    const query = normalize(input.value);
    scope.querySelectorAll(selector).forEach(function (item) {
      const text = normalize(item.textContent);
      item.classList.toggle('is-filter-hidden', query.length > 0 && !text.includes(query));
    });
  }

  function applyButtonFilter(button, rowsSelector) {
    const label = normalize(button.textContent).replace(/\(\d+\)/g, '').trim();
    const scope = button.closest('main') || document;
    scope.querySelectorAll(rowsSelector).forEach(function (row) {
      const status = rowStatus(row);
      const shouldShow =
        label === 'all' ||
        status.includes(label) ||
        (label === 'revision' && status.includes('revision')) ||
        (label === 'pending' && status.includes('pending')) ||
        (label === 'compiled' && status.includes('compiled')) ||
        (label === 'active' && status === 'active') ||
        (label === 'inactive' && status === 'inactive') ||
        (label === 'unread' && row.classList.contains('is-unread'));

      row.classList.toggle('is-filter-hidden', !shouldShow);
    });
  }

  function bindSearches() {
    const searchMap = [
      ['.review-search input', '.review-table-card tbody tr'],
      ['.users-search input', '.users-table-card tbody tr'],
      ['.repo-search input', '.repo-document-row'],
      ['.area-search input', '.area-card'],
      ['.conversation-search input', '.conversation-item'],
    ];

    searchMap.forEach(function (entry) {
      document.querySelectorAll(entry[0]).forEach(function (input) {
        input.addEventListener('input', function () {
          applyTextFilter(input, entry[1]);
        });
      });
    });
  }

  function bindFilterTabs() {
    const filterMap = [
      ['.review-filter-tabs', '.review-table-card tbody tr'],
      ['.users-filter-tabs', '.users-table-card tbody tr'],
      ['.notification-filters', '.notification-row'],
    ];

    filterMap.forEach(function (entry) {
      document.querySelectorAll(entry[0] + ' button').forEach(function (button) {
        button.addEventListener('click', function () {
          setActive(button, entry[0]);
          applyButtonFilter(button, entry[1]);
        });
      });
    });
  }

  function bindSelectableGroups() {
    [
      '.department-list',
      '.subarea-list',
      '.score-row',
      '.conversation-list',
      '.review-pagination',
    ].forEach(function (selector) {
      document.querySelectorAll(selector + ' button').forEach(function (button) {
        button.addEventListener('click', function () {
          setActive(button, selector);
        });
      });
    });
  }

  function bindSettingsTabs() {
    document.querySelectorAll('.settings-tab[data-settings-tab]').forEach(function (button) {
      button.addEventListener('click', function () {
        const target = button.dataset.settingsTab;
        const layout = button.closest('.settings-layout');
        if (!layout || !target) return;

        setActive(button, '.settings-tabs');
        layout.querySelectorAll('.settings-tab').forEach(function (tab) {
          tab.setAttribute('aria-selected', tab === button ? 'true' : 'false');
        });
        layout.querySelectorAll('.settings-panel').forEach(function (panel) {
          const isTarget = panel.dataset.settingsPanel === target;
          panel.hidden = !isTarget;
          panel.classList.toggle('is-active', isTarget);
        });
      });
    });
  }

  function bindNotifications() {
    document.querySelectorAll('.notification-dismiss').forEach(function (button) {
      button.addEventListener('click', function () {
        const row = button.closest('.notification-row');
        if (!row) return;
        row.style.opacity = '0';
        row.style.transform = 'translateX(16px)';
        window.setTimeout(function () {
          row.remove();
          showToast('Notification dismissed');
        }, 180);
      });
    });

    document.querySelectorAll('.notification-row').forEach(function (row) {
      row.addEventListener('click', function (event) {
        if (event.target.closest('button')) return;
        row.classList.remove('is-unread');
        const dot = row.querySelector('.notification-dot');
        if (dot) dot.remove();
        showToast('Notification marked as viewed');
      });
    });
  }

  function bindNotificationMenu() {
    document.querySelectorAll('[data-notification-menu]').forEach(function (menu) {
      const trigger = menu.querySelector('[data-notification-trigger]');
      const popover = menu.querySelector('[data-notification-popover]');
      if (!trigger || !popover) return;

      function closePopover() {
        popover.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
      }

      trigger.addEventListener('click', function (event) {
        event.stopPropagation();
        const isOpen = !popover.hidden;
        popover.hidden = isOpen;
        trigger.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
      });

      popover.addEventListener('click', function (event) {
        event.stopPropagation();
      });

      document.addEventListener('click', closePopover);
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') closePopover();
      });
    });
  }

  function addChatMessage(input, listSelector, mineClass) {
    const text = input.value.trim();
    if (!text) {
      showToast('Type a message first');
      return;
    }

    const list = document.querySelector(listSelector);
    if (!list) return;

    const article = document.createElement('article');
    article.className = mineClass;
    article.innerHTML =
      '<div class="message-bubble"></div><time>Now</time>';
    article.querySelector('.message-bubble').textContent = text;
    list.appendChild(article);
    input.value = '';
    list.scrollTop = list.scrollHeight;
    showToast('Message sent');
  }

  function companionAnswer(question) {
    const lower = normalize(question);
    if (lower.includes('missing') || lower.includes('documents')) {
      return 'Area II needs updated faculty credentials, current syllabi, and supporting portfolio samples. Prioritize documents tied to pending or revision items first.';
    }
    if (lower.includes('deadline') || lower.includes('july 25')) {
      return 'Before July 25, finish Level I preliminary evidence, resolve Area II revisions, and confirm overdue Student Services submissions.';
    }
    if (lower.includes('critical') || lower.includes('risk') || lower.includes('area viii')) {
      return 'The highest-risk areas are Area VII and Area VIII. Area VIII needs early follow-up because readiness is still below target and the deadline window is narrowing.';
    }
    if (lower.includes('compliance') || lower.includes('department')) {
      return 'Engineering and Arts & Sciences need the closest monitoring. Check pending evidence counts, reviewer remarks, and zero-submission areas first.';
    }
    return 'Start with the items marked pending or needs revision, then assign each item to an owner with a target upload date. I can also summarize this into a checklist.';
  }

  function createCompanionAvatar(imageUrl) {
    const avatar = document.createElement('div');
    avatar.className = 'companion-bot-icon companion-aira-avatar';

    if (imageUrl) {
      const image = document.createElement('img');
      image.src = imageUrl;
      image.alt = 'AIRA';
      avatar.appendChild(image);
    }

    return avatar;
  }

  function submitCompanionQuestion(input) {
    const question = input.value.trim();
    if (!question) {
      showToast('Choose a prompt or type a question');
      return;
    }

    const body = document.querySelector('.companion-body');
    if (!body) return;
    const airaImage = body.dataset.airaImage;

    const userMessage = document.createElement('article');
    userMessage.className = 'companion-user-message';
    userMessage.innerHTML = '<div class="assistant-bubble"></div>';
    userMessage.querySelector('.assistant-bubble').textContent = question;

    const reply = document.createElement('article');
    reply.className = 'companion-message companion-reply';
    reply.appendChild(createCompanionAvatar(airaImage));

    const messageStack = document.createElement('div');
    messageStack.className = 'message-stack';
    const bubble = document.createElement('div');
    bubble.className = 'assistant-bubble';
    bubble.textContent = companionAnswer(question);
    messageStack.appendChild(bubble);
    reply.appendChild(messageStack);

    body.appendChild(userMessage);
    body.appendChild(reply);
    input.value = '';
    body.scrollTop = body.scrollHeight;
    showToast('AIRA answered');
  }

  function bindMessaging() {
    document.querySelectorAll('.message-composer button').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = button.closest('.message-composer').querySelector('input');
        addChatMessage(input, '.message-list', 'message-row is-mine');
      });
    });

    document.querySelectorAll('.message-composer input').forEach(function (input) {
      input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          addChatMessage(input, '.message-list', 'message-row is-mine');
        }
      });
    });

    document.querySelectorAll('.sample-prompt-list button').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = document.querySelector('.composer-row input');
        if (!input) return;
        input.value = button.textContent.trim();
        input.focus();
      });
    });

    document.querySelectorAll('.composer-row button').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = button.closest('.composer-row').querySelector('input');
        submitCompanionQuestion(input);
      });
    });

    document.querySelectorAll('.composer-row input').forEach(function (input) {
      input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          submitCompanionQuestion(input);
        }
      });
    });
  }

  function downloadReport() {
    const button = document.querySelector('.export-btn');
    const exportUrl = button && button.dataset.exportUrl;
    if (!exportUrl) {
      showToast('Report export is unavailable');
      return;
    }

    window.location.assign(exportUrl);
  }

  function applyProfilePhoto(photoUrl) {
    document.querySelectorAll('[data-profile-avatar]').forEach(function (avatar) {
      avatar.replaceChildren();
      if (photoUrl) {
        const image = document.createElement('img');
        image.className = 'avatar-photo';
        image.src = photoUrl;
        image.alt = 'Profile photo';
        avatar.appendChild(image);
        avatar.classList.add('has-photo');
      } else {
        avatar.classList.remove('has-photo');
        avatar.textContent = avatar.dataset.profileInitials || '';
      }
    });
  }

  function bindProfilePhoto() {
    const avatar = document.querySelector('[data-profile-avatar]');
    applyProfilePhoto(avatar ? avatar.dataset.profilePhoto || '' : '');

    const input = document.querySelector('#profile-photo-input');
    if (!input) return;

    document.querySelectorAll('.change-photo-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        input.click();
      });
    });

    input.addEventListener('change', function () {
      const file = input.files && input.files[0];
      if (!file) return;

      if (!file.type.startsWith('image/')) {
        showToast('Choose an image file');
        input.value = '';
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        showToast('Photo must be smaller than 5 MB');
        input.value = '';
        return;
      }

      const reader = new FileReader();
      reader.addEventListener('load', function () {
        const photoUrl = typeof reader.result === 'string' ? reader.result : '';
        if (!photoUrl) return;

        applyProfilePhoto(photoUrl);
        showToast('Photo selected. Save changes to upload it.');
      });
      reader.addEventListener('error', function () {
        showToast('Could not read that photo');
        input.value = '';
      });
      reader.readAsDataURL(file);
    });
  }

  function bindActionButtons() {
    document.querySelectorAll('.print-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        window.print();
      });
    });

    document.querySelectorAll('.export-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        downloadReport();
        showToast('Report exported');
      });
    });

    document.querySelectorAll('.save-settings-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        showToast('Changes saved');
      });
    });

    document.querySelectorAll('.add-document-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf,.doc,.docx,.xls,.xlsx';
        input.addEventListener('change', function () {
          if (input.files.length > 0) showToast(input.files[0].name + ' selected');
        });
        input.click();
      });
    });

    document.querySelectorAll('.review-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        showToast('Review panel opened');
      });
    });

    document.querySelectorAll('.thread-actions button').forEach(function (button) {
      button.addEventListener('click', function () {
        showToast('Thread options opened');
      });
    });
  }

  function bindWorkspaceActions() {
    // Workspace actions are regular server-backed forms. Keep this hook for
    // compatibility with the existing page initialisation sequence.
  }

  function toneForRole(role) {
    return {
      'Program Head': 'blue',
      Dean: 'rose',
      'Area Chair': 'gold',
      'Accreditation Head': 'maroon',
      QA: 'green',
    }[role] || 'slate';
  }

  function toneForStatus(status) {
    return status === 'Active' || status === 'Approved'
      ? 'green'
      : status === 'Pending'
        ? 'gold'
        : 'slate';
  }

  function bindUserManagement() {
    const dialog = document.querySelector('.user-manage-dialog');
    if (!dialog) return;

    const form = dialog.querySelector('.user-manage-form');
    let selectedButton = null;

    function closeDialog() {
      if (dialog.open) dialog.close();
      selectedButton = null;
    }

    document.querySelectorAll('.manage-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        selectedButton = button;
        dialog.querySelector('[data-managed-name]').textContent = button.dataset.userName;
        dialog.querySelector('[data-managed-email]').textContent = button.dataset.userEmail;
        dialog.querySelector('.managed-user-avatar').textContent = button.dataset.userName
          .split(' ')
          .filter(function (part) { return !part.endsWith('.'); })
          .map(function (part) { return part.charAt(0); })
          .slice(-2)
          .join('');
        form.elements.role.value = button.dataset.userRole;
        form.elements.department.value = button.dataset.userDepartment;
        form.elements.status.value = button.dataset.userStatus;
        form.elements.approval.value = button.dataset.userApproval;
        dialog.showModal();
      });
    });

    dialog.querySelector('.dialog-close').addEventListener('click', closeDialog);
    dialog.querySelector('.dialog-cancel').addEventListener('click', closeDialog);
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) closeDialog();
    });

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (!selectedButton) return;

      const row = selectedButton.closest('tr');
      const role = form.elements.role.value;
      const department = form.elements.department.value.trim();
      const status = form.elements.status.value;
      const approval = form.elements.approval.value;
      const userName = selectedButton.dataset.userName;

      selectedButton.dataset.userRole = role;
      selectedButton.dataset.userDepartment = department;
      selectedButton.dataset.userStatus = status;
      selectedButton.dataset.userApproval = approval;

      const roleChip = row.querySelector('td:nth-child(2) .user-chip');
      roleChip.textContent = role;
      roleChip.className = 'user-chip tone-' + toneForRole(role);
      row.querySelector('td:nth-child(3)').textContent = department;

      const statusChip = row.querySelector('.user-presence');
      statusChip.textContent = status;
      statusChip.className = 'user-presence tone-' + toneForStatus(status);

      const approvalChip = row.querySelector('td:nth-child(6) .user-chip');
      approvalChip.textContent = approval;
      approvalChip.className = 'user-chip tone-' + toneForStatus(approval);

      closeDialog();
      showToast(userName + ' updated');
    });
  }

  function bindDashboardLinks() {
    document.querySelectorAll('a[href="#"]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        showToast(link.textContent.trim() + ' selected');
      });
    });
  }

  function bindAreaAssignmentForms() {
    document.querySelectorAll('[data-assignment-toggle]').forEach(function (toggle) {
      const panelId = toggle.getAttribute('aria-controls');
      const panel = panelId && document.getElementById(panelId);
      if (!panel) return;
      const dialog = panel.querySelector('[data-assignment-dialog]') || panel;
      const closeButton = panel.querySelector('[data-assignment-close]');
      let lastFocusedElement = null;

      function getFocusableElements() {
        return Array.from(dialog.querySelectorAll(
          'button, [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
        )).filter(function (element) {
          return !element.disabled && !element.closest('[hidden]');
        });
      }

      function syncBodyScroll() {
        document.body.classList.toggle(
          'modal-open',
          Boolean(document.querySelector('[data-assignment-panel]:not([hidden])'))
        );
      }

      function setPanelOpen(isOpen, restoreFocus) {
        panel.hidden = !isOpen;
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        panel.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
        syncBodyScroll();

        if (isOpen) {
          if (document.activeElement && document.activeElement !== document.body) {
            lastFocusedElement = document.activeElement;
          }
          window.setTimeout(function () {
            const firstFocusable = closeButton || getFocusableElements()[0] || dialog;
            firstFocusable.focus();
          }, 0);
        } else if (restoreFocus !== false) {
          const focusTarget = lastFocusedElement || toggle;
          if (focusTarget && typeof focusTarget.focus === 'function') focusTarget.focus();
          lastFocusedElement = null;
        }
      }

      toggle.addEventListener('click', function () {
        setPanelOpen(panel.hidden, true);
      });

      if (closeButton) {
        closeButton.addEventListener('click', function () {
          setPanelOpen(false, true);
        });
      }

      panel.addEventListener('click', function (event) {
        if (event.target === panel) setPanelOpen(false, true);
      });

      panel.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          event.preventDefault();
          setPanelOpen(false, true);
          return;
        }

        if (event.key !== 'Tab') return;

        const focusableElements = getFocusableElements();
        if (!focusableElements.length) return;

        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];
        if (event.shiftKey && document.activeElement === firstFocusable) {
          event.preventDefault();
          lastFocusable.focus();
        } else if (!event.shiftKey && document.activeElement === lastFocusable) {
          event.preventDefault();
          firstFocusable.focus();
        }
      });

      setPanelOpen(toggle.getAttribute('aria-expanded') === 'true', false);
    });

    document.querySelectorAll('[data-assignment-form]').forEach(function (form) {
      const departmentScope = form.querySelectorAll('input[name="department_scope"]');
      const departmentField = form.querySelector('[data-assignment-departments]');
      const departmentSelect = departmentField && departmentField.querySelector('select');
      if (!departmentScope.length || !departmentField || !departmentSelect) return;

      function updateDepartmentScope() {
        const selectedScope = form.querySelector('input[name="department_scope"]:checked');
        const isSpecific = selectedScope && selectedScope.value === 'specific';
        departmentField.hidden = !isSpecific;
        departmentSelect.disabled = !isSpecific;
      }

      departmentScope.forEach(function (radio) {
        radio.addEventListener('change', updateDepartmentScope);
      });
      updateDepartmentScope();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindSearches();
    bindFilterTabs();
    bindSelectableGroups();
    bindSettingsTabs();
    bindNotifications();
    bindNotificationMenu();
    bindMessaging();
    bindProfilePhoto();
    bindActionButtons();
    bindWorkspaceActions();
    bindUserManagement();
    bindDashboardLinks();
    bindProgressValues();
    bindDataTooltips();
    bindAreaAssignmentForms();
  });
})();
