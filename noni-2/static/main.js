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
    const fillsScroller = document.getElementById('fills-scroller');

    // --- State Management ---
    let accountHash = null;
    let statusPollInterval = null;
    let quotePollInterval = null;
    let instrumentStatusInterval = null;
    let activeOrder = null; // For orders placed by the UI
    let isOrderActive = false; // Flag for when an order is placed by the UI
    let instrumentOrders = []; // For passively discovered orders

    // --- Helper Functions ---
    const logError = async (errorMessage) => {
        console.error(errorMessage); // Keep logging to console
        try {
            await fetch('/api/log_error', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: errorMessage })
            });
        } catch (e) {
            console.error("Failed to log error to backend:", e);
        }
    };

    const setStatus = (message, isError = false) => {
        statusDisplay.textContent = message;
        if (isError) {
            logError(message);
        }
    };

    // --- Core Functions ---
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
                fillsScroller.innerHTML = '';
                data.fills.forEach(fill => {
                    const fillDiv = document.createElement('div');
                    fillDiv.textContent = fill;
                    fillsScroller.appendChild(fillDiv);
                });
            }
        } catch (error) {
            logError(`Error fetching recent fills: ${error.message}`);
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
            } else {
                setStatus(`Error fetching defaults: ${data.error}`, true);
            }
        } catch (error) {
            setStatus(`API Error fetching defaults: ${error.message}`, true);
        }
    };

    const fetchPositions = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        if (!symbol || !accountHash) return;
        try {
            const response = await fetch(`/api/positions/${symbol}?account_hash=${accountHash}`);
            const data = await response.json();

            positionDisplay.innerHTML = ''; // Clear previous content

            if (data.success && data.positions) {
                if (data.positions.length === 0) {
                    positionDisplay.textContent = 'No Pos';
                    return;
                }

                // 1. Separate positions and calculate DTE for options
                const stockPosition = data.positions.find(p => p.asset_type === 'EQUITY');
                const options = data.positions.filter(p => p.asset_type === 'OPTION');

                options.forEach(opt => {
                    const expiryDate = new Date(opt.expiry + 'T00:00:00');
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    const diffTime = expiryDate - today;
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                    opt.dte = diffDays >= 0 ? diffDays + 1 : 0; // Ensure DTE is not negative
                });

                // 2. Sort option positions by DTE, then by strike
                options.sort((a, b) => {
                    if (a.dte !== b.dte) {
                        return a.dte - b.dte;
                    }
                    return a.strike - b.strike;
                });

                const callPositions = options.filter(p => p.put_call === 'CALL');
                const putPositions = options.filter(p => p.put_call === 'PUT');

                // 3. Handle stock position display
                if (stockPosition) {
                    const stockDiv = document.createElement('div');
                    stockDiv.className = 'stock-position-line';
                    stockDiv.textContent = `STOCK: ${parseInt(stockPosition.quantity)} @${stockPosition.average_price.toFixed(2)}`;
                    positionDisplay.appendChild(stockDiv);
                }

                // 4. Build two-column layout for options
                if (callPositions.length > 0 || putPositions.length > 0) {
                    const columnsContainer = document.createElement('div');
                    columnsContainer.className = 'option-columns-container';

                    const callColumn = document.createElement('div');
                    callColumn.className = 'position-column';
                    callPositions.forEach(pos => {
                        const posDiv = document.createElement('div');
                        posDiv.textContent = `${pos.quantity > 0 ? '+' : ''}${parseInt(pos.quantity)} C Strk:${pos.strike} dte:${pos.dte}`;
                        callColumn.appendChild(posDiv);
                    });

                    const putColumn = document.createElement('div');
                    putColumn.className = 'position-column';
                    putPositions.forEach(pos => {
                        const posDiv = document.createElement('div');
                        posDiv.textContent = `${pos.quantity > 0 ? '+' : ''}${parseInt(pos.quantity)} P Strk:${pos.strike} dte:${pos.dte}`;
                        putColumn.appendChild(posDiv);
                    });

                    columnsContainer.appendChild(callColumn);
                    columnsContainer.appendChild(putColumn);
                    positionDisplay.appendChild(columnsContainer);
                }
            } else {
                positionDisplay.textContent = data.error || 'Pos Error';
            }
        } catch (error) {
            logError(`Error fetching positions: ${error.message}`);
            positionDisplay.textContent = 'Pos Error';
        }
    };

    const fetchQuoteAndInstrumentPosition = async (forceUpdate = false) => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (!symbol || !strike || !expiry || !accountHash) return;

        try {
            const response = await fetch(`/api/options/${symbol}/${strike}/${expiry}`);
            const data = await response.json();
            if (data.success) {
                const callMap = data.data.callExpDateMap, putMap = data.data.putExpDateMap;
                const normalizedStrikeKey = parseFloat(strike).toFixed(1);
                const callData = callMap?.[Object.keys(callMap)[0]]?.[normalizedStrikeKey]?.[0];
                const putData = putMap?.[Object.keys(putMap)[0]]?.[normalizedStrikeKey]?.[0];
                if (callData) {
                    callBidEl.textContent = callData.bid.toFixed(2);
                    callAskEl.textContent = callData.ask.toFixed(2);
                    callVolEl.textContent = callData.totalVolume;
                    if (forceUpdate) {
                        cbPriceInput.value = (callData.bid + 0.01).toFixed(2);
                        csPriceInput.value = (callData.ask - 0.01).toFixed(2);
                    }
                }
                if (putData) {
                    putBidEl.textContent = putData.bid.toFixed(2);
                    putAskEl.textContent = putData.ask.toFixed(2);
                    putVolEl.textContent = putData.totalVolume;
                    if (forceUpdate) {
                        pbPriceInput.value = (putData.bid + 0.01).toFixed(2);
                        psPriceInput.value = (putData.ask - 0.01).toFixed(2);
                    }
                }
            }
        } catch (error) {
            logError(`Error fetching options: ${error.message}`);
        }

        try {
            const posResponse = await fetch(`/api/instrument_position?account_hash=${accountHash}&symbol=${symbol}&strike=${strike}&expiry=${expiry}`);
            const posData = await posResponse.json();
            if (posData.success) {
                const { call_quantity: callQty = 0, put_quantity: putQty = 0 } = posData;
                const formatPos = (qty) => qty > 0 ? `+${qty}` : qty;
                callPositionDisplay.textContent = `C:${formatPos(callQty)}`;
                putPositionDisplay.textContent = `P:${formatPos(putQty)}`;
                callPositionDisplay.classList.toggle('has-pos', callQty != 0);
                putPositionDisplay.classList.toggle('has-pos', putQty != 0);
            }
        } catch(error) {
            logError(`Error fetching instrument position: ${error.message}`);
        }
    };

    const updateBackendWatchlist = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;

        let instrumentPayload = null;
        if (symbol && strike && expiry) {
            instrumentPayload = {
                symbol: symbol,
                strike: parseFloat(strike),
                expiry: expiry
                // Note: We don't send option_type, as the backend will match
                // either a Call or a Put for the given instrument.
            };
        }

        try {
            await fetch('/api/set_interested_instrument', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    section_id: "section-1", // Hardcoded for the current single-section UI
                    instrument: instrumentPayload
                })
            });
        } catch (error) {
            logError(`Failed to update backend watchlist: ${error.message}`);
        }
    };

    const handleInputChange = () => {
        if (quotePollInterval) clearInterval(quotePollInterval);
        if (instrumentStatusInterval) clearInterval(instrumentStatusInterval);

        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (symbol && strike && expiry) {
            fetchQuoteAndInstrumentPosition(true);
            quotePollInterval = setInterval(fetchQuoteAndInstrumentPosition, 2000);

            // Start the new instrument poller
            pollInstrumentOrders();
            instrumentStatusInterval = setInterval(pollInstrumentOrders, 2000);
        }
        updateBackendWatchlist();
    };

    const pollInstrumentOrders = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;

        if (!symbol || !strike || !expiry || !accountHash || isOrderActive) {
            return; // Don't poll if inputs are empty or if we're actively tracking a just-placed order
        }

        try {
            const response = await fetch(`/api/get_instrument_orders?symbol=${symbol}&strike=${strike}&expiry=${expiry}`);
            const data = await response.json();
            if (data.success) {
                instrumentOrders = data.orders || [];
                updateStatusDisplay();
            } else {
                setStatus(data.error || 'Status Error', true);
            }
        } catch (error) {
            setStatus(`API Error polling orders: ${error.message}`, true);
        }
    };

    const updateStatusDisplay = () => {
        cancelBtn.disabled = instrumentOrders.length === 0 && !activeOrder;
        if (instrumentOrders.length === 0 && !isOrderActive) {
            setStatus('Idle');
            return;
        }

        // Sort to ensure consistent display order: Puts first, then by ID
        instrumentOrders.sort((a, b) => {
            if (a.type === 'PUT' && b.type !== 'PUT') return -1;
            if (a.type !== 'PUT' && b.type === 'PUT') return 1;
            return a.order_id - b.order_id;
        });

        const statusHTML = instrumentOrders.map(order =>
            `<span>${order.type} ${order.status} ${order.side} @ ${order.price.toFixed(2)}</span>`
        ).join('<br>');

        statusDisplay.innerHTML = statusHTML;
    };

    const placeOrder = async (orderDetails) => {
        if (instrumentStatusInterval) clearInterval(instrumentStatusInterval);
        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order_details: orderDetails })
            });
            const data = await response.json();
            if (data.success && data.order_id) {
                isOrderActive = true;
                activeOrder = { ...orderDetails, orderId: data.order_id };
                setStatus(`Placed ${activeOrder.side} ${activeOrder.symbol}`);
                if (statusPollInterval) clearInterval(statusPollInterval);
                statusPollInterval = setInterval(pollOrderStatus, 2000);
            } else {
                setStatus(`Error: ${data.error || 'Unknown placement error'}`, true);
                instrumentStatusInterval = setInterval(pollInstrumentOrders, 2000);
            }
        } catch (error) {
            setStatus(`API Error placing order: ${error.message}`, true);
        }
    };

    const handleCancel = async () => {
        // This function now handles three cases:
        // 1. A single order placed via the UI is active (`activeOrder`).
        // 2. A single passively discovered order is active (`instrumentOrders`).
        // 3. Multiple passively discovered orders are active.

        const ordersToCancel = activeOrder ? [activeOrder] : instrumentOrders;

        if (ordersToCancel.length === 0) {
            setStatus("No active order to cancel.", true);
            return;
        }

        if (ordersToCancel.length === 1) {
            // Direct cancel if only one order
            const order = ordersToCancel[0];
            const accountId = order.account_id || accountHash; // Use account_id from order if available
            const orderId = order.orderId || order.order_id; // Handle different key names

            if (!accountId || !orderId) {
                setStatus("Error: Missing account or order ID for cancellation.", true);
                return;
            }

            try {
                const response = await fetch('/api/cancel_order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ account_id: accountId, order_id: orderId })
                });
                const data = await response.json();
                if (data.success) {
                    setStatus('Canceled');
                    if (activeOrder) { // If it was a UI-placed order, clear the state
                        if (statusPollInterval) clearInterval(statusPollInterval);
                        activeOrder = null;
                        isOrderActive = false;
                        instrumentStatusInterval = setInterval(pollInstrumentOrders, 2000);
                    }
                    pollInstrumentOrders(); // Refresh status immediately
                } else {
                    setStatus(`Cancel Error: ${data.error}`, true);
                }
            } catch (error) {
                setStatus(`API Error canceling: ${error.message}`, true);
            }
        } else {
            // Show modal if there's a choice
            showCancelModal(ordersToCancel);
        }
    };

    const showCancelModal = (orders) => {
        // Remove existing modal if any
        const existingModal = document.querySelector('.modal-overlay');
        if (existingModal) existingModal.remove();

        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';

        // Create modal content
        const content = document.createElement('div');
        content.className = 'modal-content';
        content.innerHTML = '<h3>Choose Order to Cancel</h3>';

        orders.forEach(order => {
            const choiceDiv = document.createElement('div');
            choiceDiv.className = 'modal-order-choice';
            choiceDiv.innerHTML = `
                <strong>${order.type} ${order.side}</strong><br>
                Status: ${order.status}<br>
                Price: ${order.price.toFixed(2)}
            `;
            choiceDiv.addEventListener('click', () => {
                // Fake an `activeOrder` object for the direct cancel logic
                activeOrder = { orderId: order.order_id, account_id: order.account_id };
                handleCancel(); // This will now see a single `activeOrder`
                activeOrder = null; // Reset immediately after
                overlay.remove(); // Close modal
            });
            content.appendChild(choiceDiv);
        });

        // Add a close button/area
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.remove();
            }
        });

        overlay.appendChild(content);
        document.body.appendChild(overlay);
    };

    // This poller is now only for orders placed via the UI
    const pollOrderStatus = async () => {
        if (!activeOrder) { if (statusPollInterval) clearInterval(statusPollInterval); return; }
        try {
            const response = await fetch(`/api/order_status/${activeOrder.orderId}`);
            const data = await response.json();
            if (data.success) {
                const orderData = data.data;
                setStatus(`${orderData.status} ${activeOrder.side}`);
                if (['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED'].includes(orderData.status)) {
                    if (statusPollInterval) clearInterval(statusPollInterval);
                    activeOrder = null;
                    isOrderActive = false;
                    fetchPositions();
                    fetchRecentFills();
                    // Handoff: Restart the passive poller
                    instrumentStatusInterval = setInterval(pollInstrumentOrders, 2000);
                } else if (orderData.status === 'REPLACED') {
                    // Logic for handling replaced orders can be refined here
                    setStatus('REPLACED - Manual handling required for now.');
                    if (statusPollInterval) clearInterval(statusPollInterval);
                }
            }
        } catch (error) {
            logError(`Error polling status: ${error.message}`);
        }
    };

    const init = async () => {
        try {
            const response = await fetch('/api/accounts');
            const data = await response.json();
            if (data.success) {
                accountHash = data.account_hash;
                enableControls(true);
                setStatus('Idle');
                fetchRecentFills();
                setInterval(fetchRecentFills, 30000);
                setInterval(fetchPositions, 10000);

                // Heartbeat poller for state synchronization
                setInterval(async () => {
                    if (isOrderActive && activeOrder && activeOrder.orderId) {
                        try {
                            // Use the new order-specific endpoint for the heartbeat
                            const res = await fetch(`/api/has_active_orders?order_id=${activeOrder.orderId}`);
                            const syncData = await res.json();
                            // If the backend says it's no longer tracking the order, reset the UI
                            if (syncData.success && !syncData.has_active) {
                                setStatus('Order cleared externally. Resetting.', true);
                                if (statusPollInterval) clearInterval(statusPollInterval);
                                activeOrder = null;
                                isOrderActive = false;
                            }
                        } catch (e) {
                            logError(`Heartbeat poll failed: ${e.message}`);
                        }
                    }
                }, 30000); // Poll every 30 seconds

            } else {
                setStatus(`Error: ${data.error}`, true);
            }
        } catch (error) {
            setStatus(`Backend not reachable: ${error.message}`, true);
        }
    };

    // --- Event Listeners ---
    symbolInput.addEventListener('change', fetchAndSetDefaults);
    strikeInput.addEventListener('change', handleInputChange);
    expiryInput.addEventListener('change', handleInputChange);

    useBtn.addEventListener('click', async () => {
        // First, fetch the latest quotes immediately for the UI
        fetchQuoteAndInstrumentPosition(true);

        // Then, tell the backend to enter fast poll mode
        try {
            await fetch('/api/trigger_fast_poll', { method: 'POST' });
        } catch (error) {
            logError(`Failed to trigger fast poll: ${error.message}`);
        }
    });

    document.querySelectorAll('.order-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const [type, action] = e.target.id.split('-')[0];
            const optionType = type === 'c' ? 'CALL' : 'PUT';
            const simpleAction = action === 'b' ? 'B' : 'S';
            const priceInput = document.getElementById(`${type}${action}-price`);

            const symbol = symbolInput.value.trim().toUpperCase();
            const strike = strikeInput.value;
            const expiry = expiryInput.value;

            let currentQuantity = 0;
            try {
                const posResponse = await fetch(`/api/instrument_position?account_hash=${accountHash}&symbol=${symbol}&strike=${strike}&expiry=${expiry}`);
                const posData = await posResponse.json();
                if (posData.success) {
                    currentQuantity = optionType === 'CALL' ? posData.call_quantity : posData.put_quantity;
                } else {
                    setStatus('Error getting position.', true);
                    return;
                }
            } catch (error) {
                setStatus(`API Error getting position: ${error.message}`, true);
                return;
            }

            let side = '';
            if (simpleAction === 'B') {
                side = currentQuantity < 0 ? 'BUY_TO_CLOSE' : 'BUY_TO_OPEN';
            } else {
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
