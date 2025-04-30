document.addEventListener('DOMContentLoaded', function() {
    // Get elements
    const timerText = document.getElementById('timer-text');
    const addTimeBtn = document.getElementById('add-time-btn');
    const skipBtn = document.getElementById('skip-btn');
    const submitBtn = document.getElementById('submit-btn');
    const answerForm = document.getElementById('answer-form');
    const skippedInput = document.getElementById('skipped-input');
    const timerExpiredInput = document.getElementById('timer-expired-input');
    const serverFlashes = document.getElementById('server-flashes');
    
    // Extract points value from the points display
    let currentUserPoints = 0;
    const pointsElement = document.querySelector('.quiz-points');
    if (pointsElement) {
        const pointsText = pointsElement.textContent;
        const pointsMatch = pointsText.match(/Points: (\d+)/);
        if (pointsMatch && pointsMatch[1]) {
            currentUserPoints = parseInt(pointsMatch[1]);
        }
    }
    
    console.log("Current user points:", currentUserPoints);
    
    // Timer variables - use the current value in the timer-text element
    let timeLeft = timerText ? parseInt(timerText.textContent) : 30;
    let timerInterval;
    
    // Start the timer
    function startTimer() {
        if (!timerText) return;
        
        timerInterval = setInterval(function() {
            timeLeft--;
            updateTimerDisplay();
            
            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                if (timerExpiredInput) {
                    timerExpiredInput.value = "true";
                    
                    // Show the time expired message immediately
                    showFlashMessage('Time Ran Out', 'error');
                    
                    // Submit the form after a short delay to allow the message to be seen
                    setTimeout(() => {
                        // Use regular form submission to avoid AJAX issues with timer expiration
                        answerForm.submit();
                    }, 500);
                }
            }
        }, 1000);
    }
    
    // Update the timer display
    function updateTimerDisplay() {
        if (timerText) {
            timerText.textContent = timeLeft;
        }
    }
    
    // Initialize option selection
    function initializeOptionSelection() {
        const options = document.querySelectorAll('.option');
        options.forEach(option => {
            const radio = option.querySelector('input[type="radio"]');
            const label = option.querySelector('label');
            
            option.addEventListener('click', function() {
                radio.checked = true;
                
                // Add visual feedback
                document.querySelectorAll('.option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                option.classList.add('selected');
            });
            
            // Also make the label clickable
            if (label) {
                label.addEventListener('click', function(e) {
                    e.preventDefault(); // Prevent default behavior
                    radio.checked = true;
                    
                    // Add visual feedback
                    document.querySelectorAll('.option').forEach(opt => {
                        opt.classList.remove('selected');
                    });
                    option.classList.add('selected');
                });
            }
        });
    }
    
    // Submit answer function
    function submitAnswer() {
        clearInterval(timerInterval);
    }
    
    // Add event listeners
    if (answerForm) {
        answerForm.addEventListener('submit', function(e) {
            // Check if an answer is selected
            const selectedAnswer = document.querySelector('input[name="answer"]:checked');
            
            // If no answer is selected and timer isn't expired and question isn't skipped
            if (!selectedAnswer && 
                document.getElementById('timer-expired-input').value !== "true" &&
                document.getElementById('skipped-input').value !== "true") {
                e.preventDefault(); // Prevent form submission
                showFlashMessage('Please select an answer', 'error');
                return false;
            }
            
            submitAnswer();
            // Let the normal form submission handle the rest
        });
    }
    
    if (skipBtn) {
        skipBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const points = parseInt(this.dataset.points);
            
            console.log("Skip button clicked. Required points:", points, "Current points:", currentUserPoints);
            
            if (currentUserPoints >= points) {
                skippedInput.value = "true";
                clearInterval(timerInterval); // Stop the timer
                showFlashMessage('Skipping question...', 'success');
                
                // Submit the form after a short delay to show the message
                setTimeout(() => {
                    answerForm.submit();
                }, 500);
            } else {
                showFlashMessage(`You need ${points} points to skip. You have ${currentUserPoints}.`, 'error');
            }
        });
    }
    
    if (addTimeBtn) {
        addTimeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const points = parseInt(this.dataset.points);
            
            console.log("Add time button clicked. Required points:", points, "Current points:", currentUserPoints);
            
            if (currentUserPoints >= points) {
                // Get CSRF token from meta tag
                const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
                
                fetch('/add_time', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({})
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        timeLeft += 10;
                        updateTimerDisplay();
                        
                        // Update points display
                        if (pointsElement) {
                            pointsElement.textContent = `Points: ${data.points}`;
                            currentUserPoints = data.points;
                        }
                        
                        showFlashMessage('Added 10 seconds!', 'success');
                    } else {
                        showFlashMessage(data.message || 'Failed to add time', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showFlashMessage('An error occurred when adding time.', 'error');
                });
            } else {
                showFlashMessage(`You need ${points} points to add time. You have ${currentUserPoints}.`, 'error');
            }
        });
    }
    
    function showFlashMessage(message, category) {
        // Show message in the server flashes container
        if (serverFlashes) {
            // Clear existing messages first
            serverFlashes.innerHTML = '';
            
            const flashMessage = document.createElement('div');
            flashMessage.className = `quiz-flash-message ${category}`;
            flashMessage.textContent = message;
            
            serverFlashes.appendChild(flashMessage);
            
            // Auto-remove after 3 seconds
            setTimeout(() => {
                flashMessage.style.opacity = '0';
                flashMessage.style.transform = 'translateY(-20px)';
                flashMessage.style.transition = 'all 0.3s ease';
                setTimeout(() => {
                    flashMessage.remove();
                }, 300);
            }, 3000);
        }
    }
    
    // Initialize the quiz
    initializeOptionSelection();
    startTimer();
});
