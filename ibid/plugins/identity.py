from sqlalchemy.orm import eagerload
from sqlalchemy.orm.exc import NoResultFound

import ibid
from ibid.plugins import Processor, match, handler
from ibid.models import Account, Identity, Attribute

class Accounts(Processor):

    @match('^\s*create\s+account\s+(.+)\s*$')
    def account(self, event, username):
        session = ibid.databases.ibid()

        if 'account' in event and event.account:
            try:
                account = session.query(Account).filter_by(id=event.account).one()
                event.addresponse(u'You already have an account called "%s".' % account.username)
                return
            except NoResultFound:
                pass

        try:
            account = session.query(Account).filter_by(username=username).one()
            event.addresponse(u'There is already an account called "%s". Please choose a different name.' % account.username)
            return
        except NoResultFound:
            pass

        account = Account(username)
        session.add(account)
        session.commit()
        identity = session.query(Identity).filter_by(id=event.identity).one()
        identity.account_id = account.id
        session.add(identity)
        session.commit()
        session.close()
        event.addresponse(u'Done')

class Identities(Processor):

    @match('^\s*(I|.+?)\s+(?:is|am)\s+(.+)\s+on\s+(.+)\s*$')
    def identity(self, event, username, identity, source):
        session = ibid.databases.ibid()
        if username.upper() == 'I':
            if 'account' not in event:
                event.addresponse(u"I don't know who you are")
                return
            account = session.query(Account).filter_by(id=event.account).one()

        else:
            try:
                account = session.query(Account).filter_by(username=username).one()
            except NoResultFound:
                event.addresponse(u"I don't know who %s is" % username)
                return

        try:
            identity = session.query(Identity).filter_by(identity=identity).filter_by(source=source).one()
            if identity.account:
                event.addresponse(u'This identity is already attached to account %s' % identity.account.username)
                return
            else:
                identity.account_id = account.id
        except NoResultFound:
            identity = Identity(source, identity, account.id)

        session.add(identity)
        session.commit()
        session.close()
        event.addresponse(u'Done')

class Attributes(Processor):

    @match(r"^\s*(my|.+?)(?:\'s)?\s+(.+)\s+is\s+(.+)\s*$")
    def attribute(self, event, username, name, value):
        if username.lower() == 'my':
            if 'user' not in event:
                event.addresponse(u"I don't know who you are")
                return
            username = event.user

        session = ibid.databases.ibid()
        try:
            account = session.query(Account).filter_by(username=username).one()
        except NoResultFound:
            event.addresponse(u"%s doesn't exist. Please use 'add account' first" % username)
            return

        account.attributes.append(Attribute(name, value))
        session.add(account)
        session.commit()
        session.close()
        event.addresponse(u'Done')

class Describe(Processor):

    @match('^\s*who\s+(?:is|am)\s+(I|.+?)\s*$')
    def describe(self, event, username):
        session = ibid.databases.ibid()
        if username.upper() == 'I':
            if not event.account:
                event.addresponse(u"I don't know who you are")
                return
            account = session.query(Account).filter_by(id=event.account).one()

        else:
            try:
                account = session.query(Account).filter_by(username=username).one()
            except NoResultFound:
                event.addresponse(u"I don't know who %s is" % username)
                return

        event.addresponse(str(account))
        for identity in account.identities:
            event.addresponse(str(identity))
        for attribute in account.attributes:
            event.addresponse(str(attribute))
        session.close()

class Identify(Processor):

    addressed = False
    priority = -1600

    def __init__(self, name):
        Processor.__init__(self, name)
        self.cache = {}

    @handler
    def identify(self, event):
        if 'sender_id' in event:
            #if event.sender in self.cache:
            #    (event.identity, event.account) = self.cache[event.sender]
            #    return

            session = ibid.databases.ibid()
            try:
                identity = session.query(Identity).options(eagerload('account')).filter_by(source=event.source).filter_by(identity=event.sender_id).one()
            except NoResultFound:
                identity = Identity(event.source, event.sender_id)
                session.add(identity)
                session.commit()

            event.identity = identity.id
            if identity.account:
                event.account = identity.account.id
            else:
                event.account = None
            self.cache[event.sender] = (event.identity, event.account)

            session.close()

def identify(source, user):

    session = ibid.databases.ibid()
    identity = None
    account = None

    try:
        identity = session.query(Identity).filter_by(source=source).filter_by(identity=user).one()
    except NoResultFound:
        pass

    try:
        account = session.query(Account).filter_by(username=user).one()
    except NoResultFound:
        pass

    if not account and not identity:
        return None
    if not accout:
        return identity
    if not identity or identity in account.identities:
        return account
    return (account, identity)

# vi: set et sta sw=4 ts=4: