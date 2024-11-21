document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('settingsForm');
    const startButton = document.getElementById('startButton');
    const stopButton = document.getElementById('stopButton');
    const status = document.getElementById('status');
  
    // Load saved settings
    chrome.storage.local.get([
      'apiKey',
      'agentUsername',
      'agentPassword',
      'userUsername',
      'personality'
    ], function(result) {
      if (result.apiKey) document.getElementById('apiKey').value = result.apiKey;
      if (result.agentUsername) document.getElementById('agentUsername').value = result.agentUsername;
      if (result.agentPassword) document.getElementById('agentPassword').value = result.agentPassword;
      if (result.userUsername) document.getElementById('userUsername').value = result.userUsername;
      if (result.personality) document.getElementById('personality').value = result.personality;
    });
  
    // Default button handlers
    document.getElementById('useDefaultApi').addEventListener('click', function() {
      document.getElementById('apiKey').value = '';
      document.getElementById('apiKey').placeholder = 'Using default API key';
    });
  
    document.getElementById('useDefaultUsername').addEventListener('click', function() {
      document.getElementById('agentUsername').value = '';
      document.getElementById('agentUsername').placeholder = 'Using default username';
    });
  
    document.getElementById('useDefaultPassword').addEventListener('click', function() {
      document.getElementById('agentPassword').value = '';
      document.getElementById('agentPassword').placeholder = 'Using default password';
    });
  
    // Form submit handler
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const settings = {
        apiKey: document.getElementById('apiKey').value,
        agentUsername: document.getElementById('agentUsername').value,
        agentPassword: document.getElementById('agentPassword').value,
        userUsername: document.getElementById('userUsername').value,
        personality: document.getElementById('personality').value
      };
  
      // Save settings
      chrome.storage.local.set(settings, function() {
        if (chrome.runtime.lastError) {
          showStatus('Error saving settings', 'error');
          return;
        }
  
        // Initialize System Manager
        chrome.runtime.sendMessage({
          action: 'startBot',
          settings: settings
        }, function(response) {
          if (response && response.success) {
            showStatus('Bot started successfully!', 'success');
            startButton.disabled = true;
            stopButton.disabled = false;
          } else {
            showStatus('Failed to start bot: ' + (response ? response.error : 'Unknown error'), 'error');
          }
        });
      });
    });
  
    // Stop button handler
    stopButton.addEventListener('click', function() {
      chrome.runtime.sendMessage({ action: 'stopBot' }, function(response) {
        if (response && response.success) {
          showStatus('Bot stopped successfully!', 'success');
          startButton.disabled = false;
          stopButton.disabled = true;
        } else {
          showStatus('Failed to stop bot', 'error');
        }
      });
    });
  
    function showStatus(message, type) {
      status.textContent = message;
      status.className = 'status ' + type;
      setTimeout(() => {
        status.className = 'status';
      }, 3000);
    }
  });