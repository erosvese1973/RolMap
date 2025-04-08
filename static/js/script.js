// Global utility functions for the application

/**
 * Formats a date string to a locale-specific format
 * @param {string} dateString - The date string to format
 * @returns {string} The formatted date string
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Shows a temporary toast notification
 * @param {string} message - The message to display
 * @param {string} type - The type of toast (success, error, warning, info)
 */
function showToast(message, type = 'info') {
    // Check if the toast container exists, if not create it
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create a new toast element
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    // Set the toast content
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    // Add the toast to the container
    toastContainer.appendChild(toast);
    
    // Initialize and show the toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 5000
    });
    bsToast.show();
    
    // Remove the toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

/**
 * Validates form inputs
 * @param {HTMLFormElement} form - The form to validate
 * @returns {boolean} Whether the form is valid
 */
function validateForm(form) {
    // Get all required fields
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    // Check each required field
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            
            // Add or update the feedback message
            let feedback = field.nextElementSibling;
            if (!feedback || !feedback.classList.contains('invalid-feedback')) {
                feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                field.parentNode.insertBefore(feedback, field.nextSibling);
            }
            feedback.textContent = 'Questo campo è obbligatorio';
            
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
            
            // Remove any feedback message
            const feedback = field.nextElementSibling;
            if (feedback && feedback.classList.contains('invalid-feedback')) {
                feedback.remove();
            }
        }
    });
    
    return isValid;
}

/**
 * Registers event listeners when the DOM content is loaded
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add event listener to all forms for validation
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!validateForm(this)) {
                event.preventDefault();
                event.stopPropagation();
                showToast('Per favore, compila tutti i campi obbligatori', 'warning');
            }
        });
    });
    
    // Add color picker preview functionality
    document.querySelectorAll('input[type="color"]').forEach(colorInput => {
        colorInput.addEventListener('input', function() {
            // Find the preview element that's next to this input
            const previewEl = this.parentElement.querySelector('.color-preview');
            if (previewEl) {
                previewEl.style.backgroundColor = this.value;
            }
        });
    });
    
    // Sync agent name between input fields and hidden fields
    document.querySelectorAll('input[name="agent_name"]').forEach(nameInput => {
        nameInput.addEventListener('input', function() {
            const agentId = this.closest('form').action.split('/').pop();
            // Update hidden field in the map form
            const hiddenField = document.getElementById('map_agent_name_' + agentId);
            if (hiddenField) {
                hiddenField.value = this.value;
            }
        });
    });
    
    // Add new agent row functionality
    const addNewAgentBtn = document.getElementById('addNewAgentBtn');
    if (addNewAgentBtn) {
        addNewAgentBtn.addEventListener('click', function() {
            // Get table body
            const tableBody = document.querySelector('table.table tbody');
            
            if (!tableBody) {
                // If no table exists yet (first agent), reload the page
                window.location.href = window.location.href;
                return;
            }
            
            // Create a new row
            const newRow = document.createElement('tr');
            newRow.id = 'new-agent-row';
            newRow.className = 'bg-light';
            
            // Add the new row HTML
            newRow.innerHTML = `
                <td>
                    <form action="${window.location.origin}/update_agent_contacts/new" method="post" class="d-flex align-items-center">
                        <div style="width: 20px; height: 20px; background-color: #ff9800; border-radius: 50%; margin-right: 10px; border: 1px solid #333;"></div>
                        <div class="input-group input-group-sm me-2" style="max-width: 200px;">
                            <input type="text" class="form-control form-control-sm" 
                                  name="agent_name" value="" 
                                  placeholder="Nome nuovo agente" aria-label="Nome agente" required>
                        </div>
                        <button type="submit" class="btn btn-sm btn-success btn-sm">
                            <i class="fas fa-plus"></i>
                        </button>
                    </form>
                </td>
                <td>
                    <div class="d-flex flex-column text-muted">
                        <small>Completa la creazione dell'agente</small>
                        <small>per modificare i contatti</small>
                    </div>
                </td>
                <td>
                    <span class="badge bg-secondary">0</span>
                </td>
                <td>
                    <button type="button" class="btn btn-sm btn-outline-secondary" disabled>
                        <i class="fas fa-map me-1"></i>
                        Mappa
                    </button>
                </td>
            `;
            
            // Insert row at the beginning of the table
            tableBody.insertBefore(newRow, tableBody.firstChild);
            
            // Scroll to the new row
            newRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Focus the name input
            setTimeout(() => {
                const nameInput = newRow.querySelector('input[name="agent_name"]');
                if (nameInput) {
                    nameInput.focus();
                }
            }, 100);
            
            // Disable the button to prevent multiple clicks
            addNewAgentBtn.disabled = true;
            
            // Re-enable after 3 seconds
            setTimeout(() => {
                addNewAgentBtn.disabled = false;
            }, 3000);
        });
    }
});
