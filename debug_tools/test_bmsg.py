def create_bmsg(number, text):
    msg = f"BEGIN:MSG\r\n{text}\r\nEND:MSG\r\n"
    length = len(msg.encode('utf-8'))
    
    return f"""BEGIN:BMSG\r
VERSION:1.0\r
STATUS:UNREAD\r
TYPE:SMS_GSM\r
FOLDER:telecom/msg/outbox\r
BEGIN:BENV\r
BEGIN:VCARD\r
VERSION:2.1\r
TEL:{number}\r
END:VCARD\r
BEGIN:BBODY\r
CHARSET:UTF-8\r
LENGTH:{length}\r
{msg}END:BBODY\r
END:BENV\r
END:BMSG\r
"""
print(repr(create_bmsg("123", "Test")))
