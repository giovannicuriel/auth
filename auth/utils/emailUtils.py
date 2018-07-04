import smtplib
from email.mime.text import MIMEText

import auth.conf as conf


def send_mail(to, subject, html_msg):
    if conf.emailHost == '':
        return
    # TODO: I think we should put this function in a worker thread
    msg = MIMEText(html_msg, 'html')

    msg['Subject'] = subject
    msg['From'] = conf.emailUsername
    msg['To'] = to

    try:
        s = smtplib.SMTP(conf.emailHost, conf.emailPort)
        if conf.emailTLS:
            s.starttls()
        s.login(conf.emailUsername, conf.emailPasswd)
        s.sendmail(conf.emailUsername, [to], msg.as_string())
        s.quit()
    except OSError:
        raise Exception('Failed to retrieve SMTP socket. Is the SMTP port closed?')
    except smtplib.SMTPAuthenticationError:
        raise Exception('SMTP authentication failed')
    except Exception as e:
        raise Exception(e)
