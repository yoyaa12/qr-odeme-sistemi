//Masa Ruleti- Standalone Client-Side Mini Game

window.MasaRuleti = (function () {
    let canvas, ctx;
    let players = ["Ahmet", "Mehmet", "Ayşe", "Fatma"];
    let colors = ["#FF5722", "#E91E63", "#9C27B0", "#3F51B5", "#00BCD4", "#4CAF50", "#FFEB3B", "#FF9800"];
    let startAngle = 0;
    let arc = Math.PI / (players.length / 2);
    let spinTimeout = null;
    let spinArcStart = 10;
    let spinTime = 0;
    let spinTimeTotal = 0;
    let isSpinning = false;

    function initModal() {
        if (document.getElementById("ruletModal")) return;

        const modalHtml = `
        <div id="ruletModal" class="rulet-modal-overlay" style="display:none;">
            <div class="rulet-modal-content">
                <button class="rulet-modal-close" onclick="MasaRuleti.close()">&times;</button>
                <div class="rulet-header">
                    <h2>🎰 Hesabı Kim Ödeyecek?</h2>
                    <p>Masadakilerin isimlerini ekleyin ve çarkı çevirin!</p>
                </div>
                
                <div class="rulet-body">
                    <div class="rulet-players-container">
                        <label>Oyuncular:</label>
                        <div id="ruletPlayerInputs" class="rulet-inputs-grid">
                            <!-- Oyuncu kutucukları buraya gelecek -->
                        </div>
                        <button type="button" class="btn-add-player" onclick="MasaRuleti.addPlayerInput()">+ Oyuncu Ekle</button>
                    </div>

                    <div class="rulet-wheel-wrapper">
                        <div class="rulet-arrow">▼</div>
                        <canvas id="ruletCanvas" width="320" height="320"></canvas>
                    </div>

                    <div id="ruletWinnerBanner" class="rulet-winner-banner" style="display:none;">
                        <span id="ruletWinnerText">🎉 Bugünü Ahmet ısmarlıyor!</span>
                    </div>

                    <div class="rulet-actions">
                        <button id="btnSpinWheel" class="btn-spin-wheel" onclick="MasaRuleti.spin()">🎲 ÇARKI ÇEVİR!</button>
                    </div>
                </div>
            </div>
        </div>
        `;

        document.body.insertAdjacentHTML("beforeend", modalHtml);
        injectStyles();

        canvas = document.getElementById("ruletCanvas");
        ctx = canvas.getContext("2d");

        renderPlayerInputs();
        drawWheel();
    }

    function injectStyles() {
        if (document.getElementById("ruletStyles")) return;
        const style = document.createElement("style");
        style.id = "ruletStyles";
        style.innerHTML = `
            .rulet-modal-overlay {
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px);
                z-index: 99999; display: flex; align-items: center; justify-content: center;
                animation: fadeIn 0.3s ease;
            }
            .rulet-modal-content {
                background: #1e1e2d; color: #fff; border-radius: 20px;
                padding: 24px; width: 90%; max-width: 440px; text-align: center;
                position: relative; box-shadow: 0 20px 50px rgba(0,0,0,0.5);
                border: 1px solid rgba(255,255,255,0.1);
            }
            .rulet-modal-close {
                position: absolute; top: 12px; right: 16px; background: none;
                border: none; color: #aaa; font-size: 28px; cursor: pointer;
            }
            .rulet-header h2 { margin: 0 0 4px 0; color: #ffbc00; font-size: 1.4rem; }
            .rulet-header p { margin: 0 0 16px 0; color: #aaa; font-size: 0.85rem; }
            .rulet-players-container { margin-bottom: 16px; text-align: left; }
            .rulet-players-container label { font-size: 0.8rem; color: #ffbc00; font-weight: bold; }
            .rulet-inputs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 6px; }
            .rulet-input-wrapper { display: flex; align-items: center; background: #2b2b3d; border-radius: 8px; padding: 4px 8px; }
            .rulet-input-wrapper input {
                background: none; border: none; color: #fff; width: 100%; font-size: 0.85rem; padding: 4px; outline: none;
            }
            .rulet-input-del { background: none; border: none; color: #ff5252; cursor: pointer; font-size: 14px; }
            .btn-add-player {
                background: none; border: 1px dashed #ffbc00; color: #ffbc00;
                padding: 4px 10px; border-radius: 8px; font-size: 0.75rem;
                cursor: pointer; margin-top: 8px; width: 100%; transition: 0.2s;
            }
            .btn-add-player:hover { background: rgba(255,188,0,0.1); }
            .rulet-wheel-wrapper { position: relative; display: inline-block; margin: 10px 0; }
            .rulet-arrow {
                position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
                color: #ffbc00; font-size: 24px; z-index: 10; text-shadow: 0 2px 5px rgba(0,0,0,0.5);
            }
            #ruletCanvas { border-radius: 50%; box-shadow: 0 0 20px rgba(255,188,0,0.2); }
            .rulet-winner-banner {
                background: linear-gradient(135deg, #ff9800, #e91e63);
                padding: 12px; border-radius: 12px; font-size: 1.1rem; font-weight: bold;
                margin: 12px 0; animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                box-shadow: 0 4px 15px rgba(233,30,99,0.4);
            }
            .btn-spin-wheel {
                background: linear-gradient(135deg, #ffbc00, #ff8c00); color: #111;
                border: none; padding: 14px 28px; border-radius: 30px; font-size: 1.1rem;
                font-weight: bold; cursor: pointer; width: 100%; box-shadow: 0 6px 20px rgba(255,140,0,0.4);
                transition: transform 0.1s, box-shadow 0.1s;
            }
            .btn-spin-wheel:active { transform: scale(0.96); }
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            @keyframes popIn { from { transform: scale(0.7); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        `;
        document.head.appendChild(style);
    }

    function renderPlayerInputs() {
        const container = document.getElementById("ruletPlayerInputs");
        if (!container) return;
        container.innerHTML = "";
        players.forEach((p, index) => {
            const div = document.createElement("div");
            div.className = "rulet-input-wrapper";
            div.innerHTML = `
                <input type="text" value="${p}" onchange="MasaRuleti.updatePlayerName(${index}, this.value)">
                ${players.length > 2 ? `<button class="rulet-input-del" onclick="MasaRuleti.removePlayer(${index})">&times;</button>` : ''}
            `;
            container.appendChild(div);
        });
    }

    function updatePlayerName(index, name) {
        if (name.trim()) {
            players[index] = name.trim();
        } else {
            players[index] = `Oyuncu ${index + 1}`;
        }
        drawWheel();
    }

    function addPlayerInput() {
        if (players.length >= 8) return;
        players.push(`Oyuncu ${players.length + 1}`);
        renderPlayerInputs();
        drawWheel();
    }

    function removePlayer(index) {
        if (players.length <= 2) return;
        players.splice(index, 1);
        renderPlayerInputs();
        drawWheel();
    }

    function drawWheel() {
        if (!ctx) return;
        arc = Math.PI / (players.length / 2);
        ctx.clearRect(0, 0, 320, 320);

        const outsideRadius = 150;
        const textRadius = 105;
        const insideRadius = 30;

        ctx.strokeStyle = "#1e1e2d";
        ctx.lineWidth = 4;

        for (let i = 0; i < players.length; i++) {
            const angle = startAngle + i * arc;
            ctx.fillStyle = colors[i % colors.length];

            ctx.beginPath();
            ctx.arc(160, 160, outsideRadius, angle, angle + arc, false);
            ctx.arc(160, 160, insideRadius, angle + arc, angle, true);
            ctx.stroke();
            ctx.fill();

            ctx.save();
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 14px sans-serif";
            ctx.shadowColor = "rgba(0,0,0,0.6)";
            ctx.shadowBlur = 4;
            ctx.translate(160 + Math.cos(angle + arc / 2) * textRadius,
                160 + Math.sin(angle + arc / 2) * textRadius);
            ctx.rotate(angle + arc / 2 + Math.PI / 2);
            const text = players[i];
            ctx.fillText(text, -ctx.measureText(text).width / 2, 0);
            ctx.restore();
        }

        // Merkez halka
        ctx.beginPath();
        ctx.arc(160, 160, insideRadius, 0, Math.PI * 2, false);
        ctx.fillStyle = "#1e1e2d";
        ctx.fill();
        ctx.strokeStyle = "#ffbc00";
        ctx.lineWidth = 3;
        ctx.stroke();
    }

    function spin() {
        if (isSpinning) return;
        isSpinning = true;
        document.getElementById("ruletWinnerBanner").style.display = "none";
        document.getElementById("btnSpinWheel").disabled = true;

        spinAngleStart = Math.random() * 10 + 10;
        spinTime = 0;
        spinTimeTotal = Math.random() * 3000 + 4000;
        rotateWheel();
    }

    function rotateWheel() {
        spinTime += 30;
        if (spinTime >= spinTimeTotal) {
            stopRotateWheel();
            return;
        }
        const spinAngle = spinAngleStart - easeOut(spinTime, 0, spinAngleStart, spinTimeTotal);
        startAngle += (spinAngle * Math.PI / 180);
        drawWheel();
        spinTimeout = setTimeout(rotateWheel, 30);
    }

    function stopRotateWheel() {
        clearTimeout(spinTimeout);
        isSpinning = false;
        document.getElementById("btnSpinWheel").disabled = false;

        const degrees = startAngle * 180 / Math.PI + 90;
        const arcd = arc * 180 / Math.PI;
        const index = Math.floor((360 - degrees % 360) / arcd);

        ctx.save();
        const winner = players[index];
        ctx.restore();

        const banner = document.getElementById("ruletWinnerBanner");
        const winnerText = document.getElementById("ruletWinnerText");
        winnerText.innerHTML = `🎉 Tebrikler! Bugünü <u>${winner}</u> ısmarlıyor!`;
        banner.style.display = "block";
    }

    function easeOut(t, b, c, d) {
        const ts = (t /= d) * t;
        const tc = ts * t;
        return b + c * (tc + -3 * ts + 3 * t);
    }

    return {
        open: function () {
            initModal();
            document.getElementById("ruletModal").style.display = "flex";
            document.getElementById("ruletWinnerBanner").style.display = "none";
            drawWheel();
        },
        close: function () {
            const modal = document.getElementById("ruletModal");
            if (modal) modal.style.display = "none";
        },
        spin: spin,
        addPlayerInput: addPlayerInput,
        removePlayer: removePlayer,
        updatePlayerName: updatePlayerName
    };
})();
