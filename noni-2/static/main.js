document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const symbolInput = document.getElementById('symbol-input');
    const useBtn = document.getElementById('use-btn');
    const positionDisplay = document.getElementById('position-display');
    const strikeInput = document.getElementById('strike-input');
    const expiryInput = document.getElementById('expiry-input');
    const getBtn = document.getElementById('get-btn');
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
    const cancelBtn = document.getElementById('cancel-btn');

    // --- State Management ---
    let accountHash = null;
    let positionPollInterval = null;
    let statusPollInterval = null;
    let activeOrder = null;

    // --- Function Declarations ---
    const enableControls = () => {
        useBtn.disabled = false;
        getBtn.disabled = false;
        cancelBtn.disabled = false;
        cbBtn.disabled = false;
        csBtn.disabled = false;
        pbBtn.disabled = false;
        psBtn.disabled = false;
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

    const fetchOptionQuotes = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (!symbol || !strike || !expiry) {
            statusDisplay.textContent = "Sym, Strike, Exp required.";
            return;
        }
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
                    cbPriceInput.value = (callData.bid + 0.01).toFixed(2);
                    csPriceInput.value = (callData.ask - 0.01).toFixed(2);
                }
                if (putData) {
                    putBidEl.textContent = putData.bid.toFixed(2);
                    putAskEl.textContent = putData.ask.toFixed(2);
                    putVolEl.textContent = putData.totalVolume;
                    pbPriceInput.value = (putData.bid + 0.01).toFixed(2);
                    psPriceInput.value = (putData.ask - 0.01).toFixed(2);
                }
            } else {
                statusDisplay.textContent = "Error fetching options.";
            }
        } catch (error) {
            console.error('Error fetching options:', error);
            statusDisplay.textContent = "API Error.";
        }
    };

    const handleOrderPlacement = async (action, optionType) => {
        if (!accountHash) {
            statusDisplay.textContent = 'Account not loaded.';
            return;
        }

        const priceInputId = `${optionType.toLowerCase()}${action.toLowerCase()}-price`;
        const priceInput = document.getElementById(priceInputId);

        const orderDetails = {
            account_id: accountHash,
            symbol: symbolInput.value.trim().toUpperCase(),
            option_type: optionType === 'C' ? 'CALL' : 'PUT',
            expiration_date: expiryInput.value,
            strike_price: parseFloat(strikeInput.value),
            quantity: 1,
            side: action === 'B' ? 'BUY_TO_OPEN' : 'SELL_TO_CLOSE', // Simplified logic for now
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
                statusDisplay.textContent = `${data.trade_status} ${orderDetails.symbol} ${orderDetails.strike_price}${orderDetails.option_type[0]} @ ${orderDetails.price}`;
                activeOrder = orderDetails;
                activeOrder.orderId = data.order_id;
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

    const handleCancel = async () => {
        if (!activeOrder || !accountHash) {
            statusDisplay.textContent = 'No active order to cancel.';
            return;
        }
        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'cancel' })
            });
            const data = await response.json();
            if (data.success) {
                statusDisplay.textContent = 'Order Canceled. Status: Idle';
                if (statusPollInterval) clearInterval(statusPollInterval);
                activeOrder = null;
            } else {
                 statusDisplay.textContent = `Cancel Error: ${data.error}`;
            }
        } catch(error) {
            console.error('Error canceling order:', error);
            statusDisplay.textContent = 'API Error.';
        }
    };

    const pollOrderStatus = async () => {
        if (!activeOrder) {
            if (statusPollInterval) clearInterval(statusPollInterval);
            return;
        }
        try {
            const response = await fetch('/api/order_status');
            const data = await response.json();
            if (data.success) {
                const status = data.data.status;
                if (!status) return;

                const details = activeOrder;
                statusDisplay.textContent = `${status} ${details.symbol} ${details.strike_price}${details.option_type[0]} @ ${details.price}`;

                if (['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED'].includes(status)) {
                    if (statusPollInterval) clearInterval(statusPollInterval);
                    activeOrder = null;
                    if(status === 'FILLED') {
                        statusDisplay.textContent = `FILLED! Ready for next trade.`;
                        fetchPositions();
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
            } else {
                statusDisplay.textContent = `Error: ${data.error || 'Could not load account.'}`;
            }
        } catch (error) {
            statusDisplay.textContent = `Error: ${error.message || 'Backend not reachable.'}`;
        }
    };

    // --- Event Listeners ---
    symbolInput.addEventListener('input', () => {
        if (symbolInput.value.length >= 2) {
             fetchAndSetDefaults();
        }
    });
    useBtn.addEventListener('click', () => {
        if (positionPollInterval) clearInterval(positionPollInterval);
        fetchPositions();
        positionPollInterval = setInterval(fetchPositions, 15000);
    });
    getBtn.addEventListener('click', fetchOptionQuotes);
    cbBtn.addEventListener('click', () => handleOrderPlacement('B', 'C'));
    csBtn.addEventListener('click', () => handleOrderPlacement('S', 'C'));
    pbBtn.addEventListener('click', () => handleOrderPlacement('B', 'P'));
    psBtn.addEventListener('click', () => handleOrderPlacement('S', 'P'));
    cancelBtn.addEventListener('click', handleCancel);

    // --- Start the app ---
    init();
});
