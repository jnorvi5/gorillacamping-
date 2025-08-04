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
  
  // Product data will be fetched from the API
  let products = {};

  function loadProducts() {
    fetch('/api/gear')
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        // Transform the array of products into an object keyed by affiliate_id
        products = data.reduce((obj, item) => {
          // The frontend JS expects a `link` property, but the API provides `affiliate_id`
          // We also need to map other properties if their names differ.
          // For now, let's assume the structure is close enough.
          item.link = `/affiliate/${item.affiliate_id}`;
          obj[item.affiliate_id] = item;
          return obj;
        }, {});
        console.log("Products successfully loaded from API.");
      })
      .catch(error => {
        console.error('Error fetching gear data:', error);
        // As a fallback, you could load some default static data here
        appendMessage("I'm having trouble loading the latest gear recommendations. Please try again later.", 'incoming');
      });
  }

  // Load products when the script is executed
  loadProducts();
  
  let stripe;

  // --- Stripe and User Status Initialization ---
  function initializeApp() {
    fetch('/api/config')
      .then(response => response.json())
      .then(config => {
        stripe = Stripe(config.stripe_public_key);
      });

    fetch('/api/user/status')
      .then(response => response.json())
      .then(data => {
        updateUserStatusIndicator(data.tier);
      });
  }

  function updateUserStatusIndicator(tier) {
    const indicator = document.getElementById('user-status-indicator');
    if (indicator) {
      if (tier === 'premium') {
        indicator.textContent = "Inner Circle";
        indicator.className = "user-status premium";
      } else {
        indicator.textContent = "Free Tier";
        indicator.className = "user-status free";
      }
    }
  }

  initializeApp();

  // Keyword matching and revenue paths are now handled by the AI backend.
  
  // Open chat when toggle is clicked
  toggle.addEventListener('click', function() {
    chatContainer.style.display = 'flex';
    notification.style.display = 'none';
    toggle.classList.add('guerilla-breathing');
    
    // Show initial product suggestion after 10 seconds
    setTimeout(() => {
      if (initialSuggestion) {
        initialSuggestion.style.display = 'flex';
        scrollToBottom();
      }
    }, 10000);
    
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
  
  // Process user message and generate response from backend
  function processMessage(message) {
    // Show typing indicator
    appendTypingIndicator();

    fetch('/api/guerilla-chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        body: JSON.stringify({ message: message }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        removeTypingIndicator();
        if (data.upgrade_required) {
            appendUpgradeMessage(data.response);
        } else if (data.success) {
            appendMessage(data.response, 'incoming');
            if (data.recommendations && data.recommendations.length > 0) {
                // The backend can send multiple recommendations, let's show the first one.
                const recommendedProduct = data.recommendations[0];
                if (products[recommendedProduct.product_id]) {
                    setTimeout(() => {
                        appendProductSuggestion(recommendedProduct.product_id);
                    }, 500); // Add a slight delay for a more natural feel
                }
            }
        } else {
            appendMessage(data.error || "Sorry, something went wrong. Try again.", 'incoming');
        }
    })
    .catch(error => {
        removeTypingIndicator();
        console.error('Error calling chat API:', error);
        appendMessage("Sorry, I can't connect to my brain right now. Please try again later.", 'incoming');
    });
  }
  
  // Append message to chat
  function appendMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `guerilla-message guerilla-${type}`;
    
    if (type === 'incoming') {
      // Bot message with avatar
      messageDiv.innerHTML = `
        <img src="${window.location.origin}/static/images/guerilla-mascot.png" class="guerilla-msg-avatar">
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

  function appendUpgradeMessage(message) {
    const upgradeDiv = document.createElement('div');
    upgradeDiv.className = 'guerilla-message guerilla-incoming';
    upgradeDiv.innerHTML = `
      <img src="${window.location.origin}/static/images/guerilla-mascot.png" class="guerilla-msg-avatar">
      <div class="guerilla-msg-content">
        <p>${message}</p>
        <button class="guerilla-upgrade-btn" onclick="redirectToCheckout()">Upgrade to Inner Circle</button>
      </div>
    `;
    messagesContainer.appendChild(upgradeDiv);
    scrollToBottom();
  }

  function redirectToCheckout() {
    fetch('/api/create-checkout-session', {
      method: 'POST',
    })
    .then(response => response.json())
    .then(session => {
      if (session.id) {
        return stripe.redirectToCheckout({ sessionId: session.id });
      } else {
        throw new Error('Could not create checkout session.');
      }
    })
    .catch(error => {
      console.error('Error redirecting to checkout:', error);
      appendMessage("Sorry, I'm having trouble with the upgrade process. Please try again in a moment.", 'incoming');
    });
  }
  
  // Append typing indicator
  function appendTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'guerilla-message guerilla-incoming guerilla-typing';
    typingDiv.innerHTML = `
      <img src="${window.location.origin}/static/images/guerilla-mascot.png" class="guerilla-msg-avatar">
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
  function appendProductSuggestion(productId) {
    if (!products[productId]) return;
    
    const product = products[productId];
    const suggestionDiv = document.createElement('div');
    suggestionDiv.className = 'guerilla-message guerilla-incoming guerilla-product-suggestion';
    suggestionDiv.innerHTML = `
      <img src="${window.location.origin}/static/images/guerilla-mascot.png" class="guerilla-msg-avatar">
      <div class="guerilla-msg-content">
        <p>Here's what I personally use and recommend:</p>
        <div style="margin-top:10px; display:flex; gap:10px; align-items:center;">
          <img src="${product.image}" style="width:60px; height:60px; object-fit:contain; border-radius:5px;">
          <div>
            <strong>${product.name}</strong>
            <div>${product.price} <span style="text-decoration:line-through;color:#aaa;font-size:0.9em;">${product.originalPrice}</span></div>
          </div>
        </div>
        <div class="guerilla-suggestion-actions">
          <button class="guerilla-suggestion-btn" onclick="showProductRecommendation('${productId}')">View Details</button>
          <button class="guerilla-suggestion-btn guerilla-suggestion-secondary">No Thanks</button>
        </div>
      </div>
    `;
    
    messagesContainer.appendChild(suggestionDiv);
    scrollToBottom();
    
    // Track in analytics
    trackEvent('guerilla_product_suggestion', {
      product_id: productId,
      product_name: product.name
    });
  }
  
  // This function is no longer needed as the AI backend handles suggestions.
  
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
  window.showProductRecommendation = function(productId) {
    if (!products[productId]) return;
    
    const product = products[productId];
    
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
                <span class="original">${product.originalPrice}</span>
                <span class="discounted">${product.price}</span>
              </div>
            </div>
            
            <div class="guerilla-live-visitors">
              <span class="dot"></span>
              <span>${product.visitors} people viewing this right now</span>
            </div>
          </div>
        </div>
        
        <p class="guerilla-product-desc">${product.description}</p>
        
        <div class="guerilla-testimonial">
          ${product.testimonial}
        </div>
        
        <div class="guerilla-countdown">
          <span>Limited-time offer ends in:</span>
          <div class="guerilla-countdown-timer" id="product-countdown">23:59:59</div>
        </div>
        
        <div class="guerilla-buttons">
          <a href="${product.link}" class="guerilla-buy-btn" target="_blank" rel="noopener" 
             onclick="trackProductClick('${productId}')">
            GET THIS DEAL
          </a>
          <button class="guerilla-wishlist-btn">Save for Later</button>
        </div>
        
        <div class="guerilla-guarantee">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M9 12L11 14L15 10M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>Only ${product.inventory} left at this price</span>
        </div>
      </div>
    `;
    
    // Display modal
    modal.style.display = 'block';
    
    // Start countdown timer
    startProductCountdown();
    
    // Track in analytics
    trackEvent('guerilla_product_view', {
      product_id: productId,
      product_name: product.name
    });
  };
  
  window.trackProductClick = function(productId) {
    if (!products[productId]) return;
    
    // Track in analytics
    trackEvent('guerilla_product_click', {
      product_id: productId,
      product_name: products[productId].name,
      product_price: products[productId].price
    });
  };
  
  window.redirectToCheckout = redirectToCheckout;

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
  
  // Start product countdown
  function startProductCountdown() {
    const countdownEl = document.getElementById('product-countdown');
    if (!countdownEl) return;
    
    // Generate random hours (3-23) for urgency
    const hours = generateRandomNumber(3, 23);
    const minutes = generateRandomNumber(0, 59);
    const seconds = generateRandomNumber(0, 59);
    
    let totalSeconds = hours * 3600 + minutes * 60 + seconds;
    
    const interval = setInterval(() => {
      totalSeconds--;
      
      if (totalSeconds <= 0) {
        clearInterval(interval);
        countdownEl.textContent = "EXPIRED";
        return;
      }
      
      const h = Math.floor(totalSeconds / 3600);
      const m = Math.floor((totalSeconds % 3600) / 60);
      const s = totalSeconds % 60;
      
      countdownEl.textContent = 
        String(h).padStart(2, '0') + ':' +
        String(m).padStart(2, '0') + ':' +
        String(s).padStart(2, '0');
      
      // Add urgency effect when under 1 hour
      if (h < 1 && totalSeconds % 10 === 0) {
        countdownEl.style.fontSize = '20px';
        setTimeout(() => {
          countdownEl.style.fontSize = '18px';
        }, 500);
      }
    }, 1000);
  }
  
  // Show a notification after 30 seconds if chat is not open
  setTimeout(() => {
    if (chatContainer.style.display !== 'flex') {
      notification.style.display = 'flex';
      toggle.classList.add('guerilla-breathing');
    }
  }, 30000);
});
