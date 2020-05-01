let ws_scheme = window.location.protocol == "https" ? "wss" : "ws";
        let ws_path = ws_scheme + '://' + window.location.host + "/ws/chat/{{ group.pk }}";
        let socket = new WebSocket(ws_path);

        socket.onopen = () => {
            console.log('Chat socket opened');
        };

        let messages = document.querySelector('.messages');
        let message = document.querySelector('<li class="list-group-item"></li>');