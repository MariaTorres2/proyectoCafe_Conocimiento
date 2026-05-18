/**
 * Modales — avisos claros; alert() del navegador se redirige aquí.
 */
(function () {
  "use strict";

  var backdrop = null;
  var dialog = null;
  var activeResolve = null;

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function ensureDom() {
    if (backdrop) return;
    backdrop = document.createElement("div");
    backdrop.className = "app-modal-backdrop";
    backdrop.setAttribute("role", "presentation");
    backdrop.hidden = true;
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) finish(false);
    });

    dialog = document.createElement("div");
    dialog.className = "app-modal";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.innerHTML =
      '<div class="app-modal__header">' +
      '<h2 class="app-modal__title" id="app-modal-title"></h2>' +
      '<button type="button" class="app-modal__close" aria-label="Cerrar">&times;</button>' +
      "</div>" +
      '<div class="app-modal__body"></div>' +
      '<div class="app-modal__footer"></div>';

    dialog.querySelector(".app-modal__close").addEventListener("click", function () {
      finish(false);
    });

    backdrop.appendChild(dialog);
    document.body.appendChild(backdrop);

    document.addEventListener("keydown", function (e) {
      if (!backdrop || backdrop.hidden) return;
      if (e.key === "Escape") finish(false);
    });
  }

  function finish(ok) {
    if (!backdrop) return;
    backdrop.hidden = true;
    document.body.classList.remove("app-modal-open");
    var r = activeResolve;
    activeResolve = null;
    if (r) r(!!ok);
  }

  function openModal(opts) {
    ensureDom();
    opts = opts || {};
    var title = opts.title || "Aviso";
    var body = opts.body || "";
    var confirmText = opts.confirmText || "Aceptar";
    var cancelText = opts.cancelText;
    var showCancel = !!cancelText;

    dialog.querySelector(".app-modal__title").textContent = title;
    dialog.querySelector(".app-modal__body").innerHTML = body;

    var footer = dialog.querySelector(".app-modal__footer");
    footer.innerHTML = "";

    if (showCancel) {
      var btnCancel = document.createElement("button");
      btnCancel.type = "button";
      btnCancel.className = "app-modal__btn app-modal__btn--ghost";
      btnCancel.textContent = cancelText;
      btnCancel.addEventListener("click", function () {
        finish(false);
      });
      footer.appendChild(btnCancel);
    }

    var btnOk = document.createElement("button");
    btnOk.type = "button";
    btnOk.className = "app-modal__btn app-modal__btn--primary";
    btnOk.textContent = confirmText;
    btnOk.addEventListener("click", function () {
      finish(true);
    });
    footer.appendChild(btnOk);

    activeResolve = opts.resolve || null;

    backdrop.hidden = false;
    document.body.classList.add("app-modal-open");
    btnOk.focus();
  }

  window.AppModal = {
    alert: function (message, title) {
      openModal({
        title: title || "Información",
        body: "<p class=\"app-modal__text\">" + escapeHtml(message).replace(/\n/g, "<br/>") + "</p>",
        confirmText: "Entendido",
        resolve: null,
      });
    },
    confirm: function (message, title) {
      return new Promise(function (resolve) {
        openModal({
          title: title || "Confirmar acción",
          body: "<p class=\"app-modal__text\">" + escapeHtml(message).replace(/\n/g, "<br/>") + "</p>",
          cancelText: "Cancelar",
          confirmText: "Continuar",
          resolve: resolve,
        });
      });
    },
  };

  var nativeAlert = window.alert;
  window.alert = function (msg) {
    try {
      window.AppModal.alert(String(msg));
    } catch (e) {
      nativeAlert(msg);
    }
  };
})();

/**
 * Fechas — fuerza selección desde calendario nativo y evita escritura manual.
 */
(function () {
  "use strict";

  function isDateInput(el) {
    return el && el.matches && el.matches('input[type="date"]');
  }

  function openDatePicker(input) {
    if (!input || input.disabled) return;
    if (typeof input.showPicker === "function") {
      try {
        input.showPicker();
      } catch (e) {
        input.focus();
      }
    }
  }

  document.addEventListener("click", function (e) {
    if (!isDateInput(e.target)) return;
    openDatePicker(e.target);
  });

  document.addEventListener("focusin", function (e) {
    if (!isDateInput(e.target)) return;
    openDatePicker(e.target);
  });

  document.addEventListener("keydown", function (e) {
    if (!isDateInput(e.target)) return;
    var allowedKeys = [
      "Tab",
      "Escape",
      "Enter",
      " ",
      "ArrowLeft",
      "ArrowRight",
      "ArrowUp",
      "ArrowDown",
      "PageUp",
      "PageDown",
      "Home",
      "End",
    ];
    if (allowedKeys.indexOf(e.key) !== -1 || e.ctrlKey || e.metaKey || e.altKey) return;
    // Bloquea escritura directa de fechas, pero conserva navegación del calendario.
    if (e.key.length === 1 || e.key === "Backspace" || e.key === "Delete") {
      e.preventDefault();
    }
  });

  document.addEventListener("paste", function (e) {
    if (!isDateInput(e.target)) return;
    e.preventDefault();
  });

  document.addEventListener("drop", function (e) {
    if (!isDateInput(e.target)) return;
    e.preventDefault();
  });
})();
