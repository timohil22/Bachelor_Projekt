// static/home.js

(() => {
  const listEl   = document.getElementById('lobbyList');
  const btnNew   = document.getElementById('btnNew');
  const btnReload = document.getElementById('btnReloadLobbies');

  const ov      = document.getElementById('homeOverlay');
  const ovTitle = document.getElementById('homeOvTitle');
  const ovMsg   = document.getElementById('homeOvMsg');
  const ovClose = document.getElementById('homeOvClose');

  // --- DATENSCHUTZ DOM ELEMENTE ---
  const forcedOverlay = document.getElementById('forcedConsentOverlay'); 
  const btnConsentAccept = document.getElementById('btnConsentAccept');
  const btnPrivacyDetails = document.getElementById('btnPrivacyDetails');
  
  const privacyOverlay = document.getElementById('privacyOverlay');
  const btnClosePrivacy = document.getElementById('closePrivacy');
  const openPrivacyLink = document.getElementById('openPrivacyLink');

  let lastOverlayError = null;
  
  // Lokaler Speicher aller bekannten Lobbys (auch volle, damit wir sie filtern können)
  let currentLobbies = [];

  function showOverlay(title, msg){
    lastOverlayError = msg;
    if (ovTitle) ovTitle.textContent = title;
    if (ovMsg)   ovMsg.textContent   = msg;
    if (ov)      ov.classList.add('show');
  }

  if (ovClose) {
    ovClose.addEventListener('click', () => ov.classList.remove('show'));
  }

  // -------------------------------------------------
  // DATENSCHUTZ / CONSENT LOGIK
  // -------------------------------------------------
  function initPrivacy() {
    const hasConsented = localStorage.getItem('research_consent');
    console.log("Datenschutz-Status:", hasConsented ? "Bereits zugestimmt" : "Noch nicht zugestimmt");

    if (!hasConsented) {
      if(forcedOverlay) {
          forcedOverlay.style.display = 'flex';
          document.body.style.overflow = 'hidden';
      }
    } else {
        if(forcedOverlay) forcedOverlay.style.display = 'none';
    }

    if (btnConsentAccept) {
      btnConsentAccept.addEventListener('click', () => {
        localStorage.setItem('research_consent', 'true');
        if(forcedOverlay) forcedOverlay.style.display = 'none';
        document.body.style.overflow = ''; 
      });
    }

    if (btnPrivacyDetails) {
      btnPrivacyDetails.addEventListener('click', () => {
        if(privacyOverlay) privacyOverlay.style.display = 'flex';
      });
    }

    if (openPrivacyLink) {
      openPrivacyLink.addEventListener('click', () => {
        if(privacyOverlay) privacyOverlay.style.display = 'flex';
      });
    }

    if (btnClosePrivacy) {
      btnClosePrivacy.addEventListener('click', () => {
        if(privacyOverlay) privacyOverlay.style.display = 'none';
      });
    }
  }

  // -------------------------------------------------
  // MOBILE ORIENTATION
  // -------------------------------------------------
  function isMobileDevice() {
    return /android|iphone|ipad|ipod|windows phone/i.test(navigator.userAgent);
  }

  let orientationHintShown = false;

  function showOrientationHintOverlay() {
    if (!ov) return;
    if (ovTitle) ovTitle.textContent = "Bitte ins Querformat drehen";
    if (ovMsg) {
      ovMsg.innerHTML = `
        <p style="margin-bottom: 12px;">
          Für diese Studie wird empfohlen, Ihr Smartphone ins Querformat (Landscape) zu drehen.
        </p>
        <div class="phone-orientation-hint">
          <div class="phone-orientation-icon"><div class="phone-screen"></div></div>
          <span>Gerät drehen</span>
        </div>
      `;
    }
    ov.classList.add("show");
  }

  function maybeShowOrientationHint() {
    if (!isMobileDevice()) return;
    const isPortrait = window.matchMedia("(orientation: portrait)").matches;
    if (isPortrait && !orientationHintShown) {
      showOrientationHintOverlay();
      orientationHintShown = true;
    }
  }

  // -------------------------------------------------
  // LOBBY RENDERING
  // -------------------------------------------------
  function createLobbyRow(lobby) {
    const { code, created_at, players, started, finished } = lobby;
    const row = document.createElement('div');
    row.className = 'lobby-row';

    const left = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'lobby-meta';
    title.textContent = `Lobby ${code}`;

    const sub = document.createElement('div');
    sub.className = 'lobby-sub';

    let statusText = 'Wartet auf Spieler';
    // Hier Logik für Anzeige (auch wenn wir volle Lobbys eigentlich ausblenden)
    if (players === 1) statusText = '1 Spieler wartet';
    if (players >= 2)  statusText = 'Voll'; 
    if (started)       statusText = 'Läuft bereits';
    if (finished)      statusText = 'Abgeschlossen';

    const created = new Date(created_at * 1000);
    const createdStr = created.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    sub.textContent = `${statusText} • Erstellt: ${createdStr}`;

    left.appendChild(title);
    left.appendChild(sub);

    const actions = document.createElement('div');
    actions.className = 'lobby-actions';

    const btnJoin = document.createElement('button');
    btnJoin.className = 'btn btn-secondary';
    btnJoin.textContent = 'Beitreten';
    
    // Deaktivieren, wenn voll (Sicherheitsnetz, falls Filter versagt)
    if (players >= 2 || started || finished) {
        btnJoin.disabled = true;
        btnJoin.style.opacity = "0.5";
        btnJoin.textContent = "Voll";
    } else {
        btnJoin.addEventListener('click', () => joinLobby(code, btnJoin));
    }

    actions.appendChild(btnJoin);
    row.appendChild(left);
    row.appendChild(actions);
    return row;
  }

  // Diese Funktion filtert und rendert die Liste neu
  function renderLobbyList(items) {
    // 1. Aktualisiere das globale Gedächtnis
    currentLobbies = items.slice();
    listEl.innerHTML = '';

    // 2. STRIKTER FILTER:
    // Nur Lobbys anzeigen, die NICHT gestartet sind, NICHT beendet sind 
    // UND weniger als 2 Spieler haben.
    // Sobald ein Update kommt mit players=2, fliegt sie hier sofort raus.
    const openLobbies = items.filter(lb => !lb.started && !lb.finished && lb.players < 2);

    if (openLobbies.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'hint';
      empty.textContent = 'Derzeit keine offenen Lobbys.';
      empty.style.textAlign = 'center';
      empty.style.width = '100%';
      empty.style.marginTop = '20px';
      listEl.appendChild(empty);
      return;
    }

    // Sortierung: Neueste oben
    const sorted = [...openLobbies].sort((a, b) => b.created_at - a.created_at);
    sorted.forEach(lb => listEl.appendChild(createLobbyRow(lb)));
  }

  async function loadLobbiesOnceFallback() {
    try {
      const res = await fetch('/lobbies', { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const js = await res.json();
      renderLobbyList(js.lobbies || []);
    } catch (e) {
      if (!lastOverlayError && listEl.innerHTML === '') console.error(e);
    }
  }

  // --- JOIN LOGIK ---
  async function joinLobby(code, btnElement) {
    if (!localStorage.getItem('research_consent')) {
      alert("Bitte stimmen Sie zuerst den Datenschutzbedingungen zu.");
      window.location.reload();
      return;
    }

    // Button sofort deaktivieren, um Doppelklicks zu verhindern
    if(btnElement) {
        btnElement.disabled = true;
        btnElement.textContent = "...";
    }

    try {
      // Race-Condition Check: Wir fragen den Server explizit nach dem Status
      const res = await fetch(`/lobby_status/${encodeURIComponent(code)}`, { cache: 'no-store' });
      
      if (!res.ok) {
        showOverlay('Lobby nicht verfügbar', 'Fehler beim Abruf.');
        // Liste neu laden, da Status wohl veraltet
        loadLobbiesOnceFallback();
        return;
      }
      
      const js = await res.json();
      
      if (js.ok) {
        // Alles gut -> Weiterleitung
        window.location.href = `/lobby/${code}`;
        return;
      }

      // FEHLERBEHANDLUNG (Lobby war doch schon voll)
      if (js.reason === 'full') {
        showOverlay('Lobby voll', 'Jemand war schneller. Die Lobby ist voll.');
        // Diese Lobby sofort lokal aus der Liste entfernen, damit man nicht nochmal klickt
        removeLobbyLocally(code);
      } else if (js.reason === 'running') {
        showOverlay('Verhandlung läuft', 'Diese Verhandlung hat bereits begonnen.');
        removeLobbyLocally(code);
      } else if (js.reason === 'not_found') {
        showOverlay('Lobby nicht gefunden', 'Existiert nicht mehr.');
        removeLobbyLocally(code);
      } else {
        showOverlay('Lobby nicht verfügbar', 'Status unbekannt.');
        loadLobbiesOnceFallback();
      }
    } catch (e) {
      showOverlay('Fehler', 'Verbindungsfehler.');
      if(btnElement) {
          btnElement.disabled = false;
          btnElement.textContent = "Beitreten";
      }
    }
  }

  // Hilfsfunktion: Entfernt eine Lobby sofort aus der Anzeige, ohne auf WS zu warten
  function removeLobbyLocally(code) {
      const idx = currentLobbies.findIndex(x => x.code === code);
      if (idx >= 0) {
          // Wir markieren sie lokal als "voll/finished", damit renderLobbyList sie rauswirft
          currentLobbies[idx].finished = true; 
          renderLobbyList(currentLobbies);
      }
  }

  if (btnNew) {
    btnNew.addEventListener('click', async () => {
      if (!localStorage.getItem('research_consent')) {
         alert("Bitte stimmen Sie zuerst den Datenschutzbedingungen zu.");
         window.location.reload();
         return;
      }

      // Button kurz sperren
      btnNew.disabled = true;

      try {
        const res = await fetch('/new_lobby');
        const js = await res.json();
        if (js.lobby) {
          window.location.href = `/lobby/${js.lobby}`;
        } else {
          showOverlay('Fehler', 'Lobby konnte nicht erstellt werden.');
          btnNew.disabled = false;
        }
      } catch (e) {
        showOverlay('Fehler', 'Lobby konnte nicht erstellt werden.');
        btnNew.disabled = false;
      }
    });
  }

  if (btnReload) {
    btnReload.addEventListener('click', loadLobbiesOnceFallback);
  }

  // --- CHECKBOX LOGIK ---
  const consentCheckbox = document.getElementById('consentCheckbox');
  if (consentCheckbox && btnConsentAccept) {
      consentCheckbox.addEventListener('change', () => {
          if (consentCheckbox.checked) {
              btnConsentAccept.disabled = false;
              btnConsentAccept.style.opacity = '1';
              btnConsentAccept.style.cursor = 'pointer';
          } else {
              btnConsentAccept.disabled = true;
              btnConsentAccept.style.opacity = '0.5';
              btnConsentAccept.style.cursor = 'not-allowed';
          }
      });
  }

  // -------------------------------------------------
  // WEBSOCKET (Echtzeit-Updates)
  // -------------------------------------------------
  const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl   = `${wsProto}://${location.host}/ws/home`;
  let homeWs    = null;

  function connectHomeWs() {
    homeWs = new WebSocket(wsUrl);
    homeWs.onopen = () => console.log('Home-WS verbunden');
    
    homeWs.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }

      // 1. Initiale Liste
      if (msg.type === 'lobbies') {
        renderLobbyList(msg.lobbies || []);
      } 
      // 2. Einzelne Updates (Erstellt ODER Update von Spielerzahlen)
      // WICHTIG: Der Server muss 'lobby_created' oder 'lobby_updated' senden,
      // wenn jemand einer Lobby beitritt.
      else if (msg.type === 'lobby_created' || msg.type === 'lobby_updated') {
        const lb = msg.lobby;
        if (!lb || !lb.code) return;

        // In unserer lokalen Liste aktualisieren oder hinzufügen
        const idx = currentLobbies.findIndex(x => x.code === lb.code);
        if (idx >= 0) {
            currentLobbies[idx] = lb;
        } else {
            currentLobbies.push(lb);
        }
        // Neu rendern -> Filter greift sofort -> Volle Lobbys verschwinden
        renderLobbyList(currentLobbies);
      }
      // 3. Lobby gelöscht
      else if (msg.type === 'lobby_deleted') {
         const code = msg.code;
         currentLobbies = currentLobbies.filter(x => x.code !== code);
         renderLobbyList(currentLobbies);
      }
    };

    homeWs.onclose = (ev) => {
      homeWs = null;
      // Bei Abbruch einmal manuell laden
      loadLobbiesOnceFallback();
      if (ev.code !== 1000) setTimeout(connectHomeWs, 2000);
    };
  }

  // --- INIT ---
  document.addEventListener("DOMContentLoaded", () => {
    initPrivacy();
    maybeShowOrientationHint();
  });
  
  window.addEventListener('orientationchange', () => {
    orientationHintShown = false;
    maybeShowOrientationHint();
  });

  connectHomeWs();

})();