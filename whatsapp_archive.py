#!/usr/bin/python3

"""Reads a WhatsApp conversation export file and writes a HTML file."""

import argparse
import datetime
import dateutil.parser
import itertools
import jinja2
import logging
import os.path
import re

# Format of the standard WhatsApp export line. This is likely to change in the
# future and so this application will need to be updated.
DATE_RE = '(?P<date>[\d/\-.]+)'
TIME_RE = '(?P<time>[\d:]+( [AP]M)?)'
DATETIME_RE = '\[?' + DATE_RE + ',? ' + TIME_RE + '\]?'
SEPARATOR_RE = '( - |: | )'
NAME_RE = '(?P<name>[^:]+?)'
WHATSAPP_RE = (DATETIME_RE +
               SEPARATOR_RE +
               NAME_RE +
               ': '
               '(?P<body>.*$)')

FIRSTLINE_RE = (DATETIME_RE +
                SEPARATOR_RE +
                '(?P<body>.*$)')


class Error(Exception):
    """Something bad happened."""


def replace_attachment(body):
    attachment = re.search('(<attached: (.+?)>)', body)
    if attachment:
        file = attachment.group(2)
        ext = file.split('.')[-1]
        if ext in ['jpg', 'png', 'jpeg']:
            ret = f'<a target="_blank" href="{file}"><img width="128" height="128" src="{file}" /></a><br>'
        elif ext in ['opus']:
            ret = f'<audio controls src="{file}" /><br>'
        elif ext in ['mp4']:
            ret = f'<video controls src="{file}" /><br>'
        else:
            ret = f'<a target="_blank" href="{file}" />{file}</a>' #attachment.group(1)
        body = body.replace(attachment.group(1), ret)
    return body


def ParseLine(line):
    """Parses a single line of WhatsApp export file."""
    m = re.match(WHATSAPP_RE, line)
    if m:
        body = replace_attachment(m.group('body'))
        
        d = dateutil.parser.parse("%s %s" % (m.group('date'),
                                             m.group('time')), dayfirst=True)
        return d, m.group('name'), body
    # Maybe it's the first line which doesn't contain a person's name.
    m = re.match(FIRSTLINE_RE, line)
    if m:
        body = replace_attachment(m.group('body'))

        d = dateutil.parser.parse("%s %s" % (m.group('date'),
                                             m.group('time')), dayfirst=True)
        return d, "nobody", body
    return None


def IdentifyMessages(lines):
    """Input text can contain multi-line messages. If there's a line that
    doesn't start with a date and a name, that's probably a continuation of the
    previous message and should be appended to it.
    """
    messages = []
    msg_date = None
    msg_user = None
    msg_body = None
    for line in lines:
        m = ParseLine(line)
        if m is not None:
            if msg_date is not None:
                # We have a new message, so there will be no more lines for the
                # one we've seen previously -- it's complete. Let's add it to
                # the list.
                messages.append((msg_date, msg_user, msg_body))
            msg_date, msg_user, msg_body = m
        else:
            if msg_date is None:
                raise Error("Can't parse the first line: " + repr(line) +
                            ', regexes are FIRSTLINE_RE=' + repr(FIRSTLINE_RE) +
                            ' and WHATSAPP_RE=' + repr(WHATSAPP_RE))
            msg_body += '\n' + line.strip()
    # The last message remains. Let's add it, if it exists.
    if msg_date is not None:
        messages.append((msg_date, msg_user, msg_body))
    return messages


def TemplateData(messages, input_filename):
    """Create a struct suitable for procesing in a template.
    Returns:
        A dictionary of values.
    """
    user_idx = {}
    idx = 1
    by_user = []
    file_basename = os.path.basename(input_filename)
    for user, msgs_of_user in itertools.groupby(messages, lambda x: x[1]):
        if user not in user_idx:
            user_idx[user] = idx
            idx += 1
        by_user.append((user, list(msgs_of_user)))
    return dict(by_user=by_user, input_basename=file_basename,
                input_full_path=input_filename, user_idx=user_idx)


def FormatHTML(data):
    tmpl = """<!DOCTYPE html>
    <html>
    <head>
        <title>WhatsApp archive {{ input_basename }}</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: sans-serif;
                font-size: 10px;
            }
            ol.users {
                list-style-type: none;
                list-style-position: inside;
                margin: 0;
                padding: 0;
            }
            ol.messages {
                list-style-type: none;
                list-style-position: inside;
                margin: 0;
                padding: 0;
            }
            ol.messages li {
                margin-left: 1em;
                font-size: 12px;
            }
            span.username {
                color: gray;
            }
            span.date {
                color: gray;
            }
            a {
  color: hotpink;
}

.chatbox {
    width: 100%;
    margin-bottom: 10px;
    background: #bfbfbf;
}

.u1 {
    background: #0A1518 !important;
    color: white;
    font-weight: bold;
}
.chatbox.u1 span {
    color: #fffb00 !important;
}

.u2 {
    background: #423103 !important;
    color: white;
    font-weight: bold;
}
.chatbox.u2 span {
    color: #fffb00 !important;
}

.u3 {
    background: #707010 !important;
    color: white;
    font-weight: bold;
}
.chatbox.u3 span {
    color: #fffb00 !important;
}

.u5 {
    background: #0D376E !important;
    color: white;
    font-weight: bold;
}
.chatbox.u5 span {
    color: #fffb00 !important;
}

.u6 {
    background: #692D6E !important;
    color: white;
    font-weight: bold;
}
.chatbox.u6 span {
    color: #fffb00 !important;
}

.u7 {
    background: #413A6E !important;
    color: white;
    font-weight: bold;
}
.chatbox.u7 span {
    color: #fffb00 !important;
}

.chatbox span {
    padding-bottom: 5px;
    color: darkred;
    font-weight: bold;
}



        </style>
    </head>
    <body>
        <h1>{{ input_basename }}</h1>
        <div class="container">
        {% for user, messages in by_user %}
    <div class="chatbox u{{ user_idx[user] }}">
            <div class="user">
            <span class="username" style="margin-left: 15px">{{ user }}</span>
            <span class="date" style="margin-left: 15px">{{ messages[0][0] }}</span>
            {% for message in messages %}
                <div style="margin-left: 20px">{{ message[2] }}</div><br>
            {% endfor %}
            </div>
      </div>
        {% endfor %}
        </div>
    </body>
    </html>
    """
    return jinja2.Environment().from_string(tmpl).render(**data)


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Produce a browsable history '
                                                 'of a WhatsApp conversation')
    parser.add_argument('-i', dest='input_file', required=True)
    parser.add_argument('-o', dest='output_file', required=True)
    args = parser.parse_args()
    with open(args.input_file, 'rt', encoding='utf-8-sig') as fd:
        tmp = []
        for line in fd.readlines():
            tmp.append(replace_attachment(line))
        messages = IdentifyMessages(tmp)
    template_data = TemplateData(messages, args.input_file)
    HTML = FormatHTML(template_data)
    with open(args.output_file, 'w', encoding='utf-8') as fd:
        fd.write(HTML)


if __name__ == '__main__':
    main()
