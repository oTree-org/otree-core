function createTableBodyFromJson(json)
{
    var html = '<tbody>', i, row, key, value;
    for (i in json) {
        row = json[i];
        html += '<tr>';
        for (key in row) {
            value = row[key];
            if (value === null) {
                value = '';
            }
            html += '<td data-field="' + key + '" title="' + value + '">' + value + '</td>';
        }
        html += '</tr>';
    }
    html += '</tbody>';
    return html;
}


function updateTable($table) {
    $table.toggleClass(
        'draggable',
        ($table.get(0).scrollWidth > $table.parent().width())
        || ($table.find('tbody').height() >= 450));
}


function makeTableDraggable($table) {
    var mouseX, mouseY;
    $table.mousedown(function (e) {
        e.preventDefault();
        $table.addClass('grabbing');
        mouseX = e.pageX;
        mouseY = e.pageY;
    }).on('scroll', function () {
        $table.find('> thead, > tbody').width($table.width() + $table.scrollLeft());
    });
    $(document)
        .mousemove(function (e) {
            if (!$table.hasClass('grabbing')) {
                return;
            }
            e.preventDefault();
            $table.scrollLeft($table.scrollLeft() - (e.pageX - mouseX));
            var $tableBody = $table.find('tbody');
            $tableBody.scrollTop($tableBody.scrollTop() - (e.pageY - mouseY));
            mouseX = e.pageX;
            mouseY = e.pageY;
        }).mouseup(function (e) {
            if (!$table.hasClass('grabbing')) {
                return;
            }
            e.preventDefault();
            $table.removeClass('grabbing');
    });
}

