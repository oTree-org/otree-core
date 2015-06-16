/**
 * JavaScript format string function
 * 
 */
String.prototype.format = function()
{
  var args = arguments;

  return this.replace(/{(\d+)}/g, function(match, number)
  {
    return typeof args[number] != 'undefined' ? args[number] :
                                                '{' + number + '}';
  });
};


/**
 * Convert a Javascript Oject array or String array to an HTML table
 * JSON parsing has to be made before function call
 * It allows use of other JSON parsing methods like jQuery.parseJSON
 * http(s)://, ftp://, file:// and javascript:; links are automatically computed
 *
 * JSON data samples that should be parsed and then can be converted to an HTML table
 *     var objectArray = '[{"Total":"34","Version":"1.0.4","Office":"New York"},{"Total":"67","Version":"1.1.0","Office":"Paris"}]';
 *     var nestedTable = '[{ key1: "val1", key2: "val2", key3: { tableId: "tblIdNested1", tableClassName: "clsNested", linkText: "Download", data: [{ subkey1: "subval1", subkey2: "subval2", subkey3: "subval3" }] } }]'; 
 *
 * Code sample to create a HTML table Javascript String
 *     var jsonHtmlTable = ConvertJsonToTable(eval(dataString), 'jsonTable', null, 'Download');
 *
 * Code sample explaned
 *  - eval is used to parse a JSON dataString
 *  - table HTML id attribute will be 'jsonTable'
 *  - table HTML class attribute will not be added
 *  - 'Download' text will be displayed instead of the link itself
 *
 * @author Afshin Mehrabani <afshin dot meh at gmail dot com>
 * 
 * @class ConvertJsonToTable
 * 
 * @method ConvertJsonToTable
 * 
 * @param parsedJson object Parsed JSON data
 * @param tableId string Optional table id 
 * @param tableClassName string Optional table css class name
 * @param linkText string Optional text replacement for link pattern
 *  
 * @return string Converted JSON to HTML table
 */
function ConvertJsonToTable(parsedJson, tableId, tableClassName, linkText, only_body)
{
    var link = linkText ? '<a href="{0}">' + linkText + '</a>' :
                          '<a href="{0}">{0}</a>';

    //Pattern for table                          
    var idMarkup = tableId ? ' id="' + tableId + '"' : '';

    var classMarkup = tableClassName ? ' class="' + tableClassName + '"' : '';

    var tbl = '<table border="1" cellpadding="1" cellspacing="1"' + idMarkup + classMarkup + '>{0}{1}</table>';

    //Patterns for table content
    var th = '<thead>{0}</thead>';
    var tb = '<tbody>{0}</tbody>';
    var tr = '<tr>{0}</tr>';
    var thRow = '<th class="text-center">{0}</th>';
    var tdRow = '<td title="{1}" data-field="{1}" class="text-center">{0}</td>';
    var thCon = '';
    var tbCon = '';
    var trCon = '';

    if (parsedJson)
    {
        var headers;

        // Create table headers from JSON data
        // If JSON data is an object array, headers are automatically computed
        if(typeof(parsedJson[0]) == 'object')
        {
            headers = array_keys(parsedJson[0]);

            for (i = 0; i < headers.length; i++)
                thCon += thRow.format(pretty_name(headers[i]), headers[i]);
        }
        th = th.format(tr.format(thCon));
        
        if(headers)
        {
            for (i = 0; i < parsedJson.length; i++)
            {
                for (j = 0; j < headers.length; j++)
                {
                    var value = parsedJson[i][headers[j]];
                    if(value){
                        if(typeof(value) == 'object'){
                            //for supporting nested tables
                            tbCon += tdRow.format(ConvertJsonToTable(eval(value.data), value.tableId, value.tableClassName, value.linkText));
                        } else {
                            tbCon += tdRow.format(value, headers[j]);
                        }
                    } 
                    else {    // If value == null we input empty string into cell
                        tbCon += tdRow.format("", headers[j]);
                    }
                }
                trCon += tr.format(tbCon);
                tbCon = '';
            }
        }
        tb = tb.format(trCon);
        tbl = tbl.format(th, tb);
        if (typeof only_body === 'undefined') {
            return tbl;
        }
        else {
            return tb;
        }
    }
    return null;
}

function pretty_name(name)
{
    var tmp = name.replace(/_/g, " ");
    tmp = $.trim(tmp)
    var new_name = tmp.charAt(0).toUpperCase() + tmp.slice(1);
    return new_name;
}

function array_keys(input, search_value, argStrict)
{
    var search = typeof search_value !== 'undefined', tmp_arr = [], strict = !!argStrict, include = true, key = '';

    if (input && typeof input === 'object' && input.change_key_case) { // Duck-type check for our own array()-created PHPJS_Array
        return input.keys(search_value, argStrict);
    }
 
    for (key in input)
    {
        if (input.hasOwnProperty(key))
        {
            include = true;
            if (search)
            {
                if (strict && input[key] !== search_value)
                    include = false;
                else if (input[key] != search_value)
                    include = false;
            } 
            if (include)
                tmp_arr[tmp_arr.length] = key;
        }
    }
    return tmp_arr;
}
