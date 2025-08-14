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
    const callPositionDisplay = document.getElementById('call-position-display');
    const putPositionDisplay = document.getElementById('put-position-display');
    const cancelBtn = document.getElementById('cancel-btn');
    const priceScroller = document.getElementById('price-scroller');
    const fillsScroller = document.getElementById('fills-scroller');

    // --- State Management ---
    let accountHash = null;
    let statusPollInterval = null;
    let quotePollInterval = null;
    let activeOrder = null;
    let isOrderActive = false;

    // --- Function Declarations ---
    const enableControls = (state) => {
        useBtn.disabled = !state;
        cancelBtn.disabled = !state;
        cbBtn.disabled = !state;
        csBtn.disabled = !state;
        pbBtn.disabled = !state;
        psBtn.disabled = !state;
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

    const fetchQuoteAndInstrumentPosition = async (forceUpdate = false) => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (!symbol || !strike || !expiry || !accountHash) return;

        // Fetch Quote
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
                    if (!isOrderActive || forceUpdate) {
                        cbPriceInput.value = (callData.bid + 0.01).toFixed(2);
                        csPriceInput.value = (callData.ask - 0.01).toFixed(2);
                    }
                }
                if (putData) {
                    putBidEl.textContent = putData.bid.toFixed(2);
                    putAskEl.textContent = putData.ask.toFixed(2);
                    putVolEl.textContent = putData.totalVolume;
                    if (!isOrderActive || forceUpdate) {
                        pbPriceInput.value = (putData.bid + 0.01).toFixed(2);
                        psPriceInput.value = (putData.ask - 0.01).toFixed(2);
                    }
                }
            }
        } catch (error) {
            console.error('Error fetching options:', error);
        }

        // Fetch Positions for the specific instruments
        try {
            const posResponse = await fetch(`/api/instrument_position?account_hash=${accountHash}&symbol=${symbol}&strike=${strike}&expiry=${expiry}`);
            const posData = await posResponse.json();
            if (posData.success) {
                const callQty = posData.call_quantity || 0;
                const putQty = posData.put_quantity || 0;
                callPositionDisplay.textContent = `${callQty}C`;
                putPositionDisplay.textContent = `${putQty}P`;
                callPositionDisplay.classList.toggle('has-pos', callQty != 0);
                putPositionDisplay.classList.toggle('has-pos', putQty != 0);
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

    const placeOrder = async (orderDetails) => {
        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'place', order_details: orderDetails })
            });
            const data = await response.json();
            if (data.success) {
                isOrderActive = true;
                activeOrder = { ...orderDetails, orderId: data.order_id };
                statusDisplay.textContent = `Placed ${activeOrder.side} ${activeOrder.symbol}`;
                if (statusPollInterval) clearInterval(statusPollInterval);
                statusPollInterval = setInterval(pollOrderStatus, 2000);
            } else {
                statusDisplay.textContent = `Error: ${data.error}`;
            }
        } catch (error) {
            statusDisplay.textContent = 'API Error.';
        }
    };

    const handleCancel = async () => {
        if (!activeOrder || !accountHash) return;
        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'cancel' })
            });
            const data = await response.json();
            if (data.success) {
                statusDisplay.textContent = 'Canceled';
                if (statusPollInterval) clearInterval(statusPollInterval);
                activeOrder = null;
                isOrderActive = false;
            } else {
                 statusDisplay.textContent = `Cancel Error: ${data.error}`;
            }
        } catch(error) {
            statusDisplay.textContent = 'API Error.';
        }
    };

    const pollOrderStatus = async () => {
        if (!activeOrder) { if (statusPollInterval) clearInterval(statusPollInterval); return; }
        try {
            const response = await fetch('/api/order_status');
            const data = await response.json();
            if (data.success) {
                const orderData = data.data;
                statusDisplay.textContent = `${orderData.status} ${activeOrder.side}`;
                if (['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED'].includes(orderData.status)) {
                    if (statusPollInterval) clearInterval(statusPollInterval);
                    activeOrder = null;
                    isOrderActive = false;
                    fetchPositions();
                    fetchRecentFills();
                } else if (orderData.status === 'REPLACED') {
                    const replacementResponse = await fetch('/api/find_replacement_order', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ account_hash: accountHash, original_order: activeOrder })
                    });
                    const replacementData = await replacementResponse.json();
                    if (replacementData.success) {
                        const newOrder = replacementData.replacement_order;
                        activeOrder.orderId = newOrder.orderId;
                        activeOrder.price = newOrder.price;
                        statusDisplay.textContent = `REPLACED. New order ${newOrder.orderId}`;
                    } else {
                        statusDisplay.textContent = `REPLACED, but error finding new: ${replacementData.error}`;
                        if (statusPollInterval) clearInterval(statusPollInterval);
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
                enableControls(true);
                statusDisplay.textContent = 'Idle';
                fetchRecentFills();
                setInterval(fetchRecentFills, 30000);
                setInterval(fetchPositions, 10000);
            } else {
                statusDisplay.textContent = `Error: ${data.error}`;
            }
        } catch (error) {
            statusDisplay.textContent = 'Backend not reachable.';
        }
    };

    // --- Event Listeners ---
    symbolInput.addEventListener('change', fetchAndSetDefaults);
    strikeInput.addEventListener('change', handleInputChange);
    expiryInput.addEventListener('change', handleInputChange);
    useBtn.addEventListener('click', () => fetchQuoteAndInstrumentPosition(true));

    document.querySelectorAll('.order-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const [type, action] = e.target.id.split('-')[0]; // cb -> c, b
            const optionType = type === 'c' ? 'CALL' : 'PUT';
            const simpleAction = action === 'b' ? 'B' : 'S';
            const priceInput = document.getElementById(`${type}${action}-price`);

            const symbol = symbolInput.value.trim().toUpperCase();
            const strike = strikeInput.value;
            const expiry = expiryInput.value;

            // First, get the current position for this specific instrument
            let currentQuantity = 0;
            try {
                const posResponse = await fetch(`/api/instrument_position?account_hash=${accountHash}&symbol=${symbol}&strike=${strike}&expiry=${expiry}`);
                const posData = await posResponse.json();
                if (posData.success) {
                    currentQuantity = optionType === 'CALL' ? posData.call_quantity : posData.put_quantity;
                } else {
                    statusDisplay.textContent = 'Error getting position.';
                    return;
                }
            } catch (error) {
                statusDisplay.textContent = 'API Error getting position.';
                return;
            }

            // Now, determine the correct side
            let side = '';
            if (simpleAction === 'B') {
                side = currentQuantity < 0 ? 'BUY_TO_CLOSE' : 'BUY_TO_OPEN';
            } else { // 'S'
                side = currentQuantity > 0 ? 'SELL_TO_CLOSE' : 'SELL_TO_OPEN';
            }

            const orderDetails = {
                account_id: accountHash,
                symbol: symbol,
                option_type: optionType,
                expiration_date: expiry,
                strike_price: parseFloat(strike),
                quantity: 1,
                side: side,
                order_type: 'LIMIT',
                price: parseFloat(priceInput.value)
            };

            placeOrder(orderDetails);
        });
    });

    cancelBtn.addEventListener('click', handleCancel);

    // --- Start the app ---
    init();
});
