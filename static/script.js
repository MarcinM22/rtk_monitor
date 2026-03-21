/*
 * RTK Monitor - Frontend
 * Komunikacja: HTTP polling 1 Hz
 * Nowe: wysokosc anteny, dokladnosc, temp CPU, mapa canvas z DXF
 */

(function() {
    "use strict";

    var ntripPanelOpen = false;

    // === NTRIP Panel ===

    function setupNtripPanel() {
        var toggleBtn = document.getElementById("ntrip-toggle");
        if (toggleBtn) {
            toggleBtn.addEventListener("click", function(e) {
                e.preventDefault();
                ntripPanelOpen = !ntripPanelOpen;
                var panel = document.getElementById("ntrip-panel");
                if (panel) {
                    if (ntripPanelOpen) panel.classList.remove("hidden");
                    else panel.classList.add("hidden");
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
                // Wysokosc anteny
                if (cfg.antenna_height !== undefined) {
                    var ah = document.getElementById("antenna-height");
                    if (ah) ah.value = cfg.antenna_height > 0 ? cfg.antenna_height : "";
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

    // === Wysokosc anteny ===

    function setupAntennaHeight() {
        var btn = document.getElementById("btn-save-antenna");
        if (btn) {
            btn.addEventListener("click", function(e) {
                e.preventDefault();
                var val = parseFloat(document.getElementById("antenna-height").value) || 0;
                fetch("/api/antenna_height", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ height: val })
                })
                .then(function(r) { return r.json(); })
                .then(function(res) {
                    if (res.status === "ok") {
                        btn.textContent = "OK!";
                        setTimeout(function() { btn.textContent = "Zapisz"; }, 1500);
                    } else {
                        alert(res.message || "Blad");
                    }
                })
                .catch(function() { alert("Blad komunikacji"); });
            });
        }
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

        // Dokladnosc estymowana
        var accDisp = document.getElementById("accuracy-display");
        if (d.accuracy_h != null && d.accuracy_v != null) {
            if (accDisp) accDisp.classList.remove("hidden");
            setText("acc-h", "H: \u00B1" + d.accuracy_h.toFixed(3) + " m");
            setText("acc-v", "V: \u00B1" + d.accuracy_v.toFixed(3) + " m");
            // Koloruj
            var accHEl = document.getElementById("acc-h");
            var accVEl = document.getElementById("acc-v");
            if (accHEl) accHEl.className = "acc-val " + accColor(d.accuracy_h);
            if (accVEl) accVEl.className = "acc-val " + accColor(d.accuracy_v);
        } else {
            if (accDisp) accDisp.classList.add("hidden");
        }

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

        // CPU temp
        if (d.cpu_temp != null) {
            var cpuEl = document.getElementById("cpu-temp");
            if (cpuEl) {
                cpuEl.textContent = d.cpu_temp.toFixed(0) + "\u00B0C";
                if (d.cpu_temp < 50) cpuEl.className = "cpu-temp temp-ok";
                else if (d.cpu_temp < 65) cpuEl.className = "cpu-temp temp-warm";
                else if (d.cpu_temp < 75) cpuEl.className = "cpu-temp temp-hot";
                else cpuEl.className = "cpu-temp temp-critical";
            }
        }

        // Dodatkowe
        setText("course", d.course != null ? d.course.toFixed(1) + "\u00B0" : "\u2014");
        setText("gps-time", d.timestamp || "\u2014");

        // Pomiar
        if (d.measurement) updateMeasureStatus(d.measurement);

        // Wytyczanie
        if (d.stakeout) updateStakeout(d.stakeout);
    }

    function accColor(val) {
        if (val <= 0.03) return "acc-excellent";
        if (val <= 0.05) return "acc-good";
        if (val <= 0.10) return "acc-ok";
        return "acc-poor";
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
            if (n.bytes_received > 0) parts.push("odb: " + (n.bytes_received / 1024).toFixed(1) + " KB");
            if (n.bytes_written > 0) parts.push("wys: " + (n.bytes_written / 1024).toFixed(1) + " KB");
            by.textContent = parts.length > 0 ? "(" + parts.join(" | ") + ")" : "";
        }
        if (mp) mp.textContent = n.mountpoint ? "[" + n.mountpoint + "]" : "";
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
            var input = document.getElementById("point-name");
            if (input) input.value = "";
            loadProjects();
            if (pointsOpen) loadPoints();
            if (mapOpen) loadMapData();
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
            setTimeout(function() { el.classList.add("hidden"); }, 5000);
        }
    }

    function hideMeasureResult() {
        var el = document.getElementById("measure-result");
        if (el) el.classList.add("hidden");
    }

    // === Wytyczanie ===

    var stakeoutPanelOpen = false;

    function setupStakeoutPanel() {
        var toggleBtn = document.getElementById("stakeout-toggle");
        if (toggleBtn) {
            toggleBtn.addEventListener("click", function(e) {
                e.preventDefault();
                stakeoutPanelOpen = !stakeoutPanelOpen;
                var panel = document.getElementById("stakeout-panel");
                if (panel) {
                    if (stakeoutPanelOpen) {
                        panel.classList.remove("hidden");
                        loadStakeoutSources();
                    } else {
                        panel.classList.add("hidden");
                    }
                }
            });
        }

        var srcSel = document.getElementById("stakeout-source");
        if (srcSel) {
            srcSel.addEventListener("change", function() {
                showStakeoutSource(this.value);
            });
        }

        var fileSel = document.getElementById("stakeout-file");
        if (fileSel) {
            fileSel.addEventListener("change", function() {
                if (this.value) loadStakeoutFilePoints(this.value);
            });
        }

        var startBtn = document.getElementById("btn-stakeout-start");
        if (startBtn) {
            startBtn.addEventListener("click", function(e) {
                e.preventDefault();
                startStakeout();
            });
        }

        var stopBtn = document.getElementById("btn-stakeout-stop");
        if (stopBtn) {
            stopBtn.addEventListener("click", function(e) {
                e.preventDefault();
                stopStakeout();
            });
        }
    }

    function showStakeoutSource(src) {
        var panels = ['stakeout-manual', 'stakeout-from-project', 'stakeout-from-file'];
        var map = { manual: 'stakeout-manual', project: 'stakeout-from-project', file: 'stakeout-from-file' };
        for (var i = 0; i < panels.length; i++) {
            var el = document.getElementById(panels[i]);
            if (el) {
                if (panels[i] === map[src]) el.classList.remove("hidden");
                else el.classList.add("hidden");
            }
        }
    }

    function loadStakeoutSources() {
        fetch("/api/points").then(function(r) { return r.json(); }).then(function(data) {
            var sel = document.getElementById("stakeout-project-point");
            if (sel && data.points) {
                sel.innerHTML = '<option value="">-- wybierz punkt --</option>';
                for (var i = 0; i < data.points.length; i++) {
                    var p = data.points[i];
                    var o = document.createElement("option");
                    o.value = JSON.stringify({name: p.name, x: p.x, y: p.y, h: p.h});
                    o.textContent = p.name + " (X:" + (p.x ? p.x.toFixed(1) : "?") + " Y:" + (p.y ? p.y.toFixed(1) : "?") + ")";
                    sel.appendChild(o);
                }
            }
        }).catch(function() {});

        fetch("/api/stakeout/files").then(function(r) { return r.json(); }).then(function(data) {
            var sel = document.getElementById("stakeout-file");
            if (sel && data.files) {
                sel.innerHTML = '<option value="">-- wybierz plik --</option>';
                for (var i = 0; i < data.files.length; i++) {
                    var f = data.files[i];
                    var o = document.createElement("option");
                    o.value = f.name;
                    o.textContent = f.name + " (" + f.points + " pkt)";
                    sel.appendChild(o);
                }
            }
        }).catch(function() {});
    }

    function loadStakeoutFilePoints(filename) {
        fetch("/api/stakeout/file/" + encodeURIComponent(filename))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var sel = document.getElementById("stakeout-file-point");
                if (sel && data.points) {
                    sel.innerHTML = '<option value="">-- wybierz punkt --</option>';
                    for (var i = 0; i < data.points.length; i++) {
                        var p = data.points[i];
                        var o = document.createElement("option");
                        o.value = JSON.stringify({name: p.name, x: p.x, y: p.y, h: p.h});
                        o.textContent = p.name + " (X:" + p.x.toFixed(1) + " Y:" + p.y.toFixed(1) + ")";
                        sel.appendChild(o);
                    }
                }
            })
            .catch(function() {});
    }

    function startStakeout() {
        var src = getVal("stakeout-source");
        var target = null;

        if (src === "manual") {
            var name = getVal("stakeout-name") || "Reczny";
            var x = parseFloat(getVal("stakeout-x"));
            var y = parseFloat(getVal("stakeout-y"));
            var h = getVal("stakeout-h") ? parseFloat(getVal("stakeout-h")) : null;
            if (isNaN(x) || isNaN(y)) { alert("Podaj X i Y"); return; }
            target = {name: name, x: x, y: y, h: h};
        } else if (src === "project") {
            var val = getVal("stakeout-project-point");
            if (!val) { alert("Wybierz punkt"); return; }
            target = JSON.parse(val);
        } else if (src === "file") {
            var val2 = getVal("stakeout-file-point");
            if (!val2) { alert("Wybierz punkt"); return; }
            target = JSON.parse(val2);
        }

        if (!target) return;

        fetch("/api/stakeout/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(target)
        })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "ok") {
                stakeoutPanelOpen = false;
                var panel = document.getElementById("stakeout-panel");
                if (panel) panel.classList.add("hidden");
            } else {
                alert(res.message || "Blad");
            }
        })
        .catch(function() { alert("Blad komunikacji"); });
    }

    function stopStakeout() {
        fetch("/api/stakeout/stop", { method: "POST" }).catch(function() {});
        var disp = document.getElementById("stakeout-display");
        if (disp) disp.classList.add("hidden");
    }

    function updateStakeout(s) {
        var disp = document.getElementById("stakeout-display");
        if (!s || !s.active) {
            if (disp) disp.classList.add("hidden");
            return;
        }
        if (disp) disp.classList.remove("hidden");

        setText("stakeout-target-name", "Cel: " + s.name);

        if (s.dN !== undefined && s.dN !== null) {
            var absN = Math.abs(s.dN);
            var dirN = s.dN >= 0 ? "N" : "S";
            var nsEl = document.getElementById("stakeout-ns");
            var nsLbl = document.getElementById("stakeout-ns-label");
            if (nsEl) {
                nsEl.textContent = formatDist(absN);
                nsEl.className = "stakeout-value " + (absN < 0.05 ? "on-point" : (s.dN >= 0 ? "go-north" : "go-south"));
            }
            if (nsLbl) nsLbl.textContent = dirN + " (" + (s.dN >= 0 ? "idz polnoc" : "idz poludnie") + ")";

            var absE = Math.abs(s.dE);
            var dirE = s.dE >= 0 ? "E" : "W";
            var ewEl = document.getElementById("stakeout-ew");
            var ewLbl = document.getElementById("stakeout-ew-label");
            if (ewEl) {
                ewEl.textContent = formatDist(absE);
                ewEl.className = "stakeout-value " + (absE < 0.05 ? "on-point" : (s.dE >= 0 ? "go-east" : "go-west"));
            }
            if (ewLbl) ewLbl.textContent = dirE + " (" + (s.dE >= 0 ? "idz wschod" : "idz zachod") + ")";

            setText("stakeout-dist", formatDist(s.dist2d));
        }

        var udEl = document.getElementById("stakeout-ud");
        var udLbl = document.getElementById("stakeout-ud-label");
        if (s.dH !== undefined && s.dH !== null) {
            var absH = Math.abs(s.dH);
            if (udEl) {
                udEl.textContent = formatDist(absH);
                udEl.className = "stakeout-value " + (absH < 0.05 ? "on-point" : (s.dH >= 0 ? "go-up" : "go-down"));
            }
            if (udLbl) udLbl.textContent = s.dH >= 0 ? "W gore" : "W dol";
        } else {
            if (udEl) { udEl.textContent = "---"; udEl.className = "stakeout-value"; }
            if (udLbl) udLbl.textContent = "Wys.";
        }
    }

    function formatDist(m) {
        if (m < 0.01) return "0.000 m";
        if (m < 1.0) return m.toFixed(3) + " m";
        if (m < 100) return m.toFixed(2) + " m";
        return m.toFixed(1) + " m";
    }

    // === Pomierzone punkty ===

    var pointsOpen = false;

    function setupPointsPanel() {
        var toggleBtn = document.getElementById("points-toggle");
        if (toggleBtn) {
            toggleBtn.addEventListener("click", function(e) {
                e.preventDefault();
                pointsOpen = !pointsOpen;
                var wrap = document.getElementById("points-table-wrap");
                if (wrap) {
                    if (pointsOpen) {
                        wrap.classList.remove("hidden");
                        toggleBtn.textContent = "Ukryj";
                        loadPoints();
                    } else {
                        wrap.classList.add("hidden");
                        toggleBtn.textContent = "Pokaz";
                    }
                }
            });
        }
    }

    function loadPoints() {
        fetch("/api/points").then(function(r) { return r.json(); }).then(function(data) {
            var tbody = document.getElementById("points-tbody");
            var empty = document.getElementById("points-empty");
            if (!tbody) return;
            tbody.innerHTML = "";
            if (!data.points || data.points.length === 0) {
                if (empty) empty.style.display = "";
                return;
            }
            if (empty) empty.style.display = "none";
            for (var i = 0; i < data.points.length; i++) {
                var p = data.points[i];
                var tr = document.createElement("tr");
                tr.innerHTML = "<td>" + p.id + "</td>" +
                    "<td>" + p.name + "</td>" +
                    "<td>" + (p.x ? p.x.toFixed(3) : "-") + "</td>" +
                    "<td>" + (p.y ? p.y.toFixed(3) : "-") + "</td>" +
                    "<td>" + (p.h != null ? p.h.toFixed(3) : "-") + "</td>" +
                    "<td>" + (p.antenna_h ? p.antenna_h.toFixed(2) : "-") + "</td>" +
                    "<td>" + (p.acc_h ? p.acc_h.toFixed(4) : "-") + "</td>";
                tbody.appendChild(tr);
            }
        }).catch(function() {});
    }

    // ===================================================================
    //  MAPA - Canvas z DXF overlay, pan/zoom, dotyk Android Chrome
    // ===================================================================

    var mapOpen = false;
    var mapCanvas = null;
    var mapCtx = null;
    var mapPoints = [];
    var mapDxfEntities = [];
    var mapDxfLayers = {};  // layer -> bool (visible)
    var mapCurrentDxf = "";

    // View transform
    var mapView = {
        cx: 0, cy: 0,  // srodek widoku w ukladzie PL-2000
        scale: 1,       // pikseli na metr
        w: 580, h: 400
    };

    // Touch / mouse state
    var mapDrag = { active: false, startX: 0, startY: 0, startCx: 0, startCy: 0 };
    var mapPinch = { active: false, startDist: 0, startScale: 0 };

    function setupMapPanel() {
        var toggleBtn = document.getElementById("map-toggle");
        if (toggleBtn) {
            toggleBtn.addEventListener("click", function(e) {
                e.preventDefault();
                mapOpen = !mapOpen;
                var cont = document.getElementById("map-container");
                if (cont) {
                    if (mapOpen) {
                        cont.classList.remove("hidden");
                        toggleBtn.textContent = "Ukryj";
                        initMapCanvas();
                        loadMapData();
                    } else {
                        cont.classList.add("hidden");
                        toggleBtn.textContent = "Pokaz";
                    }
                }
            });
        }

        // DXF select
        var dxfSel = document.getElementById("map-dxf-select");
        if (dxfSel) {
            dxfSel.addEventListener("change", function() {
                mapCurrentDxf = this.value;
                if (mapCurrentDxf) {
                    loadDxfFile(mapCurrentDxf);
                } else {
                    mapDxfEntities = [];
                    drawMap();
                }
            });
        }

        // Upload DXF
        var uploadBtn = document.getElementById("btn-upload-dxf");
        var fileInput = document.getElementById("dxf-file-input");
        if (uploadBtn && fileInput) {
            uploadBtn.addEventListener("click", function() { fileInput.click(); });
            fileInput.addEventListener("change", function() {
                if (this.files.length > 0) uploadDxf(this.files[0]);
            });
        }

        // Fit button
        var fitBtn = document.getElementById("btn-map-fit");
        if (fitBtn) {
            fitBtn.addEventListener("click", function(e) {
                e.preventDefault();
                fitMapView();
                drawMap();
            });
        }

        // Show points checkbox
        var showPts = document.getElementById("map-show-points");
        if (showPts) {
            showPts.addEventListener("change", function() { drawMap(); });
        }
    }

    function initMapCanvas() {
        mapCanvas = document.getElementById("map-canvas");
        if (!mapCanvas) return;

        // Dopasuj canvas do kontenera
        var parent = mapCanvas.parentElement;
        var w = parent.clientWidth - 4;
        if (w < 200) w = 200;
        mapCanvas.width = w;
        mapCanvas.height = Math.min(400, Math.round(w * 0.7));
        mapView.w = mapCanvas.width;
        mapView.h = mapCanvas.height;

        mapCtx = mapCanvas.getContext("2d");

        // === Touch events (Android Chrome) ===
        mapCanvas.addEventListener("touchstart", onMapTouchStart, { passive: false });
        mapCanvas.addEventListener("touchmove", onMapTouchMove, { passive: false });
        mapCanvas.addEventListener("touchend", onMapTouchEnd, { passive: false });

        // === Mouse events (desktop) ===
        mapCanvas.addEventListener("mousedown", onMapMouseDown);
        mapCanvas.addEventListener("mousemove", onMapMouseMove);
        mapCanvas.addEventListener("mouseup", onMapMouseUp);
        mapCanvas.addEventListener("mouseleave", onMapMouseUp);
        mapCanvas.addEventListener("wheel", onMapWheel, { passive: false });
    }

    // --- Touch handlers ---

    function onMapTouchStart(e) {
        e.preventDefault();
        if (e.touches.length === 1) {
            var t = e.touches[0];
            mapDrag.active = true;
            mapDrag.startX = t.clientX;
            mapDrag.startY = t.clientY;
            mapDrag.startCx = mapView.cx;
            mapDrag.startCy = mapView.cy;
        } else if (e.touches.length === 2) {
            mapDrag.active = false;
            mapPinch.active = true;
            var dx = e.touches[0].clientX - e.touches[1].clientX;
            var dy = e.touches[0].clientY - e.touches[1].clientY;
            mapPinch.startDist = Math.sqrt(dx * dx + dy * dy);
            mapPinch.startScale = mapView.scale;
        }
    }

    function onMapTouchMove(e) {
        e.preventDefault();
        if (mapDrag.active && e.touches.length === 1) {
            var t = e.touches[0];
            var dx = t.clientX - mapDrag.startX;
            var dy = t.clientY - mapDrag.startY;
            // Na mapie: Y rosnie w gore (PL-2000 X=northing), ekran Y rosnie w dol
            mapView.cx = mapDrag.startCx - dx / mapView.scale;
            mapView.cy = mapDrag.startCy + dy / mapView.scale;
            drawMap();
        } else if (mapPinch.active && e.touches.length === 2) {
            var dx2 = e.touches[0].clientX - e.touches[1].clientX;
            var dy2 = e.touches[0].clientY - e.touches[1].clientY;
            var dist = Math.sqrt(dx2 * dx2 + dy2 * dy2);
            var ratio = dist / mapPinch.startDist;
            mapView.scale = Math.max(0.001, Math.min(1000, mapPinch.startScale * ratio));
            drawMap();
        }
    }

    function onMapTouchEnd(e) {
        if (e.touches.length < 2) mapPinch.active = false;
        if (e.touches.length < 1) mapDrag.active = false;
    }

    // --- Mouse handlers ---

    function onMapMouseDown(e) {
        mapDrag.active = true;
        mapDrag.startX = e.clientX;
        mapDrag.startY = e.clientY;
        mapDrag.startCx = mapView.cx;
        mapDrag.startCy = mapView.cy;
    }

    function onMapMouseMove(e) {
        if (!mapDrag.active) {
            // Pokaz wspolrzedne pod kursorem
            showMapCoords(e);
            return;
        }
        var dx = e.clientX - mapDrag.startX;
        var dy = e.clientY - mapDrag.startY;
        mapView.cx = mapDrag.startCx - dx / mapView.scale;
        mapView.cy = mapDrag.startCy + dy / mapView.scale;
        drawMap();
    }

    function onMapMouseUp() {
        mapDrag.active = false;
    }

    function onMapWheel(e) {
        e.preventDefault();
        var factor = e.deltaY > 0 ? 0.85 : 1.18;
        mapView.scale = Math.max(0.001, Math.min(1000, mapView.scale * factor));
        drawMap();
    }

    function showMapCoords(e) {
        var rect = mapCanvas.getBoundingClientRect();
        var px = e.clientX - rect.left;
        var py = e.clientY - rect.top;
        // Konwertuj piksel -> PL-2000 (Y=easting na osi X ekranu, X=northing na osi Y ekranu odwroconej)
        var worldY = mapView.cx + (px - mapView.w / 2) / mapView.scale;
        var worldX = mapView.cy + (mapView.h / 2 - py) / mapView.scale;
        var el = document.getElementById("map-coords");
        if (el) el.textContent = "X:" + worldX.toFixed(1) + " Y:" + worldY.toFixed(1);
    }

    // --- Data loading ---

    function loadMapData() {
        fetch("/api/map/data")
            .then(function(r) { return r.json(); })
            .then(function(data) {
                mapPoints = data.points || [];

                // Aktualizuj select DXF
                var sel = document.getElementById("map-dxf-select");
                if (sel) {
                    var prev = sel.value;
                    sel.innerHTML = '<option value="">-- DXF (brak) --</option>';
                    if (data.dxf_files) {
                        for (var i = 0; i < data.dxf_files.length; i++) {
                            var o = document.createElement("option");
                            o.value = data.dxf_files[i];
                            o.textContent = data.dxf_files[i];
                            sel.appendChild(o);
                        }
                    }
                    if (prev) sel.value = prev;
                }

                // Dopasuj widok jesli pierwszy raz
                if (mapView.scale === 1 && mapPoints.length > 0) {
                    fitMapView();
                }

                drawMap();
            })
            .catch(function() {});
    }

    function loadDxfFile(filename) {
        fetch("/api/map/dxf/" + encodeURIComponent(filename))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                mapDxfEntities = data.entities || [];
                // Zbierz warstwy
                mapDxfLayers = {};
                for (var i = 0; i < mapDxfEntities.length; i++) {
                    var layer = mapDxfEntities[i].layer || "0";
                    if (!(layer in mapDxfLayers)) mapDxfLayers[layer] = true;
                }
                if (mapPoints.length === 0 && mapDxfEntities.length > 0) {
                    fitMapView();
                }
                drawMap();
            })
            .catch(function() {});
    }

    function uploadDxf(file) {
        var fd = new FormData();
        fd.append("file", file);
        fetch("/api/project/upload_dxf", { method: "POST", body: fd })
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.status === "ok") {
                    loadMapData();
                } else {
                    alert(res.message || "Blad wgrywania DXF");
                }
            })
            .catch(function() { alert("Blad komunikacji"); });
    }

    // --- View fitting ---

    function fitMapView() {
        var xs = [], ys = [];

        // Punkty projektu (Y=easting -> os X ekranu, X=northing -> os Y ekranu)
        for (var i = 0; i < mapPoints.length; i++) {
            var p = mapPoints[i];
            if (p.y != null && p.x != null) {
                xs.push(p.y);  // easting -> horizontal
                ys.push(p.x);  // northing -> vertical
            }
        }

        // DXF entities
        for (var j = 0; j < mapDxfEntities.length; j++) {
            var e = mapDxfEntities[j];
            if (e.type === 'line') {
                xs.push(e.y1, e.y2);
                ys.push(e.x1, e.x2);
            } else if (e.type === 'polyline' && e.points) {
                for (var k = 0; k < e.points.length; k++) {
                    xs.push(e.points[k][1]);
                    ys.push(e.points[k][0]);
                }
            } else if (e.type === 'point' || e.type === 'text') {
                xs.push(e.y);
                ys.push(e.x);
            } else if (e.type === 'circle' || e.type === 'arc') {
                xs.push(e.cy - e.r, e.cy + e.r);
                ys.push(e.cx - e.r, e.cx + e.r);
            }
        }

        if (xs.length === 0) return;

        var minX = Math.min.apply(null, xs);
        var maxX = Math.max.apply(null, xs);
        var minY = Math.min.apply(null, ys);
        var maxY = Math.max.apply(null, ys);

        var rangeX = maxX - minX || 10;
        var rangeY = maxY - minY || 10;

        // Dodaj margines 10%
        var margin = 0.1;
        rangeX *= (1 + margin * 2);
        rangeY *= (1 + margin * 2);

        mapView.cx = (minX + maxX) / 2;
        mapView.cy = (minY + maxY) / 2;
        mapView.scale = Math.min(mapView.w / rangeX, mapView.h / rangeY);
    }

    // --- Drawing ---

    function drawMap() {
        if (!mapCtx || !mapCanvas) return;
        var ctx = mapCtx;
        var w = mapView.w;
        var h = mapView.h;

        // Czyszczenie
        ctx.fillStyle = "#0a1520";
        ctx.fillRect(0, 0, w, h);

        // Grid
        drawMapGrid(ctx, w, h);

        // DXF
        if (mapDxfEntities.length > 0) {
            drawDxfEntities(ctx, w, h);
        }

        // Punkty projektu
        var showPts = document.getElementById("map-show-points");
        if (showPts && showPts.checked && mapPoints.length > 0) {
            drawMapPoints(ctx, w, h);
        }

        // Skala
        drawMapScale(ctx, w, h);
    }

    function worldToScreen(worldY, worldX) {
        // worldY = easting (PL-2000 Y) -> ekranowa os X
        // worldX = northing (PL-2000 X) -> ekranowa os Y (odwrocona)
        var sx = (worldY - mapView.cx) * mapView.scale + mapView.w / 2;
        var sy = mapView.h / 2 - (worldX - mapView.cy) * mapView.scale;
        return [sx, sy];
    }

    function drawMapGrid(ctx, w, h) {
        // Oblicz odpowiedni krok siatki
        var pixPerMeter = mapView.scale;
        var steps = [0.1, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000];
        var gridStep = 100;
        for (var i = 0; i < steps.length; i++) {
            if (steps[i] * pixPerMeter > 40) {
                gridStep = steps[i];
                break;
            }
        }

        // Zakres widoczny
        var halfW = w / 2 / pixPerMeter;
        var halfH = h / 2 / pixPerMeter;
        var left = mapView.cx - halfW;
        var right = mapView.cx + halfW;
        var bottom = mapView.cy - halfH;
        var top = mapView.cy + halfH;

        ctx.strokeStyle = "rgba(255,255,255,0.06)";
        ctx.lineWidth = 1;

        // Pionowe (easting)
        var startE = Math.floor(left / gridStep) * gridStep;
        for (var e = startE; e <= right; e += gridStep) {
            var sx = (e - mapView.cx) * pixPerMeter + w / 2;
            ctx.beginPath();
            ctx.moveTo(sx, 0);
            ctx.lineTo(sx, h);
            ctx.stroke();
        }

        // Poziome (northing)
        var startN = Math.floor(bottom / gridStep) * gridStep;
        for (var n = startN; n <= top; n += gridStep) {
            var sy = h / 2 - (n - mapView.cy) * pixPerMeter;
            ctx.beginPath();
            ctx.moveTo(0, sy);
            ctx.lineTo(w, sy);
            ctx.stroke();
        }
    }

    function drawMapPoints(ctx, w, h) {
        for (var i = 0; i < mapPoints.length; i++) {
            var p = mapPoints[i];
            if (p.x == null || p.y == null) continue;

            var pos = worldToScreen(p.y, p.x);
            var sx = pos[0], sy = pos[1];

            // Poza ekranem?
            if (sx < -20 || sx > w + 20 || sy < -20 || sy > h + 20) continue;

            // Punkt
            ctx.fillStyle = "#4fc3f7";
            ctx.beginPath();
            ctx.arc(sx, sy, 5, 0, Math.PI * 2);
            ctx.fill();

            // Obwodka
            ctx.strokeStyle = "#fff";
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Etykieta
            ctx.fillStyle = "#e0e8f0";
            ctx.font = "11px sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(p.name || p.id, sx + 8, sy - 4);
        }
    }

    function drawDxfEntities(ctx, w, h) {
        ctx.strokeStyle = "#ffa726";
        ctx.lineWidth = 1;
        ctx.fillStyle = "#ffa726";

        for (var i = 0; i < mapDxfEntities.length; i++) {
            var e = mapDxfEntities[i];
            var layer = e.layer || "0";
            if (mapDxfLayers[layer] === false) continue;

            if (e.type === 'line') {
                var p1 = worldToScreen(e.y1, e.x1);
                var p2 = worldToScreen(e.y2, e.x2);
                ctx.beginPath();
                ctx.moveTo(p1[0], p1[1]);
                ctx.lineTo(p2[0], p2[1]);
                ctx.stroke();
            } else if (e.type === 'polyline' && e.points && e.points.length > 1) {
                ctx.beginPath();
                var first = worldToScreen(e.points[0][1], e.points[0][0]);
                ctx.moveTo(first[0], first[1]);
                for (var j = 1; j < e.points.length; j++) {
                    var pt = worldToScreen(e.points[j][1], e.points[j][0]);
                    ctx.lineTo(pt[0], pt[1]);
                }
                if (e.closed) ctx.closePath();
                ctx.stroke();
            } else if (e.type === 'point') {
                var pp = worldToScreen(e.y, e.x);
                ctx.beginPath();
                ctx.arc(pp[0], pp[1], 3, 0, Math.PI * 2);
                ctx.fill();
            } else if (e.type === 'circle') {
                var cc = worldToScreen(e.cy, e.cx);
                var rPx = e.r * mapView.scale;
                if (rPx > 0.5 && rPx < 5000) {
                    ctx.beginPath();
                    ctx.arc(cc[0], cc[1], rPx, 0, Math.PI * 2);
                    ctx.stroke();
                }
            } else if (e.type === 'arc') {
                var ac = worldToScreen(e.cy, e.cx);
                var arPx = e.r * mapView.scale;
                if (arPx > 0.5 && arPx < 5000) {
                    var sa = -e.end_angle * Math.PI / 180;
                    var ea = -e.start_angle * Math.PI / 180;
                    ctx.beginPath();
                    ctx.arc(ac[0], ac[1], arPx, sa, ea);
                    ctx.stroke();
                }
            } else if (e.type === 'text') {
                var tp = worldToScreen(e.y, e.x);
                var fontSize = Math.max(8, Math.min(14, e.height * mapView.scale));
                ctx.font = fontSize + "px sans-serif";
                ctx.fillStyle = "#ffa726";
                ctx.textAlign = "left";
                ctx.fillText(e.text, tp[0], tp[1]);
            }
        }
    }

    function drawMapScale(ctx, w, h) {
        // Belka skali w lewym dolnym rogu
        var pixPerMeter = mapView.scale;
        var targetPx = 100;
        var dist = targetPx / pixPerMeter;

        // Zaokraglij do ladnej wartosci
        var niceVals = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
        var niceDist = niceVals[niceVals.length - 1];
        for (var i = 0; i < niceVals.length; i++) {
            if (niceVals[i] >= dist * 0.5) {
                niceDist = niceVals[i];
                break;
            }
        }
        var barPx = niceDist * pixPerMeter;

        var x0 = 10, y0 = h - 12;
        ctx.strokeStyle = "#8899aa";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x0 + barPx, y0);
        ctx.moveTo(x0, y0 - 4);
        ctx.lineTo(x0, y0 + 4);
        ctx.moveTo(x0 + barPx, y0 - 4);
        ctx.lineTo(x0 + barPx, y0 + 4);
        ctx.stroke();

        ctx.fillStyle = "#8899aa";
        ctx.font = "10px sans-serif";
        ctx.textAlign = "center";
        var label = niceDist >= 1000 ? (niceDist / 1000) + " km" : niceDist + " m";
        ctx.fillText(label, x0 + barPx / 2, y0 - 6);

        // Info skali
        var scaleEl = document.getElementById("map-scale");
        if (scaleEl) scaleEl.textContent = "1px = " + (1 / pixPerMeter).toFixed(2) + " m";
    }

    // === Init ===

    function init() {
        console.log("RTK Monitor: init");
        setupNtripPanel();
        setupMeasurePanel();
        setupAntennaHeight();
        setupStakeoutPanel();
        setupPointsPanel();
        setupMapPanel();
        loadConfig();
        startPolling();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
