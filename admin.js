// Common admin dashboard functions
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `flash-message ${type}`;
    alertDiv.textContent = message;
    document.querySelector('.admin-container').prepend(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}

// Question detail page functions
function updateQuestionDifficulty(questionId, difficulty) {
    fetch('/admin/update_question_difficulty', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? 
                           document.querySelector('meta[name="csrf-token"]').getAttribute('content') : ''
        },
        body: JSON.stringify({
            question_id: questionId,
            difficulty: difficulty
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Question difficulty updated successfully.', 'success');
            // Update the UI
            document.querySelector('.difficulty-badge').className = 'difficulty-badge badge-' + difficulty;
            document.querySelector('.difficulty-badge').textContent = difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
            // Update active button
            document.querySelectorAll('.difficulty-buttons .btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`.difficulty-buttons .btn[onclick*="${difficulty}"]`).classList.add('active');
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        showAlert('Error updating question difficulty.', 'danger');
        console.error('Error:', error);
    });
}

function toggleStateSpecific() {
    const isStateSpecific = document.getElementById('stateSpecificSwitch').checked;
    const stateSelectContainer = document.getElementById('stateSelectContainer');
    
    if (isStateSpecific) {
        stateSelectContainer.style.display = 'block';
    } else {
        stateSelectContainer.style.display = 'none';
        updateQuestionState();
    }
}

function updateQuestionState() {
    const isStateSpecific = document.getElementById('stateSpecificSwitch').checked;
    const state = isStateSpecific ? document.getElementById('stateSelect').value : null;
    
    if (isStateSpecific && !state) {
        showAlert('Please select a state.', 'warning');
        return;
    }
    
    const questionId = document.querySelector('.question-header h2').getAttribute('data-question-id');
    
    fetch('/admin/update_question_state', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? 
                           document.querySelector('meta[name="csrf-token"]').getAttribute('content') : ''
        },
        body: JSON.stringify({
            question_id: questionId,
            state_specific: isStateSpecific,
            state: state
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Question state settings updated successfully.', 'success');
            // Update UI if needed
            if (isStateSpecific) {
                if (document.querySelector('.state-specific-info')) {
                    document.querySelector('.state-specific-info strong').textContent = state;
                } else {
                    const stateDiv = document.createElement('div');
                    stateDiv.className = 'state-specific-info';
                    stateDiv.innerHTML = `<i class="fas fa-map-marker-alt"></i> This is a state-specific question for <strong>${state}</strong>`;
                    document.querySelector('.question-content').appendChild(stateDiv);
                }
            } else {
                const stateInfo = document.querySelector('.state-specific-info');
                if (stateInfo) {
                    stateInfo.remove();
                }
            }
        } else {
            showAlert('Error: ' + data.message, 'danger');
            // Reset the switch if there was an error
            if (!isStateSpecific) {
                document.getElementById('stateSpecificSwitch').checked = true;
                document.getElementById('stateSelectContainer').style.display = 'block';
            }
        }
    })
    .catch(error => {
        showAlert('Error updating question state settings.', 'danger');
        console.error('Error:', error);
    });
}

// Questions list page functions
document.addEventListener('DOMContentLoaded', function() {
    // Difficulty select event handlers for question management
    document.querySelectorAll('.difficulty-select').forEach(select => {
        select.addEventListener('change', function() {
            const questionId = this.getAttribute('data-question-id');
            const newDifficulty = this.value;
            
            fetch('/admin/update_question_difficulty', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? 
                                   document.querySelector('meta[name="csrf-token"]').getAttribute('content') : ''
                },
                body: JSON.stringify({
                    question_id: questionId,
                    difficulty: newDifficulty
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('Difficulty updated successfully', 'success');
                } else {
                    showAlert('Failed to update difficulty', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('An error occurred', 'error');
            });
        });
    });
    
    // State toggle event handlers
    document.querySelectorAll('.state-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const questionId = this.getAttribute('data-question-id');
            const isStateSpecific = this.checked;
            const stateSelect = document.querySelector(`.state-select[data-question-id="${questionId}"]`);
            const state = stateSelect.value;
            
            stateSelect.disabled = !isStateSpecific;
            
            updateQuestionListState(questionId, isStateSpecific, state);
        });
    });
    
    // State select event handlers
    document.querySelectorAll('.state-select').forEach(select => {
        select.addEventListener('change', function() {
            const questionId = this.getAttribute('data-question-id');
            const stateToggle = document.querySelector(`.state-toggle[data-question-id="${questionId}"]`);
            const isStateSpecific = stateToggle.checked;
            const state = this.value;
            
            updateQuestionListState(questionId, isStateSpecific, state);
        });
    });
});

function updateQuestionListState(questionId, isStateSpecific, state) {
    fetch('/admin/update_question_state', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? 
                          document.querySelector('meta[name="csrf-token"]').getAttribute('content') : ''
        },
        body: JSON.stringify({
            question_id: questionId,
            state_specific: isStateSpecific,
            state: state
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Question state updated successfully', 'success');
        } else {
            showAlert('Failed to update question state', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('An error occurred', 'error');
    });
}
