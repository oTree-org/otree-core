const RECENT_MSEC = 10 * 1000;

function initWebSocket(socketUrl, $tbody, visitedParticipants, $msgRefreshed) {
    monitorSocket = makeReconnectingWebSocket(socketUrl);
    monitorSocket.onmessage = function (e) {
        var data = JSON.parse(e.data);
        if (data.type === 'update_notes') {
            updateNotes($tbody[0], data.ids, data.note);
        } else {
            let updatedIds = refreshTable(data.rows, $tbody, visitedParticipants);
            let msg = recentlyActiveParticipantsMsg(updatedIds);
            // we shouldn't write an empty msg, because that would cause
            // the div to shrink
            if (msg) {
                $msgRefreshed.text(msg);
                $msgRefreshed.stop(0, 0);
                $msgRefreshed.css('opacity', 1);
                $msgRefreshed.fadeTo(RECENT_MSEC, 0);
            }
        }
    }
}

function recentlyActiveParticipantsMsg(newIds) {
    if (newIds.length === 0) return '';
    let d = recentlyActiveParticipants;
    let now = Date.now();
    for (let id of newIds) {
        d[id] = now;
    }
    for (let [k, v] of Object.entries(d)) {
        if (v < now - RECENT_MSEC) delete d[k];
    }
    let listing = Object.keys(d).slice(0, 10).sort().map(id => 'P' + id.toString()).join(', ');
    return `Updates: ${listing}`;
}

function advanceSlowestUsers() {
    let csrftoken = document.querySelector("[name=csrftoken]").value;
    let serverErrorDiv = $("#auto_advance_server_error");
    $.ajax({
        url: advanceUrl,
        type: 'POST',
        data: {
            csrftoken: csrftoken
        },
        error: function (jqXHR, textStatus) {
            serverErrorDiv.show();
            // enable the button so they can try again?
        },
        success: function () {
            serverErrorDiv.hide();
        }
    });
}

function getNthBodyRowSelector(n) {
    return `tr:nth-of-type(${n + 1})`;
    //return `tr:eq(${n})`;
}

function updateNotes(tbody, ids, note) {
    for (let id of ids) {
        let index = visitedParticipants.indexOf(id);
        if (index >= 0) {
            updateNthRow(tbody, index, {_monitor_note: note});
        }
    }
}

function updateNthRow(tbody, n, row) {
    let didUpdate = false;
    let nthBodyRow = tbody.querySelector(getNthBodyRowSelector(n));
    for (let fieldName of Object.keys(row)) {
        let cellToUpdate = nthBodyRow.querySelector(`td[data-field='${fieldName}']`);
        let prev = cellToUpdate.dataset.value;
        let cur = row[fieldName];
        let dataSetVal = makeCellDatasetValue(cur);
        if (prev !== dataSetVal) {
            cellToUpdate.dataset.value = dataSetVal;
            cellToUpdate.innerHTML = makeCellDisplayValue(cur, fieldName);
            flashGreen($(cellToUpdate));
            didUpdate = true;
        }
    }
    return didUpdate;
}

function refreshTable(new_json, $tbody, visitedParticipants) {
    let updatedParticipants = [];
    let tbody = $tbody[0];
    let hasNewParticipant = false;
    for (let fullRow of new_json) {
        const {id_in_session, ...row} = fullRow;
        let index = visitedParticipants.indexOf(id_in_session);
        if (index === -1) {
            index = visitedParticipants.filter((id) => id < id_in_session).length;
            let newRow = createTableRowMonitor(row);
            let rowSelector = getNthBodyRowSelector(index);
            if (index === visitedParticipants.length) {
                tbody.appendChild(newRow);
            } else {
                tbody.insertBefore(newRow, tbody.querySelector(rowSelector));
            }
            let tr = tbody.querySelector(rowSelector);
            flashGreen($(tr));
            visitedParticipants.splice(index, 0, id_in_session);
            hasNewParticipant = true;
            updatedParticipants.push(id_in_session);
        } else {
            let didUpdate = updateNthRow(tbody, index, row);
            if (didUpdate) updatedParticipants.push(id_in_session);
        }
    }
    if (hasNewParticipant) {
        $('#num_participants_visited').text(visitedParticipants.length);
    }
    $(".timeago").timeago();
    return updatedParticipants;
}