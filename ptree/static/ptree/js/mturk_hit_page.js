function turkGetParam( name, defaultValue ) { 
    var regexS = "[\?&]"+name+"=([^&#]*)"; 
    var regex = new RegExp( regexS ); 
    var tmpURL = window.location.href; 
    var results = regex.exec( tmpURL ); 
    if( results == null ) { 
        return defaultValue; 
    } else { 
        return results[1];    
    } 
}

function appendTurkInfoToUrl() {
    var anchor = document.getElementById("start_url");
    anchor.href = anchor.href + "&mturk_worker_id=" + turkGetParam('workerId', '') + "&mturk_assignment_id=" + turkGetParam('assignmentId', '');
}

appendTurkInfoToUrl();