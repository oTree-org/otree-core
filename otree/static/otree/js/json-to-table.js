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
            html += '<td data-field="' + key + '">' + value + '</td>';
        }
        html += '</tr>';
    }
    html += '</tbody>';
    return html;
}
