// static/lobby.js

(function () {
  const code = document.body.dataset.code;
  if (!code) return;

  const wsProto = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${wsProto}://${location.host}/ws/${code}`;

  let ws = null;
  let lobby = null;
  
  let myPid = null;
  let myRole = null; // "B" oder "S"
  let iAmBuyer = false;

  let timerInterval = null;
  let myCooldownDeadline = 0;
  let oppCooldownDeadline = 0;

  // Endbildschirm / Animation
  let isEnding = false;
  let hasShownResult = false;
  let lastEndResult = null;
  
  // NEU: Merkt sich, ob wir gerade das Übungs-Ende anzeigen
  let showingPracticeEnd = false;

  // --- DOM Elemente ---
  const instrOverlay = document.getElementById("instrOverlay");
  const instrHtml = document.getElementById("instrHtml");
  const btnInstrNext = document.getElementById("btnInstrNext");

  // --- Instruktions-Elemente ---
  const instrSelectionWrap = document.getElementById("instrSelectionWrap");
  const instrVideoWrap     = document.getElementById("instrVideoWrap");
  const instrTextWrap      = document.getElementById("instrTextWrap");
  
  const btnChooseVideo = document.getElementById("btnChooseVideo");
  const btnChooseText  = document.getElementById("btnChooseText");
  
  const btnBackFromVideo = document.getElementById("btnBackFromVideo");
  const btnBackFromText  = document.getElementById("btnBackFromText");
  
  const instrVideoPlayer = document.getElementById("instrVideoPlayer");
  
  // Die "Weiter"-Buttons (jetzt gibt es zwei)
  const btnInstrNextVideo = document.getElementById("btnInstrNextVideo");
  const btnInstrNextText  = document.getElementById("btnInstrNextText");

  // ...
  const btnReviewInstr = document.getElementById("btnReviewInstr");
  const btnCloseInstr  = document.getElementById("btnCloseInstr");
  
  // Flag: Schaut der User gerade freiwillig nochmal rein?
  let isReviewingInstr = false;

  const overlay = document.getElementById("overlay");
  const overlayLobbyCode = document.getElementById("overlayLobbyCode");
  const overlayPlayers = document.getElementById("overlayPlayers");
  const btnToggleReady = document.getElementById("btnToggleReady");
  const statusEl = document.getElementById("status");

  const mainWrap = document.getElementById("mainWrap"); 
  const centerOverlay = document.getElementById("centerOverlay");
  const centerTitle = document.getElementById("centerTitle");
  const centerHeader = document.getElementById("centerHeader");
  
  const timeInfo = document.getElementById("timeInfo");

  // Ergebnis-Screen
  const resultWrap = document.getElementById("resultWrap");
  const resultPrice = document.getElementById("resultPrice");
  const resultTime = document.getElementById("resultTime");
  // NEU: Der Fragebogen Button
  const btnToQuestionnaire = document.getElementById("btnToQuestionnaire");

  const topRoleDisplay = document.getElementById("topRoleDisplay");

  // Chips / Header
  const chipLeft = document.getElementById("chipLeft");
  const chipRight = document.getElementById("chipRight");
  const leftRoleTitle = document.getElementById("leftRoleTitle");
  const leftStats = document.getElementById("leftStats");
  const rightRoleTitle = document.getElementById("rightRoleTitle");
  const rightStats = document.getElementById("rightStats");

  // Inputs & Charts
  const offerInput = document.getElementById("offerInput");
  const oppPriceDisplay = document.getElementById("oppPriceDisplay");
  const myPriceLabel = document.getElementById("myPriceLabel");
  const oppPriceLabel = document.getElementById("oppPriceLabel");
  
  // Tabellen-Elemente
  const offersLogBody = document.getElementById("offersLogBody");
  const tableWrapper = document.querySelector(".table-wrapper");
  
  const btnOffer = document.getElementById("btnOffer");
  const btnAccept = document.getElementById("btnAccept");
  
  // ---------------------------------------------------------
  // TIMER ELEMENTE
  // ---------------------------------------------------------
  const myCooldownWrap = document.getElementById("myCooldownWrap");
  const myTimerCircle = document.getElementById("myTimerCircle");
  const myTimerText = document.getElementById("myTimerText");

  const oppCooldownWrap = document.getElementById("oppCooldownWrap");
  const oppTimerCircle = document.getElementById("oppTimerCircle");
  const oppTimerText = document.getElementById("oppTimerText");
  // Das Label für den Text "Käufer Wartezeit"
  const oppTimerLabel = document.getElementById("oppTimerLabel");

  const practiceEndOverlay = document.getElementById("practiceEndOverlay");
  const practiceEndPriceDisplay = document.getElementById("practiceEndPriceDisplay");
  const btnDismissPractice = document.getElementById("btnDismissPractice");

  // Umfang des Kreises bei r=45
  const CIRCUMFERENCE = 283; 

  // Toast
  let toastStack = document.getElementById("toastStack");
  if (!toastStack) {
    toastStack = document.createElement("div");
    toastStack.id = "toastStack";
    document.body.appendChild(toastStack);
  }

  function showToast(msg) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    toastStack.appendChild(t);
    setTimeout(() => t.classList.add('show'), 10);
    setTimeout(() => { t.classList.remove('show'); t.classList.add('hide'); setTimeout(()=>t.remove(),300); }, 3000);
  }

  function formatTimeSimple(seconds) {
    return `${Math.floor(seconds)} s`;
  }

  function getPriceFromInput() {
      if (!offerInput) return NaN;

      // Komma -> Punkt, Leerzeichen weg
      const raw = offerInput.value.replace(",", ".").trim();
      if (raw === "") return NaN;

      const val = Number(raw);
      return Number.isFinite(val) ? val : NaN;
  }


// NEU: nur für die Anzeige im Feld
  function normalizeOfferInput() {
      if (!offerInput) return;
      offerInput.value = offerInput.value.replace(",", ".").trim();
  }

  // -------------------------------------------------------
  // LOG HELPER
  // -------------------------------------------------------
  function scrollToBottom() {
    if (tableWrapper) {
      tableWrapper.scrollTop = tableWrapper.scrollHeight;
    }
  }

  function roleLabelForPid(pid) {
    if (!lobby || !lobby.pid_label) return "";
    const r = lobby.pid_label[pid];
    if (r === "B") return "Käufer";    // GEÄNDERT: P1 -> B
    if (r === "S") return "Verkäufer"; // GEÄNDERT: P2 -> S
    return "???";
  }

  function appendOfferLog(o) {
    if (!offersLogBody) return;
    
    const tr = document.createElement("tr");
    const isMe = (o.proposer === myPid);
    
    tr.className = isMe ? "log-row-offer log-row-me" : "log-row-offer";

    const tdTime = document.createElement("td");
    tdTime.textContent = new Date(o.timestamp * 1000).toLocaleTimeString();
    tr.appendChild(tdTime);

    const tdRole = document.createElement("td");
    tdRole.textContent = roleLabelForPid(o.proposer);
    tr.appendChild(tdRole);

    const tdPrice = document.createElement("td");
    tdPrice.textContent = o.price.toFixed(2);
    tr.appendChild(tdPrice);

    offersLogBody.appendChild(tr);
    scrollToBottom();
  }

  function appendAcceptedLog(msg) {
    if (!offersLogBody) return;

    const tr = document.createElement("tr");
    tr.className = "log-row-accepted";

    const tdTime = document.createElement("td");
    tdTime.textContent = new Date(msg.timestamp * 1000).toLocaleTimeString();
    tr.appendChild(tdTime);

    const tdRole = document.createElement("td");
    tdRole.textContent = "—"; 
    tr.appendChild(tdRole);

    const tdMsg = document.createElement("td");
    tdMsg.textContent = `Einigung: ${msg.price.toFixed(2)}`;
    tr.appendChild(tdMsg);

    offersLogBody.appendChild(tr);
    scrollToBottom();
  }

  function showInstrSection(section) {
      if(instrSelectionWrap) instrSelectionWrap.style.display = 'none';
      if(instrVideoWrap)     instrVideoWrap.style.display     = 'none';
      if(instrTextWrap)      instrTextWrap.style.display      = 'none';

      if (section === 'selection') {
          if(instrSelectionWrap) instrSelectionWrap.style.display = 'block';
          // Video stoppen, falls es lief
          if(instrVideoPlayer) instrVideoPlayer.pause();
      } 
      else if (section === 'video') {
          if(instrVideoWrap) instrVideoWrap.style.display = 'flex'; // flex für layout
          loadCorrectVideo();
      } 
      else if (section === 'text') {
          if(instrTextWrap) instrTextWrap.style.display = 'block';
          // Video stoppen
          if(instrVideoPlayer) instrVideoPlayer.pause();
      }
  }

  function loadCorrectVideo() {
      if (!lobby || !myRole || !instrVideoPlayer) return;

      // Treatment Key (T1, T2, T3)
      const treat = lobby.treatment_key || "T1"; 
      
      // Rolle Mapping: 
      // iAmBuyer = true -> "B" (Käufer)
      // iAmBuyer = false -> "S" (Verkäufer)
      const roleShort = iAmBuyer ? "B" : "S";

      // Dateiname: T1_S.mp4, T2_B.mp4 etc.
      const filename = `${treat}_${roleShort}.mp4`;
      const fullPath = `/videos/${filename}`;

      console.log("Loading Video:", fullPath);

      // Nur neu laden, wenn sich Source ändert
      const currentSrc = instrVideoPlayer.getAttribute("src");
      if (currentSrc !== fullPath) {
          instrVideoPlayer.src = fullPath;
          instrVideoPlayer.load();
      }
  }

  // Gemeinsame Funktion zum Bestätigen der Instruktionen
function confirmInstructions() {
  if (isReviewingInstr) {
    isReviewingInstr = false;
    // Wenn wir nur reviewen, reicht ein Update, kein Server-Call nötig (außer Ack war noch nicht da)
    if (lobby && lobby.instr_ack && lobby.instr_ack[myPid]) {
        update_state({ lobby: lobby });
        return;
    }
  }

  // Sicherheitscheck: Button disablen, um Doppelklicks zu verhindern
  if (btnInstrNextVideo) btnInstrNextVideo.disabled = true;
  if (btnInstrNextText) btnInstrNextText.disabled = true;

  if (ws && lobby && myPid) {
    ws.send(JSON.stringify({ type: "instr_ack" }));
    lobby.instr_ack[myPid] = true;

    // Sofort auf Countdown schalten (unser Fix von vorhin)
    lobby.stage = "practice_countdown";
    lobby.countdown_end_at = (Date.now() / 1000) + 3;

    update_state({ lobby: lobby });
  }

  // Buttons nach kurz Zeit wieder freigeben (falls was schief geht)
  setTimeout(() => {
      if (btnInstrNextVideo) btnInstrNextVideo.disabled = false;
      if (btnInstrNextText) btnInstrNextText.disabled = false;
  }, 2000);
}



  // Auswahl: Video
  if (btnChooseVideo) {
      btnChooseVideo.addEventListener("click", () => showInstrSection('video'));
  }
  // Auswahl: Text
  if (btnChooseText) {
      btnChooseText.addEventListener("click", () => showInstrSection('text'));
  }

  // Zurück Buttons
  if (btnBackFromVideo) {
      btnBackFromVideo.addEventListener("click", () => showInstrSection('selection'));
  }
  if (btnBackFromText) {
      btnBackFromText.addEventListener("click", () => showInstrSection('selection'));
  }

  // Weiter Buttons (Video & Text)
  if (btnInstrNextVideo) {
      btnInstrNextVideo.addEventListener("click", confirmInstructions);
  }
  if (btnInstrNextText) {
      btnInstrNextText.addEventListener("click", confirmInstructions);
  }

  // Button im Warte-Screen: Öffnet Instruktionen
  if (btnReviewInstr) {
      btnReviewInstr.addEventListener("click", () => {
          isReviewingInstr = true;
          // Auswahl-Screen anzeigen
          showInstrSection('selection');
          // Update aufrufen, damit das UI umschaltet
          if (lobby) update_state({lobby: lobby});
      });
  }

  // Button im Instruktions-Screen: Schließt Instruktionen
  if (btnCloseInstr) {
      btnCloseInstr.addEventListener("click", () => {
          isReviewingInstr = false;
          if (lobby) update_state({lobby: lobby});
      });
  }

  // -------------------------------------------------------
  // CHART LOGIK
  // -------------------------------------------------------
// --- lobby.js (Funktion updateCharts) ---

function updateCharts(tRel) {
  if (!lobby) return;

  const buyerVal    = lobby.buyer_value || 130;
  const sellerCost  = lobby.seller_cost || 30;
  const totalSurplus = buyerVal - sellerCost;

  const rB    = lobby.discount_rate_per_role["B"] || 0.0;
  const rS    = lobby.discount_rate_per_role["S"] || 0.0;
  const multB = Math.exp(-rB * tRel);
  const multS = Math.exp(-rS * tRel);

  const hideOpp   = !!lobby.hide_opponent_discount;
  const iAmBuyer  = (myRole === "B");

  function drawForPrice(price, prefix, txtPrefix) {
    const elBNetTxt   = document.getElementById(`${txtPrefix}BuyerNet`);
    const elBGrossTxt = document.getElementById(`${txtPrefix}BuyerGross`);
    const elSNetTxt   = document.getElementById(`${txtPrefix}SellerNet`);
    const elSGrossTxt = document.getElementById(`${txtPrefix}SellerGross`);

    const elBGrossBar = document.getElementById(`${prefix}BuyerGross`);
    const elBNetBar   = document.getElementById(`${prefix}BuyerNet`);
    const elSGrossBar = document.getElementById(`${prefix}SellerGross`);
    const elSNetBar   = document.getElementById(`${prefix}SellerNet`);

    // --- FIX HIER: Strikte Prüfung auf gültigen Preis (30 bis 130) ---
    const isValidPrice = (Number.isFinite(price) && price >= 30 && price <= 130);

    // Kein gültiger Preis → alles leeren (Hard Reset)
    if (!isValidPrice) {
      if (elBGrossBar) elBGrossBar.style.height = "0%";
      if (elBNetBar)   elBNetBar.style.height   = "0%";
      if (elSGrossBar) elSGrossBar.style.height = "0%";
      if (elSNetBar)   elSNetBar.style.height   = "0%";

      if (elBNetTxt)   elBNetTxt.textContent   = "-";
      if (elBGrossTxt) elBGrossTxt.textContent = "-";
      if (elSNetTxt)   elSNetTxt.textContent   = "-";
      if (elSGrossTxt) elSGrossTxt.textContent = "-";
      return;
    }
    
    // ... (Rest der Logik für Brutto/Netto bleibt gleich) ...
    
    // Brutto-/Netto-Werte
    const grossB = Math.max(0, buyerVal - price);
    const grossS = Math.max(0, price - sellerCost);
    const netB   = grossB * multB;
    const netS   = grossS * multS;
    
    // ... (Restliche Berechnungen und DOM-Updates bleiben gleich) ...

    const hGrossB = (grossB / totalSurplus) * 100;
    const hGrossS = (grossS / totalSurplus) * 100;
    const hNetB   = grossB > 0 ? (netB / grossB) * 100 : 0;
    const hNetS   = grossS > 0 ? (netS / grossS) * 100 : 0;

    // --- BALKEN ---

    // Käufer-Balken
    if (elBGrossBar && elBNetBar) {
      elBGrossBar.style.height = `${hGrossB}%`;

      // Wenn ich Verkäufer bin, ist Käufer der Gegner → Netto verstecken
      if (hideOpp && !iAmBuyer) {
        elBNetBar.style.height = "0%";
      } else {
        elBNetBar.style.height = `${hNetB}%`;
      }
    }

    // Verkäufer-Balken
    if (elSGrossBar && elSNetBar) {
      elSGrossBar.style.height = `${hGrossS}%`;

      // Wenn ich Käufer bin, ist Verkäufer der Gegner → Netto verstecken
      if (hideOpp && iAmBuyer) {
        elSNetBar.style.height = "0%";
      } else {
        elSNetBar.style.height = `${hNetS}%`;
      }
    }

    // --- TEXTE ---

    // Käufer-Texte
    if (elBNetTxt && elBGrossTxt) {
      if (hideOpp && !iAmBuyer) {
        // Käufer = Gegner
        elBNetTxt.textContent = "—";
      } else {
        elBNetTxt.textContent = netB.toFixed(1);
      }
      elBGrossTxt.textContent = grossB.toFixed(1);
    }

    // Verkäufer-Texte
    if (elSNetTxt && elSGrossTxt) {
      if (hideOpp && iAmBuyer) {
        // Verkäufer = Gegner
        elSNetTxt.textContent = "—";
      } else {
        elSNetTxt.textContent = netS.toFixed(1);
      }
      elSGrossTxt.textContent = grossS.toFixed(1);
    }
  }

  // Mein Eingabepreis (Komma wird zu Punkt normalisiert)
  let myInputVal = getPriceFromInput();

  // Nur aktualisieren, wenn gültig
  drawForPrice(myInputVal, "barMy", "txtMy"); // Prüft jetzt intern auf 30-130

  // Letztes Angebot des Gegenübers
  const oppRole  = (myRole === "B") ? "S" : "B";
  const oppOffer = lobby.current_offers ? lobby.current_offers[oppRole] : null;
  const oppPrice = oppOffer ? oppOffer.price : null;
  
  drawForPrice(oppPrice, "barOpp", "txtOpp"); // Prüft jetzt intern auf 30-130
}



  // -------------------------------------------------------
  // ERGEBNIS-CHARTS
  // -------------------------------------------------------
function drawResultCharts() {
    if (!lobby) return;

    const price = lastEndResult && typeof lastEndResult.price === "number"
      ? lastEndResult.price
      : lobby.agreed_price;

    if (price == null) return;

    const buyerVal    = lobby.buyer_value || 130;
    const sellerCost  = lobby.seller_cost || 30;
    const totalSurplus = buyerVal - sellerCost;

    let grossB = Math.max(0, buyerVal - price);
    let grossS = Math.max(0, price - sellerCost);

    let netB = null;
    let netS = null;

    // Falls Server Payoffs liefert (besser, da rounding korrekt)
    if (lastEndResult && lastEndResult.payoffs_by_pid && lobby.pid_label) {
        for (const [pid, role] of Object.entries(lobby.pid_label)) {
            const payoff = lastEndResult.payoffs_by_pid[pid];
            if (typeof payoff !== "number") continue;
            if (role === "B") netB = payoff; // GEÄNDERT: P1 -> B
            if (role === "S") netS = payoff; // GEÄNDERT: P2 -> S
        }
    }

    // Falls nicht vorhanden → lokal berechnen
    if (netB === null || netS === null) {
        const rB = lobby.discount_rate_per_role["B"] || 0.0; // GEÄNDERT: P1 -> B
        const rS = lobby.discount_rate_per_role["S"] || 0.0; // GEÄNDERT: P2 -> S
        const tRel = (lobby.finished_at && lobby.started_at)
          ? (lobby.finished_at - lobby.started_at)
          : 0.0;
        netB = grossB * Math.exp(-rB * tRel);
        netS = grossS * Math.exp(-rS * tRel);
    }

    const hGrossB = (grossB / totalSurplus) * 100;
    const hGrossS = (grossS / totalSurplus) * 100;
    const hNetB   = grossB > 0 ? (netB / grossB) * 100 : 0;
    const hNetS   = grossS > 0 ? (netS / grossS) * 100 : 0;

    const elBNetTxt   = document.getElementById("txtResBuyerNet");
    const elBGrossTxt = document.getElementById("txtResBuyerGross");
    const elSNetTxt   = document.getElementById("txtResSellerNet");
    const elSGrossTxt = document.getElementById("txtResSellerGross");

    const barBGross = document.getElementById("barResBuyerGross");
    const barBNet   = document.getElementById("barResBuyerNet");
    const barSGross = document.getElementById("barResSellerGross");
    const barSNet   = document.getElementById("barResSellerNet");

    // === TEXTE ===
    if (elBNetTxt) {
        elBNetTxt.textContent   = netB.toFixed(2);
        elBGrossTxt.textContent = grossB.toFixed(2);

        // --- Gegner abhängig vom Treatment ---
        if (lobby.hide_opponent_discount) {
            elSNetTxt.textContent   = "—";
        } else {
            elSNetTxt.textContent   = netS.toFixed(1);
        }

        elSGrossTxt.textContent = grossS.toFixed(1);
    }

    // === BALKEN ===

    if (barBGross && barBNet) {
        barBGross.style.height = `${hGrossB}%`;
        barBNet.style.height   = `${hNetB}%`;
    }

    if (barSGross && barSNet) {
        barSGross.style.height = `${hGrossS}%`;

        if (lobby.hide_opponent_discount) {
            barSNet.style.height = "0%";
        } else {
            barSNet.style.height = `${hNetS}%`;
        }
    }

    if (resultPrice) resultPrice.textContent = price.toFixed(2);

    if (resultTime && lobby.finished_at && lobby.started_at) {
        const dt = lobby.finished_at - lobby.started_at;
        resultTime.textContent = dt.toFixed(1);
    }
}


  function startEndAnimationIfNeeded() {
      if (isEnding || !mainWrap) return;
      isEnding = true;

      mainWrap.classList.add("fade-out-main");

      const onEnd = () => {
          mainWrap.removeEventListener("transitionend", onEnd);
          mainWrap.style.display = "none";
          mainWrap.classList.remove("fade-out-main");

          if (resultWrap) {
              resultWrap.style.display = "flex";
              requestAnimationFrame(() => {
                  resultWrap.classList.add("fade-in");
              });
          }

          drawResultCharts();
          hasShownResult = true;
      };

      setTimeout(onEnd, 600);
      mainWrap.addEventListener("transitionend", onEnd);
  }

  // -------------------------------------------------------
  // ANIMATION LOOP
  // -------------------------------------------------------
    function updateAnimations() {
      if (!lobby || !myPid) return;

      const nowMs  = Date.now();
      const nowSec = nowMs / 1000;
      let tRel = 0;
      if (lobby.started_at > 0) tRel = nowSec - lobby.started_at;

      // HIER IST DIE WICHTIGSTE ÄNDERUNG:
      // Wir definieren "aktiv" als echtes Spiel ODER Übungsrunde.
      const isActive = (lobby.stage === "running" || lobby.stage === "practice");

      // ---------- TEIL 1: Cooldowns (nur wenn aktiv) ----------
      if (isActive) {
          // --- EIGENE WARTEZEIT ---
          let myRem   = Math.max(0, (myCooldownDeadline - nowMs) / 1000);
          const myTotal = lobby.cooldown_per_role[myRole] || 1.0; 
          
          if (myRem > 0) {
              if (btnOffer)  { btnOffer.classList.add("cooldown-hide");  btnOffer.disabled  = true; }
              if (btnAccept) { btnAccept.classList.add("cooldown-hide"); btnAccept.disabled = true; }

              if (myCooldownWrap && myTimerCircle && myTimerText) {
                  myCooldownWrap.style.visibility = 'visible';
                  const ratio  = myRem / myTotal; 
                  const offset = CIRCUMFERENCE * (1 - ratio);
                  myTimerCircle.style.strokeDashoffset = offset;
                  myTimerText.textContent = Math.ceil(myRem) + "s";
              }
          } else {
              if (btnOffer)  { btnOffer.classList.remove("cooldown-hide");  btnOffer.disabled  = false; }
              if (btnAccept) { btnAccept.classList.remove("cooldown-hide"); }

              const oppRole  = myRole === "B" ? "S" : "B"; // GEÄNDERT: P1 -> B, P2 -> S
              const oppOffer = lobby.current_offers ? lobby.current_offers[oppRole] : null;
              // Akzeptieren-Button nur aktiv, wenn ein gegnerisches Angebot da ist
              if (btnAccept) btnAccept.disabled = !oppOffer;

              if (myCooldownWrap) myCooldownWrap.style.visibility = 'hidden';
          }

          // --- GEGNER WARTEZEIT ---
          let oppRem   = Math.max(0, (oppCooldownDeadline - nowMs) / 1000);
          const oppRole  = myRole === "B" ? "S" : "B"; // GEÄNDERT: P1 -> B, P2 -> S
          const oppTotal = lobby.cooldown_per_role[oppRole] || 1.0;
          
          if (oppRem > 0) {
              if (oppCooldownWrap && oppTimerCircle && oppTimerText) {
                  oppCooldownWrap.style.visibility = 'visible';
                  const ratioOpp  = oppRem / oppTotal;
                  const offsetOpp = CIRCUMFERENCE * (1 - ratioOpp);
                  oppTimerCircle.style.strokeDashoffset = offsetOpp;
                  oppTimerText.textContent = Math.ceil(oppRem) + "s";
              }
          } else {
              if (oppCooldownWrap) oppCooldownWrap.style.visibility = 'hidden';
          }
      }

      // ---------- TEIL 2: Zeit & Charts (nur wenn aktiv) ----------
      if (isActive) {
          if (timeInfo) timeInfo.textContent = `Zeit: ${formatTimeSimple(tRel)}`;
          updateCharts(tRel);
      }

      // ---------- TEIL 3: Countdown-Zahl im Overlay (nur bei Countdown) ----------
      if ((lobby.stage === "countdown" || lobby.stage === "practice_countdown") && centerTitle) {
          const timeRemaining = lobby.countdown_end_at - nowSec;
          centerTitle.textContent = Math.max(0, Math.ceil(timeRemaining));
      }
  }



function setCountdownBackdropMode(active) {
  if (!overlay) return;

  if (active) {
    // Overlay neutralisieren, damit NUR centerOverlay den Look macht
    overlay.style.background = "transparent";
    overlay.style.backdropFilter = "none";
    overlay.style.webkitBackdropFilter = "none";
  } else {
    // Zurück auf CSS-Default (wichtig!)
    overlay.style.background = "";
    overlay.style.backdropFilter = "";
    overlay.style.webkitBackdropFilter = "";
  }
}




  // -------------------------------------------------------
  // STATE UPDATE
  // -------------------------------------------------------


  // Gemeinsame Funktion zum Bestätigen der Instruktionen
function confirmInstructions() {
  // Wenn wir nur noch mal reinschauen (Review), lassen wir das Schließen zu
  if (isReviewingInstr) {
    isReviewingInstr = false;
    if (lobby && lobby.instr_ack && lobby.instr_ack[myPid]) {
        update_state({ lobby: lobby });
        return;
    }
  }

  // --- NEU: SPERRE WENN ALLEINE ---
  // Hier verhindern wir den Start der Übung, wenn Spieler < 2
  if (!lobby || !lobby.players || lobby.players.length < 2) {
      showToast("Warten auf zweiten Spieler, bevor die Übung startet.");
      return;
  }
  // --------------------------------

  // Sicherheitscheck: Button disablen
  if (btnInstrNextVideo) btnInstrNextVideo.disabled = true;
  if (btnInstrNextText) btnInstrNextText.disabled = true;

  if (ws && lobby && myPid) {
    ws.send(JSON.stringify({ type: "instr_ack" }));
    lobby.instr_ack[myPid] = true;

    // Sofort auf Countdown schalten
    lobby.stage = "practice_countdown";
    lobby.countdown_end_at = (Date.now() / 1000) + 3;

    update_state({ lobby: lobby });
  }

  // Buttons nach kurz Zeit wieder freigeben
  setTimeout(() => {
      // Nur wieder freigeben, wenn wir genug Spieler sind
      if (lobby && lobby.players && lobby.players.length >= 2) {
          if (btnInstrNextVideo) btnInstrNextVideo.disabled = false;
          if (btnInstrNextText) btnInstrNextText.disabled = false;
      }
  }, 2000);
}

function update_state(state) {
  lobby = state.lobby;
  if (!lobby) return;

  myPid = lobby.me_pid;
  if (lobby.my_role) myRole = lobby.my_role;

  iAmBuyer = (myRole === "B");
  const myRoleName  = iAmBuyer ? "Käufer" : "Verkäufer";
  const oppRoleName = iAmBuyer ? "Verkäufer" : "Käufer";

  const overlayContent = document.getElementById("overlayContent");

  // Gegner-Timer Label setzen
  if (oppTimerLabel) oppTimerLabel.textContent = `${oppRoleName} Wartezeit`;

  // --- COOLDOWN SYNCHRONISATION ---
  const srvMyRem = lobby.cooldown_remaining?.[myPid] || 0.0;
  if (srvMyRem > 0) {
    const est = Date.now() + srvMyRem * 1000;
    if (Math.abs(est - myCooldownDeadline) > 500) myCooldownDeadline = est;
  } else {
    myCooldownDeadline = 0;
  }

  const oppPidObj = (lobby.players || []).find(p => p.pid !== myPid);
  const oppPid = oppPidObj ? oppPidObj.pid : null;
  const srvOppRem = oppPid ? (lobby.cooldown_remaining?.[oppPid] || 0.0) : 0.0;
  if (srvOppRem > 0) {
    const estOpp = Date.now() + srvOppRem * 1000;
    if (Math.abs(estOpp - oppCooldownDeadline) > 500) oppCooldownDeadline = estOpp;
  } else {
    oppCooldownDeadline = 0;
  }

  // --- TIMER LOOP STEUERUNG ---
  const wantsTimer =
    lobby.stage === "running" ||
    lobby.stage === "practice" ||
    lobby.stage === "countdown" ||
    lobby.stage === "practice_countdown";

  if (wantsTimer && !timerInterval) {
    timerInterval = setInterval(updateAnimations, 100);
    updateAnimations();
  } else if (!wantsTimer && timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  // --- BLOCKIEREN, WENN ÜBUNGS-ENDE NOCH ANGEZEIGT WIRD ---
  if (showingPracticeEnd) {
    if (overlay) overlay.style.display = "none";
    if (mainWrap) mainWrap.style.display = "none";
    if (instrOverlay) instrOverlay.style.display = "none";
    return;
  }

  // --- PRACTICE BANNER ---
  const practiceBanner = document.getElementById("practiceBanner");
  if (practiceBanner) {
    if (lobby.stage === "practice" || lobby.stage === "practice_countdown") {
      practiceBanner.style.display = "block";
      if (timeInfo) timeInfo.style.color = "#b45309";
    } else {
      practiceBanner.style.display = "none";
      if (timeInfo) timeInfo.style.color = "";
    }
  }

// =========================
  // 1) INSTRUKTIONEN
  // =========================
  const iHaveConfirmedInstr = !!(lobby.instr_ack && lobby.instr_ack[myPid]);

  // Instruktionen nur zeigen, wenn noch nicht bestätigt
  // oder beim freiwilligen Review (aber NICHT wenn practice läuft)
  const showInstrOverlay =
    (!iHaveConfirmedInstr) || (isReviewingInstr && !lobby.started);

  if (showInstrOverlay) {
    if (instrHtml && (!instrHtml.innerHTML || instrHtml.innerHTML === "")) {
      instrHtml.innerHTML = lobby.instructions_html || "";
    }

    if (instrOverlay) instrOverlay.style.display = "flex";

    // --- NEU: Buttons steuern basierend auf Spieleranzahl ---
    const playerCount = (lobby.players || []).length;
    const waitingForP2 = playerCount < 2;
    
    // Hilfsfunktion um Buttons zu updaten
    const updateInstrBtn = (btn) => {
        if (btn) {
            if (waitingForP2) {
                // Wenn alleine: Button ausgrauen
                btn.disabled = true;
                btn.textContent = "Warten auf 2. Spieler...";
                btn.style.opacity = "0.5";
                btn.style.cursor = "not-allowed";
            } else {
                // Wenn zu zweit: Button aktivieren (sofern nicht gerade geklickt wurde)
                // Wir prüfen auf den Text, um nicht versehentlich den Doppelklick-Schutz zu überschreiben
                if (btn.textContent === "Warten auf 2. Spieler..." || btn.disabled === false) {
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.style.cursor = "pointer";
                    btn.textContent = "Verstanden & Weiter";
                }
            }
        }
    };

    updateInstrBtn(btnInstrNextVideo);
    updateInstrBtn(btnInstrNextText);
    // --------------------------------------------------------

    const isVideoVisible = instrVideoWrap && instrVideoWrap.style.display !== "none";
    const isTextVisible  = instrTextWrap && instrTextWrap.style.display !== "none";
    if (!isVideoVisible && !isTextVisible) {
      if (instrSelectionWrap) instrSelectionWrap.style.display = "block";
    }

    if (btnCloseInstr) {
      btnCloseInstr.style.display = iHaveConfirmedInstr ? "inline-block" : "none";
    }

    // alles andere aus
    if (overlay) overlay.style.display = "none";
    if (!isEnding && mainWrap) mainWrap.style.display = "none";
    if (centerOverlay) centerOverlay.style.display = "none";
    return;
  }

  if (instrOverlay) instrOverlay.style.display = "none";

// =========================================================
// 2) NICHT GESTARTET: READY / COUNTDOWN / PRACTICE_COUNTDOWN
// =========================================================
if (!lobby.started) {
    // Input/Charts reset
    if (offerInput) offerInput.value = "";
    document.querySelectorAll(".bar-gross, .bar-net").forEach(el => (el.style.height = "0%"));
    document.querySelectorAll(".stat-val").forEach(el => (el.textContent = "-"));
    if (oppPriceDisplay) oppPriceDisplay.textContent = "—";

    const isPracticeCd = (lobby.stage === "practice_countdown");
    const isRealCd     = (lobby.stage === "countdown");
    const showCountdown = isPracticeCd || isRealCd;

    // FIX: Wenn das Spiel nicht gestartet ist und kein Countdown läuft,
    // zeigen wir IMMER den Wartebildschirm. Das verhindert den weißen Screen.
    const showWaitingScreen = !showCountdown;

    // --- DOM STEUERUNG ---
    if (overlay) {
        // Overlay Reset
        overlay.style.background = "";
        overlay.style.backdropFilter = "";
        overlay.style.webkitBackdropFilter = "";
        
        // Overlay ist immer sichtbar in dieser Phase (entweder Warten oder Countdown)
        overlay.style.display = "flex";

        if (showCountdown) {
             centerOverlay.classList.add("countdown-backdrop");
             // Overlay selbst transparent halten, um den Body-Hintergrund zu zeigen
             overlay.style.background = "transparent";
             overlay.style.backdropFilter = "none";
             overlay.style.webkitBackdropFilter = "none";
             // Body auf weiß setzen (wichtig, da mainWrap ausgeblendet ist)
             document.body.style.background = "#fff";
        } else {
             centerOverlay.classList.remove("countdown-backdrop");
             document.body.style.background = ""; // Reset
        }
    }

    // Anzeige des Ready-Modals (nur wenn wir warten)
    if (overlayContent) overlayContent.style.display = showWaitingScreen ? "block" : "none";
    
    // Anzeige des Countdowns
    if (centerOverlay && centerTitle) {
        centerOverlay.style.display = showCountdown ? "flex" : "none";
        
        if (showCountdown) {
            const nowSec = Date.now() / 1000;
            const timeRemaining = (lobby.countdown_end_at || 0) - nowSec;
            const countdownText = Math.max(0, Math.ceil(timeRemaining));
            
            // Statischen Text einmal setzen
            if (isPracticeCd) {
                if (centerHeader && centerHeader.textContent !== "Testrunde") {
                   centerHeader.textContent = "Testrunde";
                }
            } else {
                 if (centerHeader) centerHeader.textContent = "";
            }

            // Dynamische Zahl setzen
            centerTitle.textContent = countdownText; 
        }
    }

    // Inhalt Warte-Screen füllen
    if (showWaitingScreen) {
        if (overlayLobbyCode) overlayLobbyCode.textContent = lobby.code;
        
        const readyStatus = (lobby.players || []).map(p => {
            let displayRole = "Lädt...";
            // Rollenanzeige sicherstellen
            if (myRole === "B") displayRole = (p.pid === myPid) ? "Käufer" : "Verkäufer";
            if (myRole === "S") displayRole = (p.pid === myPid) ? "Verkäufer" : "Käufer";
            
            // Fallback, falls Rollen noch nicht verteilt (ganz am Anfang)
            if (!myRole && lobby.pid_label) {
                 const label = lobby.pid_label[p.pid];
                 if(label === "B") displayRole = "Käufer";
                 if(label === "S") displayRole = "Verkäufer";
            }

            const rdy = lobby.ready?.[p.pid] ? "bereit" : "wartet";
            const mark = (p.pid === myPid) ? " (Sie)" : "";
            // Einfärben des Status für bessere Sichtbarkeit
            const statusColor = lobby.ready?.[p.pid] ? "color: #10b981;" : "color: #6b7280;";
            
            return `<div>${displayRole}${mark}: <strong style="${statusColor}">${rdy}</strong></div>`;
        }).join("");

        if (overlayPlayers) overlayPlayers.innerHTML = readyStatus;

        const isReady = !!lobby.ready?.[myPid];
        if (btnToggleReady) {
            btnToggleReady.textContent = isReady ? "Nicht bereit" : "Bereit";
            // Button Style toggeln
            if (isReady) {
                btnToggleReady.classList.add("btn-secondary");
            } else {
                btnToggleReady.classList.remove("btn-secondary");
            }
        }
        if (statusEl) statusEl.textContent = isReady ? "Warten auf Partner..." : "Bitte klicken Sie auf Bereit.";
    }

    if (!isEnding && mainWrap) mainWrap.style.display = "none";
    return;
}
  // =====================================
  // 3) SPIEL LÄUFT (running oder practice)
  // =====================================
  if (overlay) {
    overlay.style.display = "none";
    overlay.style.background = "";
    overlay.style.backdropFilter = "";
    overlay.style.webkitBackdropFilter = "";
  }
  if (centerOverlay) centerOverlay.style.display = "none";
  if (!isEnding && mainWrap) mainWrap.style.display = "block";

  const myDiscRate = lobby.discount_rate_per_role?.[myRole] || 0.0;
  const myCdVal = lobby.cooldown_per_role?.[myRole] || 0.0;
  const oppRoleKey = iAmBuyer ? "S" : "B"; // Rolle des Verhandlungspartners
  const oppDiscRate = lobby.discount_rate_per_role?.[oppRoleKey] || 0.0;
  const oppCdVal = lobby.cooldown_per_role?.[oppRoleKey] || 0.0;
  const hideOpp = !!lobby.hide_opponent_discount;
  const isPractice = (lobby.stage === "practice" || lobby.stage === "practice_countdown");

  if (topRoleDisplay) topRoleDisplay.textContent = `Rolle: ${myRoleName}`;

  // --- BESTIMMUNG DES PARTNER-TITELS (Nur Titelanpassung) ---
  let rightTitle = oppRoleName;
  // FIX: PARTNER-Titel in Testrunde ergänzen (Rechte Seite ist der Partner)
  if (isPractice) {
      rightTitle = rightTitle + " (COMPUTER)";
  }
  // ----------------------------------------------------------

  // Chips Styling (Links: Spieler, Rechts: Partner)
  if (chipLeft) chipLeft.className = iAmBuyer ? "chip chip-buyer" : "chip chip-seller";
  if (chipRight) chipRight.className = iAmBuyer ? "chip chip-seller" : "chip chip-buyer";

  // Linke Seite (SPIELER STATS)
  if (leftRoleTitle) leftRoleTitle.textContent = `${myRoleName}`;
  if (leftStats) {
    // Originale Logik für Spieler-Stats beibehalten
    leftStats.innerHTML = `
      <div>Kosten: ${(myDiscRate * 100).toFixed(2)}%/s</div>
      <div>Wartezeit: ${myCdVal}s</div>
    `;
  }

  // Rechte Seite (PARTNER STATS)
  if (rightRoleTitle) rightRoleTitle.textContent = rightTitle; // <-- VERWENDET DEN ANGEPASSTEN TITEL
  if (rightStats) {
    // Originale Logik für Partner-Stats beibehalten (unverändert)
    if (hideOpp) {
      rightStats.innerHTML = `<div>Wartezeit: ${oppCdVal}s</div>`;
    } else {
      rightStats.innerHTML = `
        <div>Kosten: ${(oppDiscRate * 100).toFixed(2)}%/s</div>
        <div>Wartezeit: ${oppCdVal}s</div>
      `;
    }
  }

  if (myPriceLabel) myPriceLabel.textContent = "Ihr Angebot";
  if (oppPriceLabel) oppPriceLabel.textContent = `Angebot ${oppRoleName}`;

  if (lobby.finished) {
    if (btnOffer) btnOffer.disabled = true;
    if (btnAccept) btnAccept.disabled = true;
    if (myCooldownWrap) myCooldownWrap.style.visibility = "hidden";
    if (oppCooldownWrap) oppCooldownWrap.style.visibility = "hidden";
  }

  const oppOffer = lobby.current_offers ? lobby.current_offers[oppRoleKey] : null;
  if (oppPriceDisplay) oppPriceDisplay.textContent = oppOffer ? oppOffer.price.toFixed(2) : "—";

  // Log Tabelle füllen (für practice wird serverseitig offers gemappt)
  if (offersLogBody) {
    offersLogBody.innerHTML = "";
    (lobby.offers || []).forEach(o => appendOfferLog(o));

    if (lobby.finished && lobby.agreed_price != null && lobby.finished_at) {
      appendAcceptedLog({
        timestamp: lobby.finished_at,
        offer_role: lobby.agreed_offer_role || "??",
        price: lobby.agreed_price
      });
    }
  }

  // Charts aktualisieren (sofort)
  const nowSec = Date.now() / 1000;
  const tRel = lobby.started_at ? (nowSec - lobby.started_at) : 0;
  updateCharts(tRel);
}


  // --- INPUT LISTENER ---
offerInput.addEventListener('input', () => {
    let tRel = 0;
    if (lobby && lobby.started_at) {
        tRel = (Date.now() / 1000) - lobby.started_at;
    }
    updateCharts(tRel);
});

offerInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
        // Eingabe normalisieren (Komma -> Punkt)
        normalizeOfferInput && normalizeOfferInput();
        const price = getPriceFromInput();

        // Nur gültige Preise erlauben
        if (!Number.isFinite(price) || price < 30 || price > 130) {
            showToast("Bitte einen Preis zwischen 30 und 130 eingeben.");
            return;
        }

        // Wenn Button disabled → nichts senden
        if (btnOffer.disabled || !ws) return;

        ws.send(JSON.stringify({ type: "offer", price }));
    }
});


if (btnDismissPractice) {
    btnDismissPractice.addEventListener("click", () => {
      // 1. Overlay ausblenden
      if (practiceEndOverlay) practiceEndOverlay.style.display = "none";
      
      // 2. Flag zurücksetzen
      showingPracticeEnd = false;
      
      // --- FIX ANFANG ---
      // Wir zwingen den Status lokal auf "ready".
      // Damit weiß update_state(), dass es das Warte-Overlay anzeigen soll,
      // anstatt alles auszublenden.
      if (lobby) {
          lobby.stage = "ready";
          lobby.started = false; // Sicherstellen, dass das Spiel als gestoppt gilt
      }
      // --- FIX ENDE ---
      
      // 3. State neu laden -> Jetzt wird der "Ready"-Screen angezeigt
      if (lobby) update_state({lobby: lobby});
    });
  }


function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => { console.log("Verbunden"); };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);

      if (msg.type === "state" || msg.type === "joined") {
        update_state(msg);

      } else if (msg.type === "offer") {
        appendOfferLog(msg.offer);

      } else if (msg.type === "error") {
        showToast(`${msg.msg}`);

      } else if (msg.type === "info") {
        showToast(`${msg.msg}`);
      
      } else if (msg.type === "practice_ended") {
        showingPracticeEnd = true;
        if (practiceEndPriceDisplay) practiceEndPriceDisplay.textContent = msg.price.toFixed(2);
        if (practiceEndOverlay) practiceEndOverlay.style.display = "flex";
        if (lobby) update_state({lobby: lobby});

      } else if (msg.type === "accepted") {
        showToast(`Einigung erreicht`);
        if(msg.price !== undefined) {
             appendAcceptedLog({
                 timestamp: Date.now()/1000,
                 offer_role: (lobby && lobby.last_offer_by_role) ? "?" : "?", 
                 price: msg.price
             });
        }
        startEndAnimationIfNeeded();

      } else if (msg.type === "ended" && msg.reason === "Einigung") {
        if (msg.result) {
          lastEndResult = msg.result;
        }
        startEndAnimationIfNeeded();
      }
    };
    ws.onclose = (e) => { if(e.code!==1000) setTimeout(connect, 2000); };
  }

  if (btnInstrNext) btnInstrNext.addEventListener("click", () => confirmInstructions());
  if (btnToggleReady) btnToggleReady.addEventListener("click", () => { ws && ws.send(JSON.stringify({ type: "toggle_ready" })); });
  
  if (btnOffer) {
    btnOffer.addEventListener("click", () => {
        if (btnOffer.disabled || !ws) return;
        normalizeOfferInput && normalizeOfferInput();
        const price = getPriceFromInput();
        if (!Number.isFinite(price) || price < 30 || price > 130) {
            showToast("Bitte Preis zwischen 30 und 130 eingeben.");
            return; 
        }
        ws.send(JSON.stringify({ type: "offer", price }));
    });
  }

  if (btnAccept) {
    btnAccept.addEventListener("click", () => {
      if (!btnAccept.disabled && ws) ws.send(JSON.stringify({ type: "accept" }));
    });
  }

  if (btnToQuestionnaire) {
    btnToQuestionnaire.addEventListener("click", () => {
        if (lobby && lobby.code && myPid) {
            window.location.href = `/questionnaire/${lobby.code}/${myPid}`;
        }
    });
  }

  connect();
})();