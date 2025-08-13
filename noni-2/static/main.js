document.addEventListener('DOMContentLoaded', () => {

    const getAccountBtn = document.getElementById('get-account-btn');
    const accountHashEl = document.getElementById('account-hash');
    const symbolInput = document.getElementById('symbol-input');
    const getQuoteBtn = document.getElementById('get-quote-btn');
    const quoteDisplay = document.getElementById('quote-display');
    const positionsDisplay = document.getElementById('positions-display');
    const tradeEntryCard = document.getElementById('trade-entry-card');

    const strikeInput = document.getElementById('strike-input');
    const expiryInput = document.getElementById('expiry-input');
    const getOptionsBtn = document.getElementById('get-options-btn');
    const optionsDisplay = document.getElementById('options-display');
    const orderFormContainer = document.getElementById('order-form-container');

    const actionSelect = document.getElementById('action-select');
    const typeSelect = document.getElementById('type-select');
    const priceInput = document.getElementById('price-input');
    const placeOrderBtn = document.getElementById('place-order-btn');
    const activeTradesDisplay = document.getElementById('active-trades-display');

    let accountHash = null;

    // --- Event Listeners ---

    getAccountBtn.addEventListener('click', async () => {
        const response = await fetch('/api/accounts');
        const data = await response.json();
        if (data.success) {
            accountHash = data.account_hash;
            accountHashEl.textContent = accountHash;
        } else {
            accountHashEl.textContent = 'Error loading account.';
        }
    });

    getQuoteBtn.addEventListener('click', async () => {
        const symbol = symbolInput.value.trim();
        if (!symbol) {
            alert('Please enter a symbol.');
            return;
        }
        if (!accountHash) {
            alert('Please load account first.');
            return;
        }

        // Get Quote
        const quoteResponse = await fetch(`/api/quote/${symbol}`);
        const quoteData = await quoteResponse.json();
        if (quoteData.success) {
            quoteDisplay.innerHTML = `<p><strong>Quote for ${symbol.toUpperCase()}:</strong> ${quoteData.data}</p>`;
            tradeEntryCard.style.display = 'block';
        } else {
            quoteDisplay.innerHTML = `<p class="error">${quoteData.error}</p>`;
        }

        // Get Positions
        const positionsResponse = await fetch(`/api/positions/${symbol}?account_hash=${accountHash}`);
        const positionsData = await positionsResponse.json();
        if (positionsData.success) {
            positionsDisplay.innerHTML = `<p><strong>Positions:</strong> <pre>${JSON.stringify(positionsData.data, null, 2)}</pre></p>`;
        } else {
            positionsDisplay.innerHTML = `<p class="error">${positionsData.error}</p>`;
        }
    });

    getOptionsBtn.addEventListener('click', async () => {
        const symbol = symbolInput.value.trim();
        const strike = strikeInput.value.trim();
        const expiry = expiryInput.value.trim();

        if (!symbol || !strike || !expiry) {
            alert('Please provide symbol, strike, and expiry.');
            return;
        }

        const response = await fetch(`/api/options/${symbol}/${strike}/${expiry}`);
        const data = await response.json();
        if (data.success) {
            optionsDisplay.innerHTML = `<p><strong>Options:</strong> <pre>${JSON.stringify(data.data, null, 2)}</pre></p>`;
            orderFormContainer.style.display = 'block';
        } else {
            optionsDisplay.innerHTML = `<p class="error">${data.error}</p>`;
        }
    });

    placeOrderBtn.addEventListener('click', async () => {
        const symbol = symbolInput.value.trim();
        const strike = parseFloat(strikeInput.value.trim());
        const expiry = expiryInput.value.trim();
        const action = actionSelect.value;
        const type = typeSelect.value;
        const price = parseFloat(priceInput.value.trim());
        const quantity = 1; // Hardcoded for now

        if (!symbol || !strike || !expiry || !action || !type || !price) {
            alert('Please fill out all order details.');
            return;
        }

        // Determine side
        const side = (action === 'B') ? 'BUY_TO_OPEN' : 'SELL_TO_OPEN'; // Simplified

        const orderDetails = {
            account_id: accountHash,
            symbol: symbol,
            option_type: (type === 'C') ? 'CALL' : 'PUT',
            expiration_date: expiry,
            strike_price: strike,
            quantity: quantity,
            side: side,
            order_type: 'LIMIT',
            price: price
        };

        const response = await fetch('/api/order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_action: 'place', order_details: orderDetails })
        });

        const data = await response.json();
        if (data.success) {
            addTradeToDashboard(data.session_id, data.order_id, orderDetails);
        } else {
            alert(`Error placing order: ${data.error}`);
        }
    });

    function addTradeToDashboard(sessionId, orderId, orderDetails) {
        if (activeTradesDisplay.innerHTML.includes('No active trades')) {
            activeTradesDisplay.innerHTML = '';
        }

        const tradeDiv = document.createElement('div');
        tradeDiv.className = 'trade-item';
        tradeDiv.id = `trade-${sessionId}`;
        tradeDiv.innerHTML = `
            <h4>Order ID: ${orderId}</h4>
            <p><strong>Status:</strong> <span id="status-${orderId}">WORKING</span></p>
            <p>${orderDetails.side} ${orderDetails.quantity} ${orderDetails.symbol} ${orderDetails.option_type} @ ${orderDetails.price}</p>
            <button class="cancel-btn" data-order-id="${orderId}">Cancel</button>
        `;
        activeTradesDisplay.appendChild(tradeDiv);

        // Add event listener for the new cancel button
        tradeDiv.querySelector('.cancel-btn').addEventListener('click', async (e) => {
            const orderToCancel = e.target.dataset.orderId;
            const cancelResponse = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order_action: 'cancel', account_id: accountHash, order_id: orderToCancel })
            });
            const cancelData = await cancelResponse.json();
            if (cancelData.success) {
                document.getElementById(`status-${orderToCancel}`).textContent = 'CANCELED';
            } else {
                alert(`Error canceling order: ${cancelData.error}`);
            }
        });

        // Start polling for status
        pollOrderStatus(orderId);
    }

    function pollOrderStatus(orderId) {
        const interval = setInterval(async () => {
            if (!accountHash) return;

            const response = await fetch(`/api/order_status/${orderId}?account_hash=${accountHash}`);
            const data = await response.json();

            if (data.success) {
                const statusEl = document.getElementById(`status-${orderId}`);
                const currentStatus = data.data.status;
                if (statusEl) {
                    statusEl.textContent = currentStatus;
                    if (['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED'].includes(currentStatus)) {
                        clearInterval(interval); // Stop polling
                    }
                } else {
                     clearInterval(interval);
                }
            }
        }, 5000); // Poll every 5 seconds
    }
});
