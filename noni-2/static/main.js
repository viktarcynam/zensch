document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const symbolInput = document.getElementById('symbol-input');
    const useBtn = document.getElementById('use-btn');
    const positionDisplay = document.getElementById('position-display');
    const strikeInput = document.getElementById('strike-input');
    const expiryInput = document.getElementById('expiry-input');
    const dteInput = document.getElementById('dte-input');
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
    const quantityInput = document.getElementById('quantity-input');
    const statusDisplay = document.getElementById('status-display');
    const callPositionDisplay = document.getElementById('call-position-display');
    const putPositionDisplay = document.getElementById('put-position-display');
    const cancelBtn = document.getElementById('cancel-btn');
    const fillsScroller = document.getElementById('fills-scroller');
    const workingOrdersScroller = document.getElementById('working-orders-scroller');
    const currentPriceEl = document.getElementById('current-price');
    const errorLogContainer = document.getElementById('error-log-container');
    const errorLogHeader = document.getElementById('error-log-header');
    const errorLogContent = document.getElementById('error-log-content');
    const errorLogToggleIcon = document.getElementById('error-log-toggle-icon');
    const percentageTicker = document.getElementById('percentage-ticker');

    // --- State Management ---
    let accountHash = null;
    let quotePollInterval = null;
    let instrumentStatusInterval = null;
    let instrumentOrders = []; // The single source of truth for active orders for the current instrument.
    let strikeInputOriginalValue = ''; // Store strike value before clearing for datalist display
    let priceHistory = []; // Array to store price history for the current instrument
    let accumValue = 0;
    let accumHistory = [];
    let rsiHistory = [];
    let rsiDailyHistory = [];

    // --- MOCK DATA GENERATOR (for testing without live data) ---
    let mockPrice = null;
    let mockDataCounter = 0;
    const generateMockData = () => {
        if (mockPrice === null) {
            mockPrice = parseFloat(strikeInput.value) || 100;
        }

        mockDataCounter = (mockDataCounter + 1) % 400;
        let percentageChange = 0;

        if (mockDataCounter < 100) { // Phase 1: Random +/- 0.02%
            percentageChange = (Math.random() - 0.5) * 2 * 0.0002; // -0.0002 to +0.0002
        } else if (mockDataCounter < 200) { // Phase 2: Increasing bias +0.01% to +0.05%
            percentageChange = (0.0001 + Math.random() * 0.0004);
        } else if (mockDataCounter < 300) { // Phase 3: Decreasing bias -0.01% to -0.05%
            percentageChange = -(0.0001 + Math.random() * 0.0004);
        } else { // Phase 4: Random +/- 0.02%
            percentageChange = (Math.random() - 0.5) * 2 * 0.0002;
        }

        mockPrice *= (1 + percentageChange);

        // Return a mock object that mimics the real API response structure
        return Promise.resolve({
            success: true,
            data: {
                underlying: { last: mockPrice },
                callExpDateMap: {}, // Provide empty objects to prevent errors
                putExpDateMap: {}
            }
        });
    };
    // --- END MOCK DATA ---

    const addPercentageToTicker = (percentageChange) => {
        if (isNaN(percentageChange)) return;

        const item = document.createElement('span');
        item.className = 'pct-item';

        const value = Math.abs(percentageChange);
        item.textContent = `${value.toFixed(1)}%`;

        if (percentageChange > 0) {
            item.classList.add('pct-green');
        } else if (percentageChange < 0) {
            item.classList.add('pct-red');
        }

        percentageTicker.appendChild(item);

        // Keep the DOM from getting too large
        while (percentageTicker.children.length > 500) {
            percentageTicker.removeChild(percentageTicker.firstChild);
        }

        // Scroll to the end
        percentageTicker.parentElement.scrollLeft = percentageTicker.parentElement.scrollWidth;
    };

    const calculateRSI = (prices, period = 14) => {
        if (prices.length <= period) return [];

        let gains = [];
        let losses = [];
        let rsiValues = [];

        // Calculate initial changes
        for (let i = 1; i <= period; i++) {
            const change = prices[i] - prices[i - 1];
            if (change > 0) {
                gains.push(change);
                losses.push(0);
            } else {
                gains.push(0);
                losses.push(Math.abs(change));
            }
        }

        let avgGain = gains.reduce((a, b) => a + b, 0) / period;
        let avgLoss = losses.reduce((a, b) => a + b, 0) / period;

        let rs = avgLoss === 0 ? Infinity : avgGain / avgLoss;
        rsiValues.push(100 - (100 / (1 + rs)));

        // Calculate subsequent RSI values
        for (let i = period + 1; i < prices.length; i++) {
            const change = prices[i] - prices[i - 1];
            let gain = change > 0 ? change : 0;
            let loss = change < 0 ? Math.abs(change) : 0;

            avgGain = (avgGain * (period - 1) + gain) / period;
            avgLoss = (avgLoss * (period - 1) + loss) / period;

            rs = avgLoss === 0 ? Infinity : avgGain / avgLoss;
            rsiValues.push(100 - (100 / (1 + rs)));
        }

        return rsiValues;
    };


    const drawRsiDailyChart = () => {
        const canvas = document.getElementById('rsi-daily-chart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (rsiDailyHistory.length < 2) return;

        const mapY = (val) => canvas.height - (val / 100) * canvas.height;
        const mapX = (index) => (index / (rsiDailyHistory.length - 1)) * canvas.width;

        // Draw reference lines at 30 and 70
        [30, 70].forEach(level => {
            const y = mapY(level);
            ctx.beginPath();
            ctx.strokeStyle = '#8B4513'; // A more visible saddle brown color
            ctx.setLineDash([2, 2]);
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        });
        ctx.setLineDash([]);

        // Draw RSI line
        ctx.beginPath();
        ctx.strokeStyle = '#FFD700'; // Gold color for daily RSI
        ctx.lineWidth = 1.5;
        rsiDailyHistory.forEach((point, index) => {
            const x = mapX(index);
            const y = mapY(point);
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    };

    const drawRsiChart = () => {
        const canvas = document.getElementById('rsi-chart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (rsiHistory.length < 2) return;

        const mapY = (val) => canvas.height - (val / 100) * canvas.height;
        const mapX = (index) => (index / (rsiHistory.length - 1)) * canvas.width;

        // Draw reference lines at 30 and 70
        [30, 70].forEach(level => {
            const y = mapY(level);
            ctx.beginPath();
            ctx.strokeStyle = '#8B4513'; // A more visible saddle brown color
            ctx.setLineDash([2, 2]);
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        });
        ctx.setLineDash([]);

        // Draw RSI line
        ctx.beginPath();
        ctx.strokeStyle = '#d8a0ff'; // Purple color
        ctx.lineWidth = 1.5;
        rsiHistory.forEach((point, index) => {
            const x = mapX(index);
            const y = mapY(point);
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    };


    const drawAccumChart = () => {
        const canvas = document.getElementById('accum-chart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        // Ensure canvas is sized correctly to avoid distortion
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (accumHistory.length < 2) return;

        const visibleData = accumHistory.slice(-200); // Draw last 200 points

        const minVal = Math.min(...visibleData);
        const maxVal = Math.max(...visibleData);
        const range = Math.max(maxVal - minVal, 0.1); // Avoid division by zero

        const mapY = (val) => {
            // y=0 in canvas is top, so we flip it
            return canvas.height - ((val - minVal) / range) * canvas.height;
        };

        const mapX = (index) => {
            return (index / (visibleData.length - 1)) * canvas.width;
        };

        // Draw the y=0 reference line
        const yZero = mapY(0);
        if (yZero >= 0 && yZero <= canvas.height) { // Only draw if visible
            ctx.beginPath();
            ctx.strokeStyle = '#8B4513'; // A more visible saddle brown color
            ctx.setLineDash([2, 2]); // Dashed line
            ctx.moveTo(0, yZero);
            ctx.lineTo(canvas.width, yZero);
            ctx.stroke();
            ctx.setLineDash([]); // Reset dash
        }

        // Draw the accum line
        ctx.beginPath();
        ctx.strokeStyle = '#68d2ff'; // Light blue color
        ctx.lineWidth = 1.5;

        visibleData.forEach((point, index) => {
            const x = mapX(index);
            const y = mapY(point);
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();
    };


    // --- Helper Functions ---
    const logErrorToUI = (message) => {
        const now = new Date();
        const timestamp = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-log-message';
        errorDiv.textContent = `[${timestamp}] ${message}`;
        errorLogContent.insertBefore(errorDiv, errorLogContent.firstChild);
        if (errorLogContainer.classList.contains('collapsed')) {
             errorLogContainer.classList.remove('collapsed');
             errorLogToggleIcon.textContent = '[-]';
        }
    };

    const logError = async (errorMessage) => {
        console.error(errorMessage);
        logErrorToUI(errorMessage); // Log to our new UI element
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
        statusDisplay.innerHTML = message; // Use innerHTML to allow for <br> tags
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
                    const expiryDate = new Date(fill.expiry + 'T00:00:00');
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    const diffTime = expiryDate - today;
                    const dte = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                    const fillString =
                        `${fill.quantity > 0 ? '+' : ''}${fill.quantity} ${fill.putCall} ${fill.symbol} ` +
                        `strk:${fill.strike} dte:${dte} ${fill.price.toFixed(2)}`;
                    const fillDiv = document.createElement('div');
                    fillDiv.className = 'fill-item';
                    fillDiv.textContent = fillString;

                    fillDiv.addEventListener('click', () => showCloseOrderModal(fill, fillDiv));
                    fillsScroller.appendChild(fillDiv);
                });
            }
        } catch (error) {
            logError(`Error fetching recent fills: ${error.message}`);
        }
    };

    const fetchWorkingOrders = async () => {
        if (!accountHash) return;
        try {
            const response = await fetch(`/api/working_orders?account_hash=${accountHash}`);
            const data = await response.json();
            if (data.success && data.orders) {
                workingOrdersScroller.innerHTML = '';
                data.orders.forEach(order => {
                    // The 'order' object here is the flattened, standardized object from the cache
                    const expiryDate = new Date(order.expiration_date + 'T00:00:00');
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    const dte = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));
                    const orderString = `${order.side.split('_')[0]} ${order.quantity} ${order.symbol} ${order.strike_price} ${order.option_type[0]} DTE:${dte} @ ${order.price.toFixed(2)}`;
                    const orderDiv = document.createElement('div');
                    orderDiv.className = 'working-order-item';
                    orderDiv.textContent = orderString;
                    orderDiv.addEventListener('click', () => showWorkingOrderModal(order, orderDiv));
                    workingOrdersScroller.appendChild(orderDiv);
                });
            }
        } catch (error) {
            logError(`Error fetching working orders: ${error.message}`);
        }
    };

    const fetchStrikes = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const expiry = expiryInput.value;
        const strikeList = document.getElementById('strike-list');

        // Clear previous results and state
        strikeList.innerHTML = '';
        strikeInput.value = '';
        strikeInput.placeholder = "Loading...";

        if (!symbol || !expiry) {
            strikeInput.placeholder = "Strike";
            return;
        }

        try {
            const response = await fetch(`/api/strikes/${symbol}/${expiry}`);
            const data = await response.json();

            if (data.success && data.strikes && data.strikes.length > 0) {
                // Populate the datalist with strike options
                data.strikes.forEach(strike => {
                    const option = document.createElement('option');
                    option.value = strike;
                    strikeList.appendChild(option);
                });

                // Find and set the closest strike as the default value in the input
                const underlyingPrice = data.underlying_price;
                if (underlyingPrice) {
                    const closestStrike = data.strikes.reduce((prev, curr) => {
                        return (Math.abs(curr - underlyingPrice) < Math.abs(prev - underlyingPrice) ? curr : prev);
                    });
                    strikeInput.value = closestStrike;
                } else if (data.strikes.length > 0) {
                    // Fallback if no price is returned: use the middle strike
                    strikeInput.value = data.strikes[Math.floor(data.strikes.length / 2)];
                }

                // Trigger quote fetch for the new default strike
                handleInputChange();
            } else {
                strikeInput.placeholder = data.error || "No strikes";
            }
        } catch (error) {
            logError(`Error fetching strikes: ${error.message}`);
            strikeInput.placeholder = "Error";
        }
    };

    const fetchAndSetDefaults = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        if (!symbol) return;
        try {
            const response = await fetch(`/api/defaults/${symbol}`);
            const data = await response.json();
            if (data.success) {
                // Set the default expiry, then fetch the strike list
                expiryInput.value = data.expiry;
                await fetchStrikes();
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
            positionDisplay.innerHTML = '';
            if (data.success && data.positions) {
                if (data.positions.length === 0) {
                    positionDisplay.textContent = 'No Pos';
                    return;
                }
                const stockPosition = data.positions.find(p => p.asset_type === 'EQUITY');
                const options = data.positions.filter(p => p.asset_type === 'OPTION');
                options.forEach(opt => {
                    const expiryDate = new Date(opt.expiry + 'T00:00:00');
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    const diffTime = expiryDate - today;
                    opt.dte = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
                });
                options.sort((a, b) => (a.dte !== b.dte) ? a.dte - b.dte : a.strike - b.strike);
                const callPositions = options.filter(p => p.put_call === 'CALL');
                const putPositions = options.filter(p => p.put_call === 'PUT');
                if (stockPosition) {
                    const stockDiv = document.createElement('div');
                    stockDiv.className = 'stock-position-line';
                    stockDiv.textContent = `STOCK: ${parseInt(stockPosition.quantity)} @${stockPosition.average_price.toFixed(2)}`;
                    positionDisplay.appendChild(stockDiv);
                }
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
            // --- MOCK DATA ACTIVATION ---
            const responsePromise = generateMockData();
            // const responsePromise = fetch(`/api/options/${symbol}/${strike}/${expiry}`).then(res => res.json());
            // --- END MOCK DATA ACTIVATION ---

            const data = await responsePromise;

            if (data.success) {
                if (data.data.underlying && data.data.underlying.last) {
                    const currentPrice = data.data.underlying.last;
                    currentPriceEl.textContent = currentPrice.toFixed(2);

                    // Add to price history and manage its size
                    priceHistory.push(currentPrice);
                    if (priceHistory.length > 9000) {
                        priceHistory.shift(); // Remove the oldest entry
                    }

                    // --- ACCUM and Percentage Ticker CALCULATION ---
                    if (priceHistory.length >= 2) {
                        const previousPrice = priceHistory[priceHistory.length - 2];
                        const delta = currentPrice - previousPrice;
                        accumValue += delta;

                        if (previousPrice !== 0) {
                            const percentageChange = (delta / previousPrice) * 100;
                            addPercentageToTicker(percentageChange);
                        }
                    }
                    accumHistory.push(accumValue);
                    if (accumHistory.length > 200) {
                        accumHistory.shift();
                    }
                    drawAccumChart();
                    // --- END ACCUM CALCULATION ---
                }
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

                // Highlight the closing action button
                [cbBtn, csBtn, pbBtn, psBtn].forEach(btn => btn.classList.remove('closing-action-btn'));
                if (callQty > 0) csBtn.classList.add('closing-action-btn');
                else if (callQty < 0) cbBtn.classList.add('closing-action-btn');
                if (putQty > 0) psBtn.classList.add('closing-action-btn');
                else if (putQty < 0) pbBtn.classList.add('closing-action-btn');
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
            };
        }
        try {
            await fetch('/api/set_interested_instrument', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    section_id: "section-1",
                    instrument: instrumentPayload
                })
            });
        } catch (error) {
            logError(`Failed to update backend watchlist: ${error.message}`);
        }
    };

    const pollInstrumentOrders = async () => {
        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (!symbol || !strike || !expiry || !accountHash) return;
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
        cancelBtn.disabled = instrumentOrders.length === 0;
        if (instrumentOrders.length === 0) {
            setStatus('Idle');
            return;
        }
        instrumentOrders.sort((a, b) => {
            if (a.type === 'PUT' && b.type !== 'PUT') return -1;
            if (a.type !== 'PUT' && b.type === 'PUT') return 1;
            return a.order_id - b.order_id;
        });
        const statusHTML = instrumentOrders.map(order =>
            `<span>${order.type} ${order.status} ${order.side} @ ${order.price ? order.price.toFixed(2) : 'N/A'}</span>`
        ).join('<br>');
        setStatus(statusHTML);
    };

    const fetchHistoryAndDrawCharts = async (symbol) => {
        let attempts = 0;
        const maxAttempts = 5;
        const interval = 2000; // 2 seconds

        const attemptFetch = async () => {
            if (attempts >= maxAttempts) {
                logError(`Failed to fetch history for ${symbol} after ${maxAttempts} attempts.`);
                return;
            }
            attempts++;

            try {
                const response = await fetch(`/api/get_history/${symbol}`);
                if (response.status === 404) {
                    // Data not ready, try again
                    setTimeout(attemptFetch, interval);
                    return;
                }
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const result = await response.json();

                if (result.success) {
                    // Process 30-minute data for the first RSI chart
                    if (result.data.data.data_30m && result.data.data.data_30m.candles) {
                        const prices30m = result.data.data.data_30m.candles.map(c => c.close);
                        rsiHistory = calculateRSI(prices30m);
                        drawRsiChart();
                    } else {
                        logError(`Could not process 30m history for ${symbol}.`);
                        rsiHistory = [];
                        drawRsiChart();
                    }

                    // Process daily data for the second RSI chart
                    if (result.data.data.data_daily && result.data.data.data_daily.candles) {
                        const pricesDaily = result.data.data.data_daily.candles.map(c => c.close);
                        rsiDailyHistory = calculateRSI(pricesDaily);
                        drawRsiDailyChart();
                    } else {
                        logError(`Could not process daily history for ${symbol}.`);
                        rsiDailyHistory = [];
                        drawRsiDailyChart();
                    }
                } else {
                     logError(`get_history API call failed for ${symbol}: ${result.error}`);
                }
            } catch (error) {
                logError(`Error in fetchHistoryAndDrawCharts for ${symbol}: ${error.message}`);
                setTimeout(attemptFetch, interval); // Retry on network error
            }
        };

        await attemptFetch();
    };

    const handleInputChange = () => {
        if (quotePollInterval) clearInterval(quotePollInterval);
        if (instrumentStatusInterval) clearInterval(instrumentStatusInterval);

        // Clear history and reset display for the new instrument
        priceHistory = [];
        accumValue = 0;
        accumHistory = [];
        rsiHistory = [];
        rsiDailyHistory = [];
        mockPrice = null; // Reset mock price for new instrument
        mockDataCounter = 0;
        currentPriceEl.textContent = '-.--';
        if(percentageTicker) percentageTicker.innerHTML = '';
        drawAccumChart(); // Clear the canvas
        drawRsiChart(); // Clear the canvas
        drawRsiDailyChart(); // Clear the canvas

        const symbol = symbolInput.value.trim().toUpperCase();
        const strike = strikeInput.value;
        const expiry = expiryInput.value;
        if (symbol && strike && expiry) {
            fetchQuoteAndInstrumentPosition(true);
            quotePollInterval = setInterval(fetchQuoteAndInstrumentPosition, 2000);
            pollInstrumentOrders();
            instrumentStatusInterval = setInterval(pollInstrumentOrders, 2000);

            // Fire-and-forget request to cache historical data on the server
            fetch(`/api/request_history/${symbol}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log(`History request for ${symbol} sent. Status: ${data.status}`);
                        // If data is already cached, fetch it immediately. Otherwise, start polling.
                        if (data.status === 'CACHED') {
                            fetchHistoryAndDrawCharts(symbol);
                        } else {
                             setTimeout(() => fetchHistoryAndDrawCharts(symbol), 2000); // Wait a bit before first attempt
                        }
                    } else {
                        logError(`History request for ${symbol} failed: ${data.error}`);
                    }
                }).catch(err => {
                    logError(`History request for ${symbol} failed: ${err.message}`);
                });
        }
        updateBackendWatchlist();
    };

    const placeOrder = async (orderDetails) => {
        setStatus(`Placing ${orderDetails.side}...`);
        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order_details: orderDetails })
            });
            const data = await response.json();
            if (data.success) {
                setStatus('Placed. Waiting for status...');
                pollInstrumentOrders();
            } else {
                setStatus(`Error: ${data.error || 'Unknown placement error'}`, true);
            }
        } catch (error) {
            setStatus(`API Error placing order: ${error.message}`, true);
        }
    };

    const handleCancel = async (orderToCancel) => {
        if (!orderToCancel && instrumentOrders.length > 1) {
            showCancelModal(instrumentOrders);
            return;
        }
        const order = orderToCancel || instrumentOrders[0];
        if (!order) {
            setStatus("No active order to cancel.", true);
            return;
        }
        const accountId = order.account_id || accountHash;
        const orderId = order.order_id;
        try {
            const response = await fetch('/api/cancel_order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: accountId, order_id: orderId })
            });
            const data = await response.json();
            if (data.success) {
                setStatus('Cancel Sent');
                pollInstrumentOrders();
            } else {
                setStatus(`Cancel Error: ${data.error}`, true);
            }
        } catch (error) {
            setStatus(`API Error canceling: ${error.message}`, true);
        }
    };

    const showCancelModal = (orders) => {
        const existingModal = document.querySelector('.modal-overlay');
        if (existingModal) existingModal.remove();
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        const content = document.createElement('div');
        content.className = 'modal-content';
        content.innerHTML = '<h3>Choose Order to Cancel</h3>';
        orders.forEach(order => {
            const choiceDiv = document.createElement('div');
            choiceDiv.className = 'modal-order-choice';
            choiceDiv.innerHTML = `<strong>${order.type} ${order.side}</strong><br>Status: ${order.status}`;
            choiceDiv.addEventListener('click', () => {
                handleCancel(order);
                overlay.remove();
            });
            content.appendChild(choiceDiv);
        });
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        overlay.appendChild(content);
        document.body.appendChild(overlay);
    };

    const showCloseOrderModal = async (fill, fillDiv) => {
        const existingModal = document.querySelector('.modal-overlay');
        if (existingModal) existingModal.remove();

        // Highlight the clicked fill and remove highlight from others
        document.querySelectorAll('.fill-item.active-fill').forEach(el => el.classList.remove('active-fill'));
        if (fillDiv) fillDiv.classList.add('active-fill');

        const isClosingBuy = fill.quantity < 0;
        const side = isClosingBuy ? 'BUY_TO_CLOSE' : 'SELL_TO_CLOSE';
        const optionType = fill.putCall === 'C' ? 'CALL' : 'PUT';

        // --- Safety Check 1: See if a closing order already exists ---
        const existingClosingOrder = instrumentOrders.find(o => o.side === side);
        if (existingClosingOrder) {
            showWarningModal("Duplicate Order", "A closing order for this instrument is already working.", fillDiv);
            return;
        }

        // --- Safety Check 2: Verify the position still exists ---
        try {
            const posResponse = await fetch(`/api/instrument_position?account_hash=${accountHash}&symbol=${fill.symbol}&strike=${fill.strike}&expiry=${fill.expiry}`);
            const posData = await posResponse.json();
            if (posData.success) {
                const currentQuantity = optionType === 'CALL' ? posData.call_quantity : posData.put_quantity;
                const positionExists = isClosingBuy ? currentQuantity < 0 : currentQuantity > 0;
                if (!positionExists) {
                    showWarningModal("No Position", "There is no existing position to close.", fillDiv);
                    return;
                }
            } else {
                 showWarningModal("Position Check Failed", "Could not verify if position exists.", fillDiv);
                 return;
            }
        } catch (error) {
            showWarningModal("Position Check Failed", `API Error: ${error.message}`, fillDiv);
            return;
        }

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';

        const content = document.createElement('div');
        content.className = 'modal-content';
        content.innerHTML = `<h3>Loading price...</h3>`;
        overlay.appendChild(content);
        document.body.appendChild(overlay);

        // Fetch the current quote to populate the price
        fetch(`/api/options/${fill.symbol}/${fill.strike}/${fill.expiry}`)
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    content.innerHTML = `<h3>Error</h3><p>Could not fetch price data.</p>`;
                    setTimeout(() => overlay.remove(), 2000);
                    return;
                }

                const isClosingBuy = fill.quantity < 0;
                const optionType = fill.putCall === 'C' ? 'CALL' : 'PUT';
                const side = isClosingBuy ? 'BUY_TO_CLOSE' : 'SELL_TO_CLOSE';

                const callMap = data.data.callExpDateMap, putMap = data.data.putExpDateMap;
                const normalizedStrikeKey = parseFloat(fill.strike).toFixed(1);
                const optionData = optionType === 'CALL'
                    ? callMap?.[Object.keys(callMap)[0]]?.[normalizedStrikeKey]?.[0]
                    : putMap?.[Object.keys(putMap)[0]]?.[normalizedStrikeKey]?.[0];

                let defaultPrice = 0;
                if(optionData) {
                    defaultPrice = isClosingBuy
                        ? (optionData.bid + 0.01)
                        : (optionData.ask - 0.01);
                }

                const expiryDate = new Date(fill.expiry + 'T00:00:00');
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const dte = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));

                const title = `CLOSING ORDER: ${side.split('_')[0]} ${Math.abs(fill.quantity)} ${fill.symbol} ${fill.strike} ${optionType} DTE:${dte}`;

                content.innerHTML = `
                    <h3 class="modal-title">${title}</h3>
                    <div class="modal-price-input-wrapper">
                        <label for="modal-price-input">Price:</label>
                        <div class="price-adjust-wrapper">
                             <button class="price-adjust-btn" data-target="modal-price-input" data-amount="-0.01">-</button>
                             <input type="number" id="modal-price-input" class="order-input" step="0.01" value="${defaultPrice.toFixed(2)}">
                             <button class="price-adjust-btn" data-target="modal-price-input" data-amount="0.01">+</button>
                        </div>
                    </div>
                    <div class="modal-buttons">
                        <button id="modal-cancel-btn" class="control-btn">Cancel</button>
                        <button id="modal-submit-btn" class="order-btn">Submit Order</button>
                    </div>
                `;

                const closeModal = () => {
                    if (fillDiv) fillDiv.classList.remove('active-fill');
                    overlay.remove();
                };

                overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
                document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
                content.querySelectorAll('.price-adjust-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const button = e.currentTarget;
                        const targetInputId = button.dataset.target;
                        const amount = parseFloat(button.dataset.amount);
                        const targetInput = document.getElementById(targetInputId);
                        if (targetInput) {
                            const currentValue = parseFloat(targetInput.value) || 0;
                            const newValue = currentValue + amount;
                            targetInput.value = Math.max(0, newValue).toFixed(2);
                        }
                    });
                });
                document.getElementById('modal-submit-btn').addEventListener('click', () => {
                    const price = parseFloat(document.getElementById('modal-price-input').value);
                    if (!price || price <= 0) {
                        setStatus("Invalid price in modal.", true);
                        return;
                    }
                    const orderDetails = {
                        account_id: accountHash,
                        symbol: fill.symbol,
                        option_type: optionType,
                        expiration_date: fill.expiry,
                        strike_price: fill.strike,
                        quantity: Math.abs(fill.quantity),
                        side: side,
                        order_type: 'LIMIT',
                        price: price
                    };
                    placeOrder(orderDetails);
                    closeModal();
                });
            })
            .catch(err => {
                logError(`Failed to fetch quote for modal: ${err.message}`);
                content.innerHTML = `<h3>Error</h3><p>Could not fetch price data.</p>`;
                if (fillDiv) fillDiv.classList.remove('active-fill');
                setTimeout(() => overlay.remove(), 2000);
            });
    };

    const showWarningModal = (title, message, elementToClear) => {
        const existingModal = document.querySelector('.modal-overlay');
        if (existingModal) existingModal.remove();

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        const content = document.createElement('div');
        content.className = 'modal-content';

        content.innerHTML = `
            <h3 class="modal-title" style="color: #d9534f;">${title}</h3>
            <p style="text-align: center;">${message}</p>
            <div class="modal-buttons">
                <button id="modal-ok-btn" class="order-btn">OK</button>
            </div>
        `;
        overlay.appendChild(content);
        document.body.appendChild(overlay);

        const closeModal = () => {
            if (elementToClear) elementToClear.classList.remove('active-fill');
            overlay.remove();
        }

        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
        document.getElementById('modal-ok-btn').addEventListener('click', closeModal);
    };

    const showWorkingOrderModal = (order, orderDiv) => {
        const existingModal = document.querySelector('.modal-overlay');
        if (existingModal) existingModal.remove();

        document.querySelectorAll('.working-order-item.active-fill').forEach(el => el.classList.remove('active-fill'));
        if (orderDiv) orderDiv.classList.add('active-fill');

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        const content = document.createElement('div');
        content.className = 'modal-content';

        const expiryDate = new Date(order.expiration_date + 'T00:00:00');
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const dte = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));

        const title = `WORKING ORDER: ${order.side.split('_')[0]} ${order.quantity} ${order.symbol} ${order.strike_price} ${order.option_type[0]} DTE:${dte}`;

        content.innerHTML = `
            <h3 class="modal-title">${title}</h3>
            <div class="modal-price-input-wrapper">
                <label for="modal-price-input">Price:</label>
                <div class="price-adjust-wrapper">
                     <button class="price-adjust-btn" data-target="modal-price-input" data-amount="-0.01">-</button>
                     <input type="number" id="modal-price-input" class="order-input" step="0.01" value="${order.price.toFixed(2)}">
                     <button class="price-adjust-btn" data-target="modal-price-input" data-amount="0.01">+</button>
                </div>
            </div>
            <div class="modal-buttons modal-three-buttons">
                <button id="modal-cancel-order-btn" class="control-btn">Cancel Order</button>
                <button id="modal-exit-btn" class="control-btn">Exit</button>
                <button id="modal-replace-btn" class="order-btn">Replace Order</button>
            </div>
        `;
        overlay.appendChild(content);
        document.body.appendChild(overlay);

        const closeModal = () => {
            if (orderDiv) orderDiv.classList.remove('active-fill');
            overlay.remove();
        };

        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
        document.getElementById('modal-exit-btn').addEventListener('click', closeModal);

        document.getElementById('modal-cancel-order-btn').addEventListener('click', () => {
            handleCancel({ order_id: order.order_id, account_id: accountHash });
            closeModal();
        });

        document.getElementById('modal-replace-btn').addEventListener('click', () => {
            const newPrice = parseFloat(document.getElementById('modal-price-input').value);
            if (!newPrice || newPrice <= 0) {
                setStatus("Invalid price in modal.", true);
                return;
            }
            // For a replacement, we need to send the full original order details plus the new price.
            // The backend will ensure quantity and side are preserved.
            const orderDetails = {
                account_id: accountHash,
                order_id: order.order_id, // Important for replacement
                symbol: order.symbol,
                option_type: order.option_type,
                expiration_date: order.expiration_date,
                strike_price: order.strike_price,
                quantity: order.quantity,
                side: order.side,
                order_type: order.order_type,
                price: newPrice
            };
            placeOrder(orderDetails);
            closeModal();
        });

        content.querySelectorAll('.price-adjust-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const button = e.currentTarget;
                const targetInputId = button.dataset.target;
                const amount = parseFloat(button.dataset.amount);
                const targetInput = document.getElementById(targetInputId);
                if (targetInput) {
                    const currentValue = parseFloat(targetInput.value) || 0;
                    const newValue = currentValue + amount;
                    targetInput.value = Math.max(0, newValue).toFixed(2);
                }
            });
        });
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
                fetchWorkingOrders();
                setInterval(fetchRecentFills, 30000);
                setInterval(fetchWorkingOrders, 5000); // Poll more frequently for working orders
                setInterval(fetchPositions, 10000);
            } else {
                setStatus(`Error: ${data.error}`, true);
            }
        } catch (error) {
            setStatus(`Backend not reachable: ${error.message}`, true);
        }
    };

    // --- Event Listeners ---
    symbolInput.addEventListener('change', fetchAndSetDefaults);

    dteInput.addEventListener('input', () => {
        const dte = parseInt(dteInput.value, 10);
        if (!isNaN(dte) && dte >= 0) {
            const today = new Date();
            today.setDate(today.getDate() + dte);
            // Format to YYYY-MM-DD for the date input
            expiryInput.value = today.toISOString().split('T')[0];
            fetchStrikes(); // Fetch new strikes for the updated date
        }
    });

    expiryInput.addEventListener('input', () => {
        if (expiryInput.value) {
            const selectedDate = new Date(expiryInput.value + 'T00:00:00');
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const diffTime = selectedDate - today;
            const dte = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            dteInput.value = dte;
        }
        fetchStrikes();
    });

    strikeInput.addEventListener('input', handleInputChange); // 'input' is better for datalist

    // This trick clears the input on click to show the full datalist,
    // then restores the value if the user clicks away.
    strikeInput.addEventListener('mousedown', () => {
        if (strikeInput.value) {
            strikeInputOriginalValue = strikeInput.value;
            strikeInput.value = '';
        }
    });

    strikeInput.addEventListener('blur', () => {
        if (!strikeInput.value && strikeInputOriginalValue) {
            strikeInput.value = strikeInputOriginalValue;
        }
    });

    useBtn.addEventListener('click', async () => {
        fetchQuoteAndInstrumentPosition(true);
        try {
            await fetch('/api/trigger_fast_poll', { method: 'POST' });
        } catch (error) {
            logError(`Failed to trigger fast poll: ${error.message}`);
        }
    });

    document.querySelectorAll('.price-adjust-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const button = e.currentTarget;
            const targetInputId = button.dataset.target;
            const amount = parseFloat(button.dataset.amount);
            const targetInput = document.getElementById(targetInputId);
            if (targetInput) {
                const currentValue = parseFloat(targetInput.value) || 0;
                const newValue = currentValue + amount;
                targetInput.value = Math.max(0, newValue).toFixed(2);
            }
        });
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
            const orderQuantity = parseInt(quantityInput.value, 10) || 1;
            if (orderQuantity <= 0) {
                setStatus("Quantity must be positive.", true);
                return;
            }

            const orderDetails = {
                account_id: accountHash,
                symbol: symbol,
                option_type: optionType,
                expiration_date: expiry,
                strike_price: parseFloat(strike),
                quantity: orderQuantity,
                side: side,
                order_type: 'LIMIT',
                price: parseFloat(priceInput.value)
            };
            placeOrder(orderDetails);
        });
    });

    cancelBtn.addEventListener('click', () => handleCancel(null));

    errorLogHeader.addEventListener('click', () => {
        errorLogContainer.classList.toggle('collapsed');
        const icon = errorLogToggleIcon;
        if (errorLogContainer.classList.contains('collapsed')) {
            icon.textContent = '[+]';
        } else {
            icon.textContent = '[-]';
        }
    });

    // --- Start the app ---
    init();
});
