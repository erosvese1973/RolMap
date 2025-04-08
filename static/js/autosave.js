/**
 * Script per gestire il salvataggio automatico dei campi nella pagina degli agenti
 */

document.addEventListener('DOMContentLoaded', function() {
    // Timeout per il salvataggio dei campi (in millisecondi)
    const saveDelay = 500;
    let saveTimers = {};

    // Seleziona tutti i campi che supportano l'autosave
    const autoSaveFields = document.querySelectorAll('.auto-save-field');
    
    // Gestione anteprima colore
    const colorFields = document.querySelectorAll('.auto-save-field[data-field-type="color"]');
    colorFields.forEach(colorField => {
        colorField.addEventListener('input', function() {
            // Trova l'elemento di anteprima più vicino
            const preview = this.closest('.d-flex').querySelector('.color-preview');
            if (preview) {
                preview.style.backgroundColor = this.value;
            }
        });
    });

    // Aggiungi event listener a tutti i campi
    autoSaveFields.forEach(field => {
        // Salva il valore originale per rilevare le modifiche
        field.setAttribute('data-original-value', field.value);
        
        // Aggiungi un event listener appropriato in base al tipo di campo
        if (field.tagName === 'INPUT' && field.type === 'color') {
            // Per i campi colore, salva al change
            field.addEventListener('change', function() {
                autoSaveField(this);
            });
        } else {
            // Per i campi di testo, salva quando si esce dal campo
            field.addEventListener('blur', function() {
                // Controlla se il valore è cambiato prima di salvare
                if (this.value !== this.getAttribute('data-original-value')) {
                    autoSaveField(this);
                }
            });
            
            // Per i campi di testo, avvia un timer dopo che l'utente smette di digitare
            field.addEventListener('input', function() {
                const fieldId = `${this.dataset.agentId}-${this.dataset.fieldType}`;
                
                // Cancella il timer esistente se presente
                if (saveTimers[fieldId]) {
                    clearTimeout(saveTimers[fieldId]);
                }
                
                // Imposta un nuovo timer
                saveTimers[fieldId] = setTimeout(() => {
                    // Controlla se il valore è cambiato prima di salvare
                    if (this.value !== this.getAttribute('data-original-value')) {
                        autoSaveField(this);
                    }
                }, saveDelay);
            });
        }
    });
    
    /**
     * Funzione per salvare automaticamente un campo
     * @param {HTMLElement} field - Il campo da salvare
     */
    function autoSaveField(field) {
        const agentId = field.dataset.agentId;
        const fieldType = field.dataset.fieldType;
        const value = field.value;
        
        // Visualizza un indicatore di caricamento
        showLoadingIndicator(field);
        
        // Invia i dati al server usando fetch
        fetch(`/api/update_agent_field/${agentId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                field_type: fieldType,
                value: value
            }),
        })
        .then(response => response.json())
        .then(data => {
            // Rimuovi l'indicatore di caricamento
            hideLoadingIndicator(field);
            
            if (data.success) {
                // Aggiorna il valore originale
                field.setAttribute('data-original-value', value);
                
                // Se è cambiato un nome, aggiorna anche eventuali riferimenti nelle pagine
                if (fieldType === 'name') {
                    updateAgentNameReferences(agentId, value);
                }
                
                // Mostra un'indicazione di successo
                showSuccessIndicator(field);
                
                // Se è cambiato un colore, aggiorna i riferimenti al colore
                if (fieldType === 'color') {
                    updateColorReferences(agentId, value);
                }
            } else {
                // Ripristina il valore originale in caso di errore
                field.value = field.getAttribute('data-original-value');
                showToast(data.error, 'danger');
                
                // Mostra un'indicazione di errore
                showErrorIndicator(field);
            }
        })
        .catch(error => {
            hideLoadingIndicator(field);
            showToast('Errore di connessione al server', 'danger');
            showErrorIndicator(field);
            console.error('Error:', error);
        });
    }
    
    /**
     * Aggiorna i riferimenti al nome dell'agente nella pagina
     * @param {string} agentId - ID dell'agente
     * @param {string} newName - Nuovo nome dell'agente
     */
    function updateAgentNameReferences(agentId, newName) {
        // Aggiorna il nome negli hidden input per il form della mappa
        const mapNameInput = document.getElementById(`map_agent_name_${agentId}`);
        if (mapNameInput) {
            mapNameInput.value = newName;
        }
        
        // Aggiorna i titoli delle modali
        const modalTitles = document.querySelectorAll(`#editColorModalLabel${agentId}`);
        modalTitles.forEach(title => {
            if (title.innerHTML.includes('Modifica Colore:')) {
                title.innerHTML = `<i class="fas fa-palette me-2"></i> Modifica Colore: ${newName}`;
            }
        });
    }
    
    /**
     * Aggiorna i riferimenti al colore dell'agente nella pagina
     * @param {string} agentId - ID dell'agente
     * @param {string} newColor - Nuovo colore dell'agente
     */
    function updateColorReferences(agentId, newColor) {
        // Aggiorna il pulsante di colore nella tabella
        const colorBtn = document.querySelector(`button.color-circle-btn[data-bs-target="#editColorModal${agentId}"]`);
        if (colorBtn) {
            colorBtn.style.backgroundColor = newColor;
        }
    }
    
    /**
     * Mostra un indicatore di caricamento per un campo
     * @param {HTMLElement} field - Il campo in caricamento
     */
    function showLoadingIndicator(field) {
        // Aggiungi una classe per indicare che è in caricamento
        field.classList.add('saving');
        field.style.opacity = '0.7';
    }
    
    /**
     * Nasconde l'indicatore di caricamento per un campo
     * @param {HTMLElement} field - Il campo in caricamento
     */
    function hideLoadingIndicator(field) {
        // Rimuovi la classe di caricamento
        field.classList.remove('saving');
        field.style.opacity = '1';
    }
    
    /**
     * Mostra un indicatore di successo per un campo
     * @param {HTMLElement} field - Il campo salvato
     */
    function showSuccessIndicator(field) {
        // Aggiungi una classe per indicare successo
        field.classList.add('save-success');
        
        // Rimuovi la classe dopo un po'
        setTimeout(() => {
            field.classList.remove('save-success');
        }, 1000);
    }
    
    /**
     * Mostra un indicatore di errore per un campo
     * @param {HTMLElement} field - Il campo con errore
     */
    function showErrorIndicator(field) {
        // Aggiungi una classe per indicare errore
        field.classList.add('save-error');
        
        // Rimuovi la classe dopo un po'
        setTimeout(() => {
            field.classList.remove('save-error');
        }, 2000);
    }
});