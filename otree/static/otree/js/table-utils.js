/*
Lame trick...I increment the filename when I release a new version of this file,
because on runserver, Chrome caches it, so all oTree users developing on Chrome
would need to Ctrl+F5.
 */

function populateTableBody(tbody, rows) {
    for (let i = 0; i < rows.length; i++) {
        tbody.appendChild(createTableRow(rows[i], i));
    }
}

let groupIsFiltered = false;

function filterGroup(rowIdx) {

    if (groupIsFiltered) {
        for (let table of tables) {
            let tbody = table.querySelector('tbody');
            let trs = tbody.querySelectorAll('tr');
            for (let tr of trs) {
                tr.style.display = '';
            }
        }

        for (let th of document.getElementsByClassName(`id-in-session`)) {
            th.style.backgroundColor = 'white';
        }
        groupIsFiltered = false;

    } else {
        for (let tid = 0; tid < tables.length; tid++) {
            let table = tables[tid];
            let data = old_json[tid];
            let tbody = table.querySelector('tbody');
            let trs = tbody.querySelectorAll('tr');

            let curGroup = data[rowIdx][0];
            let rowsInSameGroup = [];
            for (let i = 0; i < data.length; i++) {
                if (data[i][0] === curGroup)
                    rowsInSameGroup.push(i);
            }
            for (let i = 0; i < trs.length; i++) {
                if (!rowsInSameGroup.includes(i)) {
                    trs[i].style.display = 'none';
                }
            }
        }
        for (let th of document.getElementsByClassName(`row-idx-${rowIdx}`))
            th.style.backgroundColor = 'yellow';

        groupIsFiltered = true;
    }
}

function createTableRow(row, row_number) {
    let tr = document.createElement('tr');
    tr.innerHTML = `<th class='id-in-session row-idx-${row_number}'>P${row_number + 1}</th>`;
    for (let i = 0; i < row.length; i++) {
        let value = row[i];
        let td = document.createElement('td');
        if (i === 0) {
            td.innerHTML = `<a href="#" onclick="filterGroup(${row_number})">${value}</a>`;
        } else {
            td.innerHTML = makeCellDisplayValue(value);
        }
        tr.appendChild(td)
    }
    return tr;
}

function createTableRowMonitor(row) {
    let tr = document.createElement('tr');
    for (let [field, value] of Object.entries(row)) {
        let td = document.createElement('td');
        td.dataset.field = field;
        td.dataset.value = makeCellDatasetValue(value);
        td.innerHTML = makeCellDisplayValue(value, field);
        tr.appendChild(td)
    }
    return tr;
}

function truncateStringEllipsis(str, num) {
    if (str.length > num) {
        return str.slice(0, num) + "…";
    } else {
        return str;
    }
}


function makeCellDatasetValue(value) {
    if (value === null) return '';
    return value.toString();
}

function makeCellDisplayValue(value, fieldName) {
    if (value === null) {
        return '';
    }
    if (fieldName === '_last_page_timestamp') {
        let date = new Date(parseFloat(value) * 1000);
        let dateString = date.toISOString();
        return `<time class="timeago" datetime="${dateString}"></time>`;
    }
    return value.toString();
}


function updateDraggable($table) {
    $table.toggleClass(
        'draggable',
        ($table.get(0).scrollWidth > $table.parent().width())
        || ($table.find('tbody').height() >= 450));
}

function flashGreen($ele) {
    $ele.css('background-color', 'green');
    $ele.animate({
            backgroundColor: "white"
        },
        10000
    );
}


function updateDataTable($table, new_json, old_json, field_headers) {
    let changeDescriptions = [];
    let $tbody = $table.find('tbody');
    // build table for the first time
    let numRows = new_json[0].length;
    for (let i = 0; i < new_json.length; i++) {
        let rowChanges = [];
        for (let j = 0; j < numRows; j++) {
            if (new_json[i][j] !== old_json[i][j]) {
                let rawValue = new_json[i][j];
                let $cell = $tbody.find(`tr:eq(${i})`).find(`td:eq(${j})`);
                let new_value = makeCellDisplayValue(rawValue);
                $cell.text(new_value);
                flashGreen($cell);
                let fieldName = field_headers[j];
                let newValueTrunc = truncateStringEllipsis(new_value, 7);
                rowChanges.push(`${fieldName}=${newValueTrunc}`);
            }
        }
        if (rowChanges.length > 0) {
            // @ makes it easier to scan visually
            changeDescriptions.push(`@P${i + 1}: ${rowChanges.join(', ')}`)
        }
    }
    return changeDescriptions;
}
