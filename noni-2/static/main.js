document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const symbolInput = document.getElementById('symbol-input');
    const useBtn = document.getElementById('use-btn');
    const positionDisplay = document.getElementById('position-display');
    const strikeInput = document.getElementById('strike-input');
    const expiryInput = document.getElementById('expiry-input');
    const callBidEl = document.getElementById('call-bid');
    const callAskEl = document.getElementById('call-ask');
    const callVolEl = document.getElementById('call-vol');
    const putBidEl = document.getElementById('put-bid');
    const putAskEl = document.getElementById('put-ask');
    const putVolEl = document.getElementById('put-vol');
    const cbPriceInput = document.getElementById('cb-price');
    const csPriceInput = document.getElementById('cs-price');
    const pbPriceInput = document.getElementById('pb-price');
    const psPriceInput = document.getElementById('ps-price');
    const cbBtn = document.getElementById('cb-btn');
    const csBtn = document.getElementById('cs-btn');
    const pbBtn = document.getElementById('pb-btn');
    const psBtn = document.getElementById('ps-btn');
    const statusDisplay = document.getElementById('status-display');
    const inProgressPositionDisplay = document.getElementById('in-progress-position-display');
    const cancelBtn = document.getElementById('cancel-btn');
    const priceScroller = document.getElementById('price-scroller');
    const fillsScroller = document.getElementById('fills-scroller');

    // --- State Management ---
    let accountHash = null;
    let positionPollInterval = null;
    let statusPollInterval = null;
    let quotePollInterval = null;
    let underlyingPricePollInterval = null;
    let recentFillsPollInterval = null;
    let activeOrder = null;
    let isOrderActive = false;

    // --- Function Declarations ---
    const enableControls = () => {
        useBtn.disabled = false;
        cancelBtn.disabled = false;
        cbBtn.disabled = false;
        csBtn.disabled = false;
        pbBtn.disabled = false;
        psBtn.disabled = false;
    };

    const fetchUnderlyingPrice = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        if (!symbol) return;
        try {
            const response = await fetch(`/api/underlying_price/${symbol}`);
            const data = await response.json();
            if (data.success) {
                const priceDiv = document.createElement('div');
                priceDiv.textContent = data.price.toFixed(2);
                priceScroller.insertBefore(priceDiv, priceScroller.firstChild);
            }
        } catch (error) {
            console.error('Error fetching underlying price:', error);
        }
    };

    const fetchRecentFills = async () => {
        if (!accountHash) return;
        try {
            const response = await fetch(`/api/recent_fills?account_hash=${accountHash}`);
            const data = await response.json();
            if (data.success && data.fills) {
                fillsScroller.innerHTML = ''; // Clear old fills
                data.fills.forEach(fill => {
                    const fillDiv = document.createElement('div');
                    fillDiv.textContent = fill;
                    fillsScroller.appendChild(fillDiv);
                });
            }
        } catch (error) {
            console.error('Error fetching recent fills:', error);
        }
    };

    const fetchAndSetDefaults = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        if (!symbol) return;
        try {
            const response = await fetch(`/api/defaults/${symbol}`);
            const data = await response.json();
            if (data.success) {
                strikeInput.value = data.strike;
                expiryInput.value = data.expiry;
                handleInputChange();
                if (underlyingPricePollInterval) clearInterval(underlyingPricePollInterval);
                fetchUnderlyingPrice();
                underlyingPricePollInterval = setInterval(fetchUnderlyingPrice, 2000);
            }
        } catch (error) {
            console.error('Error fetching defaults:', error);
        }
    };

    const fetchPositions = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        if (!symbol || !accountHash) return;
        try {
            const response = await fetch(`/api/positions/${symbol}?account_hash=${accountHash}`);
            const data = await response.json();
            if (data.success) {
                positionDisplay.textContent = data.display_text;
            } else {
                positionDisplay.textContent = 'Error';
            }
        } catch (error) {
            console.error('Error fetching positions:', error);
            positionDisplay.textContent = 'Error';
        }
    };

    const fetchQuoteAndInstrumentPosition = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (!symbol || !strike || !expiry || !accountHash) return;

        try {
            const response = await fetch(`/api/options/${symbol}/${strike}/${expiry}`);
            const data = await response.json();
            if (data.success) {
                const callMap = data.data.callExpDateMap;
                const putMap = data.data.putExpDateMap;
                const normalizedStrikeKey = parseFloat(strike).toFixed(1);
                const callData = callMap?.[Object.keys(callMap)[0]]?.[normalizedStrikeKey]?.[0];
                const putData = putMap?.[Object.keys(putMap)[0]]?.[normalizedStrikeKey]?.[0];
                if (callData) {
                    callBidEl.textContent = callData.bid.toFixed(2);
                    callAskEl.textContent = callData.ask.toFixed(2);
                    callVolEl.textContent = callData.totalVolume;
                    if (!isOrderActive) {
                        cbPriceInput.value = (callData.bid + 0.01).toFixed(2);
                        csPriceInput.value = (callData.ask - 0.01).toFixed(2);
                    }
                }
                if (putData) {
                    putBidEl.textContent = putData.bid.toFixed(2);
                    putAskEl.textContent = putData.ask.toFixed(2);
                    putVolEl.textContent = putData.totalVolume;
                    if (!isOrderActive) {
                        pbPriceInput.value = (putData.bid + 0.01).toFixed(2);
                        psPriceInput.value = (putData.ask - 0.01).toFixed(2);
                    }
                }
            } else {
                console.error("Error fetching options.");
            }
        } catch (error) {
            console.error('Error fetching options:', error);
        }

        try {
            const optionType = activeOrder?.option_type || (document.getElementById('cb-btn').disabled ? 'PUT' : 'CALL'); // Guess based on what's active
            const posResponse = await fetch(`/api/instrument_position?account_hash=${accountHash}&symbol=${symbol}&strike=${strike}&expiry=${expiry}&option_type=${optionType}`);
            const posData = await posResponse.json();
            if (posData.success) {
                const position = posData.quantity || 0;
                let putCallText = optionType[0];
                inProgressPositionDisplay.textContent = position !== 0 ? `${position > 0 ? '+' : ''}${position} ${putCallText}` : '0';
            }
        } catch(error) {
            console.error('Error fetching instrument position:', error);
        }
    };

    const handleInputChange = () => {
        if (quotePollInterval) clearInterval(quotePollInterval);
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (symbol && strike && expiry) {
            fetchQuoteAndInstrumentPosition();
            quotePollInterval = setInterval(fetchQuoteAndInstrumentPosition, 2000);
        }
    };

    const createOrderPlacementHandler = (action, optionType) => {
        return async () => {
            if (!accountHash) { statusDisplay.textContent = 'Account not loaded.'; return; }
            const priceInputId = `${optionType[0].toLowerCase()}${action.toLowerCase()}-price`;
            const priceInput = document.getElementById(priceInputId);
            const orderDetails = {
                account_id: accountHash,
                symbol: symbolInput.value.trim().toUpperCase(),
                option_type: optionType,
                expiration_date: expiryInput.value,
                strike_price: parseFloat(strikeInput.value),
                quantity: 1,
                simple_action: action,
                order_type: 'LIMIT',
                price: parseFloat(priceInput.value)
            };
            try {
                const response = await fetch('/api/order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'place_or_replace', order_details: orderDetails })
                });
                const data = await response.json();
                if (data.success) {
                    isOrderActive = true;
                    activeOrder = { ...orderDetails, side: data.trade_status, orderId: data.order_id };
                    statusDisplay.textContent = `${activeOrder.side} ${activeOrder.symbol} ${activeOrder.strike_price}${activeOrder.option_type[0]} @ ${activeOrder.price}`;
                    if (statusPollInterval) clearInterval(statusPollInterval);
                    statusPollInterval = setInterval(pollOrderStatus, 4000);
                } else {
                    statusDisplay.textContent = `Error: ${data.error}`;
                }
            } catch (error) {
                console.error('Error placing order:', error);
                statusDisplay.textContent = 'API Error.';
            }
        };
    };

    const handleCancel = async () => {
        if (!activeOrder || !accountHash) { statusDisplay.textContent = 'No active order.'; return; }
        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'cancel' })
            });
            const data = await response.json();
            if (data.success) {
                statusDisplay.textContent = 'Order Canceled. Idle';
                if (statusPollInterval) clearInterval(statusPollInterval);
                activeOrder = null;
                isOrderActive = false;
            } else {
                 statusDisplay.textContent = `Cancel Error: ${data.error}`;
            }
        } catch(error) {
            console.error('Error canceling order:', error);
            statusDisplay.textContent = 'API Error.';
        }
    };

    const pollOrderStatus = async () => {
        if (!activeOrder) { if (statusPollInterval) clearInterval(statusPollInterval); return; }
        try {
            const response = await fetch('/api/order_status');
            const data = await response.json();
            if (data.success) {
                const status = data.data.status;
                if (!status) return;
                const details = activeOrder;
                statusDisplay.textContent = `${status} ${details.side} ${details.symbol} ${details.strike_price}${details.option_type[0]} @ ${details.price}`;
                if (['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED'].includes(status)) {
                    if (statusPollInterval) clearInterval(statusPollInterval);
                    activeOrder = null;
                    isOrderActive = false;
                    if(status === 'FILLED') {
                        statusDisplay.textContent = `FILLED! Ready for next trade.`;
                        fetchPositions();
                        fetchRecentFills(); // Refresh fills on a fill
                    }
                }
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    };

    const init = async () => {
        try {
            const response = await fetch('/api/accounts');
            const data = await response.json();
            if (data.success) {
                accountHash = data.account_hash;
                enableControls();
                statusDisplay.textContent = 'Idle';
                fetchRecentFills(); // Fetch on load
                recentFillsPollInterval = setInterval(fetchRecentFills, 30000); // Poll every 30s
            } else {
                statusDisplay.textContent = `Error: ${data.error || 'Could not load account.'}`;
            }
        } catch (error) {
            statusDisplay.textContent = `Error: ${error.message || 'Backend not reachable.'}`;
        }
    };

    // --- Event Listeners ---
    document.querySelectorAll('.price-adjust-btn').forEach(button => {
        button.addEventListener('click', () => {
            const targetInput = document.getElementById(button.dataset.target);
            const amount = parseFloat(button.dataset.amount);
            if (targetInput) {
                const currentValue = parseFloat(targetInput.value) || 0;
                targetInput.value = (currentValue + amount).toFixed(2);
            }
        });
    });

    symbolInput.addEventListener('change', () => {
        if (quotePollInterval) clearInterval(quotePollInterval);
        if (underlyingPricePollInterval) clearInterval(underlyingPricePollInterval);
        priceScroller.innerHTML = '';
        fetchAndSetDefaults();
    });
    strikeInput.addEventListener('change', handleInputChange);
    expiryInput.addEventListener('change', handleInputChange);

    useBtn.addEventListener('click', fetchQuoteAndInstrumentPosition);
    cbBtn.addEventListener('click', createOrderPlacementHandler('B', 'CALL'));
    csBtn.addEventListener('click', createOrderPlacementHandler('S', 'CALL'));
    pbBtn.addEventListener('click', createOrderPlacementHandler('B', 'PUT'));
    psBtn.addEventListener('click', createOrderPlacementHandler('S', 'PUT'));
    cancelBtn.addEventListener('click', handleCancel);

    // --- Start the app ---
    init();
});
