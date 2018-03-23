#!/usr/bin/env python
# -*- coding: utf8 -*-

"""
This script is meant as a simple way to reply to ical invitations from mutt.
See README for instructions and LICENSE for licensing information.
"""

from __future__ import with_statement

__author__="Martin Sander"
__license__="MIT"


from tzlocal import get_localzone
import pytz
import vobject
import tempfile, time
import os, sys
import warnings
from datetime import date, datetime
from subprocess import Popen, PIPE
from getopt import gnu_getopt as getopt

timezone = get_localzone()
mutt="mutt"

usage="""
usage:
%s [OPTIONS] -e your@email.address filename.ics
OPTIONS:
    -i interactive
    -a accept
    -d decline
    -t tentatively accept
    -c mutt_command
    (accept is default, last one wins)
""" % sys.argv[0]

def del_if_present(dic, key):
    if dic.has_key(key):
        del dic[key]

def set_accept_state(attendees, state):
    for attendee in attendees:
        attendee.params['PARTSTAT'] = [unicode(state)]
        for i in ["RSVP","ROLE","X-NUM-GUESTS","CUTYPE"]:
            del_if_present(attendee.params,i)
    return attendees

def get_accept_decline():
    while True:
        sys.stdout.write("\nAccept Invitation? [y/n/t/q]")
        ans = sys.stdin.readline()
        if ans.lower() == 'y\n':
            return 'ACCEPTED'
        elif ans.lower() == 'n\n':
            return 'DECLINED'
        elif ans.lower() == 't\n':
            return 'TENTATIVE'
        elif ans.lower() == 'q\n':
            return ''

def get_answer(invitation):
    # create
    ans = vobject.newFromBehavior('vcalendar')
    ans.add('method')
    ans.method.value = "REPLY"
    ans.add('vevent')

    # just copy from invitation
    for i in ["uid", "summary", "dtstart", "dtend", "organizer"]:
        if invitation.vevent.contents.has_key(i):
            ans.vevent.add( invitation.vevent.contents[i][0] )

    # new timestamp
    ans.vevent.add('dtstamp')
    ans.vevent.dtstamp.value = datetime.utcnow().replace(
            tzinfo = invitation.vevent.dtstamp.value.tzinfo)
    return ans

def write_to_tempfile(ical):
    tempdir = tempfile.mkdtemp()
    icsfile = tempdir+"/event-reply.ics"
    with open(icsfile,"w") as f:
        f.write(ical.serialize())
    return icsfile, tempdir

def get_mutt_command(ical, email_address, accept_decline, icsfile):
    accept_decline = accept_decline.capitalize()
    if ical.vevent.contents.has_key('organizer'):
        if hasattr(ical.vevent.organizer,'EMAIL_param'):
            sender = ical.vevent.organizer.EMAIL_param
        else:
            sender = ical.vevent.organizer.value.split(':')[1] #workaround for MS
    else:
        sender = "NO SENDER"
    summary = ical.vevent.contents['summary'][0].value.encode()
    command = [mutt, "-e", "my_hdr From: %s" % email_address, "-a", icsfile,
            "-s", "%s: %s" % (accept_decline, summary), "--", sender]
            #Uncomment the below line, and move it above the -s line to enable the wrapper
            #"-e", 'set sendmail=\'ical_reply_sendmail_wrapper.sh\'',
    return command

def execute(command, mailtext):
    process = Popen(command, stdin=PIPE)
    process.stdin.write(mailtext)
    process.stdin.close()

    result = None
    while result is None:
        result = process.poll()
        time.sleep(.1)
    if result != 0:
        print "unable to send reply, subprocess exited with\
                exit code %d\nPress return to continue" % result
        sys.stdin.readline()

def openics(invitation_file):
    with open(invitation_file) as f:
        try:
            with warnings.catch_warnings(): #vobject uses deprecated Exception stuff
                warnings.simplefilter("ignore")
                invitation = vobject.readOne(f, ignoreUnreadable=True)
        except AttributeError:
            invitation = vobject.readOne(f, ignoreUnreadable=True)
    return invitation

def display(ical):
    summary = ical.vevent.contents['summary'][0].value.encode()
    if ical.vevent.contents.has_key('organizer'):
        if hasattr(ical.vevent.organizer,'EMAIL_param'):
            sender = ical.vevent.organizer.EMAIL_param
        else:
            sender = ical.vevent.organizer.value.split(':')[1] #workaround for MS
    else:
        sender = "NO SENDER"
    if ical.vevent.contents.has_key('description'):
        description = ical.vevent.contents['description'][0].value
    else:
        description = "NO DESCRIPTION"
    if ical.vevent.contents.has_key('attendee'):
        attendees = ical.vevent.contents['attendee']
    else:
        attendees = ""

    sys.stdout.write("Start:\t" + ical.vevent.dtstart.value.astimezone(timezone).strftime('%Y-%m-%d %I:%M %p %Z') + "\n")
    sys.stdout.write("End:\t" + ical.vevent.dtend.value.astimezone(timezone).strftime('%Y-%m-%d %I:%M %p %Z') + "\n")
    sys.stdout.write("From:\t" + sender + "\n")
    sys.stdout.write("Title:\t" + summary + "\n")
    sys.stdout.write("To:\t")
    for attendee in attendees:
        if hasattr(attendee,'EMAIL_param'):
            sys.stdout.write(attendee.CN_param + " <" + attendee.EMAIL_param + ">, ")
        else:
            sys.stdout.write(attendee.CN_param + " <" + attendee.value.split(':')[1] + ">, ") #workaround for MS
    sys.stdout.write("\n\n")
    sys.stdout.write(description + "\n")

if __name__=="__main__":
    email_address = None
    email_addresses = []
    accept_decline = ''
    opts, args=getopt(sys.argv[1:],"e:aidtc:")

    if len(args) < 1:
        sys.stderr.write(usage)
        sys.exit(1)

    invitation = openics(args[0])
    #print(invitation)
    display(invitation)

    for opt,arg in opts:
        if opt == '-e':
            email_addresses = arg.split(',')
        if opt == '-i':
            accept_decline = get_accept_decline()
        if opt == '-a':
            accept_decline = 'ACCEPTED'
        if opt == '-d':
            accept_decline = 'DECLINED'
        if opt == '-t':
            accept_decline = 'TENTATIVE'
        if opt == '-c':
            mutt = arg

    if accept_decline == '':
        sys.exit(0)

    ans = get_answer(invitation)

    if invitation.vevent.contents.has_key('attendee'):
        attendees = invitation.vevent.contents['attendee']
    else:
        attendees = ""
    set_accept_state(attendees,accept_decline)
    ans.vevent.add('attendee')
    ans.vevent.attendee_list.pop()
    flag = 1
    for attendee in attendees:
        if hasattr(attendee,'EMAIL_param'):
            if attendee.EMAIL_param in email_addresses:
                ans.vevent.attendee_list.append(attendee)
                email_address = attendee.EMAIL_param
                flag = 0
        else:
            if attendee.value.split(':')[1] in email_addresses:
                ans.vevent.attendee_list.append(attendee)
                email_address = attendee.value.split(':')[1]
                flag = 0
    if flag:
        sys.stderr.write("Seems like you have not been invited to this event!\n")
        sys.exit(1)

    icsfile, tempdir = write_to_tempfile(ans)

    mutt_command = get_mutt_command(ans, email_address, accept_decline, icsfile)
    mailtext = "From: %s\n\n%s has %s" % (email_address, email_address, accept_decline.lower())
    execute(mutt_command, mailtext)

    os.remove(icsfile)
    os.rmdir(tempdir)
