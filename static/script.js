/*
 * RTK Monitor - Frontend
 * Komunikacja: HTTP polling 1 Hz
 */

(function() {
    "use strict";

    var ntripPanelOpen = false;

    // === NTRIP Panel - dziala NIEZALEZNIE od WebSocket ===

    function setupNtripPanel() {
        var toggleBtn = document.getElementById("ntrip-toggle");
        if (toggleBtn) {
            toggleBtn.addEventListener("click", function(e) {
                e.preventDefault();
                ntripPanelOpen = !ntripPanelOpen;
                var panel = document.getElementById("ntrip-panel");
                if (panel) {
                    if (ntripPanelOpen) {
                        panel.classList.remove("hidden");
                    } else {
                        panel.classList.add("hidden");
                    }
                }
            });
        }

        var saveBtn = document.getElementById("btn-save-ntrip");
        if (saveBtn) {
            saveBtn.addEventListener("click", function(e) {
                e.preventDefault();
                saveNtrip(true);
            });
        }

        var stopBtn = document.getElementById("btn-stop-ntrip");
        if (stopBtn) {
            stopBtn.addEventListener("click", function(e) {
                e.preventDefault();
                stopNtrip();
            });
        }
    }

    function loadConfig() {
        fetch("/api/config")
            .then(function(r) { return r.json(); })
            .then(function(cfg) {
                // Zaladuj liste stacji
                var sel = document.getElementById("ntrip-station");
                if (sel && cfg.stations) {
                    sel.innerHTML = "";
                    var keys = Object.keys(cfg.stations);
                    for (var i = 0; i < keys.length; i++) {
                        var id = keys[i];
                        var name = cfg.stations[id];
                        var o = document.createElement("option");
                        o.value = id;
                        o.textContent = id + " - " + name;
                        sel.appendChild(o);
                    }
                }
                // Ustaw wartosci z konfiguracji
                var n = cfg.ntrip;
                if (n) {
                    setVal("ntrip-host", n.host);
                    setVal("ntrip-port", n.port);
                    setVal("ntrip-station", n.station);
                    setVal("ntrip-user", n.username);
                    if (n.password && n.password !== "") {
                        setVal("ntrip-pass", n.password);
                    }
                }
            })
            .catch(function(e) {
                console.error("Blad ladowania konfiguracji:", e);
            });
    }

    function saveNtrip(andStart) {
        var data = {
            host: getVal("ntrip-host"),
            port: parseInt(getVal("ntrip-port")) || 8086,
            station: getVal("ntrip-station"),
            username: getVal("ntrip-user"),
            password: getVal("ntrip-pass"),
            enabled: !!andStart
        };
        var errEl = document.getElementById("ntrip-error");
        if (errEl) errEl.classList.add("hidden");

        fetch("/api/ntrip", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status !== "ok" && errEl) {
                errEl.textContent = res.message || "Blad";
                errEl.classList.remove("hidden");
            }
        })
        .catch(function() {
            if (errEl) {
                errEl.textContent = "Blad komunikacji z serwerem";
                errEl.classList.remove("hidden");
            }
        });
    }

    function stopNtrip() {
        fetch("/api/ntrip/stop", { method: "POST" })
            .catch(function(e) { console.error("Blad stop NTRIP:", e); });
    }

    // === Aktualizacja UI ===

    function updateUI(d) {
        // Fix badge
        var fq = d.fix_quality || 0;
        var label = d.fix_label || "No Fix";
        var badge = document.getElementById("fix-badge");
        if (badge) {
            badge.textContent = label;
            var cls = "fix-badge ";
            if (fq === 4) cls += "fixed";
            else if (fq === 5) cls += "float";
            else if (fq === 2) cls += "dgps";
            else if (fq >= 1) cls += "gps";
            else cls += "nofix";
            badge.className = cls;
        }

        // Satelity
        setText("satellites", (d.satellites_used || 0) + "/" + (d.satellites_visible || 0) + " sat");

        // Pozycja
        setText("lat", d.latitude != null ? d.latitude.toFixed(8) + "\u00B0" : "\u2014");
        setText("lon", d.longitude != null ? d.longitude.toFixed(8) + "\u00B0" : "\u2014");
        setText("alt", d.altitude != null ? d.altitude.toFixed(2) + " m" : "\u2014");
        setText("speed", d.speed_kmh != null ? d.speed_kmh.toFixed(1) + " km/h" : "\u2014");

        // DOP
        updateDOP("hdop", d.hdop);
        updateDOP("pdop", d.pdop);
        updateDOP("vdop", d.vdop);

        // NTRIP
        var ntrip = d.ntrip || {};
        // Fallback: dane moga byc flat (z /api/status)
        if (!d.ntrip && d.ntrip_connected !== undefined) {
            ntrip = {
                connected: d.ntrip_connected,
                bytes_received: d.ntrip_bytes || 0,
                bytes_written: d.ntrip_bytes_written || 0,
                mountpoint: d.ntrip_mountpoint,
                error: d.ntrip_error
            };
        }
        updateNTRIP(ntrip);

        // Diff age
        var diffEl = document.getElementById("diff-age");
        if (diffEl) {
            if (d.diff_age != null) {
                diffEl.textContent = d.diff_age.toFixed(1) + "s";
                diffEl.style.color = d.diff_age < 5 ? "#66bb6a" : d.diff_age < 15 ? "#ffa726" : "#ef5350";
            } else {
                diffEl.textContent = "";
            }
        }

        // Dodatkowe
        setText("course", d.course != null ? d.course.toFixed(1) + "\u00B0" : "\u2014");
        setText("gps-time", d.timestamp || "\u2014");

        // Pomiar
        if (d.measurement) {
            updateMeasureStatus(d.measurement);
        }
    }

    function updateDOP(id, val) {
        var el = document.getElementById(id);
        if (!el) return;
        if (val != null) {
            el.textContent = val.toFixed(1);
            el.className = "dop-value " + (val < 2 ? "dop-good" : val < 5 ? "dop-ok" : val < 10 ? "dop-poor" : "dop-bad");
        } else {
            el.textContent = "\u2014";
            el.className = "dop-value";
        }
    }

    function updateNTRIP(n) {
        var st = document.getElementById("ntrip-status-text");
        var by = document.getElementById("ntrip-bytes");
        var mp = document.getElementById("ntrip-mountpoint");

        if (st) {
            if (n.connected) {
                st.className = "connected";
                st.textContent = "Polaczony";
            } else if (n.error) {
                st.className = "error";
                st.textContent = n.error;
            } else {
                st.className = "";
                st.textContent = "Wylaczony";
            }
        }
        if (by) {
            var parts = [];
            if (n.bytes_received > 0) {
                parts.push("odb: " + (n.bytes_received / 1024).toFixed(1) + " KB");
            }
            if (n.bytes_written > 0) {
                parts.push("wys: " + (n.bytes_written / 1024).toFixed(1) + " KB");
            }
            by.textContent = parts.length > 0 ? "(" + parts.join(" | ") + ")" : "";
        }
        if (mp) {
            mp.textContent = n.mountpoint ? "[" + n.mountpoint + "]" : "";
        }
    }

    // === Polling (1 Hz) ===

    var pollingTimer = null;

    function startPolling() {
        if (pollingTimer) return;
        console.log("RTK Monitor: polling start");
        var dot = document.getElementById("connection-status");

        pollingTimer = setInterval(function() {
            fetch("/api/status")
                .then(function(r) {
                    if (!r.ok) throw new Error("HTTP " + r.status);
                    return r.json();
                })
                .then(function(d) {
                    if (dot) dot.className = "status-dot connected";
                    updateUI(d);
                })
                .catch(function() {
                    if (dot) dot.className = "status-dot disconnected";
                });
        }, 1000);
    }

    // === Helpers ===

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function setVal(id, val) {
        var el = document.getElementById(id);
        if (el && val != null) el.value = val;
    }

    function getVal(id) {
        var el = document.getElementById(id);
        return el ? el.value : "";
    }

    // === Pomiary ===

    var projectOpen = false;
    var measureActive = false;

    function setupMeasurePanel() {
        var toggleBtn = document.getElementById("measure-toggle");
        if (toggleBtn) {
            toggleBtn.addEventListener("click", function(e) {
                e.preventDefault();
                projectOpen = !projectOpen;
                var panel = document.getElementById("project-panel");
                if (panel) {
                    if (projectOpen) {
                        panel.classList.remove("hidden");
                        loadProjects();
                    } else {
                        panel.classList.add("hidden");
                    }
                }
            });
        }

        var createBtn = document.getElementById("btn-create-project");
        if (createBtn) {
            createBtn.addEventListener("click", function(e) {
                e.preventDefault();
                createProject();
            });
        }

        var measureBtn = document.getElementById("btn-measure");
        if (measureBtn) {
            measureBtn.addEventListener("click", function(e) {
                e.preventDefault();
                startMeasurement();
            });
        }

        var cancelBtn = document.getElementById("btn-cancel-measure");
        if (cancelBtn) {
            cancelBtn.addEventListener("click", function(e) {
                e.preventDefault();
                cancelMeasurement();
            });
        }
    }

    function loadProjects() {
        fetch("/api/projects")
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var listEl = document.getElementById("project-list");
                if (listEl && data.projects && data.projects.length > 0) {
                    var html = "<b>Istniejace:</b> ";
                    for (var i = 0; i < data.projects.length; i++) {
                        var p = data.projects[i];
                        html += '<span class="project-item" onclick="document.getElementById(\'project-name\').value=\'' + p.name + '\'">';
                        html += p.name + " (" + p.points + " pkt)</span>";
                        if (i < data.projects.length - 1) html += ", ";
                    }
                    listEl.innerHTML = html;
                }
                if (data.current) {
                    showProjectInfo(data.current.name, data.current.points);
                }
            })
            .catch(function() {});
    }

    function createProject() {
        var name = getVal("project-name");
        if (!name) return;
        var errEl = document.getElementById("project-error");
        if (errEl) errEl.classList.add("hidden");

        fetch("/api/project/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name })
        })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "ok") {
                showProjectInfo(res.name, res.existing_points);
                // Zamknij panel
                projectOpen = false;
                var panel = document.getElementById("project-panel");
                if (panel) panel.classList.add("hidden");
            } else if (errEl) {
                errEl.textContent = res.message || "Blad";
                errEl.classList.remove("hidden");
            }
        })
        .catch(function() {
            if (errEl) {
                errEl.textContent = "Blad komunikacji";
                errEl.classList.remove("hidden");
            }
        });
    }

    function showProjectInfo(name, points) {
        var info = document.getElementById("project-info");
        if (info) {
            info.classList.remove("hidden");
            setText("project-current-name", "Projekt: " + name);
            setText("project-point-count", points + " pkt");
        }
        // Odblokuj kontrolki pomiaru
        var input = document.getElementById("point-name");
        var btn = document.getElementById("btn-measure");
        if (input) input.disabled = false;
        if (btn) btn.disabled = false;
    }

    function startMeasurement() {
        var pointName = getVal("point-name");
        if (!pointName) {
            var input = document.getElementById("point-name");
            if (input) input.focus();
            return;
        }

        fetch("/api/measure/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ point_name: pointName, samples: 10 })
        })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "ok") {
                measureActive = true;
                showMeasureProgress(true);
                hideMeasureResult();
            } else {
                showMeasureResult(res.message || "Blad", true);
            }
        })
        .catch(function() {
            showMeasureResult("Blad komunikacji", true);
        });
    }

    function cancelMeasurement() {
        fetch("/api/measure/cancel", { method: "POST" }).catch(function() {});
        measureActive = false;
        showMeasureProgress(false);
    }

    function showMeasureProgress(show) {
        var prog = document.getElementById("measure-progress");
        var ctrl = document.getElementById("measure-controls");
        if (prog) {
            if (show) prog.classList.remove("hidden");
            else prog.classList.add("hidden");
        }
        if (ctrl) {
            if (show) ctrl.style.display = "none";
            else ctrl.style.display = "";
        }
    }

    function updateMeasureStatus(m) {
        if (!m) return;

        if (m.active) {
            measureActive = true;
            showMeasureProgress(true);
            var pct = Math.round((m.progress / m.required) * 100);
            var fill = document.getElementById("progress-fill");
            if (fill) fill.style.width = pct + "%";
            var txt = m.progress + "/" + m.required + " probek RTK Fixed";
            if (m.rejected > 0) txt += " (odrzucone: " + m.rejected + ")";
            setText("measure-status-text", txt);
        } else if (m.done && measureActive) {
            measureActive = false;
            showMeasureProgress(false);
            showMeasureResult("Punkt '" + m.point_name + "' zapisany!", false);
            // Wyczysc pole nazwy i odswierz licznik
            var input = document.getElementById("point-name");
            if (input) input.value = "";
            loadProjects();
        } else if (m.error && measureActive) {
            measureActive = false;
            showMeasureProgress(false);
            showMeasureResult(m.error, true);
        }
    }

    function showMeasureResult(msg, isError) {
        var el = document.getElementById("measure-result");
        if (el) {
            el.textContent = msg;
            el.className = "measure-result" + (isError ? " error" : "");
            el.classList.remove("hidden");
            // Auto-ukryj po 5s
            setTimeout(function() { el.classList.add("hidden"); }, 5000);
        }
    }

    function hideMeasureResult() {
        var el = document.getElementById("measure-result");
        if (el) el.classList.add("hidden");
    }

    // === Init ===

    function init() {
        console.log("RTK Monitor: init");
        setupNtripPanel();
        setupMeasurePanel();
        loadConfig();
        startPolling();
    }

    // Uruchom po zaladowaniu DOM
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
