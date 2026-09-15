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

      const sidebar = target.closest('.sidebar');
      if (sidebar && !sidebar.classList.contains('is-collapsed')) return;

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

  function applyRepositoryFilters(query) {
    const rows = document.querySelectorAll('.repo-document-row');
    if (!rows.length) return;

    const levelFilter = document.querySelector('[data-repo-filter="level"]');
    const departmentFilter = document.querySelector('[data-repo-filter="department"]');
    const normalizedQuery = normalize(query || '');
    const level = normalize(levelFilter ? levelFilter.value : '');
    const department = normalize(departmentFilter ? departmentFilter.value : '');
    let visibleCount = 0;

    rows.forEach(function (row) {
      const matchesLevel = !level || normalize(row.dataset.repoLevel) === level;
      const matchesDepartment = !department || normalize(row.dataset.repoDepartment) === department;
      const matchesSearch = !normalizedQuery || normalize(row.textContent).includes(normalizedQuery);
      const isVisible = matchesLevel && matchesDepartment && matchesSearch;
      row.classList.toggle('is-filter-hidden', !isVisible);
      if (isVisible) visibleCount += 1;
    });

    const emptyState = document.querySelector('[data-repo-empty]');
    if (emptyState) emptyState.hidden = visibleCount > 0;
  }

  function bindRepositoryFilters() {
    const filters = document.querySelectorAll('[data-repo-filter]');
    const searchInput = document.querySelector('.repo-search input');
    const departmentButtons = document.querySelectorAll('.department-list [data-repo-department]');
    if (!filters.length && !searchInput && !departmentButtons.length) return;

    filters.forEach(function (filter) {
      filter.addEventListener('change', function () {
        applyRepositoryFilters(searchInput ? searchInput.value : '');
      });
    });

    departmentButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        const departmentFilter = document.querySelector('[data-repo-filter="department"]');
        if (departmentFilter) departmentFilter.value = button.dataset.repoDepartment || '';
        applyRepositoryFilters(searchInput ? searchInput.value : '');
      });
    });

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        applyRepositoryFilters(searchInput.value);
      });
    }

    applyRepositoryFilters(searchInput ? searchInput.value : '');
  }

  function applyAreaFilters(query) {
    const cards = document.querySelectorAll('.area-card');
    if (!cards.length) return;

    const searchInput = document.querySelector('.area-search input');
    const departmentFilter = document.querySelector('[data-area-filter="department"]');
    const statusFilter = document.querySelector('[data-area-filter="status"]');
    const normalizedQuery = normalize(
      query !== undefined ? query : searchInput ? searchInput.value : '',
    );
    const department = normalize(departmentFilter ? departmentFilter.value : '');
    const status = normalize(statusFilter ? statusFilter.value : '');
    let visibleCount = 0;

    cards.forEach(function (card) {
      const departments = (card.dataset.areaDepartments || '')
        .split('||')
        .map(normalize)
        .filter(Boolean);
      const statuses = (card.dataset.areaStatuses || '')
        .split(',')
        .map(normalize)
        .filter(Boolean);
      const matchesDepartment = !department || departments.includes(department);
      const matchesStatus = !status || statuses.includes(status);
      const matchesSearch = !normalizedQuery || normalize(card.textContent).includes(normalizedQuery);
      const isVisible = matchesDepartment && matchesStatus && matchesSearch;
      card.classList.toggle('is-filter-hidden', !isVisible);
      if (isVisible) visibleCount += 1;
    });

    const emptyState = document.querySelector('[data-area-filter-empty]');
    if (emptyState) emptyState.hidden = visibleCount > 0;
  }

  function bindAreaFilters() {
    const filters = document.querySelectorAll('[data-area-filter]');
    const searchInput = document.querySelector('.area-search input');
    if (!filters.length && !searchInput) return;

    filters.forEach(function (filter) {
      filter.addEventListener('change', function () {
        applyAreaFilters();
      });
    });

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        applyAreaFilters(searchInput.value);
      });
    }

    applyAreaFilters(searchInput ? searchInput.value : '');
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
        (label === 'complied' && status.includes('complied')) ||
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
      ['.conversation-search input', '.conversation-item'],
    ];

    const globalSearchSelector = [
      '.review-table-card tbody tr',
      '.users-table-card tbody tr',
      '.repo-document-row',
      '.area-card',
      '.task-row',
      '.requirements-list li',
      '.conversation-item',
      '.notification-row',
    ].join(', ');

    searchMap.forEach(function (entry) {
      document.querySelectorAll(entry[0]).forEach(function (input) {
        input.addEventListener('input', function () {
          applyTextFilter(input, entry[1]);
        });
      });
    });

    document.querySelectorAll('[data-global-search]').forEach(function (input) {
      input.addEventListener('input', function () {
        applyTextFilter(input, globalSearchSelector);
        if (document.querySelector('[data-repo-filter]')) {
          applyRepositoryFilters(input.value);
        }
        if (document.querySelector('[data-area-filter]')) {
          applyAreaFilters(input.value);
        }
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

  function bindProfileMenu() {
    document.querySelectorAll('[data-profile-menu]').forEach(function (menu) {
      const trigger = menu.querySelector('[data-profile-trigger]');
      const popover = menu.querySelector('[data-profile-popover]');
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

  function bindSidebarCollapse() {
    const sidebar = document.querySelector('[data-mobile-sidebar]');
    const toggle = document.querySelector('[data-sidebar-collapse]');
    if (!sidebar || !toggle) return;

    const desktopQuery = window.matchMedia('(min-width: 881px)');
    const STORAGE_KEY = 'jmcfi-sidebar-collapsed';

    function storedCollapsed() {
      try {
        return localStorage.getItem(STORAGE_KEY) === '1';
      } catch (error) {
        return false;
      }
    }

    function setCollapsed(collapsed) {
      sidebar.classList.toggle('is-collapsed', collapsed);
      toggle.setAttribute('aria-expanded', String(!collapsed));
      toggle.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
      toggle.setAttribute('title', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    }

    toggle.addEventListener('click', function () {
      const collapsed = !sidebar.classList.contains('is-collapsed');
      setCollapsed(collapsed);
      try {
        localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
      } catch (error) {}
    });

    function syncToViewport() {
      if (desktopQuery.matches) {
        const collapsed = storedCollapsed();
        if (collapsed !== sidebar.classList.contains('is-collapsed')) {
          setCollapsed(collapsed);
        }
      } else if (sidebar.classList.contains('is-collapsed')) {
        setCollapsed(false);
      }
    }

    if (typeof desktopQuery.addEventListener === 'function') {
      desktopQuery.addEventListener('change', syncToViewport);
    } else if (typeof desktopQuery.addListener === 'function') {
      desktopQuery.addListener(syncToViewport);
    }

    syncToViewport();
  }

  function bindMobileNavigation() {
    const sidebar = document.querySelector('[data-mobile-sidebar]');
    const backdrop = document.querySelector('[data-mobile-menu-backdrop]');
    const triggers = document.querySelectorAll('[data-mobile-menu-trigger]');
    const closeButton = sidebar && sidebar.querySelector('[data-mobile-menu-close]');
    if (!sidebar || !triggers.length) return;

    function setMenuOpen(isOpen, moveFocus) {
      sidebar.classList.toggle('is-mobile-open', isOpen);
      if (backdrop) backdrop.hidden = !isOpen;
      document.body.classList.toggle('mobile-nav-open', isOpen);
      triggers.forEach(function (trigger) {
        trigger.setAttribute('aria-expanded', String(isOpen));
        trigger.setAttribute('aria-label', isOpen ? 'Close navigation menu' : 'Open navigation menu');
        trigger.setAttribute('title', isOpen ? 'Close menu' : 'Open menu');
      });

      if (moveFocus) {
        const focusTarget = isOpen ? closeButton : triggers[0];
        if (focusTarget) focusTarget.focus();
      }
    }

    triggers.forEach(function (trigger) {
      trigger.addEventListener('click', function () {
        setMenuOpen(!sidebar.classList.contains('is-mobile-open'), true);
      });
    });

    if (closeButton) {
      closeButton.addEventListener('click', function () {
        setMenuOpen(false, true);
      });
    }

    if (backdrop) {
      backdrop.addEventListener('click', function () {
        setMenuOpen(false, false);
      });
    }

    sidebar.querySelectorAll('.sidebar-nav a').forEach(function (link) {
      link.addEventListener('click', function () {
        setMenuOpen(false, false);
      });
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && sidebar.classList.contains('is-mobile-open')) {
        setMenuOpen(false, true);
      }
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 880 && sidebar.classList.contains('is-mobile-open')) {
        setMenuOpen(false, false);
      }
    });

    setMenuOpen(false, false);
  }

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function createCompanionReply(body, airaImage) {
    const reply = document.createElement('article');
    reply.className = 'companion-message companion-reply';
    reply.appendChild(createCompanionAvatar(airaImage));

    const messageStack = document.createElement('div');
    messageStack.className = 'message-stack';
    const bubble = document.createElement('div');
    bubble.className = 'assistant-bubble';
    messageStack.appendChild(bubble);
    reply.appendChild(messageStack);
    body.appendChild(reply);
    body.scrollTop = body.scrollHeight;
    return { reply: reply, stack: messageStack, bubble: bubble };
  }

  function addSourceChip(stack, source) {
    if (!source) return;
    const chip = document.createElement('span');
    chip.className = 'companion-source';
    chip.textContent = 'Source: ' + source;
    stack.appendChild(chip);
  }

  function addCompanionSuggestions(stack, suggestions, composerInput) {
    if (!suggestions || !suggestions.length) return;
    const row = document.createElement('div');
    row.className = 'companion-suggestions';
    suggestions.forEach(function (suggestion) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = suggestion;
      button.addEventListener('click', function () {
        if (!composerInput) return;
        composerInput.value = suggestion;
        composerInput.focus();
      });
      row.appendChild(button);
    });
    stack.appendChild(row);
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

  function bindAiraCompanion() {
    document.querySelectorAll('[data-aira-companion]').forEach(function (companion) {
      const dismiss = companion.querySelector('[data-aira-dismiss]');
      const restore = companion.querySelector('[data-aira-restore]');
      if (!dismiss || !restore) return;

      function setMinimized(isMinimized, moveFocus) {
        companion.classList.toggle('is-minimized', isMinimized);
        restore.hidden = !isMinimized;
        dismiss.disabled = isMinimized;
        dismiss.tabIndex = isMinimized ? -1 : 0;
        dismiss.setAttribute('aria-hidden', String(isMinimized));
        dismiss.setAttribute('aria-expanded', String(!isMinimized));
        companion.setAttribute(
          'aria-label',
          isMinimized ? 'AIRA Smart Companion minimized' : 'AIRA Smart Companion',
        );

        if (moveFocus) {
          window.setTimeout(function () {
            (isMinimized ? restore : dismiss).focus();
          }, 0);
        }
      }

      dismiss.addEventListener('click', function () {
        setMinimized(true, true);
      });

      restore.addEventListener('click', function () {
        setMinimized(false, true);
      });

      companion.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape' || companion.classList.contains('is-minimized')) return;
        event.preventDefault();
        setMinimized(true, true);
      });

      setMinimized(false, false);
    });
  }

  function submitCompanionQuestion(input) {
    const question = input.value.trim();
    if (!question) {
      showToast('Choose a prompt or type a question');
      return;
    }

    const body = document.querySelector('[data-aira-endpoint]');
    const composerForm = document.querySelector('[data-companion-form]');
    if (!body) return;
    const airaImage = body.dataset.airaImage;
    const endpoint = body.dataset.airaEndpoint;

    const userMessage = document.createElement('article');
    userMessage.className = 'companion-user-message';
    const userBubble = document.createElement('div');
    userBubble.className = 'assistant-bubble';
    userBubble.textContent = question;
    userMessage.appendChild(userBubble);

    const created = createCompanionReply(body, airaImage);
    created.bubble.textContent = 'Thinking…';
    created.bubble.classList.add('is-pending');
    created.reply.setAttribute('aria-busy', 'true');

    body.appendChild(userMessage);
    body.scrollTop = body.scrollHeight;

    if (composerForm) {
      const sendButton = composerForm.querySelector('button[type="submit"]');
      const field = composerForm.querySelector('input');
      sendButton.disabled = true;
      field.disabled = true;
    }

    function settle(replyText, source, suggestions) {
      created.bubble.classList.remove('is-pending');
      created.bubble.textContent = replyText;
      created.reply.removeAttribute('aria-busy');
      addSourceChip(created.stack, source);
      addCompanionSuggestions(created.stack, suggestions, composerForm ? composerForm.querySelector('input') : null);
      if (composerForm) {
        const sendButton = composerForm.querySelector('button[type="submit"]');
        const field = composerForm.querySelector('input');
        sendButton.disabled = false;
        field.disabled = false;
        field.focus();
      }
      body.scrollTop = body.scrollHeight;
    }

    function fail() {
      created.bubble.classList.remove('is-pending');
      created.bubble.textContent =
        'I could not reach the accreditation service. Please try again.';
      created.bubble.classList.add('is-error');
      created.reply.removeAttribute('aria-busy');

      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'companion-retry';
      retry.textContent = 'Retry';
      retry.addEventListener('click', function () {
        created.reply.remove();
        submitCompanionQuestion(input);
      });
      created.stack.appendChild(retry);

      if (composerForm) {
        const sendButton = composerForm.querySelector('button[type="submit"]');
        const field = composerForm.querySelector('input');
        sendButton.disabled = false;
        field.disabled = false;
        if (field.value === '') field.value = question;
      }
      body.scrollTop = body.scrollHeight;
    }

    input.value = '';

    fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      credentials: 'same-origin',
      body: JSON.stringify({ question: question }),
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Request failed with status ' + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        settle(data.reply || '', data.source || '', data.suggestions || []);
      })
      .catch(function () {
        fail();
      });
  }

  function bindMessaging() {
    document.querySelectorAll('.sample-prompt-list button').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = document.querySelector('.composer-row input');
        if (!input) return;
        input.value = button.textContent.trim();
        input.focus();
      });
    });

    document.querySelectorAll('form[data-companion-form]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        const input = form.querySelector('input');
        if (!input) return;
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

    document.querySelectorAll('.save-settings-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        showToast('Changes saved');
      });
    });

    document.querySelectorAll('.add-document-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png';
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
      const departmentInputs = departmentField
        ? departmentField.querySelectorAll('input[name="departments"]')
        : [];

      if (departmentScope.length && departmentField && departmentInputs.length) {
        function updateDepartmentScope() {
          const selectedScope = form.querySelector('input[name="department_scope"]:checked');
          const isSpecific = selectedScope && selectedScope.value === 'specific';
          departmentField.hidden = !isSpecific;
          departmentInputs.forEach(function (input) {
            input.disabled = !isSpecific;
          });
        }

        departmentScope.forEach(function (radio) {
          radio.addEventListener('change', updateDepartmentScope);
        });
        updateDepartmentScope();
      }

      const deadlineField = form.querySelector('.assignment-deadline-field');
      const deadlineInput = form.querySelector('input[name="deadline"]');
      const noDeadlineInput = form.querySelector('input[name="no_deadline"]');
      if (!deadlineField || !deadlineInput || !noDeadlineInput) return;

      function updateDeadlineState() {
        const noDeadline = noDeadlineInput.checked;
        deadlineInput.disabled = noDeadline;
        deadlineInput.required = !noDeadline;
        deadlineInput.setAttribute('aria-disabled', noDeadline ? 'true' : 'false');
        deadlineField.classList.toggle('is-no-deadline', noDeadline);
        if (noDeadline) deadlineInput.value = '';
      }

      noDeadlineInput.addEventListener('change', updateDeadlineState);
      updateDeadlineState();
    });
  }

  function bindConfirmDialogs() {
    const dialog = document.createElement('dialog');
    dialog.className = 'confirm-dialog';
    dialog.innerHTML =
      '<div class="confirm-dialog-head">' +
        '<h2 data-confirm-title>Please confirm</h2>' +
        '<button type="button" class="confirm-dialog-close" data-confirm-cancel aria-label="Cancel and close">&times;</button>' +
      '</div>' +
      '<p class="confirm-dialog-copy" data-confirm-copy></p>' +
      '<div class="confirm-dialog-actions">' +
        '<button type="button" class="btn btn-ghost" data-confirm-cancel>Cancel</button>' +
        '<button type="button" class="btn btn-primary" data-confirm-accept></button>' +
      '</div>';
    document.body.appendChild(dialog);

    let pendingAction = null;

    function openConfirm(options) {
      const title = dialog.querySelector('[data-confirm-title]');
      const copy = dialog.querySelector('[data-confirm-copy]');
      const accept = dialog.querySelector('[data-confirm-accept]');
      title.textContent = options.title || 'Please confirm';
      copy.textContent = options.message || 'Are you sure you want to continue?';
      accept.textContent = options.acceptLabel || 'Continue';
      accept.className = 'btn ' + (options.danger ? 'btn-danger' : 'btn-primary');
      pendingAction = options.action || null;
      if (typeof dialog.showModal === 'function') dialog.showModal();
    }

    function closeConfirm() {
      pendingAction = null;
      if (dialog.open) dialog.close();
    }

    dialog.querySelectorAll('[data-confirm-cancel]').forEach(function (button) {
      button.addEventListener('click', closeConfirm);
    });

    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) closeConfirm();
    });

    dialog.querySelector('[data-confirm-accept]').addEventListener('click', function () {
      const action = pendingAction;
      closeConfirm();
      if (action) action();
    });

    document.addEventListener('submit', function (event) {
      const form = event.target;
      const submitter = form && event.submitter;
      const formConfirms = form && form.matches('[data-confirm]');
      const submitterConfirms = submitter && submitter.matches('[data-confirm]');
      if (!formConfirms && !submitterConfirms) return;

      if (form.dataset.confirmTriggered === 'true') {
        delete form.dataset.confirmTriggered;
        return;
      }

      event.preventDefault();
      const source = submitterConfirms ? submitter : form;
      const actionSelect = form.querySelector('select[name="action"]');
      let title = source.dataset.confirmTitle || 'Please confirm';
      let message = source.dataset.confirmMessage || 'Are you sure you want to continue?';
      let acceptLabel = source.dataset.confirmAccept || 'Continue';
      let danger = source.dataset.confirmTone === 'danger';
      if (actionSelect && actionSelect.customLabel) {
        title = actionSelect.customTitle || title;
        message = 'Submit this review decision as "' + actionSelect.customLabel + '"? The decision is recorded in the evidence history and audit trail.';
        acceptLabel = 'Confirm decision';
        danger = actionSelect.customTone === 'danger';
      }
      openConfirm({
        title: title,
        message: message,
        acceptLabel: acceptLabel,
        danger: danger,
        action: function () {
          form.dataset.confirmTriggered = 'true';
          if (submitter && typeof form.requestSubmit === 'function') {
            form.requestSubmit(submitter);
          } else if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
          } else {
            form.submit();
          }
        },
      });
    });

    document.addEventListener('click', function (event) {
      const target = event.target.closest('[data-confirm]');
      if (!target) return;

      if (target.dataset.confirmHandled === 'true') {
        target.dataset.confirmHandled = '';
        return;
      }

      const form = target.closest('form');
      const isSubmit = form && (target.type === 'submit' || target.matches('button[type="submit"]'));
      if (form && isSubmit) return;

      event.preventDefault();
      event.stopPropagation();
      openConfirm({
        title: target.dataset.confirmTitle || 'Please confirm',
        message: target.dataset.confirmMessage || 'Are you sure you want to continue?',
        acceptLabel: target.dataset.confirmAccept || 'Continue',
        danger: target.dataset.confirmTone === 'danger',
        action: function () {
          if (target.hasAttribute('href')) {
            window.location.href = target.getAttribute('href');
          } else {
            target.dataset.confirmHandled = 'true';
            target.click();
          }
        },
      });
    });
  }

  function bindReviewActionLabels() {
    document.querySelectorAll('select[name="action"]').forEach(function (select) {
      function update() {
        const option = select.selectedOptions[0];
        if (!option) return;
        const value = option.value;
        select.customLabel = option.text;
        if (value === 'approve') {
          select.customTitle = 'Confirm approval';
          select.customTone = '';
        } else if (value === 'revision') {
          select.customTitle = 'Confirm revision request';
          select.customTone = '';
        } else if (value === 'non_complied') {
          select.customTitle = 'Confirm non-compliance';
          select.customTone = 'danger';
        } else {
          select.customTitle = 'Confirm review decision';
          select.customTone = '';
        }
      }
      update();
      select.addEventListener('change', update);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindSearches();
    bindFilterTabs();
    bindSelectableGroups();
    bindSettingsTabs();
    bindNotifications();
    bindNotificationMenu();
    bindProfileMenu();
    bindMobileNavigation();
    bindSidebarCollapse();
    bindAiraCompanion();
    bindMessaging();
    bindProfilePhoto();
    bindActionButtons();
    bindWorkspaceActions();
    bindUserManagement();
    bindDashboardLinks();
    bindProgressValues();
    bindDataTooltips();
    bindAreaAssignmentForms();
    bindAreaFilters();
    bindRepositoryFilters();
    bindConfirmDialogs();
    bindReviewActionLabels();
  });
})();
