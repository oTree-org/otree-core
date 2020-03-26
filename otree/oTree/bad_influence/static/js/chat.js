const chatsocket = new WebSocket(
    'ws://' +
    window.location.host +
    '/ws/chat/'
);

chatsocket.onopen = () => {
    console.log("Chatsocket Opened")
}