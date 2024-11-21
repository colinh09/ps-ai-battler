let systemManager = null;

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'startBot') {
    // Here you would initialize your SystemManager
    // You'll need to create a bridge between your Python backend and this JS frontend
    // This could be done through a local server, native messaging, or other methods
    try {
      const settings = request.settings;
      
      // Example response - replace with actual implementation
      sendResponse({ success: true });
      
      // Keep the service worker alive
      return true;
    } catch (error) {
      sendResponse({ success: false, error: error.message });
      return true;
    }
  }
  
  if (request.action === 'stopBot') {
    try {
      // Stop the system manager
      systemManager = null;
      sendResponse({ success: true });
    } catch (error) {
      sendResponse({ success: false, error: error.message });
    }
    return true;
  }
});