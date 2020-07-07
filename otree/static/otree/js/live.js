var liveSocket;

var $currentScript = $('#otree-live');

var socketUrl = $currentScript.data('socketUrl');

liveSocket = makeReconnectingWebSocket(socketUrl);

liveSocket.onmessage = function (e) {
    var data = JSON.parse(e.data);

    if (liveRecv !== undefined) {
        liveRecv(data);
    }
};

function liveSend(msg) {
    liveSocket.send(JSON.stringify(msg));
}

// prevent form submission when user presses enter in an input
$(document).ready(function() {
  $('input').on('keypress', function (e) {
      if (e.key === 'Enter') {
          e.preventDefault();
      }
  });
});
