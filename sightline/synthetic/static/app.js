/**
 * Sightline Synthetic Target Application — Client-Side Deterministic Behavior
 */
function initSightlineApp() {
  // Scenario 1: Form Submission & Validation
  const form = document.getElementById("form-intake");
  const inputName = document.getElementById("input-full-name");
  const inputEmail = document.getElementById("input-email");
  const selectDept = document.getElementById("select-department");
  const selectPriority = document.getElementById("select-priority");
  const nameError = document.getElementById("name-error");
  const emailError = document.getElementById("email-error");
  const formFeedback = document.getElementById("form-feedback");
  const formStatus = document.getElementById("form-feedback-status");
  const formMessage = document.getElementById("form-confirmation-message");
  const btnReset = document.getElementById("btn-reset-form");

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      let valid = true;

      // Reset error badges
      nameError.classList.remove("visible");
      emailError.classList.remove("visible");
      formFeedback.style.display = "none";
      formFeedback.className = "feedback-box";

      const nameVal = inputName.value.trim();
      const emailVal = inputEmail.value.trim();

      if (!nameVal || nameVal.length < 2) {
        nameError.classList.add("visible");
        valid = false;
      }

      if (!emailVal || !emailVal.includes("@") || !emailVal.includes(".")) {
        emailError.classList.add("visible");
        valid = false;
      }

      if (!valid) {
        formFeedback.style.display = "block";
        formFeedback.className = "feedback-box error";
        formStatus.textContent = "error";
        formMessage.textContent = "Validation failed: Please correct indicated errors.";
        return;
      }

      // Valid submission
      formFeedback.style.display = "block";
      formFeedback.className = "feedback-box success";
      formStatus.textContent = "success";
      formMessage.textContent = `Intake record created successfully: ${nameVal} (${selectDept.value}, ${selectPriority.value})`;
    });

    if (btnReset) {
      btnReset.addEventListener("click", () => {
        inputName.value = "";
        inputEmail.value = "";
        selectDept.selectedIndex = 0;
        selectPriority.selectedIndex = 0;
        nameError.classList.remove("visible");
        emailError.classList.remove("visible");
        formFeedback.style.display = "none";
        formStatus.textContent = "idle";
        formMessage.textContent = "";
      });
    }
  }

  // Scenario 2: Button Disambiguation
  const btnSave = document.getElementById("btn-action-save");
  const btnDiscard = document.getElementById("btn-action-discard");
  const editorStatusBadge = document.getElementById("editor-status-badge");
  const actionResultText = document.getElementById("action-result-text");
  const actionResultStatus = document.getElementById("action-result-status");

  if (btnSave && btnDiscard) {
    btnSave.addEventListener("click", async () => {
      const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:" || window.__ENABLE_SYNTHETIC_API__;
      let success = false;
      let statusVal = "saved";
      let msg = "Draft saved successfully at " + new Date().toLocaleTimeString();

      if (canFetch) {
        try {
          const resp = await fetch("/api/synthetic/editor-action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "save" }),
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data.status === "saved") {
              success = true;
              statusVal = "saved";
              msg = `Draft saved successfully at ${new Date().toLocaleTimeString()}`;
            }
          }
        } catch (err) {
          console.error("Save draft error:", err);
          success = false;
        }
      } else {
        // file:/// protocol fallback for headless tests without active HTTP server
        success = true;
      }

      if (success) {
        editorStatusBadge.textContent = "Saved (Draft)";
        editorStatusBadge.className = "badge badge-success";
        actionResultText.textContent = msg;
        actionResultStatus.textContent = statusVal;
      } else {
        editorStatusBadge.textContent = "Save Failed";
        editorStatusBadge.className = "badge badge-danger";
        actionResultText.textContent = "Error: Unable to persist draft edits to server.";
        actionResultStatus.textContent = "error";
      }
    });

    btnDiscard.addEventListener("click", async () => {
      const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:" || window.__ENABLE_SYNTHETIC_API__;
      let success = false;
      let statusVal = "discarded";
      let msg = "Pending changes were discarded.";

      if (canFetch) {
        try {
          const resp = await fetch("/api/synthetic/editor-action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "discard" }),
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data.status === "discarded") {
              success = true;
              statusVal = "discarded";
              msg = data.message || "Pending changes were discarded.";
            }
          }
        } catch (err) {
          console.error("Discard error:", err);
          success = false;
        }
      } else {
        // file:/// protocol fallback for headless tests without active HTTP server
        success = true;
      }

      if (success) {
        editorStatusBadge.textContent = "Changes Discarded";
        editorStatusBadge.className = "badge badge-danger";
        actionResultText.textContent = msg;
        actionResultStatus.textContent = statusVal;
      } else {
        editorStatusBadge.textContent = "Discard Failed";
        editorStatusBadge.className = "badge badge-danger";
        actionResultText.textContent = "Error: Unable to discard changes on server.";
        actionResultStatus.textContent = "error";
      }
    });
  }

  // Scenario 3: Modal Confirmation Workflow
  const btnOpenModal = document.getElementById("btn-open-deploy-modal");
  const modalOverlay = document.getElementById("deploy-modal-overlay");
  const btnModalConfirm = document.getElementById("btn-modal-confirm");
  const btnModalCancel = document.getElementById("btn-modal-cancel");
  const btnModalCloseX = document.getElementById("btn-modal-close-x");
  const deployStateBadge = document.getElementById("deploy-state-badge");
  const deployAuditLog = document.getElementById("deploy-audit-log");

  const closeModal = () => {
    if (modalOverlay) modalOverlay.classList.add("hidden");
  };

  if (btnOpenModal && modalOverlay) {
    btnOpenModal.addEventListener("click", () => {
      modalOverlay.classList.remove("hidden");
    });

    if (btnModalCancel) btnModalCancel.addEventListener("click", closeModal);
    if (btnModalCloseX) btnModalCloseX.addEventListener("click", closeModal);

    if (btnModalConfirm) {
      btnModalConfirm.addEventListener("click", () => {
        deployStateBadge.textContent = "Deployed (v1.4.2)";
        deployStateBadge.className = "badge badge-success";
        deployAuditLog.textContent = "Deployment v1.4.2 released to production at " + new Date().toLocaleTimeString();
        closeModal();
      });
    }
  }

  // Scenario 4: Temporarily Disabled Button with Delayed Enablement
  const checkboxCompliance = document.getElementById("checkbox-compliance");
  const btnProcessReport = document.getElementById("btn-process-report");
  const processingStatusBadge = document.getElementById("processing-status-badge");
  const timerCountdown = document.getElementById("timer-countdown");

  if (checkboxCompliance && btnProcessReport) {
    checkboxCompliance.addEventListener("change", (e) => {
      if (e.target.checked) {
        processingStatusBadge.textContent = "Verifying compliance...";
        processingStatusBadge.className = "badge badge-pending";
        if (timerCountdown) timerCountdown.textContent = "(verifying prerequisites...)";

        // Deterministic delay (500ms) to model real-world asynchronous validation
        setTimeout(() => {
          btnProcessReport.disabled = false;
          btnProcessReport.removeAttribute("disabled");
          processingStatusBadge.textContent = "Ready to process";
          processingStatusBadge.className = "badge badge-idle";
          if (timerCountdown) timerCountdown.textContent = "(ready)";
        }, 500);
      } else {
        btnProcessReport.disabled = true;
        btnProcessReport.setAttribute("disabled", "true");
        processingStatusBadge.textContent = "Awaiting terms";
        processingStatusBadge.className = "badge badge-idle";
        if (timerCountdown) timerCountdown.textContent = "";
      }
    });

    btnProcessReport.addEventListener("click", () => {
      if (!btnProcessReport.disabled) {
        processingStatusBadge.textContent = "Report processed successfully";
        processingStatusBadge.className = "badge badge-success";
      }
    });
  }

  // Scenario 5: Destructive Action with Explicit Approval Gate
  const btnExecutePurge = document.getElementById("btn-execute-purge");
  const toggleApproval = document.getElementById("toggle-operator-approval");
  const inputApprovalToken = document.getElementById("input-approval-token");
  const safetyGateIndicator = document.getElementById("safety-gate-indicator");
  const databaseStatusBadge = document.getElementById("database-status-badge");
  const purgeAlert = document.getElementById("purge-feedback-alert");

  if (toggleApproval && inputApprovalToken) {
    toggleApproval.addEventListener("change", (e) => {
      if (e.target.checked) {
        inputApprovalToken.value = "APPROVAL-SIGHTLINE-2026";
      } else {
        inputApprovalToken.value = "";
      }
    });
  }

  if (btnExecutePurge) {
    btnExecutePurge.addEventListener("click", () => {
      const token = inputApprovalToken ? inputApprovalToken.value.trim() : "";
      const isApproved = token === "APPROVAL-SIGHTLINE-2026";

      if (!isApproved) {
        // Enforce safety boundary
        safetyGateIndicator.textContent = "LOCKED";
        safetyGateIndicator.className = "badge badge-locked";
        purgeAlert.style.display = "block";
        purgeAlert.className = "feedback-box error";
        purgeAlert.textContent = "SAFETY VIOLATION: Purge rejected. Valid operator authorization token required.";
        return;
      }

      // Approved execution
      safetyGateIndicator.textContent = "APPROVED";
      safetyGateIndicator.className = "badge badge-approved";
      databaseStatusBadge.textContent = "Purged under Ticket #APP-PURGE-001";
      databaseStatusBadge.className = "badge badge-danger";
      purgeAlert.style.display = "block";
      purgeAlert.className = "feedback-box success";
      purgeAlert.textContent = "PURGE COMPLETE: Database wiped under authorized governance ticket #APP-PURGE-001.";
    });
  }

  // Global Reset Button
  const btnGlobalReset = document.getElementById("btn-global-reset");
  if (btnGlobalReset) {
    btnGlobalReset.addEventListener("click", async () => {
      try {
        await fetch("/api/synthetic/reset", { method: "POST" });
        window.location.reload();
      } catch (err) {
        console.error("Reset failed", err);
      }
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSightlineApp);
} else {
  initSightlineApp();
}
