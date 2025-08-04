// Guerilla the Gorilla - AI Chatbot with Revenue-Driving Features
document.addEventListener('DOMContentLoaded', function() {
  // Initialize elements
  const toggle = document.getElementById('guerilla-toggle');
  const chatContainer = document.querySelector('.guerilla-chat-container');
  const closeButton = document.getElementById('guerilla-close');
  const sendButton = document.getElementById('guerilla-send');
  const inputField = document.getElementById('guerilla-input');
  const messagesContainer = document.getElementById('guerilla-messages');
  const notification = document.getElementById('guerilla-notification');
  const initialSuggestion = document.getElementById('guerilla-initial-suggestion');
  const modal = document.getElementById('guerilla-product-modal');
  const modalClose = document.querySelector('.guerilla-modal-close');
  const modalBody = document.getElementById('guerilla-modal-body');
  
  // Open chat when toggle is clicked
  toggle.addEventListener('click', function() {
    chatContainer.style.display = 'flex';
    notification.style.display = 'none';
    toggle.classList.add('guerilla-breathing');
    
    // Track open in analytics
    trackEvent('guerilla_chat_open');
  });
  
  // Close chat when close button is clicked
  closeButton.addEventListener('click', function() {
    chatContainer.style.display = 'none';
    toggle.classList.remove('guerilla-breathing');
    
    // Track close in analytics
    trackEvent('guerilla_chat_close');
  });
  
  // Handle send button click
  sendButton.addEventListener('click', function() {
    sendMessage();
  });
  
  // Handle enter key press
  inputField.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      sendMessage();
    }
  });
  
  // Close modal when X is clicked
  modalClose.addEventListener('click', function() {
    modal.style.display = 'none';
  });
  
  // Close modal when clicking outside the modal content
  window.addEventListener('click', function(event) {
    if (event.target === modal) {
      modal.style.display = 'none';
    }
  });
  
  // Send user message and get response
  function sendMessage() {
    const message = inputField.value.trim();
    if (message === '') return;
    
    // Display user message
    appendMessage(message, 'outgoing');
    
    // Clear input field
    inputField.value = '';
    
    // Process message
    processMessage(message);
    
    // Track in analytics
    trackEvent('guerilla_chat_message', {
      message_text: message
    });
  }
  
  // Process user message and generate response
  async function processMessage(message) {
    // Show typing indicator
    appendTypingIndicator();
    
    try {
      const response = await fetch('/api/guerilla-chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: message })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();

      // Remove typing indicator
      removeTypingIndicator();
      
      // Display bot response
      appendMessage(data.response, 'incoming');
      
      // Display product recommendations if any
      if (data.recommendations && data.recommendations.length > 0) {
        setTimeout(() => {
          appendProductSuggestion(data.recommendations[0]);
        }, 1000);
      }
    } catch (error) {
      console.error('Error fetching AI response:', error);
      removeTypingIndicator();
      appendMessage('Sorry, something went wrong. Please try again.', 'incoming');
    }
  }
  
  // Append message to chat
  function appendMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `guerilla-message guerilla-${type}`;
    
    if (type === 'incoming') {
      // Bot message with avatar
      messageDiv.innerHTML = `
        <img src="${window.location.origin}/static/img/guerilla_mascot.png" class="guerilla-msg-avatar">
        <div class="guerilla-msg-content">
          <p>${message}</p>
        </div>
      `;
    } else {
      // User message
      messageDiv.innerHTML = `
        <div class="guerilla-msg-content">
          <p>${message}</p>
        </div>
      `;
    }
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
  }
  
  // Append typing indicator
  function appendTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'guerilla-message guerilla-incoming guerilla-typing';
    typingDiv.innerHTML = `
      <img src="${window.location.origin}/static/img/guerilla_mascot.png" class="guerilla-msg-avatar">
      <div class="guerilla-msg-content">
        <div class="guerilla-typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    `;
    messagesContainer.appendChild(typingDiv);
    scrollToBottom();
  }
  
  // Remove typing indicator
  function removeTypingIndicator() {
    const typingIndicator = document.querySelector('.guerilla-typing');
    if (typingIndicator) {
      typingIndicator.remove();
    }
  }
  
  // Append product suggestion
  function appendProductSuggestion(product) {
    const suggestionDiv = document.createElement('div');
    suggestionDiv.className = 'guerilla-message guerilla-incoming guerilla-product-suggestion';
    suggestionDiv.innerHTML = `
      <img src="${window.location.origin}/static/img/guerilla_mascot.png" class="guerilla-msg-avatar">
      <div class="guerilla-msg-content">
        <p>Here's what I personally use and recommend:</p>
        <div style="margin-top:10px; display:flex; gap:10px; align-items:center;">
          <img src="${product.image}" style="width:60px; height:60px; object-fit:contain; border-radius:5px;">
          <div>
            <strong>${product.name}</strong>
            <div>${product.price}</div>
          </div>
        </div>
        <div class="guerilla-suggestion-actions">
          <button class="guerilla-suggestion-btn" onclick="showProductRecommendation('${product.product_id}')">View Details</button>
          <button class="guerilla-suggestion-btn guerilla-suggestion-secondary">No Thanks</button>
        </div>
      </div>
    `;
    
    messagesContainer.appendChild(suggestionDiv);
    scrollToBottom();
    
    // Track in analytics
    trackEvent('guerilla_product_suggestion', {
      product_id: product.product_id,
      product_name: product.name
    });
  }
  
  // Scroll to bottom of chat
  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
  
  // Helper to generate random numbers
  function generateRandomNumber(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }
  
  // Track events in Google Analytics and/or other analytics tools
  function trackEvent(eventName, params = {}) {
    // Google Analytics
    if (typeof gtag !== 'undefined') {
      gtag('event', eventName, params);
    }
    
    // Microsoft Clarity (custom event)
    if (typeof clarity !== 'undefined') {
      clarity('set', eventName, params);
    }
    
    // Log to console in development
    console.log(`[Guerilla Analytics] ${eventName}`, params);
  }
  
  // Make these functions globally available
  window.showProductRecommendation = async function(productId) {
    try {
      const response = await fetch('/api/gear');
      const gearItems = await response.json();
      const product = gearItems.find(item => item.affiliate_id === productId);

      if (!product) return;

      // Build modal content
      modalBody.innerHTML = `
        <div class="guerilla-product-card">
          <div class="guerilla-product-header">
            <img src="${product.image}" class="guerilla-product-image">
            <div class="guerilla-product-info">
              <div>
                <h2 class="guerilla-product-title">${product.name}</h2>
                <div class="guerilla-product-badges">
                  ${product.badges.map(badge => `<span class="guerilla-badge">${badge}</span>`).join('')}
                </div>
                <div class="guerilla-product-price">
                  <span class="original">${product.old_price}</span>
                  <span class="discounted">${product.price}</span>
                </div>
              </div>

              <div class="guerilla-live-visitors">
                <span class="dot"></span>
                <span>${generateRandomNumber(3, 15)} people viewing this right now</span>
              </div>
            </div>
          </div>

          <p class="guerilla-product-desc">${product.description}</p>

          <div class="guerilla-buttons">
            <a href="/affiliate/${product.affiliate_id}" class="guerilla-buy-btn" target="_blank" rel="noopener"
               onclick="trackProductClick('${product.affiliate_id}')">
              GET THIS DEAL
            </a>
            <button class="guerilla-wishlist-btn">Save for Later</button>
          </div>

          <div class="guerilla-guarantee">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9 12L11 14L15 10M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>Only ${generateRandomNumber(1, 8)} left at this price</span>
          </div>
        </div>
      `;

      // Display modal
      modal.style.display = 'block';

      // Track in analytics
      trackEvent('guerilla_product_view', {
        product_id: productId,
        product_name: product.name
      });
    } catch (error) {
      console.error('Error fetching product details:', error);
    }
  };
  
  window.trackProductClick = function(productId) {
    // Track in analytics
    trackEvent('guerilla_product_click', {
      product_id: productId
    });

    // Also send to backend for tracking
    fetch('/api/affiliate-click', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId, source: 'chat' })
    });
  };
  
  window.userSendMessage = function(message) {
    // Display user message
    appendMessage(message, 'outgoing');
    
    // Process message
    processMessage(message);
    
    // Track in analytics
    trackEvent('guerilla_suggested_path_click', {
      message: message
    });
  };
  
  // Show a notification after 30 seconds if chat is not open
  setTimeout(() => {
    if (chatContainer.style.display !== 'flex') {
      notification.style.display = 'flex';
      toggle.classList.add('guerilla-breathing');
    }
  }, 30000);
});
