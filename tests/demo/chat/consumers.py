from channels import Group
import json


def read_chat_message(data):
    return json.loads(data)


def make_chat_message(text):
    return json.dumps({
        'message': text,
    })


def connect_chat(message):
    group = Group('chat')
    group.add(message.reply_channel)
    group.send({
        'text': make_chat_message('A new user connected'),
    })


def disconnect_chat(message):
    Group('chat').discard(message.reply_channel)


def handle_message(message):
    data = read_chat_message(message['text'])
    group = Group('chat')
    group.send({
        'text': make_chat_message(data['message']),
    })
